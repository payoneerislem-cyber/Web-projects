from datetime import date, timedelta

from sqlalchemy import select

from app import QuoteRequest, create_app


def make_app(tmp_path):
    return create_app({
        'TESTING': True,
        'SECRET_KEY': 'test-secret-that-is-long-enough',
        'ADMIN_PASSWORD': 'test-admin-password',
        'WTF_CSRF_ENABLED': False,
        'DATABASE_URL': 'sqlite:///' + str(tmp_path / 'test.db'),
    })


def test_home_health_and_privacy(tmp_path):
    client = make_app(tmp_path).test_client()
    assert client.get('/').status_code == 200
    assert client.get('/healthz').json['status'] == 'ok'
    assert client.get('/privacy').status_code == 200
    assert 'نسخة عرض تجريبي' in client.get('/').get_data(as_text=True)


def test_admin_is_protected(tmp_path):
    response = make_app(tmp_path).test_client().get('/admin')
    assert response.status_code == 302
    assert '/admin/login' in response.headers['Location']


def test_quote_form_page_and_service_prefill(tmp_path):
    response = make_app(tmp_path).test_client().get('/request-quote?service=maintenance')
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert 'name="service"' in body
    assert 'value="maintenance"' in body and 'selected' in body


def test_quote_request_is_saved(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    target = (date.today() + timedelta(days=5)).isoformat()
    response = client.post('/request-quote', data={
        'name': 'Portfolio Test Customer',
        'phone': '05501234567',
        'email': '',
        'service': 'maintenance',
        'property_type': 'home',
        'preferred_date': target,
        'details': 'Please inspect and maintain a small apartment.',
        'consent': 'y',
        'website': '',
    }, follow_redirects=True)
    assert response.status_code == 200
    assert 'تم استلام طلبك التجريبي بنجاح' in response.get_data(as_text=True)
    with app.extensions['db_factory']() as db:
        lead = db.scalar(select(QuoteRequest).where(QuoteRequest.is_demo.is_(False)))
        assert lead is not None
        assert lead.service == 'maintenance'
        assert lead.name == 'Portfolio Test Customer'


def test_invalid_quote_is_not_saved(tmp_path):
    app = make_app(tmp_path)
    response = app.test_client().post('/request-quote', data={
        'name': 'A', 'phone': 'bad phone!', 'email': '', 'service': 'maintenance',
        'property_type': 'home', 'preferred_date': '', 'details': 'Short',
        'consent': 'y', 'website': '',
    })
    assert response.status_code == 422
    with app.extensions['db_factory']() as db:
        assert db.scalar(select(QuoteRequest).where(QuoteRequest.is_demo.is_(False))) is None
