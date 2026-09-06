from django.contrib.auth.models import User
from django.test import TestCase

from apps.accounts.models import UserProfile
from apps.company.models import Company
from apps.file_watch.models import Watch, WatchBatch, WatchMembership
from apps.file_watch.services import watch_claim
from apps.file_watch.services import watch_fire as fire_svc
from apps.file_watch.services import watch_intake as intake_svc
from apps.file_watch.services import watch_lifecycle_service as svc
from apps.file_watch.services import watch_route as route_svc
from apps.file_watch.services import watch_source as source_svc


class WatchLifecycleTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            name_short="ACME",
            name_long="Acme Ops",
            is_active=True,
        )
        self.us = User.objects.create_user("ops-watch", password="x")
        UserProfile.objects.create(
            user=self.us,
            company=self.company,
            user_type=UserProfile.USER_SYSTEM,
            email_confirmed=True,
            tfa_verified=True,
            totp_secret="secret",
            status=UserProfile.STATUS_ACTIVE,
        )

    def _posted(self, **extra):
        data = {
            "name": "Extracto SFTP",
            "slug": "extracto-sftp",
            "description": "Bandeja de prueba",
            "visibility": Watch.VISIBILITY_MEMBERS_ONLY,
        }
        data.update(extra)
        return data

    def test_unique_slug_per_company(self):
        self.assertTrue(svc.create_watch(self.us, self._posted()).ok)
        result = svc.create_watch(self.us, self._posted(name="Otro"))
        self.assertFalse(result.ok)
        self.assertIn(result.error_code, {"watch_slug_taken", "validation_form"})
        self.assertIn("slug", result.errors or {})
        self.assertEqual(Watch.objects.filter(company=self.company).count(), 1)

    def test_fire_on_arrival_defer_conflict(self):
        watch = svc.create_watch(self.us, self._posted()).payload["watch"]
        route_svc.save_route(
            self.us,
            watch,
            {"route_mode": "defer", "kind": "", "project_id": "", "pipeline_id": ""},
        )
        watch.refresh_from_db()
        result = fire_svc.save_fire(self.us, watch, {"fire_mode": "on_arrival"})
        self.assertFalse(result.ok)
        self.assertEqual(result.error_code, "watch_fire_route_conflict")


class WatchClaimTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            name_short="ACME",
            name_long="Acme Ops",
            is_active=True,
        )
        self.us = User.objects.create_user("ops-claim", password="x")
        UserProfile.objects.create(
            user=self.us,
            company=self.company,
            user_type=UserProfile.USER_SYSTEM,
            email_confirmed=True,
            tfa_verified=True,
            totp_secret="secret",
            status=UserProfile.STATUS_ACTIVE,
        )
        from django.utils import timezone

        now = timezone.now()
        self.watch = Watch.objects.create(
            company=self.company,
            name="Bandeja claim",
            slug="bandeja-claim",
            owner=self.us,
            status=Watch.STATUS_ACTIVE,
            pending_pick_policy=Watch.PICK_FIFO,
            source_kind=Watch.SOURCE_API_PUSH,
            source_saved_at=now,
            fire_mode=Watch.FIRE_PENDING_ONLY,
            fire_saved_at=now,
            route_mode=Watch.ROUTE_DEFER,
            route_saved_at=now,
        )
        WatchMembership.objects.create(
            watch=self.watch,
            user=self.us,
            role=WatchMembership.ROLE_PA,
            is_active=True,
        )

    def test_claim_pending_batch_fifo(self):
        older = WatchBatch.objects.create(
            company=self.company,
            watch=self.watch,
            original_filename="a.txt",
            content_hash="a" * 64,
            storage_key="watches/x/a.txt",
            status=WatchBatch.STATUS_PENDING,
        )
        newer = WatchBatch.objects.create(
            company=self.company,
            watch=self.watch,
            original_filename="b.txt",
            content_hash="b" * 64,
            storage_key="watches/x/b.txt",
            status=WatchBatch.STATUS_PENDING,
        )
        claimed = watch_claim.claim_pending_batch(
            self.company,
            self.watch.slug,
            pick_policy=Watch.PICK_FIFO,
            schedule_slug="plan-nocturno",
        )
        self.assertIsNotNone(claimed)
        self.assertEqual(claimed.id, older.id)
        claimed.refresh_from_db()
        self.assertEqual(claimed.status, WatchBatch.STATUS_CONSUMED)
        self.assertEqual(claimed.consumed_by, "schedule:plan-nocturno")
        newer.refresh_from_db()
        self.assertEqual(newer.status, WatchBatch.STATUS_PENDING)

    def test_ingest_hash(self):
        from django.utils import timezone

        self.watch.status = Watch.STATUS_ACTIVE
        self.watch.source_kind = Watch.SOURCE_API_PUSH
        self.watch.source_saved_at = timezone.now()
        self.watch.fire_mode = Watch.FIRE_PENDING_ONLY
        self.watch.fire_saved_at = timezone.now()
        self.watch.save()
        data = b"hello-watch-batch"
        result = intake_svc.ingest_bytes(
            self.watch, "hello.txt", data, source_kind=Watch.SOURCE_API_PUSH
        )
        self.assertTrue(result.ok, result.user_message)
        batch = result.payload["batch"]
        self.assertEqual(len(batch.content_hash), 64)
        self.assertEqual(batch.status, WatchBatch.STATUS_PENDING)
        self.assertTrue(batch.storage_key)
