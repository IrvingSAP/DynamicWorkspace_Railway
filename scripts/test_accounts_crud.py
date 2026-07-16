import os
import sys

import django

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dynamicworkspace.settings")
django.setup()

from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.backends.db import SessionStore
from django.test import RequestFactory

from apps.accounts.services import account_service
from apps.accounts.views import account_create, account_list

User = get_user_model()
ua = User.objects.filter(profile__user_type="UA").first()
factory = RequestFactory()


def make_request(method, path, data=None, user=None, session=None):
    request = factory.post(path, data or {}) if method == "POST" else factory.get(path)
    request.user = user
    if session is None:
        session = SessionStore()
        session.create()
    request.session = session
    request._messages = FallbackStorage(request)
    return request, session


request, _ = make_request("GET", "/app/admin/usuarios/", user=ua)
print("list", account_list(request).status_code)

bad = {
    "username": "newus",
    "email": "bad",
    "password": "short",
    "company": "",
    "is_active": "1",
}
request, session = make_request("POST", "/app/admin/usuarios/nuevo/", bad, ua)
print("create redirect", account_create(request).status_code)

request, session = make_request("GET", "/app/admin/usuarios/nuevo/", user=ua, session=session)
html = account_create(request).content.decode()
print("email kept", 'value="bad"' in html)
print("username kept", 'value="newus"' in html)
print("scope", account_service.get_management_scope(ua.profile)["target_type"])
