import os
import sys
import django
from datetime import datetime, timedelta
import random
from django.utils import timezone

# Настраиваем Django
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

try:
    django.setup()
    
    from apps.users.models import User, Department, Employee
    from apps.timesheet.models import Timesheet
    
    print("=" * 60)
    print("Создание тестовых данных для системы учета рабочего времени")
    print("=" * 60)
    
    # Удаляем старые данные (опционально)
    clear_data = input("Очистить старые данные? (y/n): ").strip().lower()
    if clear_data == 'y':
        print("\nОчистка старых данных...")
        Timesheet.objects.all().delete()
        Employee.objects.all().delete()
        User.objects.filter(is_superuser=False).delete()
        Department.objects.all().delete()
        print("✓ Старые данные очищены")
    
    # 1. Создаем отделы
    print("\n1. Создание отделов...")
    departments = []
    
    dept_data = [
        {'name': 'Производственный цех №1', 'code': 'P1'},
        {'name': 'Производственный цех №2', 'code': 'P2'},
        {'name': 'Планово-экономический отдел', 'code': 'PEO'},
        {'name': 'Отдел кадров', 'code': 'OK'},
        {'name': 'Бухгалтерия', 'code': 'BUX'},
        {'name': 'Склад', 'code': 'SKL'},
    ]
    
    for data in dept_data:
        dept, created = Department.objects.get_or_create(
            code=data['code'],
            defaults={'name': data['name']}
        )
        if created:
            departments.append(dept)
            print(f"   ✓ Создан отдел: {dept.name} ({dept.code})")
    
    # 2. Создаем роли пользователей
    print("\n2. Создание пользователей...")
    
    # Суперпользователь (если нет)
    if not User.objects.filter(username='admin').exists():
        admin = User.objects.create_superuser(
            username='admin',
            password='admin123',
            email='admin@example.com',
            employee_id='00001',
            department=departments[0] if departments else None,
            role='admin',
            first_name='Администратор',
            last_name='Системы',
            position='Системный администратор',
            phone='+7 (999) 123-45-67'
        )
        print(f"   ✓ Создан администратор: admin / admin123")
    
    # Создаем мастеров
    masters = []
    master_data = [
        {
            'username': 'master1',
            'password': 'master123',
            'employee_id': '10001',
            'first_name': 'Иван',
            'last_name': 'Петров',
            'position': 'Мастер цеха',
            'phone': '+7 (999) 111-11-11',
            'department': departments[0] if len(departments) > 0 else None
        },
        {
            'username': 'master2',
            'password': 'master123',
            'employee_id': '10002',
            'first_name': 'Сергей',
            'last_name': 'Сидоров',
            'position': 'Старший мастер',
            'phone': '+7 (999) 222-22-22',
            'department': departments[1] if len(departments) > 1 else None
        }
    ]
    
    for data in master_data:
        user, created = User.objects.get_or_create(
            username=data['username'],
            defaults={
                'employee_id': data['employee_id'],
                'department': data['department'],
                'role': 'master',
                'first_name': data['first_name'],
                'last_name': data['last_name'],
                'position': data['position'],
                'phone': data['phone'],
                'email': f"{data['username']}@example.com"
            }
        )
        if created:
            user.set_password(data['password'])
            user.save()
            masters.append(user)
            print(f"   ✓ Создан мастер: {data['username']} / {data['password']}")
    
    # Создаем плановый отдел
    planner_data = [
        {
            'username': 'planner1',
            'password': 'planner123',
            'employee_id': '20001',
            'first_name': 'Ольга',
            'last_name': 'Иванова',
            'position': 'Экономист',
            'phone': '+7 (999) 333-33-33',
            'department': departments[2] if len(departments) > 2 else None
        }
    ]
    
    for data in planner_data:
        user, created = User.objects.get_or_create(
            username=data['username'],
            defaults={
                'employee_id': data['employee_id'],
                'department': data['department'],
                'role': 'planner',
                'first_name': data['first_name'],
                'last_name': data['last_name'],
                'position': data['position'],
                'phone': data['phone'],
                'email': f"{data['username']}@example.com"
            }
        )
        if created:
            user.set_password(data['password'])
            user.save()
            print(f"   ✓ Создан плановик: {data['username']} / {data['password']}")
    
    # 3. Создаем сотрудников
    print("\n3. Создание сотрудников...")
    
    employee_data = [
        # Сотрудники мастера 1
        {'first_name': 'Алексей', 'last_name': 'Смирнов', 'position': 'Токарь 5 разряда'},
        {'first_name': 'Дмитрий', 'last_name': 'Кузнецов', 'position': 'Фрезеровщик 4 разряда'},
        {'first_name': 'Михаил', 'last_name': 'Попов', 'position': 'Слесарь 6 разряда'},
        {'first_name': 'Андрей', 'last_name': 'Васильев', 'position': 'Сварщик 5 разряда'},
        {'first_name': 'Павел', 'last_name': 'Павлов', 'position': 'Наладчик оборудования'},
        
        # Сотрудники мастера 2
        {'first_name': 'Анна', 'last_name': 'Семенова', 'position': 'Контролер ОТК'},
        {'first_name': 'Елена', 'last_name': 'Голубева', 'position': 'Упаковщица'},
        {'first_name': 'Татьяна', 'last_name': 'Виноградова', 'position': 'Комплектовщица'},
        {'first_name': 'Наталья', 'last_name': 'Крылова', 'position': 'Кладовщик'},
        {'first_name': 'Ирина', 'last_name': 'Максимова', 'position': 'Уборщица'},
    ]
    
    employees = []
    for i, emp_data in enumerate(employee_data, 1):
        # Чередуем мастеров
        master = masters[0] if i <= 5 else masters[1]
        
        # Создаем пользователя для сотрудника
        username = f'emp{i:03d}'
        employee_id = f'{30000 + i}'
        
        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                'employee_id': employee_id,
                'department': master.department,
                'role': 'master',  # Сотрудники тоже имеют роль master для простоты
                'first_name': emp_data['first_name'],
                'last_name': emp_data['last_name'],
                'position': emp_data['position'],
                'email': f'{username}@example.com',
                'phone': f'+7 (999) {400 + i:03d}-{i:02d}{i:02d}'
            }
        )
        
        if created:
            user.set_password(f'emp{i:03d}123')
            user.save()
            
            # Создаем профиль сотрудника
            employee = Employee.objects.create(
                user=user,
                master=master,
                hire_date=timezone.now().date() - timedelta(days=random.randint(100, 1000)),
                is_active=random.choice([True, True, True, False])  # 75% активны
            )
            employees.append(employee)
            print(f"   ✓ Создан сотрудник: {username} / emp{i:03d}123 - {emp_data['first_name']} {emp_data['last_name']}")
    
    # 4. Создаем табели
    print("\n4. Создание табелей...")
    
    # Коды для табелей
    codes = ['В', 'К', 'О', 'Б', 'Р', 'М', 'Н', 'Ч']
    
    # Создаем табели за последние 60 дней
    today = timezone.now().date()
    days_to_create = 60
    
    for day_offset in range(days_to_create):
        date = today - timedelta(days=day_offset)
        
        # Пропускаем будущие даты
        if date > today:
            continue
        
        for employee in employees:
            # 80% вероятность создания табеля на день
            if random.random() > 0.2:
                # Проверяем, не существует ли уже табель
                if not Timesheet.objects.filter(date=date, employee=employee).exists():
                    # Определяем значение
                    if random.random() < 0.3:  # 30% вероятность использования кода
                        value = random.choice(codes)
                    else:  # 70% - рабочие часы
                        value = str(random.randint(1, 12))
                    
                    # Определяем статус (старые табели чаще утверждены)
                    days_ago = (today - date).days
                    if days_ago > 7 and random.random() < 0.8:  # Табели старше недели
                        status = 'approved'
                        approved_by = random.choice([masters[0], masters[1], User.objects.filter(role='planner').first()])
                        approved_at = date + timedelta(days=random.randint(1, 3))
                    else:
                        status = 'draft'
                        approved_by = None
                        approved_at = None
                    
                    # Создаем табель
                    timesheet = Timesheet.objects.create(
                        date=date,
                        employee=employee,
                        master=employee.master,
                        value=value,
                        status=status,
                        approved_by=approved_by,
                        approved_at=approved_at
                    )
    
    # Подсчет созданных табелей
    total_timesheets = Timesheet.objects.count()
    approved_timesheets = Timesheet.objects.filter(status='approved').count()
    draft_timesheets = Timesheet.objects.filter(status='draft').count()
    
    print(f"   ✓ Создано табелей: {total_timesheets}")
    print(f"     - Утверждено: {approved_timesheets}")
    print(f"     - Черновиков: {draft_timesheets}")
    
    # 5. Создаем тестовые данные для месячного табеля (текущий месяц)
    print("\n5. Создание данных текущего месяца...")
    
    current_year = today.year
    current_month = today.month
    
    # Удаляем табели текущего месяца (чтобы можно было тестировать создание месячного табеля)
    Timesheet.objects.filter(
        date__year=current_year,
        date__month=current_month
    ).delete()
    
    print(f"   ✓ Очищены табели за {today.strftime('%B %Y')} для тестирования")
    
    # 6. Статистика
    print("\n" + "=" * 60)
    print("СТАТИСТИКА:")
    print("=" * 60)
    
    print(f"\nПользователи:")
    print(f"  Администраторы: {User.objects.filter(role='admin').count()}")
    print(f"  Мастера: {User.objects.filter(role='master').count()}")
    print(f"  Плановики: {User.objects.filter(role='planner').count()}")
    
    print(f"\nСотрудники:")
    print(f"  Всего: {Employee.objects.count()}")
    print(f"  Активных: {Employee.objects.filter(is_active=True).count()}")
    print(f"  Неактивных: {Employee.objects.filter(is_active=False).count()}")
    
    print(f"\nОтделы: {Department.objects.count()}")
    
    print(f"\nТабели: {total_timesheets}")
    
    print("\n" + "=" * 60)
    print("ДОСТУП ДЛЯ ТЕСТИРОВАНИЯ:")
    print("=" * 60)
    print("\nАдминистратор:")
    print("  Логин: admin")
    print("  Пароль: admin123")
    print("  Доступ: Полный (админка Django)")
    
    print("\nМастера:")
    for i, master in enumerate(masters, 1):
        print(f"  Мастер {i}:")
        print(f"    Логин: {master.username}")
        print(f"    Пароль: master123")
        print(f"    Сотрудников: {Employee.objects.filter(master=master).count()}")
    
    print("\nПлановый отдел:")
    print("  Логин: planner1")
    print("  Пароль: planner123")
    
    print("\nСотрудники (для просмотра):")
    print("  Формат логина: emp001, emp002, ... emp010")
    print("  Формат пароля: emp001123, emp002123, ... emp010123")
    
    print("\n" + "=" * 60)
    print("Для создания месячного табеля:")
    print("1. Войдите как мастер (master1/master123)")
    print("2. Перейдите в 'Табели'")
    print("3. Нажмите 'Месячный табель'")
    print("4. Выберите месяц и нажмите 'Создать табели'")
    print("=" * 60)
    
except Exception as e:
    print(f"\n✗ Ошибка: {e}")
    import traceback
    traceback.print_exc()