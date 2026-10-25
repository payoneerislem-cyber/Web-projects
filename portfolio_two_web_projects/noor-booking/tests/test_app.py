from datetime import timedelta

from sqlalchemy import select

from app import Booking, Service, Staff, create_app, get_available_slots, local_now


def make_app(tmp_path):
    return create_app({
        'TESTING': True,
        'SECRET_KEY': 'test-secret-that-is-long-enough',
        'ADMIN_PASSWORD': 'test-admin-password',
        'WTF_CSRF_ENABLED': False,
        'DATABASE_URL': 'sqlite:///' + str(tmp_path / 'test.db'),
    })


def next_weekday(days_ahead=10):
    target = local_now().date() + timedelta(days=days_ahead)
    while target.weekday() == 6:
        target += timedelta(days=1)
    return target


def test_home_health_privacy_and_slots(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    home = client.get('/')
    assert home.status_code == 200
    assert client.get('/healthz').json['status'] == 'ok'
    assert client.get('/privacy').status_code == 200
    assert 'data-booking-form' in home.get_data(as_text=True)
    factory = app.extensions['db_factory']
    with factory() as db:
        service = db.scalar(select(Service).where(Service.slug == 'classic-cut'))
    slots = get_available_slots(factory, next_weekday(), service.id, 'any')
    assert slots
    assert all(s['start_minutes'] >= 9 * 60 and s['end_minutes'] <= 19 * 60 for s in slots)


def test_admin_is_protected(tmp_path):
    response = make_app(tmp_path).test_client().get('/admin')
    assert response.status_code == 302
    assert '/admin/login' in response.headers['Location']


def test_cannot_find_arbitrary_booking(tmp_path):
    assert make_app(tmp_path).test_client().get('/booking/not-a-real-code').status_code == 404


def test_booking_request_is_saved_as_pending(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    target = next_weekday()
    with app.extensions['db_factory']() as db:
        service = db.scalar(select(Service).where(Service.slug == 'classic-cut'))
    slot_response = client.get(f'/api/slots?date={target.isoformat()}&service_id={service.id}&staff_preference=any')
    assert slot_response.status_code == 200
    slots = slot_response.json['slots']
    assert slots
    chosen = slots[0]
    response = client.post('/', data={
        'service_id': str(service.id),
        'appointment_date': target.isoformat(),
        'staff_preference': 'any',
        'start_time': chosen['value'],
        'customer_name': 'Portfolio Test Customer',
        'phone': '05501234567',
        'email': '',
        'notes': 'Test booking only.',
        'consent': 'y',
        'website': '',
    }, follow_redirects=False)
    assert response.status_code == 302
    assert response.headers['Location'].startswith('/booking/')
    with app.extensions['db_factory']() as db:
        booking = db.scalar(select(Booking).where(Booking.is_demo.is_(False)))
        assert booking is not None
        assert booking.status == 'pending'
        code = booking.confirmation_code
    detail = client.get(f'/booking/{code}')
    assert detail.status_code == 200
    assert code in detail.get_data(as_text=True)


def test_admin_cannot_reactivate_overlapping_booking(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    target = next_weekday(12)
    with app.extensions['db_factory'].begin() as db:
        service_short = db.scalar(select(Service).where(Service.slug == 'classic-cut'))
        service_long = db.scalar(select(Service).where(Service.slug == 'cut-and-beard'))
        person = db.scalar(select(Staff).order_by(Staff.sort_order))
        cancelled = Booking(
            confirmation_code='TEST-CANCELLED-BOOKING', customer_name='Test Cancelled', phone='05501234567',
            email=None, service_id=service_short.id, staff_id=person.id, appointment_date=target,
            start_minutes=10 * 60, end_minutes=10 * 60 + 30, service_name=service_short.name_en,
            duration_minutes=30, price_da=service_short.price_da, notes='', status='cancelled', is_demo=False,
        )
        active = Booking(
            confirmation_code='TEST-ACTIVE-BOOKING', customer_name='Test Active', phone='05501234568',
            email=None, service_id=service_long.id, staff_id=person.id, appointment_date=target,
            start_minutes=10 * 60, end_minutes=11 * 60, service_name=service_long.name_en,
            duration_minutes=60, price_da=service_long.price_da, notes='', status='confirmed', is_demo=False,
        )
        db.add_all([cancelled, active])
    login = client.post('/admin/login', data={'password': 'test-admin-password'}, follow_redirects=False)
    assert login.status_code == 302
    with app.extensions['db_factory']() as db:
        cancelled = db.scalar(select(Booking).where(Booking.confirmation_code == 'TEST-CANCELLED-BOOKING'))
        cancelled_id = cancelled.id
    response = client.post('/admin', data={'booking_id': str(cancelled_id), 'status': 'confirmed'}, follow_redirects=True)
    assert response.status_code == 200
    assert 'يتعارض مع حجز آخر' in response.get_data(as_text=True)
    with app.extensions['db_factory']() as db:
        cancelled = db.scalar(select(Booking).where(Booking.confirmation_code == 'TEST-CANCELLED-BOOKING'))
        assert cancelled.status == 'cancelled'
