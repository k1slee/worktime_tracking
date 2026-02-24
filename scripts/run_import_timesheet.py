import os
import sys
import glob

# Определяем корень проекта и добавляем его в sys.path
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from django.core.management import call_command

def main():
    # Ищем файл табеля 'Табели январь 2026.xls' в корне проекта
    patterns = [
        os.path.join(base_dir, "Табели*январ*2026*.xls*"),
        os.path.join(base_dir, "*январ*2026*.xls*"),
    ]
    candidates = []
    for p in patterns:
        candidates.extend(glob.glob(p))
    if not candidates:
        print("Файл табеля не найден. Поместите файл в корень проекта.")
        sys.exit(2)
    # Берем первый найденный
    filename = candidates[0]
    print(f"Импорт из файла: {filename}")
    # Вызываем команду импорта
    call_command("import_timesheet_staff", filename, year=2026, month=1)

if __name__ == "__main__":
    main()
