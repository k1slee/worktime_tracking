from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings
from pathlib import Path
import csv
from apps.users.models import User

class Command(BaseCommand):
    help = "Сброс паролей мастеров (без входов) и экспорт логинов/паролей в CSV"

    def add_arguments(self, parser):
        parser.add_argument(
            "--all",
            action="store_true",
            help="Сбрасывать пароли у всех мастеров (по умолчанию только у тех, кто ни разу не входил)",
        )
        parser.add_argument(
            "--outfile",
            type=str,
            help="Путь к CSV файлу для сохранения (по умолчанию: logs/masters_credentials_<ts>.csv)",
        )

    def handle(self, *args, **options):
        reset_all = options["all"]
        outfile = options.get("outfile")

        if reset_all:
            qs = User.objects.filter(role="master", is_active=True)
        else:
            qs = User.objects.filter(role="master", is_active=True, last_login__isnull=True)

        if not qs.exists():
            self.stdout.write(self.style.WARNING("Нет мастеров для сброса пароля по заданному условию"))
            return

        ts = timezone.now().strftime("%Y%m%d_%H%M%S")
        logs_dir = Path(getattr(settings, "BASE_DIR", ".")) / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        if not outfile:
            outfile = logs_dir / f"masters_credentials_{ts}.csv"
        else:
            outfile = Path(outfile)
            outfile.parent.mkdir(parents=True, exist_ok=True)

        with outfile.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, delimiter=";")
            writer.writerow(["username", "employee_id", "last_name", "first_name", "middle_name", "password"])
            count = 0
            for user in qs:
                pwd = User.objects.make_random_password()
                user.set_password(pwd)
                user.save(update_fields=["password"])
                writer.writerow([
                    user.username,
                    user.employee_id,
                    user.last_name,
                    user.first_name,
                    getattr(user, "middle_name", ""),
                    pwd,
                ])
                count += 1

        self.stdout.write(self.style.SUCCESS(f"Сброшено паролей: {count}. Файл: {outfile}"))
