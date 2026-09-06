from django.contrib.auth.models import User
from django.test import TestCase

from apps.accounts.models import UserProfile
from apps.company.models import Company
from apps.file_scheduler.models import Schedule, ScheduleAuditEvent, ScheduleMembership
from apps.file_scheduler.services import schedule_lifecycle_service as svc


class ScheduleLifecycleTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            name_short="ACME",
            name_long="Acme Ops",
            is_active=True,
        )
        self.us = User.objects.create_user("ops", password="x")
        UserProfile.objects.create(
            user=self.us,
            company=self.company,
            user_type=UserProfile.USER_SYSTEM,
            email_confirmed=True,
            tfa_verified=True,
            totp_secret="secret",
            status=UserProfile.STATUS_ACTIVE,
        )
        self.uf = User.objects.create_user("ana", password="x")
        UserProfile.objects.create(
            user=self.uf,
            company=self.company,
            user_type=UserProfile.USER_FINAL,
            email_confirmed=True,
            tfa_verified=True,
            totp_secret="secret",
            status=UserProfile.STATUS_ACTIVE,
        )

    def _posted(self, **extra):
        data = {
            "name": "Cierre de nómina",
            "slug": "nomina-cierre",
            "description": "Plan de cierre",
            "visibility": Schedule.VISIBILITY_MEMBERS_ONLY,
        }
        data.update(extra)
        return data

    def test_uf_cannot_create(self):
        result = svc.create_schedule(self.uf, self._posted())
        self.assertFalse(result.ok)
        self.assertEqual(result.error_code, "schedule_forbidden")
        self.assertEqual(Schedule.objects.count(), 0)

    def test_hub_stepper_next_active_rest_pending(self):
        schedule = svc.create_schedule(self.us, self._posted()).payload["schedule"]
        hub = svc.get_hub_context(self.us, schedule)
        self.assertEqual(hub["cron_step_class"], "is-active")
        self.assertEqual(hub["target_step_class"], "is-pending")
        self.assertEqual(hub["overlap_step_class"], "is-pending")
        self.assertEqual(hub["dependency_step_class"], "is-pending")
        self.assertEqual(hub["notify_step_class"], "is-pending")
        self.assertEqual(hub["activity_step_class"], "is-pending")
        self.assertEqual(hub["audit_step_class"], "is-pending")
        self.assertEqual(hub["members_step_class"], "is-pending")

    def test_us_creates_as_pa_in_progress(self):
        result = svc.create_schedule(self.us, self._posted())
        self.assertTrue(result.ok, result.user_message)
        schedule = result.payload["schedule"]
        self.assertEqual(schedule.status, Schedule.STATUS_IN_PROGRESS)
        membership = ScheduleMembership.objects.get(schedule=schedule, user=self.us)
        self.assertEqual(membership.role, ScheduleMembership.ROLE_PA)
        self.assertTrue(
            ScheduleAuditEvent.objects.filter(
                schedule=schedule, event=ScheduleAuditEvent.EVENT_CREATED
            ).exists()
        )

    def test_duplicate_slug(self):
        self.assertTrue(svc.create_schedule(self.us, self._posted()).ok)
        result = svc.create_schedule(self.us, self._posted(name="Otro"))
        self.assertFalse(result.ok)
        self.assertIn("slug", result.errors or {})

    def test_resume_blocked_without_m2_m3(self):
        schedule = svc.create_schedule(self.us, self._posted()).payload["schedule"]
        schedule.status = Schedule.STATUS_INACTIVE
        schedule.save(update_fields=["status"])
        result = svc.resume_schedule(self.us, schedule)
        self.assertFalse(result.ok)
        self.assertEqual(result.error_code, "schedule_incomplete")

    def test_save_daily_programming(self):
        schedule = svc.create_schedule(self.us, self._posted()).payload["schedule"]
        result = svc.save_programming(
            self.us,
            schedule,
            {
                "schedule_kind": "daily",
                "time_local": "02:30",
                "timezone": "America/Caracas",
                "day_of_week": "",
                "monthly_mode": "",
                "day_of_month": "",
                "cron_expr": "",
            },
        )
        self.assertTrue(result.ok, result.user_message)
        schedule.refresh_from_db()
        self.assertTrue(schedule.programming_complete)
        self.assertEqual(schedule.cron_expr, "30 2 * * *")
        self.assertEqual(schedule.status, Schedule.STATUS_IN_PROGRESS)
        hub = svc.get_hub_context(self.us, schedule)
        self.assertEqual(hub["cron_step_class"], "is-done")
        self.assertEqual(hub["target_step_class"], "is-active")
        self.assertEqual(hub["dependency_step_class"], "is-pending")
        self.assertFalse(hub["dependency_complete"])

    def test_invalid_cron_rejected(self):
        schedule = svc.create_schedule(self.us, self._posted()).payload["schedule"]
        result = svc.save_programming(
            self.us,
            schedule,
            {
                "schedule_kind": "cron",
                "time_local": "",
                "timezone": "America/Caracas",
                "cron_expr": "bad",
            },
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.error_code, "schedule_cron_invalid")
        self.assertIn("cron_expr", result.errors or {})
        self.assertFalse(schedule.programming_complete)

    def test_ge_cannot_save_cron(self):
        schedule = svc.create_schedule(self.us, self._posted()).payload["schedule"]
        ScheduleMembership.objects.create(
            schedule=schedule,
            user=self.uf,
            role=ScheduleMembership.ROLE_GE,
            is_active=True,
        )
        result = svc.save_programming(
            self.uf,
            schedule,
            {
                "schedule_kind": "daily",
                "time_local": "06:00",
                "timezone": "America/Caracas",
            },
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.error_code, "schedule_forbidden")
        schedule.refresh_from_db()
        self.assertIsNone(schedule.programming_saved_at)

    def test_archive(self):
        schedule = svc.create_schedule(self.us, self._posted()).payload["schedule"]
        result = svc.archive_schedule(self.us, schedule)
        self.assertTrue(result.ok)
        schedule.refresh_from_db()
        self.assertEqual(schedule.status, Schedule.STATUS_ARCHIVED)
        self.assertTrue(
            ScheduleAuditEvent.objects.filter(
                schedule=schedule, event=ScheduleAuditEvent.EVENT_ARCHIVED
            ).exists()
        )

    def test_list_row_exposes_edit_members_archive(self):
        schedule = svc.create_schedule(self.us, self._posted()).payload["schedule"]
        rows, _stats = svc.list_with_stats(self.us)
        row = next(r for r in rows if r["schedule"].pk == schedule.pk)
        self.assertTrue(row["can_edit"])
        self.assertTrue(row["can_manage_members"])
        self.assertTrue(row["can_archive"])
        self.assertFalse(row["can_pause"])
        self.assertFalse(row["can_resume"])


class ScheduleTargetTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            name_short="ACME",
            name_long="Acme Ops",
            is_active=True,
        )
        self.us = User.objects.create_user("ops", password="x")
        UserProfile.objects.create(
            user=self.us,
            company=self.company,
            user_type=UserProfile.USER_SYSTEM,
            email_confirmed=True,
            tfa_verified=True,
            totp_secret="secret",
            status=UserProfile.STATUS_ACTIVE,
        )
        self.uf = User.objects.create_user("ana", password="x")
        UserProfile.objects.create(
            user=self.uf,
            company=self.company,
            user_type=UserProfile.USER_FINAL,
            email_confirmed=True,
            tfa_verified=True,
            totp_secret="secret",
            status=UserProfile.STATUS_ACTIVE,
        )

    def _schedule(self):
        return svc.create_schedule(
            self.us,
            {
                "name": "Cierre",
                "slug": "cierre-m3",
                "description": "",
                "visibility": Schedule.VISIBILITY_MEMBERS_ONLY,
            },
        ).payload["schedule"]

    def _published_gate(self):
        from apps.dms.mapping.models import DmsProjectConfig
        from apps.dms.source_profile.models import DmsMappingVersion
        from apps.projects.models import Project

        project = Project.objects.create(
            company=self.company,
            name="Gate",
            slug="gate-pub",
            owner=self.us,
            project_kind=Project.KIND_FILE_GATE,
        )
        version = DmsMappingVersion.objects.create(
            project=project,
            version_number=1,
            status=DmsMappingVersion.STATUS_PUBLISHED,
        )
        DmsProjectConfig.objects.create(project=project, current_version=version)
        return project

    def _unpublished_gate(self):
        from apps.projects.models import Project

        return Project.objects.create(
            company=self.company,
            name="Gate draft",
            slug="gate-draft",
            owner=self.us,
            project_kind=Project.KIND_FILE_GATE,
        )

    def _pipeline(self, *, active=True, published=True):
        from apps.file_pipeline.models import PipelineDefinition, PipelineVersion

        pipeline = PipelineDefinition.objects.create(
            company=self.company,
            name="Cadena",
            slug="cadena-1",
            owner=self.us,
            status=(
                PipelineDefinition.STATUS_ACTIVE
                if active
                else PipelineDefinition.STATUS_IN_PROGRESS
            ),
        )
        if published:
            version = PipelineVersion.objects.create(
                pipeline=pipeline,
                version_number=1,
                status=PipelineVersion.STATUS_PUBLISHED,
            )
            pipeline.current_version = version
            pipeline.save(update_fields=["current_version"])
        return pipeline

    def _job_data(self, project, **extra):
        data = {
            "target_mode": "job",
            "kind": "file_gate",
            "project_id": str(project.id),
            "pipeline_id": "",
            "input_origin": "watch",
            "watch_id": "watch-nomina",
            "artifact_ref": "",
            "pipeline_inputs_resolved": "",
        }
        data.update(extra)
        return data

    def test_ge_cannot_save_target(self):
        schedule = self._schedule()
        project = self._published_gate()
        ScheduleMembership.objects.create(
            schedule=schedule,
            user=self.uf,
            role=ScheduleMembership.ROLE_GE,
            is_active=True,
        )
        result = svc.save_target(self.uf, schedule, self._job_data(project))
        self.assertFalse(result.ok)
        self.assertEqual(result.error_code, "schedule_forbidden")
        schedule.refresh_from_db()
        self.assertIsNone(schedule.target_saved_at)

    def test_job_none_rejected(self):
        schedule = self._schedule()
        project = self._published_gate()
        result = svc.save_target(
            self.us,
            schedule,
            self._job_data(project, input_origin="none", watch_id=""),
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.error_code, "schedule_missing_input")

    def test_unpublished_project_rejected(self):
        schedule = self._schedule()
        project = self._unpublished_gate()
        result = svc.save_target(self.us, schedule, self._job_data(project))
        self.assertFalse(result.ok)
        self.assertEqual(result.error_code, "schedule_no_published_target")

    def test_pipeline_without_published_rejected(self):
        schedule = self._schedule()
        pipeline = self._pipeline(active=True, published=False)
        result = svc.save_target(
            self.us,
            schedule,
            {
                "target_mode": "pipeline",
                "kind": "",
                "project_id": "",
                "pipeline_id": str(pipeline.id),
                "input_origin": "watch",
                "watch_id": "w1",
                "artifact_ref": "",
                "pipeline_inputs_resolved": "",
            },
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.error_code, "schedule_no_published_target")

    def test_pipeline_none_without_confirm(self):
        schedule = self._schedule()
        pipeline = self._pipeline()
        result = svc.save_target(
            self.us,
            schedule,
            {
                "target_mode": "pipeline",
                "kind": "",
                "project_id": "",
                "pipeline_id": str(pipeline.id),
                "input_origin": "none",
                "watch_id": "",
                "artifact_ref": "",
                "pipeline_inputs_resolved": "",
            },
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.error_code, "schedule_missing_input")

    def test_save_job_watch_does_not_activate(self):
        schedule = self._schedule()
        project = self._published_gate()
        result = svc.save_target(self.us, schedule, self._job_data(project))
        self.assertTrue(result.ok, result.user_message)
        schedule.refresh_from_db()
        self.assertTrue(schedule.target_complete)
        self.assertEqual(schedule.status, Schedule.STATUS_IN_PROGRESS)
        self.assertEqual(schedule.target_kind, "file_gate")
        self.assertEqual(schedule.published_version_number, 1)

    def test_activate_requires_m2_and_m3(self):
        schedule = self._schedule()
        project = self._published_gate()
        self.assertFalse(svc.activate_schedule(self.us, schedule).ok)
        svc.save_target(self.us, schedule, self._job_data(project))
        self.assertFalse(svc.activate_schedule(self.us, schedule).ok)
        svc.save_programming(
            self.us,
            schedule,
            {
                "schedule_kind": "daily",
                "time_local": "02:30",
                "timezone": "America/Caracas",
                "day_of_week": "",
                "monthly_mode": "",
                "day_of_month": "",
                "cron_expr": "",
            },
        )
        result = svc.activate_schedule(self.us, schedule)
        self.assertTrue(result.ok, result.user_message)
        schedule.refresh_from_db()
        self.assertEqual(schedule.status, Schedule.STATUS_ACTIVE)


class ScheduleTickTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            name_short="ACME",
            name_long="Acme Ops",
            is_active=True,
        )
        self.us = User.objects.create_user("ops-tick", password="x")
        UserProfile.objects.create(
            user=self.us,
            company=self.company,
            user_type=UserProfile.USER_SYSTEM,
            email_confirmed=True,
            tfa_verified=True,
            totp_secret="secret",
            status=UserProfile.STATUS_ACTIVE,
        )

    def _ready_pipeline_plan(self):
        from apps.file_pipeline.models import PipelineDefinition, PipelineVersion
        from apps.file_scheduler.models import ScheduleTick
        from apps.file_scheduler.services import schedule_tick as tick_svc

        self.ScheduleTick = ScheduleTick
        self.tick_svc = tick_svc
        schedule = svc.create_schedule(
            self.us,
            {
                "name": "Tick plan",
                "slug": "tick-plan",
                "description": "",
                "visibility": Schedule.VISIBILITY_MEMBERS_ONLY,
            },
        ).payload["schedule"]
        pipeline = PipelineDefinition.objects.create(
            company=self.company,
            name="Cadena tick",
            slug="cadena-tick",
            owner=self.us,
            status=PipelineDefinition.STATUS_ACTIVE,
        )
        version = PipelineVersion.objects.create(
            pipeline=pipeline,
            version_number=1,
            status=PipelineVersion.STATUS_PUBLISHED,
        )
        pipeline.current_version = version
        pipeline.save(update_fields=["current_version"])
        svc.save_programming(
            self.us,
            schedule,
            {
                "schedule_kind": "daily",
                "time_local": "02:30",
                "timezone": "America/Caracas",
                "day_of_week": "",
                "monthly_mode": "",
                "day_of_month": "",
                "cron_expr": "",
            },
        )
        svc.save_target(
            self.us,
            schedule,
            {
                "target_mode": "pipeline",
                "kind": "",
                "project_id": "",
                "pipeline_id": str(pipeline.id),
                "input_origin": "none",
                "watch_id": "",
                "artifact_ref": "",
                "pipeline_inputs_resolved": "1",
            },
        )
        svc.activate_schedule(self.us, schedule)
        schedule.refresh_from_db()
        return schedule, pipeline

    def _now_due(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo

        return datetime(2026, 9, 1, 2, 35, tzinfo=ZoneInfo("America/Caracas"))

    def test_inactive_not_fired(self):
        from apps.file_scheduler.services import schedule_tick as tick_svc

        schedule = svc.create_schedule(
            self.us,
            {
                "name": "No",
                "slug": "no-tick",
                "description": "",
                "visibility": Schedule.VISIBILITY_MEMBERS_ONLY,
            },
        ).payload["schedule"]
        self.assertIsNone(
            tick_svc.process_schedule_slot(schedule, now=self._now_due())
        )

    def test_pipeline_none_enqueues_once(self):
        from apps.file_pipeline.models import PipelineRun
        from apps.file_scheduler.models import ScheduleTick
        from apps.file_scheduler.services import schedule_tick as tick_svc

        schedule, pipeline = self._ready_pipeline_plan()
        now = self._now_due()
        tick = tick_svc.process_schedule_slot(schedule, now=now)
        self.assertIsNotNone(tick)
        self.assertEqual(tick.status, ScheduleTick.STATUS_ENQUEUED)
        self.assertTrue(tick.pipeline_run_id)
        run = PipelineRun.objects.get(pk=tick.pipeline_run_id)
        self.assertEqual(run.trigger_source, PipelineRun.TRIGGER_SCHEDULER)
        self.assertEqual(run.schedule_id, str(schedule.id))
        self.assertEqual(run.pipeline_id, pipeline.id)
        again = tick_svc.process_schedule_slot(schedule, now=now)
        self.assertIsNone(again)
        self.assertEqual(ScheduleTick.objects.filter(schedule=schedule).count(), 1)

    def test_watch_missing_input(self):
        from apps.dms.mapping.models import DmsProjectConfig
        from apps.dms.source_profile.models import DmsMappingVersion
        from apps.file_scheduler.models import ScheduleTick
        from apps.file_scheduler.services import schedule_tick as tick_svc
        from apps.projects.models import Project

        schedule = svc.create_schedule(
            self.us,
            {
                "name": "Watch",
                "slug": "tick-watch",
                "description": "",
                "visibility": Schedule.VISIBILITY_MEMBERS_ONLY,
            },
        ).payload["schedule"]
        project = Project.objects.create(
            company=self.company,
            name="Gate",
            slug="gate-tick",
            owner=self.us,
            project_kind=Project.KIND_FILE_GATE,
        )
        version = DmsMappingVersion.objects.create(
            project=project,
            version_number=1,
            status=DmsMappingVersion.STATUS_PUBLISHED,
        )
        DmsProjectConfig.objects.create(project=project, current_version=version)
        svc.save_programming(
            self.us,
            schedule,
            {
                "schedule_kind": "daily",
                "time_local": "02:30",
                "timezone": "America/Caracas",
                "day_of_week": "",
                "monthly_mode": "",
                "day_of_month": "",
                "cron_expr": "",
            },
        )
        svc.save_target(
            self.us,
            schedule,
            {
                "target_mode": "job",
                "kind": "file_gate",
                "project_id": str(project.id),
                "pipeline_id": "",
                "input_origin": "watch",
                "watch_id": "watch-1",
                "artifact_ref": "",
                "pipeline_inputs_resolved": "",
            },
        )
        svc.activate_schedule(self.us, schedule)
        schedule.refresh_from_db()
        tick = tick_svc.process_schedule_slot(schedule, now=self._now_due())
        self.assertIsNotNone(tick)
        self.assertEqual(tick.status, ScheduleTick.STATUS_FAILED)
        self.assertEqual(tick.error_code, "schedule_missing_input")

    def test_misfire_skips_without_enqueue(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo

        from apps.file_pipeline.models import PipelineRun
        from apps.file_scheduler.models import ScheduleTick
        from apps.file_scheduler.services import schedule_tick as tick_svc

        schedule, _pipeline = self._ready_pipeline_plan()
        late = datetime(2026, 9, 1, 6, 0, tzinfo=ZoneInfo("America/Caracas"))
        tick = tick_svc.process_schedule_slot(schedule, now=late)
        self.assertIsNotNone(tick)
        self.assertEqual(tick.status, ScheduleTick.STATUS_SKIPPED)
        self.assertEqual(tick.error_code, "schedule_misfire")
        self.assertEqual(PipelineRun.objects.count(), 0)

    def test_unpublished_pipeline_fails(self):
        from apps.file_pipeline.models import PipelineDefinition
        from apps.file_scheduler.models import ScheduleTick
        from apps.file_scheduler.services import schedule_tick as tick_svc

        schedule, pipeline = self._ready_pipeline_plan()
        pipeline.status = PipelineDefinition.STATUS_INACTIVE
        pipeline.save(update_fields=["status"])
        tick = tick_svc.process_schedule_slot(schedule, now=self._now_due())
        self.assertIsNotNone(tick)
        self.assertEqual(tick.status, ScheduleTick.STATUS_FAILED)
        self.assertEqual(tick.error_code, "schedule_no_published_target")

    def _published_clean(self):
        from apps.dms.mapping.models import DmsProjectConfig
        from apps.dms.source_profile.models import DmsMappingVersion
        from apps.projects.models import Project

        project = Project.objects.create(
            company=self.company,
            name="Clean tick",
            slug="clean-tick",
            owner=self.us,
            project_kind=Project.KIND_FILE_CLEAN,
        )
        version = DmsMappingVersion.objects.create(
            project=project,
            version_number=1,
            status=DmsMappingVersion.STATUS_PUBLISHED,
        )
        DmsProjectConfig.objects.create(project=project, current_version=version)
        return project, version

    def _activate_job_plan(self, project, *, kind="file_clean", artifact_ref="ab"):
        schedule = svc.create_schedule(
            self.us,
            {
                "name": "Clean plan",
                "slug": "clean-plan-tick",
                "description": "",
                "visibility": Schedule.VISIBILITY_MEMBERS_ONLY,
            },
        ).payload["schedule"]
        svc.save_programming(
            self.us,
            schedule,
            {
                "schedule_kind": "daily",
                "time_local": "02:30",
                "timezone": "America/Caracas",
                "day_of_week": "",
                "monthly_mode": "",
                "day_of_month": "",
                "cron_expr": "",
            },
        )
        svc.save_target(
            self.us,
            schedule,
            {
                "target_mode": "job",
                "kind": kind,
                "project_id": str(project.id),
                "pipeline_id": "",
                "input_origin": "artifact",
                "watch_id": "",
                "artifact_ref": artifact_ref,
                "pipeline_inputs_resolved": "",
            },
        )
        svc.activate_schedule(self.us, schedule)
        schedule.refresh_from_db()
        return schedule

    def test_artifact_not_found_fails(self):
        from apps.file_scheduler.models import ScheduleTick
        from apps.file_scheduler.services import schedule_tick as tick_svc

        project, _version = self._published_clean()
        schedule = self._activate_job_plan(
            project, artifact_ref="c" * 64
        )
        tick = tick_svc.process_schedule_slot(schedule, now=self._now_due())
        self.assertIsNotNone(tick)
        self.assertEqual(tick.status, ScheduleTick.STATUS_FAILED)
        self.assertEqual(tick.error_code, "schedule_artifact_not_found")

    def test_clean_artifact_invokes_runner(self):
        import hashlib
        import tempfile
        from pathlib import Path
        from unittest.mock import patch

        from apps.core.services.operation_result import OperationResult
        from apps.dms.file_intake.models import DmsSampleFile
        from apps.file_clean.models import CleanJob
        from apps.file_scheduler.models import ScheduleTick
        from apps.file_scheduler.services import schedule_tick as tick_svc

        project, version = self._published_clean()
        payload = b"hello-scheduler-clean\n"
        digest = hashlib.sha256(payload).hexdigest()
        with tempfile.TemporaryDirectory() as tmp:
            with self.settings(MEDIA_ROOT=tmp):
                stored = Path(tmp) / "sample.txt"
                stored.write_bytes(payload)
                DmsSampleFile.objects.create(
                    project=project,
                    original_filename="sample.txt",
                    stored_path="sample.txt",
                    size_bytes=len(payload),
                    content_hash=digest,
                )
                clean_job = CleanJob(
                    project=project,
                    published_version=version,
                    published_version_number=1,
                    status=CleanJob.STATUS_COMPLETED,
                    input_original_filename="sample.txt",
                    input_content_hash=digest,
                )
                clean_job.save()
                schedule = self._activate_job_plan(project, artifact_ref=digest)
                with patch(
                    "apps.file_clean.run.services.clean_run_service.run_clean_job"
                ) as mocked:
                    mocked.return_value = OperationResult.success(
                        "Limpieza finalizada correctamente.",
                        payload={"job": clean_job, "job_id": str(clean_job.id)},
                    )
                    tick = tick_svc.process_schedule_slot(
                        schedule, now=self._now_due()
                    )
                self.assertIsNotNone(tick)
                self.assertEqual(tick.status, ScheduleTick.STATUS_ENQUEUED)
                self.assertEqual(tick.job_id, str(clean_job.id))
                mocked.assert_called_once()
                row = tick_svc.tick_row(tick, user=self.us)
                self.assertEqual(row["delegated_status"], CleanJob.STATUS_COMPLETED)
                self.assertFalse(row["run_href"])



class ScheduleOverlapTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            name_short="ACME",
            name_long="Acme Ops",
            is_active=True,
        )
        self.us = User.objects.create_user("ops-ov", password="x")
        UserProfile.objects.create(
            user=self.us,
            company=self.company,
            user_type=UserProfile.USER_SYSTEM,
            email_confirmed=True,
            tfa_verified=True,
            totp_secret="secret",
            status=UserProfile.STATUS_ACTIVE,
        )
        self.uf = User.objects.create_user("ana-ov", password="x")
        UserProfile.objects.create(
            user=self.uf,
            company=self.company,
            user_type=UserProfile.USER_FINAL,
            email_confirmed=True,
            tfa_verified=True,
            totp_secret="secret",
            status=UserProfile.STATUS_ACTIVE,
        )

    def _ready(self, slug="ov-plan"):
        from apps.file_pipeline.models import PipelineDefinition, PipelineVersion

        schedule = svc.create_schedule(
            self.us,
            {
                "name": "Overlap",
                "slug": slug,
                "description": "",
                "visibility": Schedule.VISIBILITY_MEMBERS_ONLY,
            },
        ).payload["schedule"]
        pipeline = PipelineDefinition.objects.create(
            company=self.company,
            name="Cadena ov",
            slug=f"cadena-{slug}",
            owner=self.us,
            status=PipelineDefinition.STATUS_ACTIVE,
        )
        version = PipelineVersion.objects.create(
            pipeline=pipeline,
            version_number=1,
            status=PipelineVersion.STATUS_PUBLISHED,
        )
        pipeline.current_version = version
        pipeline.save(update_fields=["current_version"])
        svc.save_programming(
            self.us,
            schedule,
            {
                "schedule_kind": "daily",
                "time_local": "02:30",
                "timezone": "America/Caracas",
                "day_of_week": "",
                "monthly_mode": "",
                "day_of_month": "",
                "cron_expr": "",
            },
        )
        svc.save_target(
            self.us,
            schedule,
            {
                "target_mode": "pipeline",
                "kind": "",
                "project_id": "",
                "pipeline_id": str(pipeline.id),
                "input_origin": "none",
                "watch_id": "",
                "artifact_ref": "",
                "pipeline_inputs_resolved": "1",
            },
        )
        svc.activate_schedule(self.us, schedule)
        schedule.refresh_from_db()
        return schedule

    def _now(self, day=1):
        from datetime import datetime
        from zoneinfo import ZoneInfo

        return datetime(2026, 9, day, 2, 35, tzinfo=ZoneInfo("America/Caracas"))

    def test_ge_cannot_save_overlap(self):
        schedule = self._ready("ov-ge")
        ScheduleMembership.objects.create(
            schedule=schedule,
            user=self.uf,
            role=ScheduleMembership.ROLE_GE,
            is_active=True,
        )
        result = svc.save_overlap(
            self.uf, schedule, {"overlap_policy": Schedule.OVERLAP_QUEUE}
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.error_code, "schedule_forbidden")
        schedule.refresh_from_db()
        self.assertEqual(schedule.overlap_policy, Schedule.OVERLAP_SKIP)
        self.assertIsNone(schedule.overlap_saved_at)

    def test_save_queue_does_not_activate_change(self):
        schedule = self._ready("ov-save")
        result = svc.save_overlap(
            self.us, schedule, {"overlap_policy": Schedule.OVERLAP_QUEUE}
        )
        self.assertTrue(result.ok, result.user_message)
        schedule.refresh_from_db()
        self.assertEqual(schedule.overlap_policy, Schedule.OVERLAP_QUEUE)
        self.assertEqual(schedule.status, Schedule.STATUS_ACTIVE)
        self.assertTrue(schedule.overlap_configured)

    def test_skip_omits_second_slot(self):
        from apps.file_pipeline.models import PipelineRun
        from apps.file_scheduler.models import ScheduleTick
        from apps.file_scheduler.services import schedule_tick as tick_svc

        schedule = self._ready("ov-skip")
        first = tick_svc.process_schedule_slot(schedule, now=self._now(1))
        self.assertEqual(first.status, ScheduleTick.STATUS_ENQUEUED)
        second = tick_svc.process_schedule_slot(schedule, now=self._now(2))
        self.assertIsNotNone(second)
        self.assertEqual(second.status, ScheduleTick.STATUS_SKIPPED)
        self.assertEqual(second.error_code, "schedule_overlap_skip")
        self.assertEqual(PipelineRun.objects.filter(pipeline=schedule.target_pipeline).count(), 1)

    def test_queue_enqueues_second_slot(self):
        from apps.file_pipeline.models import PipelineRun
        from apps.file_scheduler.models import ScheduleTick
        from apps.file_scheduler.services import schedule_tick as tick_svc

        schedule = self._ready("ov-queue")
        svc.save_overlap(self.us, schedule, {"overlap_policy": Schedule.OVERLAP_QUEUE})
        schedule.refresh_from_db()
        first = tick_svc.process_schedule_slot(schedule, now=self._now(1))
        second = tick_svc.process_schedule_slot(schedule, now=self._now(2))
        self.assertEqual(first.status, ScheduleTick.STATUS_ENQUEUED)
        self.assertEqual(second.status, ScheduleTick.STATUS_ENQUEUED)
        self.assertEqual(PipelineRun.objects.filter(pipeline=schedule.target_pipeline).count(), 2)

    def test_cancel_previous_aborts_live_run(self):
        from apps.file_pipeline.models import PipelineRun
        from apps.file_scheduler.models import ScheduleTick
        from apps.file_scheduler.services import schedule_tick as tick_svc

        schedule = self._ready("ov-cancel")
        svc.save_overlap(
            self.us, schedule, {"overlap_policy": Schedule.OVERLAP_CANCEL}
        )
        schedule.refresh_from_db()
        first = tick_svc.process_schedule_slot(schedule, now=self._now(1))
        run1 = PipelineRun.objects.get(pk=first.pipeline_run_id)
        self.assertEqual(run1.status, PipelineRun.STATUS_QUEUED)
        second = tick_svc.process_schedule_slot(schedule, now=self._now(2))
        self.assertEqual(second.status, ScheduleTick.STATUS_ENQUEUED)
        run1.refresh_from_db()
        self.assertEqual(run1.status, PipelineRun.STATUS_CANCELLED)
        self.assertEqual(PipelineRun.objects.filter(pipeline=schedule.target_pipeline).count(), 2)


class ScheduleDependencyTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            name_short="ACME",
            name_long="Acme Ops",
            is_active=True,
        )
        self.us = User.objects.create_user("ops-dep", password="x")
        UserProfile.objects.create(
            user=self.us,
            company=self.company,
            user_type=UserProfile.USER_SYSTEM,
            email_confirmed=True,
            tfa_verified=True,
            totp_secret="secret",
            status=UserProfile.STATUS_ACTIVE,
        )

    def _pipe(self, slug):
        from apps.file_pipeline.models import PipelineDefinition, PipelineVersion

        pipeline = PipelineDefinition.objects.create(
            company=self.company,
            name=slug,
            slug=slug,
            owner=self.us,
            status=PipelineDefinition.STATUS_ACTIVE,
        )
        version = PipelineVersion.objects.create(
            pipeline=pipeline,
            version_number=1,
            status=PipelineVersion.STATUS_PUBLISHED,
        )
        pipeline.current_version = version
        pipeline.save(update_fields=["current_version"])
        return pipeline

    def _child(self, target, parent):
        schedule = svc.create_schedule(
            self.us,
            {
                "name": "Dep",
                "slug": "dep-child",
                "description": "",
                "visibility": Schedule.VISIBILITY_MEMBERS_ONLY,
            },
        ).payload["schedule"]
        svc.save_target(
            self.us,
            schedule,
            {
                "target_mode": "pipeline",
                "kind": "",
                "project_id": "",
                "pipeline_id": str(target.id),
                "input_origin": "none",
                "watch_id": "",
                "artifact_ref": "",
                "pipeline_inputs_resolved": "1",
            },
        )
        result = svc.save_dependency(
            self.us,
            schedule,
            {
                "trigger_mode": "dependency",
                "parent_kind": "pipeline",
                "parent_project_id": "",
                "parent_pipeline_id": str(parent.id),
                "on_parent": "succeeded",
            },
        )
        self.assertTrue(result.ok, result.user_message)
        svc.activate_schedule(self.us, schedule)
        schedule.refresh_from_db()
        return schedule

    def test_activate_without_cron_if_dependency(self):
        parent = self._pipe("padre-dep")
        target = self._pipe("hijo-dep")
        schedule = self._child(target, parent)
        self.assertEqual(schedule.status, Schedule.STATUS_ACTIVE)
        self.assertFalse(schedule.programming_complete)
        self.assertTrue(schedule.dependency_complete)

    def test_cycle_rejected(self):
        pipe = self._pipe("mismo-dep")
        schedule = svc.create_schedule(
            self.us,
            {
                "name": "Ciclo",
                "slug": "dep-ciclo",
                "description": "",
                "visibility": Schedule.VISIBILITY_MEMBERS_ONLY,
            },
        ).payload["schedule"]
        svc.save_target(
            self.us,
            schedule,
            {
                "target_mode": "pipeline",
                "kind": "",
                "project_id": "",
                "pipeline_id": str(pipe.id),
                "input_origin": "none",
                "watch_id": "",
                "artifact_ref": "",
                "pipeline_inputs_resolved": "1",
            },
        )
        result = svc.save_dependency(
            self.us,
            schedule,
            {
                "trigger_mode": "dependency",
                "parent_kind": "pipeline",
                "parent_pipeline_id": str(pipe.id),
                "on_parent": "succeeded",
            },
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.error_code, "schedule_dependency_cycle")

    def test_parent_success_enqueues_once(self):
        from apps.file_pipeline.models import PipelineRun
        from apps.file_scheduler.models import ScheduleTick
        from apps.file_scheduler.services.schedule_dependency import notify_pipeline_finished
        from apps.file_scheduler.services.schedule_tick import process_due_ticks

        parent = self._pipe("padre-ok")
        target = self._pipe("hijo-ok")
        schedule = self._child(target, parent)
        self.assertEqual(process_due_ticks()["processed"], 0)
        run = PipelineRun.objects.create(
            pipeline=parent,
            version=parent.current_version,
            status=PipelineRun.STATUS_QUEUED,
        )
        run.status = PipelineRun.STATUS_COMPLETED
        run.save(update_fields=["status"])
        notify_pipeline_finished(run)
        ticks = ScheduleTick.objects.filter(schedule=schedule)
        self.assertEqual(ticks.count(), 1)
        tick = ticks.get()
        self.assertEqual(tick.status, ScheduleTick.STATUS_ENQUEUED)
        self.assertEqual(tick.parent_pipeline_run_id, str(run.id))
        child = PipelineRun.objects.get(pk=tick.pipeline_run_id)
        self.assertEqual(child.trigger_source, PipelineRun.TRIGGER_DEPENDENCY)
        self.assertEqual(child.parent_pipeline_run_id, str(run.id))
        notify_pipeline_finished(run)
        self.assertEqual(ScheduleTick.objects.filter(schedule=schedule).count(), 1)

    def test_parent_failed_does_not_fire_on_succeeded(self):
        from apps.file_pipeline.models import PipelineRun
        from apps.file_scheduler.models import ScheduleTick
        from apps.file_scheduler.services.schedule_dependency import notify_pipeline_finished

        parent = self._pipe("padre-fail")
        target = self._pipe("hijo-fail")
        schedule = self._child(target, parent)
        run = PipelineRun.objects.create(
            pipeline=parent,
            version=parent.current_version,
            status=PipelineRun.STATUS_FAILED,
        )
        notify_pipeline_finished(run)
        self.assertEqual(ScheduleTick.objects.filter(schedule=schedule).count(), 0)


class ScheduleAuditTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            name_short="ACME",
            name_long="Acme Ops",
            is_active=True,
        )
        self.us = User.objects.create_user("ops-audit", password="x")
        UserProfile.objects.create(
            user=self.us,
            company=self.company,
            user_type=UserProfile.USER_SYSTEM,
            email_confirmed=True,
            tfa_verified=True,
            totp_secret="secret",
            status=UserProfile.STATUS_ACTIVE,
        )

    def test_create_always_has_created_event(self):
        from apps.file_scheduler.services import schedule_audit as audit_svc

        schedule = svc.create_schedule(
            self.us,
            {
                "name": "Audit",
                "slug": "audit-plan",
                "description": "",
                "visibility": Schedule.VISIBILITY_MEMBERS_ONLY,
            },
        ).payload["schedule"]
        rows = audit_svc.list_audit_rows(schedule)
        self.assertTrue(rows)
        created = [r for r in rows if r["event_code"] == ScheduleAuditEvent.EVENT_CREATED]
        self.assertEqual(len(created), 1)
        self.assertEqual(created[0]["plane"], audit_svc.PLANE_DEFINITION)
        self.assertEqual(created[0]["actor_label"], "ops-audit")
        payload = created[0]["event"].payload
        self.assertEqual(payload.get("schedule_id"), str(schedule.id))
        self.assertEqual(payload.get("company_id"), str(self.company.id))

    def test_tick_events_are_plane_b_system_actor(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo

        from apps.file_pipeline.models import PipelineDefinition, PipelineVersion
        from apps.file_scheduler.services import schedule_audit as audit_svc
        from apps.file_scheduler.services import schedule_tick as tick_svc

        schedule = svc.create_schedule(
            self.us,
            {
                "name": "Audit tick",
                "slug": "audit-tick",
                "description": "",
                "visibility": Schedule.VISIBILITY_MEMBERS_ONLY,
            },
        ).payload["schedule"]
        pipeline = PipelineDefinition.objects.create(
            company=self.company,
            name="Cadena audit",
            slug="cadena-audit",
            owner=self.us,
            status=PipelineDefinition.STATUS_ACTIVE,
        )
        version = PipelineVersion.objects.create(
            pipeline=pipeline,
            version_number=1,
            status=PipelineVersion.STATUS_PUBLISHED,
        )
        pipeline.current_version = version
        pipeline.save(update_fields=["current_version"])
        prog = svc.save_programming(
            self.us,
            schedule,
            {
                "schedule_kind": "daily",
                "time_local": "02:30",
                "timezone": "America/Caracas",
                "day_of_week": "",
                "monthly_mode": "",
                "day_of_month": "",
                "cron_expr": "",
            },
        )
        self.assertTrue(prog.ok, prog.user_message)
        tgt = svc.save_target(
            self.us,
            schedule,
            {
                "target_mode": "pipeline",
                "kind": "",
                "project_id": "",
                "pipeline_id": str(pipeline.id),
                "input_origin": "none",
                "watch_id": "",
                "artifact_ref": "",
                "pipeline_inputs_resolved": "1",
            },
        )
        svc.activate_schedule(self.us, schedule)
        schedule.refresh_from_db()
        now = datetime(2026, 9, 1, 2, 35, tzinfo=ZoneInfo("America/Caracas"))
        tick = tick_svc.process_schedule_slot(schedule, now=now)
        self.assertIsNotNone(tick)
        self.assertEqual(tick.status, "enqueued", tick.error_code)
        rows = audit_svc.list_audit_rows(schedule)
        tick_rows = [r for r in rows if r["plane"] == audit_svc.PLANE_TICK]
        self.assertTrue(tick_rows)
        enqueued = [
            r
            for r in tick_rows
            if r["event_code"] == ScheduleAuditEvent.EVENT_TICK_ENQUEUED
        ]
        self.assertEqual(len(enqueued), 1, [r["event_code"] for r in tick_rows])
        self.assertEqual(enqueued[0]["actor_label"], audit_svc.SYSTEM_ACTOR)
        self.assertTrue(enqueued[0]["pipeline_run_id"])
        self.assertTrue(enqueued[0]["run_href"])
        self.assertEqual(
            enqueued[0]["event"].payload.get("schedule_id"), str(schedule.id)
        )


class ScheduleErrorsTests(TestCase):
    def test_catalog_covers_layer_2_and_3(self):
        from apps.file_scheduler.services import schedule_errors as err

        codes = {row["code"] for row in err.catalog_rows()}
        required = {
            err.VALIDATION_REQUIRED,
            err.SLUG_TAKEN,
            err.FORBIDDEN,
            err.CRON_INVALID,
            err.TIMEZONE_INVALID,
            err.NO_PUBLISHED,
            err.MISSING_INPUT,
            err.DEPENDENCY_CYCLE,
            err.INCOMPLETE,
            err.PAUSED,
            err.OVERLAP_SKIP,
            err.MISFIRE,
            err.ENQUEUE_FAILED,
        }
        self.assertTrue(required.issubset(codes))
        self.assertEqual(err.message_for(err.INCOMPLETE), err.MSG_INCOMPLETE)
        self.assertFalse(err.message_for(err.TARGET_CROSS_TENANT))

    def test_unknown_plan_is_404(self):
        from django.test import Client

        company = Company.objects.create(
            name_short="ACME",
            name_long="Acme Ops",
            is_active=True,
        )
        user = User.objects.create_user("ops-err", password="x")
        UserProfile.objects.create(
            user=user,
            company=company,
            user_type=UserProfile.USER_SYSTEM,
            email_confirmed=True,
            tfa_verified=True,
            totp_secret="secret",
            status=UserProfile.STATUS_ACTIVE,
        )
        client = Client()
        self.assertTrue(client.login(username="ops-err", password="x"))
        response = client.get("/app/file-scheduler/planes/no-existe/")
        self.assertEqual(response.status_code, 404)


class ScheduleNotifyTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            name_short="ACME",
            name_long="Acme Ops",
            is_active=True,
        )
        self.us = User.objects.create_user("ops-nt", password="x", email="ops@acme.example")
        UserProfile.objects.create(
            user=self.us,
            company=self.company,
            user_type=UserProfile.USER_SYSTEM,
            email_confirmed=True,
            tfa_verified=True,
            totp_secret="secret",
            status=UserProfile.STATUS_ACTIVE,
        )

    def _plan(self):
        return svc.create_schedule(
            self.us,
            {
                "name": "Avisos",
                "slug": "avisos-plan",
                "description": "",
                "visibility": Schedule.VISIBILITY_MEMBERS_ONLY,
            },
        ).payload["schedule"]

    def test_default_off_and_required_when_on(self):
        from apps.file_scheduler.services import schedule_notify as notify_svc

        schedule = self._plan()
        off = notify_svc.save_notify(self.us, schedule, {"notify_enabled": ""})
        self.assertTrue(off.ok, off.user_message)
        schedule.refresh_from_db()
        self.assertFalse(schedule.notify_enabled)
        on = notify_svc.save_notify(self.us, schedule, {"notify_enabled": "1"})
        self.assertFalse(on.ok)
        self.assertEqual(on.error_code, "validation_required")

    def test_http_webhook_rejected(self):
        from apps.file_scheduler.services import schedule_notify as notify_svc

        schedule = self._plan()
        result = notify_svc.save_notify(
            self.us,
            schedule,
            {
                "notify_enabled": "1",
                "notify_webhook_url": "http://hooks.example/cb",
            },
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.error_code, "schedule_notify_webhook_invalid")

    def test_tick_failed_emails_once(self):
        from unittest.mock import patch

        from apps.core.services.operation_result import OperationResult
        from apps.file_scheduler.models import ScheduleAuditEvent, ScheduleNotifyDispatch
        from apps.file_scheduler.services import schedule_notify as notify_svc

        schedule = self._plan()
        saved = notify_svc.save_notify(
            self.us,
            schedule,
            {
                "notify_enabled": "1",
                "notify_on_tick_failed": "1",
                "notify_on_run_failed": "1",
                "notify_user_ids": [str(self.us.id)],
            },
        )
        self.assertTrue(saved.ok, saved.user_message)
        schedule.refresh_from_db()
        tick = schedule.ticks.create(
            company=self.company,
            scheduled_for=schedule.updated_at,
            status="failed",
            error_code="schedule_missing_input",
            user_message="Falta el archivo de entrada.",
        )
        with patch(
            "apps.file_scheduler.services.schedule_notify.send_email",
            return_value=OperationResult.success(),
        ) as mocked:
            notify_svc.dispatch_for_tick(tick)
            notify_svc.dispatch_for_tick(tick)
        self.assertEqual(mocked.call_count, 1)
        self.assertEqual(
            ScheduleNotifyDispatch.objects.filter(
                schedule=schedule, kind=ScheduleNotifyDispatch.KIND_TICK_FAILED
            ).count(),
            1,
        )
        self.assertTrue(
            ScheduleAuditEvent.objects.filter(
                schedule=schedule, event=ScheduleAuditEvent.EVENT_NOTIFY_SENT
            ).exists()
        )

    def test_skip_does_not_notify_by_default(self):
        from unittest.mock import patch

        from apps.core.services.operation_result import OperationResult
        from apps.file_scheduler.services import schedule_notify as notify_svc

        schedule = self._plan()
        notify_svc.save_notify(
            self.us,
            schedule,
            {
                "notify_enabled": "1",
                "notify_on_tick_failed": "1",
                "notify_user_ids": [str(self.us.id)],
            },
        )
        tick = schedule.ticks.create(
            company=self.company,
            scheduled_for=schedule.updated_at,
            status="skipped",
            error_code="schedule_overlap_skip",
        )
        with patch(
            "apps.file_scheduler.services.schedule_notify.send_email",
            return_value=OperationResult.success(),
        ) as mocked:
            notify_svc.dispatch_for_tick(tick)
        mocked.assert_not_called()


class ScheduleIntegrationTests(TestCase):
    def test_map_lists_scheduler_and_dependency_channels(self):
        from apps.file_scheduler.services import schedule_integration as integ

        ctx = integ.map_context()
        codes = {row["code"] for row in ctx["channels"]}
        self.assertIn("scheduler", codes)
        self.assertIn("dependency", codes)
        self.assertIn("watch", codes)
        self.assertIn("api", codes)
        self.assertTrue(ctx["worker_command"])

    def test_dashboard_filters_scheduler_runs(self):
        from apps.file_pipeline.models import PipelineDefinition, PipelineRun, PipelineVersion
        from apps.file_pipeline.services import pipeline_dashboard_service as dash_svc

        company = Company.objects.create(
            name_short="ACME",
            name_long="Acme Ops",
            is_active=True,
        )
        user = User.objects.create_user("ops-int", password="x")
        UserProfile.objects.create(
            user=user,
            company=company,
            user_type=UserProfile.USER_SYSTEM,
            email_confirmed=True,
            tfa_verified=True,
            totp_secret="secret",
            status=UserProfile.STATUS_ACTIVE,
        )
        pipeline = PipelineDefinition.objects.create(
            company=company,
            name="Cadena int",
            slug="cadena-int",
            owner=user,
            status=PipelineDefinition.STATUS_ACTIVE,
            visibility=PipelineDefinition.VISIBILITY_COMPANY,
        )
        version = PipelineVersion.objects.create(
            pipeline=pipeline,
            version_number=1,
            status=PipelineVersion.STATUS_PUBLISHED,
        )
        PipelineRun.objects.create(
            pipeline=pipeline,
            version=version,
            trigger_source=PipelineRun.TRIGGER_UI,
            status=PipelineRun.STATUS_COMPLETED,
        )
        scheduled = PipelineRun.objects.create(
            pipeline=pipeline,
            version=version,
            trigger_source=PipelineRun.TRIGGER_SCHEDULER,
            status=PipelineRun.STATUS_FAILED,
            schedule_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        )
        mixed = dash_svc.dashboard_context(user, {"days": "7"})
        self.assertEqual(mixed["total"], 2)
        self.assertEqual(mixed["trigger"], dash_svc.TRIGGER_ALL)
        filtered = dash_svc.dashboard_context(user, {"days": "7", "trigger": "scheduler"})
        self.assertEqual(filtered["total"], 1)
        self.assertEqual(filtered["failed"], 1)
        self.assertEqual(filtered["recent"][0]["run"].id, scheduled.id)
        self.assertEqual(filtered["recent"][0]["schedule_short"], "aaaaaaaa")

