import hmac
import logging
import os
import smtplib
from datetime import date, datetime, timedelta
from email.message import EmailMessage
from functools import wraps
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from flask import Flask, Response, abort, current_app, flash, g, jsonify, redirect, render_template, request, session, url_for
from flask_wtf import FlaskForm
from sqlalchemy import Boolean, Date, DateTime, Integer, String, Text, create_engine, delete, func, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from wtforms import BooleanField, DateField, PasswordField, SelectField, StringField, TextAreaField
from wtforms.validators import DataRequired, Email, Length, Optional, Regexp

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / '.env')
logging.basicConfig(level=os.getenv('LOG_LEVEL', 'INFO'))
logger = logging.getLogger('madar')
TZ = ZoneInfo(os.getenv('BUSINESS_TIMEZONE', 'Africa/Algiers'))

SERVICE_LABELS = {
    'deep_cleaning': {'ar': 'تنظيف شامل', 'en': 'Deep cleaning'},
    'maintenance': {'ar': 'صيانة منزلية', 'en': 'Home maintenance'},
    'painting': {'ar': 'الطلاء والتشطيب', 'en': 'Painting & finishing'},
    'office_care': {'ar': 'العناية بالمكاتب', 'en': 'Office care'},
    'other': {'ar': 'خدمة أخرى', 'en': 'Other service'},
}
PROPERTY_LABELS = {
    'home': {'ar': 'منزل أو شقة', 'en': 'Home or apartment'},
    'office': {'ar': 'مكتب', 'en': 'Office'},
    'retail': {'ar': 'محل تجاري', 'en': 'Retail space'},
    'other': {'ar': 'نوع آخر', 'en': 'Other'},
}
STATUS_LABELS = {
    'new': {'ar': 'جديد', 'en': 'New'},
    'contacted': {'ar': 'تم التواصل', 'en': 'Contacted'},
    'scheduled': {'ar': 'تم تحديد الموعد', 'en': 'Scheduled'},
    'closed': {'ar': 'مغلق', 'en': 'Closed'},
}

class Base(DeclarativeBase):
    pass

class QuoteRequest(Base):
    __tablename__ = 'quote_requests'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[str] = mapped_column(String(40), nullable=False)
    email: Mapped[str | None] = mapped_column(String(254), nullable=True)
    service: Mapped[str] = mapped_column(String(40), nullable=False)
    property_type: Mapped[str] = mapped_column(String(40), nullable=False)
    preferred_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    details: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default='new')
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(TZ).replace(tzinfo=None))

class QuoteForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired(), Length(min=2, max=100)])
    phone = StringField('Phone', validators=[DataRequired(), Length(min=7, max=40), Regexp(r'^[0-9+().\s-]+$', message='Use a valid phone number.')])
    email = StringField('Email', validators=[Optional(), Email(), Length(max=254)])
    service = SelectField('Service', choices=[(k, v['ar']) for k, v in SERVICE_LABELS.items()], validators=[DataRequired()])
    property_type = SelectField('Property type', choices=[(k, v['ar']) for k, v in PROPERTY_LABELS.items()], validators=[DataRequired()])
    preferred_date = DateField('Preferred date', format='%Y-%m-%d', validators=[Optional()])
    details = TextAreaField('Details', validators=[DataRequired(), Length(min=12, max=2000)])
    consent = BooleanField('Consent', validators=[DataRequired(message='Please confirm that we may contact you about this request.')])
    website = StringField('Website', validators=[Length(max=200)])  # Honeypot field; keep empty.

class LoginForm(FlaskForm):
    password = PasswordField('Password', validators=[DataRequired(), Length(max=200)])

class StatusForm(FlaskForm):
    status = SelectField('Status', choices=[(k, v['ar']) for k, v in STATUS_LABELS.items()], validators=[DataRequired()])

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
    db_path = Path(app.config.get('DATABASE_PATH') or BASE_DIR / 'instance' / 'madar.sqlite3')
    if str(db_path) != ':memory:':
        if not db_path.is_absolute():
            db_path = BASE_DIR / db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        return 'sqlite:///' + str(db_path.resolve())
    return 'sqlite:///:memory:'

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
        logger.exception('Request was saved, but SMTP notification failed.')
        return False

def send_admin_email(subject, body):
    return send_email(os.getenv('MAIL_TO'), subject, body)

def demo_date(offset=3):
    candidate = datetime.now(TZ).date() + timedelta(days=offset)
    while candidate.weekday() == 6:
        candidate += timedelta(days=1)
    return candidate

def seed_data(factory):
    if os.getenv('SEED_DEMO_DATA', 'true').lower() != 'true':
        with factory.begin() as db:
            db.execute(delete(QuoteRequest).where(QuoteRequest.is_demo.is_(True)))
        return
    with factory.begin() as db:
        exists = db.scalar(select(func.count()).select_from(QuoteRequest).where(QuoteRequest.is_demo.is_(True)))
        if exists:
            return
        samples = [
            QuoteRequest(name='Demo — Samir B.', phone='0550 00 00 01', email='samir.demo@example.test', service='deep_cleaning', property_type='home', preferred_date=demo_date(4), details='Example request for a full apartment deep clean. This is seeded portfolio data, not a real customer.', status='new', is_demo=True),
            QuoteRequest(name='Demo — Lina K.', phone='0550 00 00 02', email='lina.demo@example.test', service='maintenance', property_type='office', preferred_date=demo_date(6), details='Example request to inspect a small office maintenance issue. This is demo data.', status='contacted', is_demo=True),
            QuoteRequest(name='Demo — Yacine M.', phone='0550 00 00 03', email='yacine.demo@example.test', service='painting', property_type='retail', preferred_date=None, details='Example inquiry about repainting a retail space. This is demo data.', status='scheduled', is_demo=True),
        ]
        db.add_all(samples)

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
        BUSINESS_NAME_AR=os.getenv('BUSINESS_NAME_AR', 'مَدار'),
        BUSINESS_NAME_EN=os.getenv('BUSINESS_NAME_EN', 'MADAR'),
        PUBLIC_PHONE=os.getenv('PUBLIC_PHONE', '0550 00 00 00'),
        PUBLIC_EMAIL=os.getenv('PUBLIC_EMAIL', 'bonjour@example.test'),
        PUBLIC_CITY=os.getenv('PUBLIC_CITY', 'Mascara, Algeria'),
        DATABASE_URL=os.getenv('DATABASE_URL'),
    )
    if test_config:
        app.config.update(test_config)
    if os.getenv('RENDER') and not os.getenv('SECRET_KEY') and not (test_config and test_config.get('SECRET_KEY')):
        raise RuntimeError('Set SECRET_KEY in the deployment environment.')
    if os.getenv('RENDER') and not os.getenv('ADMIN_PASSWORD'):
        raise RuntimeError('Set a strong ADMIN_PASSWORD before deploying the admin panel.')
    if app.config['SESSION_COOKIE_SECURE'] is False and os.getenv('RENDER'):
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
            'business_name_ar': app.config['BUSINESS_NAME_AR'],
            'business_name_en': app.config['BUSINESS_NAME_EN'],
            'public_phone': app.config['PUBLIC_PHONE'],
            'public_email': app.config['PUBLIC_EMAIL'],
            'public_city': app.config['PUBLIC_CITY'],
            'service_labels': SERVICE_LABELS,
            'property_labels': PROPERTY_LABELS,
            'status_labels': STATUS_LABELS,
            'now_date': datetime.now(TZ).date().isoformat(),
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
        return Response('User-agent: *\nAllow: /\nDisallow: /admin\n', mimetype='text/plain')

    @app.get('/healthz')
    def healthz():
        return jsonify(status='ok', service='madar-services')

    @app.get('/')
    def index():
        with factory() as db:
            total_services = len(SERVICE_LABELS) - 1
            open_requests = db.scalar(select(func.count()).select_from(QuoteRequest).where(QuoteRequest.status.in_(['new', 'contacted']))) or 0
        return render_template('index.html', total_services=total_services, open_requests=open_requests)

    @app.route('/request-quote', methods=['GET', 'POST'])
    def request_quote():
        form = QuoteForm()
        if request.method == 'GET':
            requested_service = request.args.get('service', '')
            if requested_service in SERVICE_LABELS:
                form.service.data = requested_service
        if form.validate_on_submit():
            if form.website.data:
                abort(400)
            if form.preferred_date.data and form.preferred_date.data < datetime.now(TZ).date():
                form.preferred_date.errors.append(tr('اختر تاريخًا اليوم أو بعده.', 'Choose today or a future date.'))
            else:
                with factory.begin() as db:
                    lead = QuoteRequest(
                        name=form.name.data.strip(), phone=form.phone.data.strip(),
                        email=(form.email.data or '').strip() or None,
                        service=form.service.data, property_type=form.property_type.data,
                        preferred_date=form.preferred_date.data, details=form.details.data.strip(),
                        status='new', is_demo=False,
                    )
                    db.add(lead)
                    db.flush()
                    lead_id = lead.id
                notification_body = f"Your request has been received (this is not a confirmed booking or quote).\nReference: #{lead_id}\nService: {SERVICE_LABELS[form.service.data]['en']}\nPreferred date: {form.preferred_date.data or 'Not specified'}\nWe will review the details and contact you."
                send_admin_email(
                    f"New MADAR quote request #{lead_id}",
                    f"New quote request #{lead_id}\nName: {form.name.data}\nPhone: {form.phone.data}\nEmail: {form.email.data or '-'}\nService: {SERVICE_LABELS[form.service.data]['en']}\nProperty: {PROPERTY_LABELS[form.property_type.data]['en']}\nPreferred date: {form.preferred_date.data or 'Not specified'}\n\nDetails:\n{form.details.data}",
                )
                if form.email.data:
                    send_email(form.email.data.strip(), 'MADAR Services — request received', notification_body)
                flash(tr('تم استلام طلبك التجريبي بنجاح. سنتواصل معك بعد ضبط بيانات التواصل الحقيقية.', 'Your demo request has been recorded. Configure real contact details before using this publicly.'), 'success')
                return redirect(url_for('request_quote'))
        return render_template('quote.html', form=form), (422 if request.method == 'POST' and form.errors else 200)

    @app.route('/admin/login', methods=['GET', 'POST'])
    def admin_login():
        if session.get('admin_logged_in'):
            return redirect(url_for('admin_dashboard'))
        form = LoginForm()
        if form.validate_on_submit():
            if hmac.compare_digest(form.password.data, app.config['ADMIN_PASSWORD']):
                session.clear()
                session['admin_logged_in'] = True
                session.permanent = True
                flash(tr('تم تسجيل الدخول.', 'Signed in.'), 'success')
                return redirect(url_for('admin_dashboard'))
            flash(tr('كلمة المرور غير صحيحة.', 'Incorrect password.'), 'error')
        return render_template('admin_login.html', form=form)

    @app.route('/admin/logout', methods=['POST'])
    @admin_required
    def admin_logout():
        form = LogoutForm()
        if form.validate_on_submit():
            session.clear()
        return redirect(url_for('index'))

    @app.route('/admin', methods=['GET', 'POST'])
    @admin_required
    def admin_dashboard():
        status_form = StatusForm()
        if request.method == 'POST' and status_form.validate_on_submit():
            request_id = request.form.get('request_id', type=int)
            with factory.begin() as db:
                lead = db.get(QuoteRequest, request_id) if request_id else None
                if not lead:
                    abort(404)
                lead.status = status_form.status.data
            flash(tr('تم تحديث حالة الطلب.', 'Request status updated.'), 'success')
            return redirect(url_for('admin_dashboard'))
        with factory() as db:
            leads = db.scalars(select(QuoteRequest).order_by(QuoteRequest.created_at.desc(), QuoteRequest.id.desc())).all()
            totals = {
                'all': len(leads),
                'new': sum(1 for item in leads if item.status == 'new'),
                'active': sum(1 for item in leads if item.status in ('new', 'contacted', 'scheduled')),
            }
        return render_template('admin_dashboard.html', leads=leads, totals=totals, status_form=status_form)

    @app.errorhandler(404)
    def not_found(_error):
        return render_template('error.html', code=404, title_ar='الصفحة غير موجودة', title_en='Page not found'), 404

    @app.errorhandler(413)
    def too_large(_error):
        return render_template('error.html', code=413, title_ar='حجم الطلب كبير جدًا', title_en='Request too large'), 413

    return app

app = create_app()

if __name__ == '__main__':
    app.run(debug=os.getenv('FLASK_DEBUG', 'false').lower() == 'true')
