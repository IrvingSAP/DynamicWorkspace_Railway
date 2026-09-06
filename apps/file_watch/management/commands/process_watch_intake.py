from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.file_watch.services import watch_intake as intake_svc


class Command(BaseCommand):
    help = (
        "Worker de intake File Watch: escanea bandejas activas con "
        "source_kind=managed_folder e ingiere archivos nuevos."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--loop",
            action="store_true",
            help="Repetir hasta interrupción (proceso worker).",
        )
        parser.add_argument(
            "--interval",
            type=int,
            default=60,
            help="Segundos entre pasadas en --loop (default 60).",
        )

    def handle(self, *args, **options):
        loop = options["loop"]
        interval = max(5, int(options["interval"] or 60))
        if loop:
            import time

            self.stdout.write("File Watch intake worker en bucle.")
            while True:
                self._once()
                time.sleep(interval)
        self._once()

    def _once(self):
        stats = intake_svc.process_active_managed_watches()
        self.stdout.write(
            f"{timezone.now().isoformat()} watch intake "
            f"watches={stats['watches']} ingested={stats['ingested']} "
            f"skipped={stats['skipped']} failed={stats['failed']}"
        )
