import os
import sys
import sqlite3
import django

# Настраиваем пути
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

print("=" * 60)
print("Инициализация базы данных SQLite")
print("=" * 60)

# 1. Удаляем старый файл (если есть)
db_path = os.path.join(BASE_DIR, 'db.sqlite3')
if os.path.exists(db_path):
    print(f"1. Удаляю старый файл db.sqlite3...")
    os.remove(db_path)

# 2. Создаём пустую базу данных SQLite
print("2. Создаю новую базу данных SQLite...")
conn = sqlite3.connect(db_path)
conn.close()
print(f"   ✓ База данных создана: {db_path}")

# 3. Настраиваем Django
print("3. Настраиваю Django...")
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

try:
    django.setup()
    print("   ✓ Django успешно настроен")
    
    # 4. Создаём миграции
    print("4. Создаю миграции...")
    from django.core.management import execute_from_command_line
    
    print("   Создание миграций для 'users'...")
    execute_from_command_line(['manage.py', 'makemigrations', 'users'])
    
    print("   Создание миграций для 'timesheet'...")
    execute_from_command_line(['manage.py', 'makemigrations', 'timesheet'])
    
    # 5. Применяем миграции
    print("5. Применяю миграции...")
    execute_from_command_line(['manage.py', 'migrate'])
    
    print("\n" + "=" * 60)
    print("База данных успешно инициализирована!")
    print("\nТеперь создайте суперпользователя:")
    print("python manage.py createsuperuser")
    print("\nИ запустите сервер:")
    print("python manage.py runserver")
    print("=" * 60)
    
except Exception as e:
    print(f"\n✗ Ошибка: {e}")
    import traceback
    traceback.print_exc()