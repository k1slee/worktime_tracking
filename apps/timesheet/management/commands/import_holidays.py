import pandas as pd
from apps.timesheet.models import Holiday
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = "Импорт выходных и праздников из Excel"

    def add_arguments(self, parser):
        parser.add_argument("filename", type=str, help="Путь к Excel файлу")

    def handle(self, *args, **options):
        filename = options["filename"]
        df = pd.read_excel(filename, header=None)

        for row in df.iloc[1:].itertuples(index=False):
            for cell in row:
                if pd.notna(cell):
                    try:
                        # пробуем преобразовать в дату
                        day = pd.to_datetime(cell, errors="coerce")
                        if pd.notna(day):
                            Holiday.objects.get_or_create(
                                date=day.date(),
                                defaults={"type": "holiday", "name": "Выходной"}
                            )
                        else:
                            self.stdout.write(self.style.WARNING(f"Пропущено: {cell}"))
                    except Exception as e:
                        self.stdout.write(self.style.WARNING(f"Ошибка для {cell}: {e}"))

        self.stdout.write(self.style.SUCCESS("Импорт завершён"))
