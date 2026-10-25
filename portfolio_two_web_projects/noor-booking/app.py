import hmac
import logging
import os
import secrets
import smtplib
from datetime import date, datetime, timedelta
from email.message import EmailMessage
from functools import wraps
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from flask import Flask, Response, abort, current_app, flash, g, jsonify, redirect, render_template, request, session, url_for
from flask_wtf import FlaskForm
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, create_engine, delete, func, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from wtforms import BooleanField, DateField, PasswordField, SelectField, StringField, TextAreaField
from wtforms.validators import DataRequired, Email, Length, Optional, Regexp

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / '.env')
logging.basicConfig(level=os.getenv('LOG_LEVEL', 'INFO'))
logger = logging.getLogger('noor-booking')
TZ = ZoneInfo(os.getenv('BUSINESS_TIMEZONE', 'Africa/Algiers'))
OPEN_MINUTE = 9 * 60
CLOSE_MINUTE = 19 * 60
SLOT_STEP = 30
BOOKING_STATUSES = {
    'pending': {'ar': 'بانتظار التأكيد', 'en': 'Pending'},
    'confirmed': {'ar': 'مؤكد', 'en': 'Confirmed'},
    'cancelled': {'ar': 'ملغى', 'en': 'Cancelled'},
    'completed': {'ar': 'مكتمل', 'en': 'Completed'},
}

class Base(DeclarativeBase):
    pass

class Service(Base):
    __tablename__ = 'services'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name_ar: Mapped[str] = mapped_column(String(100), nullable=False)
    name_en: Mapped[str] = mapped_column(String(100), nullable=False)
    description_ar: Mapped[str] = mapped_column(String(500), nullable=False)
    description_en: Mapped[str] = mapped_column(String(500), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    price_da: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

class Staff(Base):
    __tablename__ = 'staff'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    role_ar: Mapped[str] = mapped_column(String(100), nullable=False)
    role_en: Mapped[str] = mapped_column(String(100), nullable=False)
    initials: Mapped[str] = mapped_column(String(5), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

class Booking(Base):
    __tablename__ = 'bookings'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    confirmation_code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)
    customer_name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[str] = mapped_column(String(40), nullable=False)
    email: Mapped[str | None] = mapped_column(String(254), nullable=True)
    service_id: Mapped[int] = mapped_column(ForeignKey('services.id'), nullable=False)
    staff_id: Mapped[int] = mapped_column(ForeignKey('staff.id'), nullable=False)
    appointment_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    start_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    end_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    service_name: Mapped[str] = mapped_column(String(100), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    price_da: Mapped[int] = mapped_column(Integer, nullable=False)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default='')
    status: Mapped[str] = mapped_column(String(20), nullable=False, default='pending')
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

class SlotUnavailable(Exception):
    pass

class BookingForm(FlaskForm):
    customer_name = StringField('Name', validators=[DataRequired(), Length(min=2, max=100)])
    phone = StringField('Phone', validators=[DataRequired(), Length(min=7, max=40), Regexp(r'^[0-9+().\s-]+$', message='Use a valid phone number.')])
    email = StringField('Email', validators=[Optional(), Email(), Length(max=254)])
    service_id = SelectField('Service', coerce=int, validators=[DataRequired()])
    appointment_date = DateField('Date', format='%Y-%m-%d', validators=[DataRequired()])
    staff_preference = SelectField('Team member', choices=[('any', 'Any available')], validators=[DataRequired()])
    start_time = SelectField('Available time', choices=[('', 'Choose a date and service first')], validators=[DataRequired()])
    notes = TextAreaField('Notes', validators=[Optional(), Length(max=1000)])
    consent = BooleanField('Consent', validators=[DataRequired(message='Please confirm that we may contact you about this booking.')])
    website = StringField('Website', validators=[Length(max=200)])

class LoginForm(FlaskForm):
    password = PasswordField('Password', validators=[DataRequired(), Length(max=200)])

class StatusForm(FlaskForm):
    status = SelectField('Status', choices=[(k, v['ar']) for k, v in BOOKING_STATUSES.items()], validators=[DataRequired()])

class CancelForm(FlaskForm):
    pass

class LogoutForm(FlaskForm):
    pass

def database_url(app):
    raw = app.config.get('DATABASE_URL') or os.getenv('DATABASE_URL')
    if raw:
        if raw.startswith('postgres://'):
            raw = raw.replace('postgres://', 'postgresql+psycopg://', 1)
        elif raw.startswith('postgresql://'):
            raw = raw.replace('postgresql://', 'postgresql+psycopg://', 1)
        return raw
    if os.getenv('RENDER'):
        raise RuntimeError('DATABASE_URL must point to a durable PostgreSQL database on Render. Do not use ephemeral SQLite for real appointments.')
    db_path = Path(app.config.get('DATABASE_PATH') or BASE_DIR / 'instance' / 'noor.sqlite3')
    if str(db_path) != ':memory:':
        if not db_path.is_absolute():
            db_path = BASE_DIR / db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        return 'sqlite:///' + str(db_path.resolve())
    return 'sqlite:///:memory:'

def local_now():
    return datetime.now(TZ)

def next_open_date(offset=2):
    candidate = local_now().date() + timedelta(days=offset)
    while candidate.weekday() == 6:
        candidate += timedelta(days=1)
    return candidate

def minute_label(minutes):
    return f'{minutes // 60:02d}:{minutes % 60:02d}'

def parse_iso_date(value):
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None

def seed_data(factory):
    with factory.begin() as db:
        if not db.scalar(select(func.count()).select_from(Service)):
            db.add_all([
                Service(slug='classic-cut', name_ar='قصّة كلاسيكية', name_en='Classic cut', description_ar='قصّة متقنة بتفاصيل نظيفة ولمسة نهائية مرتبة.', description_en='A precise cut with clean details and a considered finish.', duration_minutes=30, price_da=1000),
                Service(slug='beard-care', name_ar='تهذيب اللحية', name_en='Beard grooming', description_ar='تحديد اللحية وتنظيف الخطوط والعناية بالتفاصيل.', description_en='Shape, define, and refine your beard with care.', duration_minutes=30, price_da=700),
                Service(slug='cut-and-beard', name_ar='قصّة ولحية', name_en='Cut & beard', description_ar='جلسة متكاملة للقصّة واللحية ضمن موعد واحد.', description_en='A complete cut and beard session in one appointment.', duration_minutes=60, price_da=1500),
                Service(slug='signature-session', name_ar='جلسة مميزة', name_en='Signature session', description_ar='قصّة وتهذيب مع وقت إضافي للتفاصيل والتصفيف.', description_en='A cut, grooming, and extra time for styling details.', duration_minutes=60, price_da=2000),
            ])
        if not db.scalar(select(func.count()).select_from(Staff)):
            db.add_all([
                Staff(slug='adam', name='Adam', role_ar='حلاق أول', role_en='Senior barber', initials='AD', sort_order=1),
                Staff(slug='younes', name='Younes', role_ar='مختص القصّات', role_en='Cut specialist', initials='YN', sort_order=2),
                Staff(slug='lina', name='Lina', role_ar='مختصة العناية والتصفيف', role_en='Grooming stylist', initials='LN', sort_order=3),
            ])
    if os.getenv('SEED_DEMO_DATA', 'true').lower() != 'true':
        with factory.begin() as db:
            db.execute(delete(Booking).where(Booking.is_demo.is_(True)))
        return
    with factory.begin() as db:
        if db.scalar(select(func.count()).select_from(Booking).where(Booking.is_demo.is_(True))):
            return
        services = {s.slug: s for s in db.scalars(select(Service)).all()}
        staff = db.scalars(select(Staff).order_by(Staff.sort_order)).all()
        d1, d2 = next_open_date(2), next_open_date(3)
        if d1 == d2:
            d2 = next_open_date(4)
        samples = [
            Booking(confirmation_code='DEMO-NOOR-A1', customer_name='Demo — Karim A.', phone='0550 00 00 11', email='karim.demo@example.test', service_id=services['classic-cut'].id, staff_id=staff[0].id, appointment_date=d1, start_minutes=10*60, end_minutes=10*60+30, service_name=services['classic-cut'].name_en, duration_minutes=30, price_da=services['classic-cut'].price_da, notes='Fictional sample appointment for portfolio demonstration.', status='confirmed', is_demo=True),
            Booking(confirmation_code='DEMO-NOOR-B2', customer_name='Demo — Mehdi R.', phone='0550 00 00 12', email='mehdi.demo@example.test', service_id=services['cut-and-beard'].id, staff_id=staff[1].id, appointment_date=d1, start_minutes=11*60, end_minutes=12*60, service_name=services['cut-and-beard'].name_en, duration_minutes=60, price_da=services['cut-and-beard'].price_da, notes='Fictional sample appointment for portfolio demonstration.', status='pending', is_demo=True),
            Booking(confirmation_code='DEMO-NOOR-C3', customer_name='Demo — Walid S.', phone='0550 00 00 13', email=None, service_id=services['beard-care'].id, staff_id=staff[2].id, appointment_date=d2, start_minutes=15*60, end_minutes=15*60+30, service_name=services['beard-care'].name_en, duration_minutes=30, price_da=services['beard-care'].price_da, notes='Fictional sample appointment for portfolio demonstration.', status='confirmed', is_demo=True),
        ]
        db.add_all(samples)

def get_available_slots(factory, target_date, service_id, staff_preference='any'):
    today = local_now().date()
    if not target_date or target_date < today or target_date > today + timedelta(days=45) or target_date.weekday() == 6:
        return []
    with factory() as db:
        service = db.get(Service, service_id)
        if not service or not service.is_active:
            return []
        all_staff = db.scalars(select(Staff).order_by(Staff.sort_order)).all()
        if staff_preference != 'any':
            try:
                chosen_id = int(staff_preference)
            except (TypeError, ValueError):
                return []
            eligible_staff = [person for person in all_staff if person.id == chosen_id]
            if not eligible_staff:
                return []
        else:
            eligible_staff = all_staff
        busy = db.scalars(select(Booking).where(
            Booking.appointment_date == target_date,
            Booking.status.in_(['pending', 'confirmed']),
        )).all()
        workloads = {person.id: sum(1 for appt in busy if appt.staff_id == person.id) for person in eligible_staff}
        now = local_now()
        earliest = now.hour * 60 + now.minute + 30 if target_date == today else OPEN_MINUTE
        first_allowed = max(OPEN_MINUTE, ((earliest + SLOT_STEP - 1) // SLOT_STEP) * SLOT_STEP)
        slots = []
        for start in range(first_allowed, CLOSE_MINUTE, SLOT_STEP):
            end = start + service.duration_minutes
            if end > CLOSE_MINUTE:
                continue
            available_staff = []
            for person in eligible_staff:
                conflict = any(
                    appt.staff_id == person.id and appt.start_minutes < end and appt.end_minutes > start
                    for appt in busy
                )
                if not conflict:
                    available_staff.append(person)
            if not available_staff:
                continue
            available_staff.sort(key=lambda person: (workloads.get(person.id, 0), person.sort_order))
            assigned = available_staff[0]
            slots.append({
                'time': minute_label(start),
                'start_minutes': start,
                'end_minutes': end,
                'staff_id': assigned.id,
                'staff_name': assigned.name,
                'staff_role_ar': assigned.role_ar,
                'staff_role_en': assigned.role_en,
            })
        return slots

def send_email(recipient, subject, body):
    host = os.getenv('MAIL_SERVER')
    sender = os.getenv('MAIL_DEFAULT_SENDER') or os.getenv('MAIL_USERNAME')
    if not all([host, recipient, sender]):
        return False
    message = EmailMessage()
    message['Subject'] = subject
    message['From'] = sender
    message['To'] = recipient
    message.set_content(body)
    try:
        port = int(os.getenv('MAIL_PORT', '587'))
        with smtplib.SMTP(host, port, timeout=8) as smtp:
            smtp.ehlo()
            if os.getenv('MAIL_USE_TLS', 'true').lower() == 'true':
                smtp.starttls(); smtp.ehlo()
            username, password = os.getenv('MAIL_USERNAME'), os.getenv('MAIL_PASSWORD')
            if username and password:
                smtp.login(username, password)
            smtp.send_message(message)
        return True
    except Exception:
        logger.exception('Record was saved, but SMTP notification failed.')
        return False

def send_admin_email(subject, body):
    return send_email(os.getenv('MAIL_TO'), subject, body)

def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.update(
        SECRET_KEY=os.getenv('SECRET_KEY') or 'local-development-secret-change-before-deploy',
        ADMIN_PASSWORD=os.getenv('ADMIN_PASSWORD') or 'demo-admin-12345-change-me',
        WTF_CSRF_ENABLED=True,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
        SESSION_COOKIE_SECURE=os.getenv('COOKIE_SECURE', 'false').lower() == 'true',
        PERMANENT_SESSION_LIFETIME=timedelta(minutes=60),
        MAX_CONTENT_LENGTH=2 * 1024 * 1024,
        STUDIO_NAME=os.getenv('STUDIO_NAME', 'NOOR Studio'),
        PUBLIC_PHONE=os.getenv('PUBLIC_PHONE', '0550 00 00 00'),
        PUBLIC_EMAIL=os.getenv('PUBLIC_EMAIL', 'hello@example.test'),
        PUBLIC_CITY=os.getenv('PUBLIC_CITY', 'Mascara, Algeria'),
        DATABASE_URL=os.getenv('DATABASE_URL'),
    )
    if test_config:
        app.config.update(test_config)
    if os.getenv('RENDER') and not os.getenv('SECRET_KEY') and not (test_config and test_config.get('SECRET_KEY')):
        raise RuntimeError('Set SECRET_KEY in the deployment environment.')
    if os.getenv('RENDER') and not os.getenv('ADMIN_PASSWORD'):
        raise RuntimeError('Set a strong ADMIN_PASSWORD before deploying the admin panel.')
    if os.getenv('RENDER'):
        app.config['SESSION_COOKIE_SECURE'] = True
    url = database_url(app)
    connect_args = {'check_same_thread': False} if url.startswith('sqlite:') else {}
    if url == 'sqlite:///:memory:':
        from sqlalchemy.pool import StaticPool
        engine = create_engine(url, connect_args={'check_same_thread': False}, poolclass=StaticPool)
    else:
        engine = create_engine(url, connect_args=connect_args, pool_pre_ping=True)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    app.extensions['db_engine'] = engine
    app.extensions['db_factory'] = factory
    seed_data(factory)

    @app.before_request
    def select_language():
        selected = request.values.get('lang')
        if selected in ('ar', 'en'):
            session['lang'] = selected
        g.lang = session.get('lang', 'ar')

    @app.context_processor
    def inject_globals():
        return {
            'current_lang': getattr(g, 'lang', 'ar'),
            'studio_name': app.config['STUDIO_NAME'],
            'public_phone': app.config['PUBLIC_PHONE'],
            'public_email': app.config['PUBLIC_EMAIL'],
            'public_city': app.config['PUBLIC_CITY'],
            'booking_statuses': BOOKING_STATUSES,
            'now_date': local_now().date().isoformat(),
            'max_date': (local_now().date() + timedelta(days=45)).isoformat(),
            'admin_logged_in': bool(session.get('admin_logged_in')),
            'logout_form': LogoutForm(),
        }

    def tr(ar, en):
        return en if session.get('lang', 'ar') == 'en' else ar

    def admin_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not session.get('admin_logged_in'):
                return redirect(url_for('admin_login', next=request.path))
            return view(*args, **kwargs)
        return wrapped

    def make_booking_form(db):
        form = BookingForm()
        services = db.scalars(select(Service).where(Service.is_active.is_(True)).order_by(Service.id)).all()
        people = db.scalars(select(Staff).order_by(Staff.sort_order)).all()
        form.service_id.choices = [(s.id, s.name_ar) for s in services]
        form.staff_preference.choices = [('any', 'أي عضو متاح')] + [(str(p.id), p.name) for p in people]
        form.start_time.choices = [('', 'اختر التاريخ والخدمة أولًا')]
        return form, services, people

    @app.after_request
    def security_headers(response):
        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
        response.headers.setdefault('X-Frame-Options', 'DENY')
        response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
        response.headers.setdefault('Permissions-Policy', 'camera=(), microphone=(), geolocation=()')
        response.headers.setdefault('Content-Security-Policy', "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'")
        return response

    @app.get('/privacy')
    def privacy():
        return render_template('privacy.html')

    @app.get('/robots.txt')
    def robots_txt():
        return Response('User-agent: *\nAllow: /\nDisallow: /admin\nDisallow: /booking/\n', mimetype='text/plain')

    @app.get('/healthz')
    def healthz():
        return jsonify(status='ok', service='noor-booking')

    @app.get('/api/slots')
    def available_slots_api():
        target = parse_iso_date(request.args.get('date'))
        try:
            service_id = int(request.args.get('service_id', ''))
        except ValueError:
            return jsonify(error='invalid service_id', slots=[]), 400
        staff_preference = request.args.get('staff_preference', 'any')
        slots = get_available_slots(factory, target, service_id, staff_preference)
        with factory() as db:
            people = {person.id: person for person in db.scalars(select(Staff)).all()}
        response_slots = []
        for item in slots:
            person = people[item['staff_id']]
            response_slots.append({
                'value': f"{item['time']}|{item['staff_id']}",
                'staff_id': item['staff_id'],
                'label_ar': f"{item['time']} — مع {person.name}",
                'label_en': f"{item['time']} — with {person.name}",
            })
        return jsonify(slots=response_slots, date=target.isoformat() if target else None)

    @app.route('/', methods=['GET', 'POST'])
    def index():
        with factory() as db:
            form, services, people = make_booking_form(db)
        if request.method == 'POST':
            target = form.appointment_date.data or parse_iso_date(request.form.get('appointment_date'))
            service_id = form.service_id.data
            staff_pref = form.staff_preference.data or request.form.get('staff_preference', 'any')
            if target and service_id:
                slot_data = get_available_slots(factory, target, service_id, staff_pref)
                form.start_time.choices = [(f"{item['time']}|{item['staff_id']}", item['time']) for item in slot_data]
            if form.validate_on_submit():
                if form.website.data:
                    abort(400)
                if target is None:
                    form.appointment_date.errors.append(tr('اختر تاريخًا صالحًا.', 'Choose a valid date.'))
                else:
                    slot_data = get_available_slots(factory, target, form.service_id.data, form.staff_preference.data)
                    chosen = next((item for item in slot_data if f"{item['time']}|{item['staff_id']}" == form.start_time.data), None)
                    if not chosen:
                        form.start_time.errors.append(tr('هذا الموعد لم يعد متاحًا. اختر وقتًا آخر.', 'That time is no longer available. Choose another slot.'))
                    else:
                        with factory() as db:
                            service = db.get(Service, form.service_id.data)
                            person = db.get(Staff, chosen['staff_id'])
                            service_name = service.name_en if session.get('lang') == 'en' else service.name_ar
                            service_duration = service.duration_minutes
                            service_price = service.price_da
                            person_id = person.id
                        code = secrets.token_urlsafe(18)
                        try:
                            with factory.begin() as db:
                                # On PostgreSQL, locking the staff row serializes competing requests for the same person.
                                db.execute(select(Staff.id).where(Staff.id == person_id).with_for_update()).scalar_one()
                                overlap = db.scalar(select(Booking.id).where(
                                    Booking.staff_id == person_id,
                                    Booking.appointment_date == target,
                                    Booking.status.in_(['pending', 'confirmed']),
                                    Booking.start_minutes < chosen['end_minutes'],
                                    Booking.end_minutes > chosen['start_minutes'],
                                ).limit(1))
                                if overlap:
                                    raise SlotUnavailable()
                                booking = Booking(
                                    confirmation_code=code,
                                    customer_name=form.customer_name.data.strip(),
                                    phone=form.phone.data.strip(),
                                    email=(form.email.data or '').strip() or None,
                                    service_id=form.service_id.data,
                                    staff_id=person_id,
                                    appointment_date=target,
                                    start_minutes=chosen['start_minutes'],
                                    end_minutes=chosen['end_minutes'],
                                    service_name=service_name,
                                    duration_minutes=service_duration,
                                    price_da=service_price,
                                    notes=(form.notes.data or '').strip(),
                                    status='pending',
                                    is_demo=False,
                                )
                                db.add(booking)
                                db.flush()
                                booking_id = booking.id
                        except SlotUnavailable:
                            form.start_time.errors.append(tr('سبق أن حُجز هذا الوقت. اختر وقتًا آخر.', 'That slot was just taken. Please choose another time.'))
                            return render_template('index.html', form=form, services=services, staff=people), 409
                        email_body = f'Appointment request received (not yet confirmed).\nReference: {code}\nService: {service_name}\nDate: {target.isoformat()}\nTime: {chosen["time"]}\nTeam member: {person.name}\nStatus: pending.'
                        send_admin_email(
                            f'New NOOR Studio booking request #{booking_id}',
                            f'New appointment request #{booking_id}\nCustomer: {form.customer_name.data}\nPhone: {form.phone.data}\nEmail: {form.email.data or "-"}\nService: {service_name}\nDate: {target.isoformat()}\nTime: {chosen["time"]}\nTeam member: {person.name}\nStatus: pending\nConfirmation code: {code}',
                        )
                        if form.email.data:
                            send_email(form.email.data.strip(), 'NOOR Studio — appointment request received', email_body)
                        flash(tr('تم استلام طلب الموعد. الموعد بانتظار تأكيد الاستوديو.', 'Your appointment request was received and is awaiting studio confirmation.'), 'success')
                        return redirect(url_for('booking_detail', confirmation_code=code))
        return render_template('index.html', form=form, services=services, staff=people), (422 if request.method == 'POST' and form.errors else 200)

    @app.route('/booking/<confirmation_code>', methods=['GET', 'POST'])
    def booking_detail(confirmation_code):
        cancel_form = CancelForm()
        with factory() as db:
            booking = db.scalar(select(Booking).where(Booking.confirmation_code == confirmation_code))
            if not booking:
                abort(404)
            service = db.get(Service, booking.service_id)
            person = db.get(Staff, booking.staff_id)
        if request.method == 'POST' and cancel_form.validate_on_submit():
            with factory.begin() as db:
                current = db.scalar(select(Booking).where(Booking.confirmation_code == confirmation_code))
                if not current:
                    abort(404)
                appointment_time = datetime.combine(current.appointment_date, datetime.min.time(), tzinfo=TZ) + timedelta(minutes=current.start_minutes)
                if current.status not in ('pending', 'confirmed'):
                    flash(tr('لا يمكن إلغاء هذا الموعد في حالته الحالية.', 'This appointment cannot be cancelled in its current state.'), 'error')
                elif appointment_time - local_now() <= timedelta(hours=24):
                    flash(tr('لإلغاء موعد خلال 24 ساعة، يرجى التواصل مباشرة مع الاستوديو.', 'For cancellations within 24 hours, contact the studio directly.'), 'error')
                else:
                    current.status = 'cancelled'
                    flash(tr('تم إلغاء طلب الموعد.', 'The appointment request has been cancelled.'), 'success')
            return redirect(url_for('booking_detail', confirmation_code=confirmation_code))
        return render_template('booking_detail.html', booking=booking, service=service, person=person, cancel_form=cancel_form)

    @app.route('/admin/login', methods=['GET', 'POST'])
    def admin_login():
        if session.get('admin_logged_in'):
            return redirect(url_for('admin_dashboard'))
        form = LoginForm()
        if form.validate_on_submit():
            if hmac.compare_digest(form.password.data, app.config['ADMIN_PASSWORD']):
                session.clear(); session['admin_logged_in'] = True; session.permanent = True
                flash(tr('تم تسجيل الدخول.', 'Signed in.'), 'success')
                return redirect(url_for('admin_dashboard'))
            flash(tr('كلمة المرور غير صحيحة.', 'Incorrect password.'), 'error')
        return render_template('admin_login.html', form=form)

    @app.route('/admin/logout', methods=['POST'])
    @admin_required
    def admin_logout():
        form = LogoutForm()
        if form.validate_on_submit(): session.clear()
        return redirect(url_for('index'))

    @app.route('/admin', methods=['GET', 'POST'])
    @admin_required
    def admin_dashboard():
        status_form = StatusForm()
        if request.method == 'POST' and status_form.validate_on_submit():
            booking_id = request.form.get('booking_id', type=int)
            conflict = False
            with factory.begin() as db:
                booking = db.get(Booking, booking_id) if booking_id else None
                if not booking:
                    abort(404)
                next_status = status_form.status.data
                if next_status in ('pending', 'confirmed'):
                    conflict = db.scalar(select(Booking.id).where(
                        Booking.id != booking.id,
                        Booking.staff_id == booking.staff_id,
                        Booking.appointment_date == booking.appointment_date,
                        Booking.status.in_(['pending', 'confirmed']),
                        Booking.start_minutes < booking.end_minutes,
                        Booking.end_minutes > booking.start_minutes,
                    ).limit(1)) is not None
                if not conflict:
                    booking.status = next_status
            if conflict:
                flash(tr('لا يمكن تفعيل الموعد لأنه يتعارض مع حجز آخر لعضو الفريق نفسه.', 'This appointment overlaps another active booking for the same team member.'), 'error')
            else:
                flash(tr('تم تحديث حالة الموعد.', 'Appointment status updated.'), 'success')
            return redirect(url_for('admin_dashboard'))
        with factory() as db:
            bookings = db.scalars(select(Booking).order_by(Booking.appointment_date.desc(), Booking.start_minutes.desc(), Booking.id.desc())).all()
            services = {s.id: s for s in db.scalars(select(Service)).all()}
            staff = {p.id: p for p in db.scalars(select(Staff)).all()}
            rows = [{'booking': b, 'service': services[b.service_id], 'person': staff[b.staff_id]} for b in bookings]
            totals = {
                'all': len(bookings),
                'pending': sum(1 for b in bookings if b.status == 'pending'),
                'confirmed': sum(1 for b in bookings if b.status == 'confirmed'),
            }
        return render_template('admin_dashboard.html', rows=rows, totals=totals, status_form=status_form)

    @app.errorhandler(404)
    def not_found(_error):
        return render_template('error.html', code=404, title_ar='الصفحة أو الحجز غير موجود', title_en='Page or booking not found'), 404

    @app.errorhandler(413)
    def too_large(_error):
        return render_template('error.html', code=413, title_ar='حجم الطلب كبير جدًا', title_en='Request too large'), 413

    return app

app = create_app()
if __name__ == '__main__':
    app.run(debug=os.getenv('FLASK_DEBUG', 'false').lower() == 'true')
