from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.dms.file_intake.models import DmsExecutionJob
from apps.file_clean.models import CleanJob
from apps.file_pipeline.models import PipelineRun


@receiver(post_save, sender=DmsExecutionJob)
def schedule_on_job_finished(sender, instance, created, **kwargs):
    if created:
        return
    terminal = {
        DmsExecutionJob.STATUS_COMPLETED,
        DmsExecutionJob.STATUS_PARTIAL,
        DmsExecutionJob.STATUS_FAILED,
    }
    if instance.status not in terminal:
        return
    from apps.file_scheduler.services.schedule_dependency import notify_job_finished

    try:
        notify_job_finished(instance)
    except Exception:
        import logging

        logging.getLogger(__name__).exception("notify_job_finished job=%s", instance.pk)
    if instance.status == DmsExecutionJob.STATUS_FAILED:
        from apps.file_scheduler.services import schedule_notify as notify_svc

        try:
            notify_svc.dispatch_for_job(instance)
        except Exception:
            import logging

            logging.getLogger(__name__).exception("dispatch_for_job job=%s", instance.pk)


@receiver(post_save, sender=CleanJob)
def schedule_on_clean_finished(sender, instance, created, **kwargs):
    if created:
        return
    if instance.status not in {CleanJob.STATUS_COMPLETED, CleanJob.STATUS_FAILED}:
        return
    from apps.file_scheduler.services.schedule_dependency import notify_job_finished

    try:
        notify_job_finished(instance)
    except Exception:
        import logging

        logging.getLogger(__name__).exception("notify_job_finished clean=%s", instance.pk)
    if instance.status == CleanJob.STATUS_FAILED:
        from apps.file_scheduler.services import schedule_notify as notify_svc

        try:
            notify_svc.dispatch_for_job(instance)
        except Exception:
            import logging

            logging.getLogger(__name__).exception("dispatch_for_job clean=%s", instance.pk)


@receiver(post_save, sender=PipelineRun)
def schedule_on_pipeline_finished(sender, instance, created, **kwargs):
    if created:
        return
    if instance.status not in {PipelineRun.STATUS_COMPLETED, PipelineRun.STATUS_FAILED}:
        return
    from apps.file_scheduler.services.schedule_dependency import notify_pipeline_finished

    try:
        notify_pipeline_finished(instance)
    except Exception:
        import logging

        logging.getLogger(__name__).exception(
            "notify_pipeline_finished run=%s", instance.pk
        )
    if instance.status == PipelineRun.STATUS_FAILED:
        from apps.file_scheduler.services import schedule_notify as notify_svc

        try:
            notify_svc.dispatch_for_pipeline(instance)
        except Exception:
            import logging

            logging.getLogger(__name__).exception(
                "dispatch_for_pipeline run=%s", instance.pk
            )
