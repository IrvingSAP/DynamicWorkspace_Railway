from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.file_scheduler.services.schedule_tick import process_due_ticks


class Command(BaseCommand):
    help = "Evalúa planes activos y encola ticks vencidos (un slot por plan)."

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

            self.stdout.write("File Scheduler worker en bucle.")
            while True:
                self._once()
                time.sleep(interval)
        self._once()

    def _once(self):
        result = process_due_ticks()
        self.stdout.write(
            f"{timezone.now().isoformat()} ticks procesados={result['processed']}"
        )
