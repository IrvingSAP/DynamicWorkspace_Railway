import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dynamicworkspace.settings")
django.setup()

from django.contrib.auth import get_user_model
from django.test import Client

from apps.projects.models import Project, ProjectMembership

User = get_user_model()
slug = sys.argv[1] if len(sys.argv) > 1 else "proyecto-cm"
project = Project.objects.filter(slug=slug, project_kind="dms").first()
if project is None:
    project = Project.objects.filter(project_kind="dms").first()
print("project:", project.slug if project else None)

membership = None
user = None
if project:
    membership = ProjectMembership.objects.filter(
        project=project, role__in=["PA", "ED"], is_active=True
    ).first()
    user = membership.user if membership else User.objects.filter(is_superuser=True).first()
print("user:", user.username if user else None)

if not project or not user:
    sys.exit(1)

client = Client()
client.force_login(user)
url_step3 = f"/app/filepipe/proyectos/{project.slug}/origen/paso/3/"
url_save = f"/app/filepipe/proyectos/{project.slug}/origen/guardar/"

r = client.get(url_step3)
print("GET step3:", r.status_code)
match = re.search(rb'data-csrf-token="([^"]+)"', r.content)
token = match.group(1).decode() if match else ""
print("csrf:", token[:16] + "..." if token else "MISSING")

from apps.dms.source_profile.services import source_persistence_service

source = source_persistence_service.get_source_dict(project)
payload = dict(source)
payload["capture_end"] = {"mode": "eof"}

r2 = client.post(
    url_save,
    data={"source_payload": json.dumps(payload)},
    HTTP_X_REQUESTED_WITH="XMLHttpRequest",
    HTTP_X_CSRFTOKEN=token,
)
print("POST save:", r2.status_code, r2.get("Content-Type", ""))
body = r2.content[:800].decode("utf-8", errors="replace")
print(body)
