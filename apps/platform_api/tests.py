from django.test import TestCase
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from unittest.mock import MagicMock, patch
from types import SimpleNamespace
from pathlib import Path
import uuid

from apps.core.services.operation_result import OperationResult
from apps.accounts.models import UserProfile
from apps.company.models import Company
from apps.platform_api.models import (
    ACTION_CREATED,
    ACTION_KEY_ROTATED,
    ACTION_REVOKED,
    ACTION_UPDATED,
    SCOPE_ARTIFACTS_DOWNLOAD,
    SCOPE_JOBS_CANCEL,
    SCOPE_JOBS_READ,
    SCOPE_JOBS_RUN,
    SCOPE_PIPELINE_RUN,
    STATUS_REVOKED,
    ApiClientAuditEvent,
)
from apps.platform_api.services import (
    api_client_service,
    bearer_auth,
    client_audit_service,
    contract_service,
    job_run_service,
    process_security_service,
    webhook_service,
)
from apps.platform_api.services.bearer_auth import AuthFailure
from apps.projects.models import Project


class PlatformApiAuthTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            name_short="ACME",
            name_long="Acme Ops",
            is_active=True,
        )
        self.user = User.objects.create_user("ops", password="x")
        UserProfile.objects.create(
            user=self.user,
            company=self.company,
            user_type=UserProfile.USER_SYSTEM,
            email_confirmed=True,
            tfa_verified=True,
            totp_secret="secret",
            status=UserProfile.STATUS_ACTIVE,
        )

    def _create(self, **extra):
        posted = {
            "code": extra.get("code", "client-erp-01"),
            "name": "ERP banco",
            "description": extra.get(
                "description",
                "Integración ERP nómina: envío diario de archivos al banco. Dueño: Tesorería.",
            ),
            "environment": extra.get("environment", "sandbox"),
            "scopes": extra.get("scopes", [SCOPE_JOBS_RUN, SCOPE_JOBS_READ]),
        }
        return api_client_service.create_client(self.user, posted)

    def test_create_stores_hash_not_plaintext(self):
        result = self._create()
        self.assertTrue(result.ok)
        raw = result.payload["plaintext_key"]
        client = result.payload["client"]
        self.assertNotIn(raw, client.secret_hash)
        self.assertTrue(raw.startswith("dw_test_"))
        self.assertIn("Tesorería", client.description)

    def test_create_requires_description(self):
        result = self._create(description="")
        self.assertFalse(result.ok)
        self.assertEqual(result.error_code, "validation_form")
        self.assertIn("description", result.errors)

    def test_same_key_authenticates_twice(self):
        result = self._create()
        raw = result.payload["plaintext_key"]
        first = bearer_auth.authenticate_token(raw)
        second = bearer_auth.authenticate_token(raw)
        self.assertEqual(first.pk, second.pk)

    def test_rotate_invalidates_old_key(self):
        created = self._create()
        old = created.payload["plaintext_key"]
        client = created.payload["client"]
        rotated = api_client_service.rotate_key(self.user, client)
        self.assertTrue(rotated.ok)
        with self.assertRaises(bearer_auth.AuthFailure) as ctx:
            bearer_auth.authenticate_token(old)
        self.assertEqual(ctx.exception.status, 401)
        bearer_auth.authenticate_token(rotated.payload["plaintext_key"])

    def test_revoke_blocks_auth(self):
        created = self._create()
        raw = created.payload["plaintext_key"]
        client = created.payload["client"]
        api_client_service.revoke_client(self.user, client)
        client.refresh_from_db()
        self.assertEqual(client.status, STATUS_REVOKED)
        with self.assertRaises(bearer_auth.AuthFailure):
            bearer_auth.authenticate_token(raw)

    def test_tenant_isolation(self):
        other = Company.objects.create(name_short="OTRO", name_long="Otro", is_active=True)
        other_user = User.objects.create_user("other", password="x")
        UserProfile.objects.create(
            user=other_user,
            company=other,
            user_type=UserProfile.USER_SYSTEM,
            email_confirmed=True,
            tfa_verified=True,
            totp_secret="secret",
            status=UserProfile.STATUS_ACTIVE,
        )
        created = self._create()
        found = api_client_service.get_for_user(other_user, created.payload["client"].pk)
        self.assertIsNone(found)

    def test_create_writes_audit_event(self):
        result = self._create()
        client = result.payload["client"]
        events = ApiClientAuditEvent.objects.filter(client=client)
        self.assertEqual(events.count(), 1)
        event = events.get()
        self.assertEqual(event.action, ACTION_CREATED)
        self.assertEqual(event.actor_id, self.user.pk)
        self.assertEqual(event.after["code"], client.code)

    def test_update_and_rotate_and_revoke_are_audited(self):
        created = self._create()
        client = created.payload["client"]
        posted = {
            "code": client.code,
            "name": "ERP banco (tesorería)",
            "description": client.description,
            "environment": client.environment,
            "scopes": list(client.scopes),
        }
        api_client_service.update_client(self.user, client, posted)
        client.refresh_from_db()
        api_client_service.rotate_key(self.user, client)
        client.refresh_from_db()
        api_client_service.revoke_client(self.user, client)
        actions = list(
            ApiClientAuditEvent.objects.filter(client=client).order_by("created_at").values_list("action", flat=True)
        )
        self.assertEqual(
            actions,
            [ACTION_CREATED, ACTION_UPDATED, ACTION_KEY_ROTATED, ACTION_REVOKED],
        )

    def test_audit_is_tenant_scoped(self):
        created = self._create()
        other = Company.objects.create(name_short="OTRO2", name_long="Otro 2", is_active=True)
        other_user = User.objects.create_user("other2", password="x")
        UserProfile.objects.create(
            user=other_user,
            company=other,
            user_type=UserProfile.USER_SYSTEM,
            email_confirmed=True,
            tfa_verified=True,
            totp_secret="secret",
            status=UserProfile.STATUS_ACTIVE,
        )
        rows, _stats = client_audit_service.list_for_user(other_user)
        self.assertEqual(rows, [])
        self.assertIsNone(
            client_audit_service.get_event_for_user(
                other_user,
                created.payload["client"].audit_events.first().pk,
            )
        )


class PlatformApiProcessSecurityTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            name_short="ACME",
            name_long="Acme Ops",
            is_active=True,
        )
        self.user = User.objects.create_user("ops", password="x")
        UserProfile.objects.create(
            user=self.user,
            company=self.company,
            user_type=UserProfile.USER_SYSTEM,
            email_confirmed=True,
            tfa_verified=True,
            totp_secret="secret",
            status=UserProfile.STATUS_ACTIVE,
        )
        posted = {
            "code": "client-erp-01",
            "name": "ERP banco",
            "description": "Integración ERP nómina. Dueño: Tesorería.",
            "environment": "sandbox",
            "scopes": [SCOPE_JOBS_RUN, SCOPE_JOBS_READ],
        }
        created = api_client_service.create_client(self.user, posted)
        self.client_row = created.payload["client"]
        self.plaintext = created.payload["plaintext_key"]

    def test_upload_rejects_type_and_size(self):
        bad_type = process_security_service.validate_upload(
            filename="nomina.exe",
            size_bytes=10,
            company=self.company,
        )
        self.assertFalse(bad_type.ok)
        too_big = process_security_service.validate_upload(
            filename="nomina.csv",
            size_bytes=60 * 1024 * 1024,
            company=self.company,
        )
        self.assertFalse(too_big.ok)
        ok = process_security_service.validate_upload(
            filename="nomina.csv",
            size_bytes=1024,
            company=self.company,
        )
        self.assertTrue(ok.ok)

    def test_callback_blocks_ssrf(self):
        process_security_service.update_policy(
            self.user,
            {
                "max_upload_mb": "50",
                "rate_per_minute": "60",
                "artifact_ttl_hours": "24",
                "allowed_extensions": [".csv"],
                "webhook_host_allowlist": ["hooks.banco.example"],
            },
        )
        self.assertFalse(
            process_security_service.validate_callback_url(
                "http://hooks.banco.example/cb", self.company
            ).ok
        )
        self.assertFalse(
            process_security_service.validate_callback_url(
                "https://127.0.0.1/cb", self.company
            ).ok
        )
        self.assertFalse(
            process_security_service.validate_callback_url(
                "https://evil.example/cb", self.company
            ).ok
        )
        self.assertTrue(
            process_security_service.validate_callback_url(
                "https://hooks.banco.example/cb", self.company
            ).ok
        )

    def test_artifact_token_roundtrip_and_tenant(self):
        token = process_security_service.sign_artifact_token(
            company_id=self.company.pk,
            job_id="job-1",
            name="report.csv",
        )
        job_id, name = process_security_service.verify_artifact_token(
            token, company_id=self.company.pk, max_age=3600
        )
        self.assertEqual(job_id, "job-1")
        self.assertEqual(name, "report.csv")
        other = Company.objects.create(name_short="OTRO", name_long="Otro", is_active=True)
        with self.assertRaises(AuthFailure) as ctx:
            process_security_service.verify_artifact_token(
                token, company_id=other.pk, max_age=3600
            )
        self.assertEqual(ctx.exception.status, 404)

    def test_redact_strips_pii(self):
        safe = process_security_service.redact_for_log({"token": "abc", "job_id": "1"})
        self.assertEqual(safe["token"], "[redacted]")
        self.assertEqual(safe["job_id"], "1")

    def test_whoami_rate_limit(self):
        policy = process_security_service.get_policy(self.company)
        policy.rate_per_minute = 1
        policy.save(update_fields=["rate_per_minute"])
        headers = {"Authorization": f"Bearer {self.plaintext}"}
        first = self.client.get("/api/v1/whoami", headers=headers)
        self.assertEqual(first.status_code, 200)
        self.assertIn("process_policy", first.json())
        second = self.client.get("/api/v1/whoami", headers=headers)
        self.assertEqual(second.status_code, 429)
        self.assertEqual(second.json()["error_code"], "rate_limited")

    def test_policy_is_tenant_scoped(self):
        other = Company.objects.create(name_short="OTRO3", name_long="Otro 3", is_active=True)
        other_user = User.objects.create_user("other3", password="x")
        UserProfile.objects.create(
            user=other_user,
            company=other,
            user_type=UserProfile.USER_SYSTEM,
            email_confirmed=True,
            tfa_verified=True,
            totp_secret="secret",
            status=UserProfile.STATUS_ACTIVE,
        )
        process_security_service.update_policy(
            self.user,
            {
                "max_upload_mb": "10",
                "rate_per_minute": "5",
                "artifact_ttl_hours": "2",
                "allowed_extensions": [".csv"],
                "webhook_host_allowlist": ["hooks.banco.example"],
            },
        )
        other_policy = process_security_service.get_policy(other)
        self.assertEqual(other_policy.max_upload_bytes, 50 * 1024 * 1024)
        mine = process_security_service.get_policy(self.company)
        self.assertEqual(mine.max_upload_bytes, 10 * 1024 * 1024)


class PlatformApiContractTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            name_short="ACME",
            name_long="Acme Ops",
            is_active=True,
        )
        self.user = User.objects.create_user("ops2", password="x")
        UserProfile.objects.create(
            user=self.user,
            company=self.company,
            user_type=UserProfile.USER_SYSTEM,
            email_confirmed=True,
            tfa_verified=True,
            totp_secret="secret",
            status=UserProfile.STATUS_ACTIVE,
        )
        created = api_client_service.create_client(
            self.user,
            {
                "code": "client-contract-01",
                "name": "ERP contrato",
                "description": "Cliente para validar el contrato HTTP. Dueño: Tesorería.",
                "environment": "sandbox",
                "scopes": [SCOPE_JOBS_RUN, SCOPE_JOBS_READ],
            },
        )
        self.plaintext = created.payload["plaintext_key"]
        self.auth = {"Authorization": f"Bearer {self.plaintext}"}

    def test_parse_job_requires_project_slug(self):
        result = contract_service.parse_run_request({"kind": "file_gate", "wait": "sync"})
        self.assertFalse(result.ok)
        self.assertIn("project_slug", result.errors)

    def test_pipeline_default_wait_is_async(self):
        result = contract_service.parse_run_request(
            {"kind": "file_pipeline", "pipeline_id": "nomina-diaria"}
        )
        self.assertTrue(result.ok)
        parsed = result.payload["parsed"]
        self.assertEqual(parsed["wait"], "async")
        self.assertEqual(parsed["scope"], SCOPE_PIPELINE_RUN)
        self.assertEqual(parsed["default_http_status"], 202)

    def test_mode_pipeline_alias(self):
        result = contract_service.parse_run_request(
            {"mode": "pipeline", "pipeline_id": "nomina-diaria"}
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.payload["parsed"]["kind"], "file_pipeline")

    def test_gate_verdict_is_not_job_status(self):
        body = contract_service.envelope(
            ok=False,
            job_id="job-1",
            kind="file_gate",
            status=contract_service.STATUS_COMPLETED,
            project_slug="nomina-mensual",
            summary={"verdict": contract_service.GATE_REJECTED},
            errors=[
                contract_service.error_item(
                    row=2,
                    field="amount",
                    code="required",
                    message="Falta el monto.",
                )
            ],
        )
        self.assertEqual(body["status"], "completed")
        self.assertEqual(body["summary"]["verdict"], "rejected")
        self.assertFalse(body["ok"])
        self.assertNotIn("accepted", contract_service.JOB_STATUSES)

    def test_http_validate_ok_and_unknown_kind(self):
        ok = self.client.post(
            "/api/v1/jobs/validate",
            data={"kind": "file_gate", "project_slug": "nomina-mensual", "wait": "sync"},
            headers=self.auth,
        )
        self.assertEqual(ok.status_code, 200)
        self.assertTrue(ok.json()["validated"])
        self.assertFalse(ok.json()["executed"])
        bad = self.client.post(
            "/api/v1/jobs/validate",
            data={"kind": "nope", "project_slug": "nomina-mensual"},
            headers=self.auth,
        )
        self.assertEqual(bad.status_code, 400)

    def test_pipeline_validate_needs_scope(self):
        response = self.client.post(
            "/api/v1/jobs/validate",
            data={"kind": "file_pipeline", "pipeline_id": "nomina-diaria"},
            headers=self.auth,
        )
        self.assertEqual(response.status_code, 403)

    def test_contract_catalog_requires_bearer(self):
        anon = self.client.get("/api/v1/contract")
        self.assertEqual(anon.status_code, 401)
        ok = self.client.get("/api/v1/contract", headers=self.auth)
        self.assertEqual(ok.status_code, 200)
        kinds = [row["kind"] for row in ok.json()["kinds"]]
        self.assertIn("file_gate", kinds)
        self.assertIn("file_pipeline", kinds)

    def test_openapi_catalog_lists_canonical_paths(self):
        anon = self.client.get("/api/v1/openapi")
        self.assertEqual(anon.status_code, 401)
        ok = self.client.get("/api/v1/openapi", headers=self.auth)
        self.assertEqual(ok.status_code, 200)
        body = ok.json()
        self.assertTrue(body["yaml_deferred"])
        self.assertEqual(body["api_version"], "v1")
        paths = {(row["method"], row["path"]): row for row in body["paths"]}
        run = paths[("POST", "/api/v1/jobs/run")]
        self.assertTrue(run["implemented"])
        self.assertFalse(paths[("GET", "/api/v1/ops/summary")]["implemented"])
        self.assertTrue(paths[("POST", "/api/v1/pipelines/{pipeline_id}/runs")]["implemented"])
        runs = [row for row in body["paths"] if row["key"] == "run"]
        self.assertEqual(len(runs), 1)

    def test_integration_catalog_maps_wired_runners(self):
        from apps.platform_api.services import integration_service

        catalog = integration_service.catalog()
        kinds = [row["kind"] for row in catalog["runners"]]
        self.assertIn("file_gate", kinds)
        self.assertIn("file_pipeline", kinds)
        self.assertNotIn("workspace", kinds)
        wired = {row["kind"]: row["wired"] for row in catalog["runners"]}
        self.assertTrue(wired["file_gate"])
        self.assertTrue(wired["dms"])
        self.assertTrue(wired["file_pipeline"])
        self.assertTrue(wired["reverse"])
        self.assertTrue(wired["file_match"])
        self.assertTrue(wired["structure_scout"])
        self.assertTrue(wired["file_clean"])
        self.assertTrue(wired["file_split"])
        self.assertTrue(wired["file_merge"])
        self.assertFalse(wired["file_repair"])
        self.assertFalse(wired["data_profiler"])
        self.assertEqual(catalog["identity"]["product_code"], "PLATFORM_API")
        self.assertEqual(catalog["identity"]["django_app"], "apps.platform_api")
        self.assertFalse(catalog["identity"]["uf_sidebar"])
        self.assertEqual(catalog["single_run_path"], "/api/v1/jobs/run")
        gate = next(row for row in catalog["runners"] if row["kind"] == "file_gate")
        self.assertIn("validate_and_run", gate["runner"])
        pipe = next(row for row in catalog["runners"] if row["kind"] == "dms")
        self.assertIn("run_full_job", pipe["runner"])
        pipeline = next(row for row in catalog["runners"] if row["kind"] == "file_pipeline")
        self.assertIn("start_run", pipeline["runner"])

        anon = self.client.get("/api/v1/integration")
        self.assertEqual(anon.status_code, 401)
        ok = self.client.get("/api/v1/integration", headers=self.auth)
        self.assertEqual(ok.status_code, 200)
        body = ok.json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["user_message"], integration_service.MSG_CATALOG)
        self.assertEqual(body["wired_kinds"], ["file_gate", "dms", "reverse", "file_match", "structure_scout", "file_clean", "file_split", "file_merge", "file_pipeline"])
        self.assertEqual(body["paths"]["run"], "/api/v1/jobs/run")
        self.assertTrue(body["paths"]["integration"].endswith("/integration"))



class PlatformApiJobsRunTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            name_short="ACME",
            name_long="Acme Ops",
            is_active=True,
        )
        self.user = User.objects.create_user("ops3", password="x")
        UserProfile.objects.create(
            user=self.user,
            company=self.company,
            user_type=UserProfile.USER_SYSTEM,
            email_confirmed=True,
            tfa_verified=True,
            totp_secret="secret",
            status=UserProfile.STATUS_ACTIVE,
        )
        created = api_client_service.create_client(
            self.user,
            {
                "code": "client-run-01",
                "name": "ERP run",
                "description": "Cliente para disparar jobs Gate. Dueño: Tesorería.",
                "environment": "sandbox",
                "scopes": [SCOPE_JOBS_RUN, SCOPE_JOBS_READ],
            },
        )
        self.plaintext = created.payload["plaintext_key"]
        self.auth = {"Authorization": f"Bearer {self.plaintext}"}
        self.api_client = created.payload["client"]
        self.project = Project.objects.create(
            company=self.company,
            name="Nómina mensual",
            slug="nomina-mensual",
            owner=self.user,
            project_kind=Project.KIND_FILE_GATE,
        )

    def _file(self):
        return SimpleUploadedFile("nomina.csv", b"id,name\n1,a\n", content_type="text/csv")

    def test_run_async_returns_202(self):
        job_id = uuid.uuid4()
        job = SimpleNamespace(
            id=job_id,
            status="queued",
            STATUS_COMPLETED="completed",
            STATUS_PARTIAL="partial",
            STATUS_CANCELLED="cancelled",
            STATUS_FAILED="failed",
            STATUS_RUNNING="running",
            rows_read=0,
            rows_ok=0,
            rows_rejected=0,
            report_path="",
            output_stored_path="",
            input_content_hash="",
            input_suggestions={},
            version=SimpleNamespace(version_number=1),
            save=MagicMock(),
        )
        with patch(
            "apps.platform_api.services.job_run_service.file_intake_persistence_service.upload_production"
        ) as mocked_upload:
            mocked_upload.return_value = OperationResult.success("ok", job=job)
            response = self.client.post(
                "/api/v1/jobs/run",
                data={
                    "kind": "file_gate",
                    "project_slug": "nomina-mensual",
                    "wait": "async",
                    "file": self._file(),
                },
                headers=self.auth,
            )
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()["status"], "queued")
        self.assertEqual(response.json()["job_id"], str(job_id))

    def test_run_unknown_project_is_opaque(self):
        response = self.client.post(
            "/api/v1/jobs/run",
            data={
                "kind": "file_gate",
                "project_slug": "no-existe",
                "wait": "sync",
                "file": self._file(),
            },
            headers=self.auth,
        )
        self.assertEqual(response.status_code, 404)

    @patch("apps.platform_api.services.job_run_service.validation_run_service.validate_and_run")
    def test_run_gate_sync_ok(self, mocked_run):
        job_id = uuid.uuid4()
        job = SimpleNamespace(
            id=job_id,
            status="completed",
            STATUS_COMPLETED="completed",
            STATUS_PARTIAL="partial",
            STATUS_CANCELLED="cancelled",
            rows_read=10,
            rows_ok=10,
            rows_rejected=0,
            report_path="reports/gate.json",
            output_stored_path="",
            input_content_hash="abc",
            input_suggestions={"gate_result": {"status": "passed", "issues_preview": []}},
            version=SimpleNamespace(version_number=3),
            save=MagicMock(),
        )
        mocked_run.return_value = OperationResult.success("ok", job=job)
        response = self.client.post(
            "/api/v1/jobs/run",
            data={
                "kind": "file_gate",
                "project_slug": "nomina-mensual",
                "wait": "sync",
                "file": self._file(),
            },
            headers=self.auth,
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["status"], "completed")
        self.assertEqual(body["summary"]["verdict"], "accepted")
        self.assertEqual(body["job_id"], str(job_id))
        self.assertEqual(body["audit"]["trigger_source"], "api")
        self.assertEqual(body["audit"]["triggered_by_api_client_id"], str(self.api_client.pk))
        self.assertTrue(body["audit"]["correlation_id"])
        self.assertEqual(body["audit"]["job_id"], str(job_id))
        mocked_run.assert_called_once()

    @patch("apps.platform_api.services.job_run_service.execution_service.run_full_job")
    @patch("apps.platform_api.services.job_run_service.file_intake_persistence_service.upload_production")
    def test_run_reverse_sync_ok(self, mocked_upload, mocked_run):
        Project.objects.create(
            company=self.company,
            name="Emisor banco",
            slug="emisor-banco",
            owner=self.user,
            project_kind=Project.KIND_REVERSE,
        )
        job_id = uuid.uuid4()
        job = SimpleNamespace(
            id=job_id,
            status="completed",
            STATUS_COMPLETED="completed",
            STATUS_PARTIAL="partial",
            STATUS_CANCELLED="cancelled",
            STATUS_FAILED="failed",
            STATUS_RUNNING="running",
            rows_read=4,
            rows_ok=4,
            rows_rejected=0,
            report_path="reports/reverse.json",
            output_stored_path="out/emisor.txt",
            input_content_hash="rev",
            input_suggestions={},
            version=SimpleNamespace(version_number=2),
            save=MagicMock(),
        )
        mocked_upload.return_value = OperationResult.success("ok", job=job)
        mocked_run.return_value = OperationResult.success("ok", job=job)
        response = self.client.post(
            "/api/v1/jobs/run",
            data={
                "kind": "reverse",
                "project_slug": "emisor-banco",
                "wait": "sync",
                "file": self._file(),
            },
            headers=self.auth,
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["kind"], "reverse")
        self.assertEqual(body["job_id"], str(job_id))
        self.assertEqual(body["user_message"], job_run_service.MSG_REVERSE_OK)
        mocked_run.assert_called_once()

    def test_run_reverse_rejects_gate_project(self):
        response = self.client.post(
            "/api/v1/jobs/run",
            data={
                "kind": "reverse",
                "project_slug": "nomina-mensual",
                "wait": "sync",
                "file": self._file(),
            },
            headers=self.auth,
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["user_message"], job_run_service.MSG_KIND_MISMATCH)

    @patch("apps.platform_api.services.job_run_service.match_run_service.match_and_run")
    def test_run_match_sync_ok(self, mocked_run):
        Project.objects.create(
            company=self.company,
            name="Conciliacion banco",
            slug="conciliacion-banco",
            owner=self.user,
            project_kind=Project.KIND_FILE_MATCH,
        )
        job_id = uuid.uuid4()
        job = SimpleNamespace(
            id=job_id,
            status="completed",
            STATUS_COMPLETED="completed",
            STATUS_PARTIAL="partial",
            STATUS_CANCELLED="cancelled",
            STATUS_FAILED="failed",
            STATUS_RUNNING="running",
            verdict="passed",
            report_path="reports/match.json",
            output_stored_path="",
            input_content_hash="",
            input_suggestions={},
            metrics={
                "rows_a": 3,
                "rows_b": 3,
                "keys_total": 3,
                "matched": 3,
                "match_pct": 100.0,
            },
            version=SimpleNamespace(version_number=1),
            save=MagicMock(),
        )
        mocked_run.return_value = OperationResult.success("ok", job=job)
        response = self.client.post(
            "/api/v1/jobs/run",
            data={
                "kind": "file_match",
                "project_slug": "conciliacion-banco",
                "wait": "sync",
                "file_a": SimpleUploadedFile("lado-a.csv", b"id\n1\n", content_type="text/csv"),
                "file_b": SimpleUploadedFile("lado-b.csv", b"id\n1\n", content_type="text/csv"),
            },
            headers=self.auth,
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["kind"], "file_match")
        self.assertEqual(body["job_id"], str(job_id))
        self.assertEqual(body["user_message"], job_run_service.MSG_MATCH_OK)
        self.assertEqual(body["summary"]["verdict"], "passed")
        self.assertTrue(body["ok"])
        mocked_run.assert_called_once()
        self.assertFalse(mocked_run.call_args.kwargs["require_membership"])

    def test_run_match_rejects_gate_project(self):
        response = self.client.post(
            "/api/v1/jobs/run",
            data={
                "kind": "file_match",
                "project_slug": "nomina-mensual",
                "wait": "sync",
                "file_a": SimpleUploadedFile("lado-a.csv", b"id\n1\n", content_type="text/csv"),
                "file_b": SimpleUploadedFile("lado-b.csv", b"id\n1\n", content_type="text/csv"),
            },
            headers=self.auth,
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["user_message"], job_run_service.MSG_KIND_MISMATCH)

    def test_run_match_rejects_async_wait(self):
        Project.objects.create(
            company=self.company,
            name="Conciliacion async",
            slug="conciliacion-async",
            owner=self.user,
            project_kind=Project.KIND_FILE_MATCH,
        )
        response = self.client.post(
            "/api/v1/jobs/run",
            data={
                "kind": "file_match",
                "project_slug": "conciliacion-async",
                "wait": "async",
                "file_a": SimpleUploadedFile("lado-a.csv", b"id\n1\n", content_type="text/csv"),
                "file_b": SimpleUploadedFile("lado-b.csv", b"id\n1\n", content_type="text/csv"),
            },
            headers=self.auth,
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["user_message"], job_run_service.MSG_MATCH_WAIT)

    @patch("apps.platform_api.services.job_run_service.detect_pattern_service.rerun_detection")
    @patch("apps.platform_api.services.job_run_service.sample_upload_service.upload_sample")
    def test_run_scout_sync_ok(self, mocked_upload, mocked_detect):
        Project.objects.create(
            company=self.company,
            name="Explorar nomina",
            slug="explorar-nomina",
            owner=self.user,
            project_kind=Project.KIND_STRUCTURE_SCOUT,
        )
        job_id = uuid.uuid4()
        sample_id = uuid.uuid4()
        state = SimpleNamespace(
            id=job_id,
            status="idle",
            STATUS_FAILED="failed",
            suggestions_snapshot={"file_type_code": "csv"},
            file_type_code="csv",
            encoding_code="utf-8",
            line_ending_code="lf",
            delimiter=",",
            has_header=True,
            header_row=1,
            confidence="high",
            notes="",
            sample_id=sample_id,
            sample=SimpleNamespace(
                original_filename="muestra.csv",
                content_hash="abc",
                size_bytes=12,
            ),
            created_at=None,
            updated_at=None,
            save=MagicMock(),
        )
        mocked_upload.return_value = OperationResult.success("ok", sample=state.sample)
        mocked_detect.return_value = OperationResult.success("ok", state=state)
        response = self.client.post(
            "/api/v1/jobs/run",
            data={
                "kind": "structure_scout",
                "project_slug": "explorar-nomina",
                "wait": "sync",
                "file": self._file(),
            },
            headers=self.auth,
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["kind"], "structure_scout")
        self.assertEqual(body["job_id"], str(job_id))
        self.assertEqual(body["user_message"], job_run_service.MSG_SCOUT_OK)
        self.assertEqual(body["summary"]["file_type_code"], "csv")
        self.assertTrue(body["ok"])
        mocked_upload.assert_called_once()
        self.assertFalse(mocked_upload.call_args.kwargs["require_membership"])
        mocked_detect.assert_called_once()
        self.assertFalse(mocked_detect.call_args.kwargs["require_membership"])

    def test_run_scout_rejects_gate_project(self):
        response = self.client.post(
            "/api/v1/jobs/run",
            data={
                "kind": "structure_scout",
                "project_slug": "nomina-mensual",
                "wait": "sync",
                "file": self._file(),
            },
            headers=self.auth,
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["user_message"], job_run_service.MSG_KIND_MISMATCH)

    def test_run_scout_rejects_async_wait(self):
        Project.objects.create(
            company=self.company,
            name="Explorar async",
            slug="explorar-async",
            owner=self.user,
            project_kind=Project.KIND_STRUCTURE_SCOUT,
        )
        response = self.client.post(
            "/api/v1/jobs/run",
            data={
                "kind": "structure_scout",
                "project_slug": "explorar-async",
                "wait": "async",
                "file": self._file(),
            },
            headers=self.auth,
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["user_message"], job_run_service.MSG_SCOUT_WAIT)

    @patch("apps.platform_api.services.job_run_service.clean_run_service.run_clean_job")
    def test_run_clean_sync_ok(self, mocked_run):
        Project.objects.create(
            company=self.company,
            name="Limpieza nomina",
            slug="limpieza-nomina",
            owner=self.user,
            project_kind=Project.KIND_FILE_CLEAN,
        )
        job_id = uuid.uuid4()
        job = SimpleNamespace(
            id=job_id,
            status="completed",
            STATUS_COMPLETED="completed",
            STATUS_PARTIAL="partial",
            STATUS_CANCELLED="cancelled",
            STATUS_FAILED="failed",
            STATUS_RUNNING="running",
            dry_run=False,
            error_message="",
            error_code="",
            report_path="",
            change_log_path="reports/clean.csv",
            output_stored_path="out/limpio.csv",
            input_content_hash="abc",
            input_suggestions={},
            metrics={
                "rows_read": 10,
                "rows_written": 9,
                "cells_changed": 4,
                "dedupe_count": 1,
            },
            version=SimpleNamespace(version_number=2),
            save=MagicMock(),
        )
        mocked_run.return_value = OperationResult.success("ok", job=job)
        response = self.client.post(
            "/api/v1/jobs/run",
            data={
                "kind": "file_clean",
                "project_slug": "limpieza-nomina",
                "wait": "sync",
                "file": self._file(),
            },
            headers=self.auth,
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["kind"], "file_clean")
        self.assertEqual(body["job_id"], str(job_id))
        self.assertEqual(body["user_message"], job_run_service.MSG_CLEAN_OK)
        self.assertEqual(body["summary"]["rows_read"], 10)
        self.assertTrue(body["ok"])
        mocked_run.assert_called_once()
        self.assertFalse(mocked_run.call_args.kwargs["require_membership"])
        self.assertFalse(mocked_run.call_args.kwargs["dry_run"])

    def test_run_clean_rejects_gate_project(self):
        response = self.client.post(
            "/api/v1/jobs/run",
            data={
                "kind": "file_clean",
                "project_slug": "nomina-mensual",
                "wait": "sync",
                "file": self._file(),
            },
            headers=self.auth,
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["user_message"], job_run_service.MSG_KIND_MISMATCH)

    def test_run_clean_rejects_async_wait(self):
        Project.objects.create(
            company=self.company,
            name="Limpieza async",
            slug="limpieza-async",
            owner=self.user,
            project_kind=Project.KIND_FILE_CLEAN,
        )
        response = self.client.post(
            "/api/v1/jobs/run",
            data={
                "kind": "file_clean",
                "project_slug": "limpieza-async",
                "wait": "async",
                "file": self._file(),
            },
            headers=self.auth,
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["user_message"], job_run_service.MSG_CLEAN_WAIT)

    def _sm_job(self, *, operation: str):
        job_id = uuid.uuid4()
        return SimpleNamespace(
            id=job_id,
            status="completed",
            STATUS_COMPLETED="completed",
            STATUS_PARTIAL="partial",
            STATUS_CANCELLED="cancelled",
            STATUS_FAILED="failed",
            STATUS_RUNNING="running",
            operation=operation,
            dry_run=False,
            error_message="",
            error_code="",
            report_path="",
            manifest_path="reports/manifest.json",
            output_stored_path="",
            inputs=[{"filename": "a.csv"}] if operation == "split" else [{"filename": "a.csv"}, {"filename": "b.csv"}],
            outputs=[{"stored_path": "out/part.csv"}] if operation == "split" else [{"stored_path": "out/merged.csv"}],
            metrics={"rows_read": 5},
            version=SimpleNamespace(version_number=1),
            save=MagicMock(),
        )

    @patch("apps.platform_api.services.job_run_service.sm_run_service.run_sm_job")
    def test_run_split_sync_ok(self, mocked_run):
        Project.objects.create(
            company=self.company,
            name="Partir nomina",
            slug="partir-nomina",
            owner=self.user,
            project_kind=Project.KIND_FILE_SPLIT_MERGE,
        )
        job = self._sm_job(operation="split")
        mocked_run.return_value = OperationResult.success("ok", job=job)
        response = self.client.post(
            "/api/v1/jobs/run",
            data={
                "kind": "file_split",
                "project_slug": "partir-nomina",
                "wait": "sync",
                "file": self._file(),
            },
            headers=self.auth,
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["kind"], "file_split")
        self.assertEqual(body["job_id"], str(job.id))
        self.assertEqual(body["user_message"], job_run_service.MSG_SPLIT_OK)
        self.assertEqual(body["summary"]["operation"], "split")
        self.assertTrue(body["ok"])
        self.assertEqual(mocked_run.call_args.kwargs["expected_operation"], "split")
        self.assertFalse(mocked_run.call_args.kwargs["require_membership"])

    @patch("apps.platform_api.services.job_run_service.sm_run_service.run_sm_job")
    def test_run_merge_sync_ok(self, mocked_run):
        Project.objects.create(
            company=self.company,
            name="Unir nomina",
            slug="unir-nomina",
            owner=self.user,
            project_kind=Project.KIND_FILE_SPLIT_MERGE,
        )
        job = self._sm_job(operation="merge")
        mocked_run.return_value = OperationResult.success("ok", job=job)
        response = self.client.post(
            "/api/v1/jobs/run",
            data={
                "kind": "file_merge",
                "project_slug": "unir-nomina",
                "wait": "sync",
                "files": [
                    SimpleUploadedFile("a.csv", b"id\n1\n", content_type="text/csv"),
                    SimpleUploadedFile("b.csv", b"id\n2\n", content_type="text/csv"),
                ],
            },
            headers=self.auth,
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["kind"], "file_merge")
        self.assertEqual(body["job_id"], str(job.id))
        self.assertEqual(body["user_message"], job_run_service.MSG_MERGE_OK)
        self.assertEqual(mocked_run.call_args.kwargs["expected_operation"], "merge")
        self.assertEqual(len(mocked_run.call_args.args[2]), 2)

    def test_run_split_rejects_gate_project(self):
        response = self.client.post(
            "/api/v1/jobs/run",
            data={
                "kind": "file_split",
                "project_slug": "nomina-mensual",
                "wait": "sync",
                "file": self._file(),
            },
            headers=self.auth,
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["user_message"], job_run_service.MSG_KIND_MISMATCH)

    def test_run_merge_rejects_async_wait(self):
        Project.objects.create(
            company=self.company,
            name="Unir async",
            slug="unir-async",
            owner=self.user,
            project_kind=Project.KIND_FILE_SPLIT_MERGE,
        )
        response = self.client.post(
            "/api/v1/jobs/run",
            data={
                "kind": "file_merge",
                "project_slug": "unir-async",
                "wait": "async",
                "files": [
                    SimpleUploadedFile("a.csv", b"id\n1\n", content_type="text/csv"),
                    SimpleUploadedFile("b.csv", b"id\n2\n", content_type="text/csv"),
                ],
            },
            headers=self.auth,
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["user_message"], job_run_service.MSG_SM_WAIT)

    @patch("apps.platform_api.services.job_run_service.validation_run_service.validate_and_run")
    def test_idempotency_replay_and_conflict(self, mocked_run):
        job_id = uuid.uuid4()
        job = SimpleNamespace(
            id=job_id,
            status="completed",
            STATUS_COMPLETED="completed",
            STATUS_PARTIAL="partial",
            STATUS_CANCELLED="cancelled",
            STATUS_FAILED="failed",
            STATUS_RUNNING="running",
            rows_read=1,
            rows_ok=1,
            rows_rejected=0,
            report_path="",
            output_stored_path="",
            input_content_hash="abc",
            input_suggestions={"gate_result": {"status": "passed", "issues_preview": []}},
            version=SimpleNamespace(version_number=1),
            save=MagicMock(),
        )
        mocked_run.return_value = OperationResult.success("ok", job=job)
        headers = {**self.auth, "Idempotency-Key": "run-once-001"}
        first = self.client.post(
            "/api/v1/jobs/run",
            data={
                "kind": "file_gate",
                "project_slug": "nomina-mensual",
                "wait": "sync",
                "file": self._file(),
            },
            headers=headers,
        )
        second = self.client.post(
            "/api/v1/jobs/run",
            data={
                "kind": "file_gate",
                "project_slug": "nomina-mensual",
                "wait": "sync",
                "file": self._file(),
            },
            headers=headers,
        )
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json()["job_id"], str(job_id))
        mocked_run.assert_called_once()
        conflict = self.client.post(
            "/api/v1/jobs/run",
            data={
                "kind": "file_gate",
                "project_slug": "nomina-mensual",
                "wait": "sync",
                "file": SimpleUploadedFile("otro.csv", b"id,name\n2,b\n", content_type="text/csv"),
            },
            headers=headers,
        )
        self.assertEqual(conflict.status_code, 409)

    @patch("apps.platform_api.services.job_run_service.validation_run_service.validate_and_run")
    def test_dry_run_and_retry_of(self, mocked_run):
        prior = uuid.uuid4()
        job_id = uuid.uuid4()
        job = SimpleNamespace(
            id=job_id,
            status="completed",
            STATUS_COMPLETED="completed",
            STATUS_PARTIAL="partial",
            STATUS_CANCELLED="cancelled",
            STATUS_FAILED="failed",
            STATUS_RUNNING="running",
            rows_read=2,
            rows_ok=2,
            rows_rejected=0,
            report_path="",
            output_stored_path="",
            input_content_hash="abc",
            input_suggestions={"gate_result": {"status": "passed", "issues_preview": []}},
            version=SimpleNamespace(version_number=1),
            save=MagicMock(),
        )
        mocked_run.return_value = OperationResult.success("ok", job=job)
        response = self.client.post(
            "/api/v1/jobs/run",
            data={
                "kind": "file_gate",
                "project_slug": "nomina-mensual",
                "wait": "sync",
                "dry_run": "true",
                "retry_of_job_id": str(prior),
                "file": self._file(),
            },
            headers={**self.auth, "Idempotency-Key": "retry-key-1"},
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["dry_run"])
        self.assertEqual(body["retry_of_job_id"], str(prior))


class PlatformApiJobsQueryTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            name_short="ACME",
            name_long="Acme Ops",
            is_active=True,
        )
        self.user = User.objects.create_user("ops4", password="x")
        UserProfile.objects.create(
            user=self.user,
            company=self.company,
            user_type=UserProfile.USER_SYSTEM,
            email_confirmed=True,
            tfa_verified=True,
            totp_secret="secret",
            status=UserProfile.STATUS_ACTIVE,
        )
        created = api_client_service.create_client(
            self.user,
            {
                "code": "client-query-01",
                "name": "ERP query",
                "description": "Cliente para consultar jobs. Dueño: Tesorería.",
                "environment": "sandbox",
                "scopes": [SCOPE_JOBS_RUN, SCOPE_JOBS_READ, SCOPE_ARTIFACTS_DOWNLOAD, SCOPE_JOBS_CANCEL],
            },
        )
        self.plaintext = created.payload["plaintext_key"]
        self.auth = {"Authorization": f"Bearer {self.plaintext}"}
        self.api_client = created.payload["client"]
        self.project = Project.objects.create(
            company=self.company,
            name="Nómina mensual",
            slug="nomina-query",
            owner=self.user,
            project_kind=Project.KIND_FILE_GATE,
        )
        from apps.dms.source_profile.models import DmsMappingVersion
        from apps.dms.file_intake.models import DmsExecutionJob
        from django.conf import settings

        self.version = DmsMappingVersion.objects.create(
            project=self.project,
            version_number=1,
            status=DmsMappingVersion.STATUS_PUBLISHED,
        )
        report_dir = Path(settings.MEDIA_ROOT) / "tests"
        report_dir.mkdir(parents=True, exist_ok=True)
        self.report_abs = report_dir / "gate_report.json"
        self.report_abs.write_text('{"ok": true}', encoding="utf-8")
        rel = str(self.report_abs.relative_to(Path(settings.MEDIA_ROOT))).replace("\\", "/")
        self.job = DmsExecutionJob.objects.create(
            project=self.project,
            version=self.version,
            job_type=DmsExecutionJob.JOB_FULL,
            status=DmsExecutionJob.STATUS_COMPLETED,
            input_original_filename="nomina.csv",
            input_content_hash="abc",
            report_path=rel,
            rows_read=10,
            rows_ok=10,
            rows_rejected=0,
            executed_by=self.user,
            input_suggestions={
                "trigger_source": "api",
                "api_client_id": str(self.api_client.pk),
                "gate_result": {"status": "passed", "issues_preview": []},
            },
        )

    def test_detail_and_list_and_report(self):
        detail = self.client.get(f"/api/v1/jobs/{self.job.id}", headers=self.auth)
        self.assertEqual(detail.status_code, 200)
        body = detail.json()
        self.assertEqual(body["job_id"], str(self.job.id))
        self.assertEqual(body["kind"], "file_gate")
        self.assertEqual(body["audit"]["trigger_source"], "api")
        self.assertEqual(body["audit"]["triggered_by_api_client_id"], str(self.api_client.pk))
        self.assertEqual(body["audit"]["job_id"], str(self.job.id))
        self.assertEqual(body["audit"]["input_hash"], "abc")
        self.assertIn("token=", body["artifacts"]["report_url"])
        listing = self.client.get("/api/v1/jobs", headers=self.auth)
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.json()["total"], 1)
        token = body["artifacts"]["report_url"].split("token=", 1)[1]
        report = self.client.get(f"/api/v1/jobs/{self.job.id}/report?token={token}")
        self.assertEqual(report.status_code, 200)
        self.assertEqual(b"".join(report.streaming_content), b'{"ok": true}')
        output = self.client.get(
            f"/api/v1/jobs/{self.job.id}/output",
            headers=self.auth,
        )
        self.assertEqual(output.status_code, 404)

    def test_other_company_is_opaque(self):
        other = Company.objects.create(name_short="OTROQ", name_long="Otro Q", is_active=True)
        other_user = User.objects.create_user("opsq", password="x")
        UserProfile.objects.create(
            user=other_user,
            company=other,
            user_type=UserProfile.USER_SYSTEM,
            email_confirmed=True,
            tfa_verified=True,
            totp_secret="secret",
            status=UserProfile.STATUS_ACTIVE,
        )
        created = api_client_service.create_client(
            other_user,
            {
                "code": "client-query-other",
                "name": "Otro",
                "description": "Cliente de otra compañía para aislamiento. Dueño: Tesorería.",
                "environment": "sandbox",
                "scopes": [SCOPE_JOBS_READ],
            },
        )
        headers = {"Authorization": f"Bearer {created.payload['plaintext_key']}"}
        response = self.client.get(f"/api/v1/jobs/{self.job.id}", headers=headers)
        self.assertEqual(response.status_code, 404)

    def test_cancel_queued_and_reject_completed(self):
        from apps.dms.file_intake.models import DmsExecutionJob

        queued = DmsExecutionJob.objects.create(
            project=self.project,
            version=self.version,
            job_type=DmsExecutionJob.JOB_FULL,
            status=DmsExecutionJob.STATUS_QUEUED,
            input_original_filename="lote.csv",
            executed_by=self.user,
            input_suggestions={"trigger_source": "api", "api_client_id": str(self.api_client.pk)},
        )
        cancelled = self.client.post(f"/api/v1/jobs/{queued.id}/cancel", headers=self.auth)
        self.assertEqual(cancelled.status_code, 200)
        self.assertEqual(cancelled.json()["status"], "cancelled")
        queued.refresh_from_db()
        self.assertEqual(queued.status, DmsExecutionJob.STATUS_CANCELLED)
        done = self.client.post(f"/api/v1/jobs/{self.job.id}/cancel", headers=self.auth)
        self.assertEqual(done.status_code, 409)

    def _ops_version(self, project):
        from apps.dms.source_profile.models import DmsMappingVersion

        return DmsMappingVersion.objects.create(
            project=project,
            version_number=1,
            status=DmsMappingVersion.STATUS_PUBLISHED,
        )

    def test_match_detail_report_and_kind_filter(self):
        from django.conf import settings
        from apps.file_match.models import FileMatchJob

        project = Project.objects.create(
            company=self.company,
            name="Conciliación nómina",
            slug="nomina-match-query",
            owner=self.user,
            project_kind=Project.KIND_FILE_MATCH,
        )
        version = self._ops_version(project)
        report_dir = Path(settings.MEDIA_ROOT) / "tests"
        report_dir.mkdir(parents=True, exist_ok=True)
        report_abs = report_dir / "match_report.json"
        report_abs.write_text('{"matched": 3}', encoding="utf-8")
        rel = str(report_abs.relative_to(Path(settings.MEDIA_ROOT))).replace("\\", "/")
        job = FileMatchJob.objects.create(
            project=project,
            published_version=version,
            published_version_number=1,
            status=FileMatchJob.STATUS_COMPLETED,
            verdict=FileMatchJob.VERDICT_PASSED,
            report_path=rel,
            executed_by=self.user,
            metrics={"api": {"trigger_source": "api", "api_client_id": str(self.api_client.pk)}},
        )
        detail = self.client.get(f"/api/v1/jobs/{job.id}", headers=self.auth)
        self.assertEqual(detail.status_code, 200)
        body = detail.json()
        self.assertEqual(body["kind"], "file_match")
        self.assertEqual(body["job_id"], str(job.id))
        self.assertEqual(body["audit"]["trigger_source"], "api")
        self.assertIn("token=", body["artifacts"]["report_url"])
        listing = self.client.get("/api/v1/jobs?kind=file_match", headers=self.auth)
        self.assertEqual(listing.status_code, 200)
        listed = listing.json()
        self.assertEqual(listed["total"], 1)
        self.assertEqual(listed["jobs"][0]["job_id"], str(job.id))
        token = body["artifacts"]["report_url"].split("token=", 1)[1]
        report = self.client.get(f"/api/v1/jobs/{job.id}/report?token={token}")
        self.assertEqual(report.status_code, 200)
        self.assertEqual(b"".join(report.streaming_content), b'{"matched": 3}')

    def test_clean_output_and_split_report(self):
        from django.conf import settings
        from apps.file_clean.models import CleanJob
        from apps.file_split_merge.models import SplitMergeJob

        media = Path(settings.MEDIA_ROOT) / "tests"
        media.mkdir(parents=True, exist_ok=True)
        out_abs = media / "clean_out.csv"
        out_abs.write_text("id,name\n1,a\n", encoding="utf-8")
        log_abs = media / "clean_log.json"
        log_abs.write_text('{"cells_changed": 1}', encoding="utf-8")
        man_abs = media / "split_manifest.json"
        man_abs.write_text('{"parts": 2}', encoding="utf-8")
        out_rel = str(out_abs.relative_to(Path(settings.MEDIA_ROOT))).replace("\\", "/")
        log_rel = str(log_abs.relative_to(Path(settings.MEDIA_ROOT))).replace("\\", "/")
        man_rel = str(man_abs.relative_to(Path(settings.MEDIA_ROOT))).replace("\\", "/")

        clean_project = Project.objects.create(
            company=self.company,
            name="Limpieza nómina",
            slug="nomina-clean-query",
            owner=self.user,
            project_kind=Project.KIND_FILE_CLEAN,
        )
        clean_job = CleanJob.objects.create(
            project=clean_project,
            published_version=self._ops_version(clean_project),
            published_version_number=1,
            status=CleanJob.STATUS_COMPLETED,
            change_log_path=log_rel,
            output_stored_path=out_rel,
            output_filename="clean_out.csv",
            executed_by=self.user,
            metrics={"api": {"trigger_source": "api", "api_client_id": str(self.api_client.pk)}},
        )
        clean_detail = self.client.get(f"/api/v1/jobs/{clean_job.id}", headers=self.auth)
        self.assertEqual(clean_detail.status_code, 200)
        self.assertEqual(clean_detail.json()["kind"], "file_clean")
        output = self.client.get(f"/api/v1/jobs/{clean_job.id}/output", headers=self.auth)
        self.assertEqual(output.status_code, 200)
        self.assertIn(b"1,a", b"".join(output.streaming_content))

        sm_project = Project.objects.create(
            company=self.company,
            name="Partición nómina",
            slug="nomina-split-query",
            owner=self.user,
            project_kind=Project.KIND_FILE_SPLIT_MERGE,
        )
        sm_job = SplitMergeJob.objects.create(
            project=sm_project,
            published_version=self._ops_version(sm_project),
            published_version_number=1,
            operation=SplitMergeJob.OPERATION_SPLIT,
            status=SplitMergeJob.STATUS_COMPLETED,
            manifest_path=man_rel,
            executed_by=self.user,
            metrics={"api": {"trigger_source": "api", "api_client_id": str(self.api_client.pk)}},
        )
        split_detail = self.client.get(f"/api/v1/jobs/{sm_job.id}", headers=self.auth)
        self.assertEqual(split_detail.status_code, 200)
        self.assertEqual(split_detail.json()["kind"], "file_split")
        token = split_detail.json()["artifacts"]["report_url"].split("token=", 1)[1]
        report = self.client.get(f"/api/v1/jobs/{sm_job.id}/report?token={token}")
        self.assertEqual(report.status_code, 200)
        self.assertEqual(b"".join(report.streaming_content), b'{"parts": 2}')

    def test_scout_detail_without_bytes_and_cancel_not_allowed(self):
        from apps.file_match.models import FileMatchJob
        from apps.structure_scout.models import ScoutDetectionState

        scout_project = Project.objects.create(
            company=self.company,
            name="Explorar muestra",
            slug="nomina-scout-query",
            owner=self.user,
            project_kind=Project.KIND_STRUCTURE_SCOUT,
        )
        state = ScoutDetectionState.objects.create(
            project=scout_project,
            status=ScoutDetectionState.STATUS_DRAFT_READY,
            file_type_code="csv",
            suggestions_snapshot={"api": {"trigger_source": "api", "api_client_id": str(self.api_client.pk)}},
        )
        detail = self.client.get(f"/api/v1/jobs/{state.id}", headers=self.auth)
        self.assertEqual(detail.status_code, 200)
        body = detail.json()
        self.assertEqual(body["kind"], "structure_scout")
        self.assertFalse(body["artifacts"])
        missing = self.client.get(f"/api/v1/jobs/{state.id}/report", headers=self.auth)
        self.assertEqual(missing.status_code, 404)

        match_project = Project.objects.create(
            company=self.company,
            name="Match cancel",
            slug="nomina-match-cancel",
            owner=self.user,
            project_kind=Project.KIND_FILE_MATCH,
        )
        match_job = FileMatchJob.objects.create(
            project=match_project,
            published_version=self._ops_version(match_project),
            published_version_number=1,
            status=FileMatchJob.STATUS_COMPLETED,
            verdict=FileMatchJob.VERDICT_PASSED,
            executed_by=self.user,
        )
        cancelled = self.client.post(f"/api/v1/jobs/{match_job.id}/cancel", headers=self.auth)
        self.assertEqual(cancelled.status_code, 409)


class PlatformApiPipelineTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            name_short="ACME",
            name_long="Acme Ops",
            is_active=True,
        )
        self.user = User.objects.create_user("ops5", password="x")
        UserProfile.objects.create(
            user=self.user,
            company=self.company,
            user_type=UserProfile.USER_SYSTEM,
            email_confirmed=True,
            tfa_verified=True,
            totp_secret="secret",
            status=UserProfile.STATUS_ACTIVE,
        )
        created = api_client_service.create_client(
            self.user,
            {
                "code": "client-pipe-01",
                "name": "ERP pipeline",
                "description": "Cliente para disparar pipelines. Dueño: Tesorería.",
                "environment": "sandbox",
                "scopes": [SCOPE_PIPELINE_RUN, SCOPE_JOBS_READ],
            },
        )
        self.plaintext = created.payload["plaintext_key"]
        self.auth = {"Authorization": f"Bearer {self.plaintext}"}
        self.api_client = created.payload["client"]
        from apps.file_pipeline.models import PipelineDefinition

        self.pipeline = PipelineDefinition.objects.create(
            company=self.company,
            name="Nómina diaria",
            slug="nomina-diaria",
            owner=self.user,
            status=PipelineDefinition.STATUS_ACTIVE,
        )

    def _file(self):
        return SimpleUploadedFile("nomina.csv", b"id,name\n1,a\n", content_type="text/csv")

    def _run(self, status="completed"):
        run_id = uuid.uuid4()
        step = SimpleNamespace(
            order=1,
            kind="file_gate",
            label="Gate",
            status="completed",
            project_slug="nomina-mensual",
            app_job_id=str(uuid.uuid4()),
            user_message="ok",
        )
        return SimpleNamespace(
            id=run_id,
            status=status,
            STATUS_COMPLETED="completed",
            STATUS_PARTIAL="partial",
            STATUS_CANCELLED="cancelled",
            STATUS_FAILED="failed",
            STATUS_RUNNING="running",
            dry_run=False,
            error_message="",
            failed_step_order=None,
            duration_ms=12,
            input_sha256="abc",
            trigger_source="api",
            pipeline=SimpleNamespace(slug="nomina-diaria"),
            version=SimpleNamespace(version_number=2),
            steps=SimpleNamespace(all=lambda: [step]),
            report_path="",
            output_stored_path="",
        )

    @patch("apps.platform_api.services.job_run_service.pipeline_run_service.start_run")
    def test_run_pipeline_delegates_to_orchestrator(self, mocked_start):
        run = self._run()
        mocked_start.return_value = OperationResult.success("ok", run=run)
        response = self.client.post(
            "/api/v1/jobs/run",
            data={
                "kind": "file_pipeline",
                "pipeline_id": "nomina-diaria",
                "wait": "async",
                "file": self._file(),
            },
            headers=self.auth,
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["kind"], "file_pipeline")
        self.assertEqual(body["pipeline_id"], "nomina-diaria")
        self.assertEqual(body["pipeline_run_id"], str(run.id))
        self.assertEqual(len(body["steps"]), 1)
        self.assertEqual(body["audit"]["trigger_source"], "api")
        self.assertEqual(body["steps"][0]["app_job_id"], body["steps"][0]["job_id"])
        mocked_start.assert_called_once()
        kwargs = mocked_start.call_args.kwargs
        self.assertFalse(kwargs["require_membership"])
        self.assertEqual(kwargs["trigger_source"], "api")
        self.assertEqual(kwargs["api_client_id"], str(self.api_client.pk))

    @patch("apps.platform_api.services.job_run_service.pipeline_run_service.start_run")
    def test_shortcut_pipeline_runs_url(self, mocked_start):
        run = self._run()
        mocked_start.return_value = OperationResult.success("ok", run=run)
        response = self.client.post(
            "/api/v1/pipelines/nomina-diaria/runs",
            data={"file": self._file()},
            headers=self.auth,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["kind"], "file_pipeline")

    def test_pipeline_missing_scope_is_403(self):
        created = api_client_service.create_client(
            self.user,
            {
                "code": "client-pipe-noscope",
                "name": "Sin pipeline",
                "description": "Cliente sin scope de pipeline. Dueño: Tesorería.",
                "environment": "sandbox",
                "scopes": [SCOPE_JOBS_READ],
            },
        )
        headers = {"Authorization": f"Bearer {created.payload['plaintext_key']}"}
        response = self.client.post(
            "/api/v1/jobs/run",
            data={
                "kind": "file_pipeline",
                "pipeline_id": "nomina-diaria",
                "file": self._file(),
            },
            headers=headers,
        )
        self.assertEqual(response.status_code, 403)

    @patch("apps.platform_api.services.job_run_service.pipeline_run_service.start_run")
    def test_pipeline_unpublished_is_409(self, mocked_start):
        from apps.file_pipeline.services.pipeline_run_service import MSG_NO_VERSION

        mocked_start.return_value = OperationResult.failure("validation_form", MSG_NO_VERSION)
        response = self.client.post(
            "/api/v1/jobs/run",
            data={
                "kind": "file_pipeline",
                "pipeline_id": "nomina-diaria",
                "file": self._file(),
            },
            headers=self.auth,
        )
        self.assertEqual(response.status_code, 409)


class PlatformApiWebhookTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            name_short="ACME",
            name_long="Acme Ops",
            is_active=True,
        )
        self.user = User.objects.create_user("opswh", password="x")
        UserProfile.objects.create(
            user=self.user,
            company=self.company,
            user_type=UserProfile.USER_SYSTEM,
            email_confirmed=True,
            tfa_verified=True,
            totp_secret="secret",
            status=UserProfile.STATUS_ACTIVE,
        )
        created = api_client_service.create_client(
            self.user,
            {
                "code": "client-wh-01",
                "name": "ERP webhook",
                "description": "Cliente para callbacks HMAC. Dueño: Tesorería.",
                "environment": "sandbox",
                "scopes": [SCOPE_JOBS_RUN, SCOPE_JOBS_READ],
            },
        )
        self.api_client = created.payload["client"]
        process_security_service.update_policy(
            self.user,
            {
                "max_upload_mb": "50",
                "rate_per_minute": "60",
                "artifact_ttl_hours": "24",
                "allowed_extensions": [".csv"],
                "webhook_host_allowlist": ["hooks.banco.example"],
            },
        )

    def test_hmac_and_https_allowlist(self):
        body = b'{"ok":true}'
        header = webhook_service.sign_payload("s3cret", body)
        self.assertTrue(webhook_service.signatures_match("s3cret", body, header))
        self.assertFalse(webhook_service.signatures_match("other", body, header))
        bad = webhook_service.update_webhook(
            self.user,
            self.api_client,
            {
                "webhook_url": "http://hooks.banco.example/cb",
                "webhook_enabled": True,
                "webhook_events": ["job.completed"],
                "rotate_secret": True,
            },
        )
        self.assertFalse(bad.ok)
        self.assertIn("webhook_url", bad.errors)

    @patch("apps.platform_api.services.webhook_service.urlopen")
    def test_notify_posts_signed_payload_without_file_bytes(self, mocked_open):
        mocked_open.return_value.__enter__.return_value.status = 200
        saved = webhook_service.update_webhook(
            self.user,
            self.api_client,
            {
                "webhook_url": "https://hooks.banco.example/jobs",
                "webhook_enabled": True,
                "webhook_events": ["job.completed", "job.failed", "job.cancelled"],
                "rotate_secret": True,
            },
        )
        self.assertTrue(saved.ok)
        self.api_client.refresh_from_db()
        envelope = {
            "job_id": str(uuid.uuid4()),
            "kind": "file_gate",
            "status": "completed",
            "ok": True,
            "correlation_id": "corr-1",
            "artifacts": {"report_url": "/api/v1/jobs/x/report"},
            "audit": {"correlation_id": "corr-1"},
        }
        delivery = webhook_service.notify_from_envelope(self.api_client, envelope)
        self.assertIsNotNone(delivery)
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, "delivered")
        self.assertNotIn("file", delivery.payload)
        self.assertNotIn("cells", delivery.payload)
        self.assertEqual(delivery.payload["event"], "job.completed")
        request = mocked_open.call_args[0][0]
        self.assertEqual(request.get_method(), "POST")
        self.assertTrue(request.headers.get("X-platform-signature") or request.headers.get("X-Platform-Signature"))

    @patch("apps.platform_api.services.webhook_service.urlopen")
    def test_retry_backoff_is_finite(self, mocked_open):
        mocked_open.side_effect = OSError("down")
        webhook_service.update_webhook(
            self.user,
            self.api_client,
            {
                "webhook_url": "https://hooks.banco.example/jobs",
                "webhook_enabled": True,
                "webhook_events": ["job.failed"],
                "rotate_secret": True,
            },
        )
        self.api_client.refresh_from_db()
        delivery = webhook_service.notify_from_envelope(
            self.api_client,
            {
                "job_id": str(uuid.uuid4()),
                "kind": "file_gate",
                "status": "failed",
                "ok": False,
            },
        )
        self.assertEqual(delivery.status, "pending")
        self.assertEqual(delivery.attempt_count, 1)
        self.assertIsNotNone(delivery.next_retry_at)
        for _ in range(6):
            delivery.next_retry_at = delivery.next_retry_at
            from django.utils import timezone

            delivery.next_retry_at = timezone.now()
            delivery.save(update_fields=["next_retry_at"])
            webhook_service.process_due_retries(limit=5)
            delivery.refresh_from_db()
        self.assertEqual(delivery.status, "failed")
        self.assertLessEqual(delivery.attempt_count, delivery.max_attempts)

