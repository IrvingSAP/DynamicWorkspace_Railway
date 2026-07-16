import os
import sys

import django

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dynamicworkspace.settings")
django.setup()

from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory

from apps.company.models import Company
from apps.company.views import company_create, company_update

User = get_user_model()
user = User.objects.filter(profile__user_type="UA").first() or User.objects.first()
company = Company.objects.first()
factory = RequestFactory()


def assert_values(label, response, expected):
    html = response.content.decode()
    print(label, "status", response.status_code)
    for key, value in expected.items():
        ok = value in html
        print(f"  {key}: {'OK' if ok else 'MISSING'} -> {value!r}")


post_data = {
    "name_short": "TESTCO",
    "name_long": "Test Company Long Name",
    "tax_id": "123",
    "email": "bad-email",
    "phone": "+57 300",
    "address": "Calle 1",
    "is_active": "1",
}


def make_request(method, path, data=None, session=None):
    if method == "POST":
        request = factory.post(path, data or {})
    else:
        request = factory.get(path)
    request.user = user
    if session is None:
        from django.contrib.sessions.backends.db import SessionStore

        session = SessionStore()
        session.create()
    request.session = session
    request._messages = FallbackStorage(request)
    return request, session


session = None
request, session = make_request("POST", "/app/admin/compañias/nueva/", post_data)
redirect_resp = company_create(request)
assert redirect_resp.status_code == 302

request, session = make_request("GET", "/app/admin/compañias/nueva/", session=session)
get_resp = company_create(request)
assert_values(
    "create-after-prg",
    get_resp,
    {
        "name_short": 'value="TESTCO"',
        "email": 'value="bad-email"',
        "address": "Calle 1",
    },
)

request, session = make_request(
    "POST",
    f"/app/admin/compañias/{company.pk}/editar/",
    post_data,
    session=None,
)
redirect_resp = company_update(request, pk=company.pk)
assert redirect_resp.status_code == 302

request, session = make_request(
    "GET",
    f"/app/admin/compañias/{company.pk}/editar/",
    session=session,
)
get_resp = company_update(request, pk=company.pk)
assert_values(
    "update-after-prg",
    get_resp,
    {
        "name_short": 'value="TESTCO"',
        "email": 'value="bad-email"',
        "address": "Calle 1",
    },
)

print("done")
