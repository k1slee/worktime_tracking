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
    from apps.timesheet.models import Timesheet, MonthlyTimesheet
    
    print("=" * 60)
    print("Создание тестовых данных для системы учета рабочего времени")
    print("=" * 60)
    
    # Удаляем старые данные (опционально)
    clear_data = input("Очистить старые данные? (y/n): ").strip().lower()
    if clear_data == 'y':
        print("\nОчистка старых данных...")
        MonthlyTimesheet.objects.all().delete()
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
        {'name': 'Производственный цех №3', 'code': 'P3'},
        {'name': 'Планово-экономический отдел', 'code': 'PEO'},
        {'name': 'Отдел кадров', 'code': 'OK'},
        {'name': 'Бухгалтерия', 'code': 'BUX'},
        {'name': 'Склад готовой продукции', 'code': 'SKL1'},
        {'name': 'Склад сырья', 'code': 'SKL2'},
    ]
    
    # Создаем иерархию отделов
    for i, data in enumerate(dept_data):
        parent = None
        if i >= 3:  # Делаем первые 3 отдела родительскими
            parent = random.choice(departments[:3]) if departments[:3] else None
        
        dept, created = Department.objects.get_or_create(
            code=data['code'],
            defaults={
                'name': data['name'],
                'parent': parent
            }
        )
        if created:
            departments.append(dept)
            parent_info = f", родительский: {parent.name}" if parent else ""
            print(f"   ✓ Создан отдел: {dept.name} ({dept.code}){parent_info}")
    
    # 2. Создаем пользователей
    print("\n2. Создание пользователей...")
    
    # Суперпользователь
    if not User.objects.filter(username='admin').exists():
        admin = User.objects.create_superuser(
            username='admin',
            password='admin123',
            email='admin@company.com',
            employee_id='00001',
            department=departments[3] if len(departments) > 3 else None,
            role='admin',
            first_name='Александр',
            last_name='Смирнов',
            position='Системный администратор',
            phone='+7 (999) 123-45-67'
        )
        print(f"   ✓ Создан администратор: admin / admin123")
    
    # Создаем мастеров
    masters = []
    master_data = [
        {
            'username': 'master_p1',
            'password': 'master123',
            'employee_id': '10001',
            'first_name': 'Иван',
            'last_name': 'Петров',
            'middle_name': 'Иванович',
            'position': 'Старший мастер цеха №1',
            'phone': '+7 (999) 111-11-11',
            'department': departments[0] if len(departments) > 0 else None
        },
        {
            'username': 'master_p2',
            'password': 'master123',
            'employee_id': '10002',
            'first_name': 'Сергей',
            'last_name': 'Сидоров',
            'middle_name': 'Сергеевич',
            'position': 'Мастер цеха №2',
            'phone': '+7 (999) 222-22-22',
            'department': departments[1] if len(departments) > 1 else None
        },
        {
            'username': 'master_p3',
            'password': 'master123',
            'employee_id': '10003',
            'first_name': 'Андрей',
            'last_name': 'Кузнецов',
            'middle_name': 'Андреевич',
            'position': 'Мастер цеха №3',
            'phone': '+7 (999) 333-33-33',
            'department': departments[2] if len(departments) > 2 else None
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
                'middle_name': data.get('middle_name', ''),
                'position': data['position'],
                'phone': data['phone'],
                'email': f"{data['username']}@company.com"
            }
        )
        if created:
            user.set_password(data['password'])
            user.save()
            masters.append(user)
            print(f"   ✓ Создан мастер: {data['username']} / {data['password']}")
    
    # Создаем плановый отдел
    planners = []
    planner_data = [
        {
            'username': 'planner1',
            'password': 'planner123',
            'employee_id': '20001',
            'first_name': 'Ольга',
            'last_name': 'Иванова',
            'position': 'Главный экономист',
            'phone': '+7 (999) 444-44-44',
            'department': departments[3] if len(departments) > 3 else None
        },
        {
            'username': 'planner2',
            'password': 'planner123',
            'employee_id': '20002',
            'first_name': 'Екатерина',
            'last_name': 'Смирнова',
            'position': 'Экономист',
            'phone': '+7 (999) 555-55-55',
            'department': departments[3] if len(departments) > 3 else None
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
                'email': f"{data['username']}@company.com"
            }
        )
        if created:
            user.set_password(data['password'])
            user.save()
            planners.append(user)
            print(f"   ✓ Создан плановик: {data['username']} / {data['password']}")
    
    # Создаем обычных пользователей (не мастера, не плановики)
    regular_users = []
    regular_data = [
        {
            'username': 'user_hr1',
            'password': 'user123',
            'employee_id': '30001',
            'first_name': 'Мария',
            'last_name': 'Васильева',
            'position': 'Менеджер по персоналу',
            'phone': '+7 (999) 666-66-66',
            'department': departments[4] if len(departments) > 4 else None,
            'role': 'master'  # Обычные пользователи имеют роль master
        },
        {
            'username': 'user_bux1',
            'password': 'user123',
            'employee_id': '30002',
            'first_name': 'Наталья',
            'last_name': 'Петрова',
            'position': 'Бухгалтер',
            'phone': '+7 (999) 777-77-77',
            'department': departments[5] if len(departments) > 5 else None,
            'role': 'master'
        }
    ]
    
    for data in regular_data:
        user, created = User.objects.get_or_create(
            username=data['username'],
            defaults={
                'employee_id': data['employee_id'],
                'department': data['department'],
                'role': data['role'],
                'first_name': data['first_name'],
                'last_name': data['last_name'],
                'position': data['position'],
                'phone': data['phone'],
                'email': f"{data['username']}@company.com"
            }
        )
        if created:
            user.set_password(data['password'])
            user.save()
            regular_users.append(user)
            print(f"   ✓ Создан пользователь: {data['username']} / {data['password']}")
    
    # 3. Создаем сотрудников
    print("\n3. Создание сотрудников...")
    
    employee_names = [
        # Сотрудники мастера 1 (цех №1)
        {'first_name': 'Алексей', 'last_name': 'Смирнов', 'position': 'Токарь 5 разряда'},
        {'first_name': 'Дмитрий', 'last_name': 'Кузнецов', 'position': 'Фрезеровщик 4 разряда'},
        {'first_name': 'Михаил', 'last_name': 'Попов', 'position': 'Слесарь 6 разряда'},
        {'first_name': 'Андрей', 'last_name': 'Васильев', 'position': 'Сварщик 5 разряда'},
        {'first_name': 'Павел', 'last_name': 'Павлов', 'position': 'Наладчик оборудования'},
        {'first_name': 'Владимир', 'last_name': 'Семенов', 'position': 'Станочник 3 разряда'},
        
        # Сотрудники мастера 2 (цех №2)
        {'first_name': 'Анна', 'last_name': 'Семенова', 'position': 'Контролер ОТК'},
        {'first_name': 'Елена', 'last_name': 'Голубева', 'position': 'Упаковщица'},
        {'first_name': 'Татьяна', 'last_name': 'Виноградова', 'position': 'Комплектовщица'},
        {'first_name': 'Наталья', 'last_name': 'Крылова', 'position': 'Кладовщик'},
        {'first_name': 'Ирина', 'last_name': 'Максимова', 'position': 'Уборщица'},
        {'first_name': 'Светлана', 'last_name': 'Орлова', 'position': 'Оператор линии'},
        
        # Сотрудники мастера 3 (цех №3)
        {'first_name': 'Александр', 'last_name': 'Морозов', 'position': 'Электрик 4 разряда'},
        {'first_name': 'Юрий', 'last_name': 'Захаров', 'position': 'Слесарь-сантехник'},
        {'first_name': 'Роман', 'last_name': 'Белов', 'position': 'Маляр'},
        {'first_name': 'Виктор', 'last_name': 'Комаров', 'position': 'Плотник'},
        {'first_name': 'Геннадий', 'last_name': 'Титов', 'position': 'Штукатур'},
        {'first_name': 'Борис', 'last_name': 'Кудрявцев', 'position': 'Каменщик'},
    ]
    
    employees = []
    for i, emp_data in enumerate(employee_names, 1):
        # Распределяем по мастерам
        if i <= 6:
            master = masters[0]
            employee_id = f'400{i:02d}'
            username = f'emp_c1_{i:02d}'
        elif i <= 12:
            master = masters[1]
            employee_id = f'401{i-6:02d}'
            username = f'emp_c2_{i-6:02d}'
        else:
            master = masters[2]
            employee_id = f'402{i-12:02d}'
            username = f'emp_c3_{i-12:02d}'
        
        # Создаем пользователя для сотрудника
        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                'employee_id': employee_id,
                'department': master.department,
                'role': 'master',  # Все сотрудники имеют роль master
                'first_name': emp_data['first_name'],
                'last_name': emp_data['last_name'],
                'position': emp_data['position'],
                'email': f'{username}@company.com',
                'phone': f'+7 (999) {500 + i:03d}-{i:02d}{i:02d}',
                'is_active': True
            }
        )
        
        if created:
            user.set_password(f'emp{i:03d}123')
            user.save()
            
            # Создаем профиль сотрудника
            hire_date = timezone.now().date() - timedelta(days=random.randint(100, 2000))
            
            employee = Employee.objects.create(
                user=user,
                master=master,
                hire_date=hire_date,
                is_active=random.choice([True, True, True, False])  # 75% активны
            )
            employees.append(employee)
            print(f"   ✓ Создан сотрудник: {username} / emp{i:03d}123 - {emp_data['first_name']} {emp_data['last_name']} ({emp_data['position']})")
    
    # 4. Создаем табели
    print("\n4. Создание табелей...")
    
    # Все возможные значения для табелей
    all_codes = ['В', 'К', 'О', 'Б', 'Р', 'М', 'Т', 'Н', 'ОС', 'П', 'ЦП', 'Ч', 'Г', 'ДМ', 'А']
    
    # Часовые значения
    hour_values = ['4', '6', '7', '8', '9', '10', '7/2', '8/2', '9/2', '10/2', '6/2', '7/3', '3,5']
    
    # Создаем табели за последние 90 дней
    today = timezone.now().date()
    days_to_create = 90
    
    created_count = 0
    
    for day_offset in range(days_to_create):
        date = today - timedelta(days=day_offset)
        
        # Пропускаем будущие даты
        if date > today:
            continue
        
        # Для каждого сотрудника
        for employee in employees:
            # 85% вероятность создания табеля на день
            if random.random() > 0.15:
                # Проверяем, не существует ли уже табель
                if not Timesheet.objects.filter(date=date, employee=employee).exists():
                    # Определяем значение
                    rand_val = random.random()
                    if rand_val < 0.25:  # 25% - выходные/отпуск/больничный
                        value = random.choice(['В', 'О', 'Б', 'Р'])
                    elif rand_val < 0.4:  # 15% - другие коды
                        value = random.choice(['К', 'М', 'Т', 'Н', 'ОС', 'Г', 'ДМ', 'А'])
                    elif rand_val < 0.5:  # 10% - простои/прогулы
                        value = random.choice(['П', 'ЦП'])
                    else:  # 50% - рабочие часы
                        value = random.choice(hour_values)
                    
                    # Определяем день недели (0=понедельник, 6=воскресенье)
                    weekday = date.weekday()
                    
                    # Выходные дни
                    if weekday >= 5:  # Суббота и воскресенье
                        value = 'В'  # Выходной
                    
                    # Определяем статус в зависимости от давности
                    days_ago = (today - date).days
                    if days_ago > 30:  # Старые табели (старше месяца)
                        status = 'approved'
                        approved_by = random.choice(planners)
                        approved_at = date + timedelta(days=random.randint(1, 5))
                    elif days_ago > 7:  # Табели старше недели
                        status = random.choice(['submitted', 'approved'])
                        approved_by = random.choice(planners) if status == 'approved' else None
                        approved_at = date + timedelta(days=random.randint(1, 3)) if status == 'approved' else None
                    else:  # Свежие табели
                        status = random.choice(['draft', 'submitted', 'approved'])
                        approved_by = random.choice(planners) if status == 'approved' else None
                        approved_at = date + timedelta(days=random.randint(0, 2)) if status == 'approved' else None
                    
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
                    created_count += 1
    
    # Подсчет созданных табелей
    total_timesheets = Timesheet.objects.count()
    approved_timesheets = Timesheet.objects.filter(status='approved').count()
    submitted_timesheets = Timesheet.objects.filter(status='submitted').count()
    draft_timesheets = Timesheet.objects.filter(status='draft').count()
    
    print(f"   ✓ Создано табелей: {total_timesheets}")
    print(f"     - Утверждено: {approved_timesheets}")
    print(f"     - Сдано: {submitted_timesheets}")
    print(f"     - Черновиков: {draft_timesheets}")
    
    # 5. Создаем месячные табели
    print("\n5. Создание месячных табелей...")
    
    # Создаем месячные табели за последние 3 месяца
    for month_offset in range(3):
        month_date = today.replace(day=1) - timedelta(days=month_offset * 30)
        
        for master in masters:
            # Проверяем, не существует ли уже месячный табель
            if not MonthlyTimesheet.objects.filter(month=month_date, master=master).exists():
                monthly_timesheet = MonthlyTimesheet.objects.create(
                    month=month_date,
                    master=master,
                    created_by=master
                )
                print(f"   ✓ Создан месячный табель: {month_date.strftime('%B %Y')} - {master.get_full_name()}")
    
    # 6. Очищаем табели текущего месяца для тестирования
    print("\n6. Подготовка текущего месяца для тестирования...")
    
    current_year = today.year
    current_month = today.month
    
    # Удаляем табели текущего месяца (чтобы можно было тестировать создание месячного табеля)
    timesheets_current_month = Timesheet.objects.filter(
        date__year=current_year,
        date__month=current_month
    ).count()
    
    Timesheet.objects.filter(
        date__year=current_year,
        date__month=current_month
    ).delete()
    
    print(f"   ✓ Удалено табелей текущего месяца: {timesheets_current_month}")
    print(f"   Теперь можно тестировать создание месячного табеля через интерфейс")
    
    # 7. Статистика
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
    
    print(f"\nРаспределение по мастерам:")
    for i, master in enumerate(masters, 1):
        emp_count = Employee.objects.filter(master=master).count()
        emp_active = Employee.objects.filter(master=master, is_active=True).count()
        print(f"  Мастер {i} ({master.get_full_name()}): {emp_count} сотрудников ({emp_active} активных)")
    
    print(f"\nОтделы: {Department.objects.count()}")
    
    print(f"\nТабели: {total_timesheets}")
    print(f"  За последние 30 дней: {Timesheet.objects.filter(date__gte=today - timedelta(days=30)).count()}")
    print(f"  За последние 7 дней: {Timesheet.objects.filter(date__gte=today - timedelta(days=7)).count()}")
    
    print(f"\nМесячные табели: {MonthlyTimesheet.objects.count()}")
    
    print("\n" + "=" * 60)
    print("ДОСТУП ДЛЯ ТЕСТИРОВАНИЯ:")
    print("=" * 60)
    
    print("\nАдминистратор:")
    print("  Логин: admin")
    print("  Пароль: admin123")
    print("  Роль: Администратор системы")
    
    print("\nМастера:")
    for i, master in enumerate(masters, 1):
        dept_name = master.department.name if master.department else "Без отдела"
        print(f"  Мастер {i}:")
        print(f"    Логин: {master.username}")
        print(f"    Пароль: master123")
        print(f"    Отдел: {dept_name}")
        print(f"    Сотрудников: {Employee.objects.filter(master=master).count()}")
    
    print("\nПлановый отдел:")
    for i, planner in enumerate(planners, 1):
        print(f"  Плановик {i}:")
        print(f"    Логин: {planner.username}")
        print(f"    Пароль: planner123")
    
    print("\nОбычные пользователи:")
    for user in regular_users:
        print(f"  {user.position}:")
        print(f"    Логин: {user.username}")
        print(f"    Пароль: user123")
    
    print("\nСотрудники (18 человек):")
    print("  Формат логина: emp_c1_01, emp_c1_02, ..., emp_c3_06")
    print("  Формат пароля: emp001123, emp002123, ..., emp018123")
    
    print("\n" + "=" * 60)
    print("ВОЗМОЖНОСТИ ДЛЯ ТЕСТИРОВАНИЯ:")
    print("=" * 60)
    
    print("\nДля мастера (master_p1/master123):")
    print("1. Управление сотрудниками (добавление, редактирование, удаление)")
    print("2. Создание месячного табеля (текущий месяц очищен)")
    print("3. Массовое редактирование табелей")
    print("4. Просмотр табелей в табличном виде")
    print("5. Сдача табелей на утверждение")
    
    print("\nДля плановика (planner1/planner123):")
    print("1. Утверждение табелей")
    print("2. Просмотр всех табелей")
    print("3. Экспорт данных")
    print("4. Печать табелей")
    
    print("\nДля администратора (admin/admin123):")
    print("1. Полный доступ через Django Admin")
    print("2. Управление всеми пользователями")
    print("3. Настройка системы")
    
    print("\n" + "=" * 60)
    print("ВАЖНО:")
    print("=" * 60)
    print("✓ Текущий месяц очищен для тестирования создания месячного табеля")
    print("✓ Данные созданы за последние 90 дней")
    print("✓ Созданы тестовые месячные табели за последние 3 месяца")
    print("✓ У каждого мастера есть свои сотрудники")
    print("✓ Реализована проверка прав доступа")
    
    print("\n" + "=" * 60)
    print("Следующие шаги:")
    print("=" * 60)
    print("1. Запустите сервер: python manage.py runserver")
    print("2. Откройте http://localhost:8000/timesheet/")
    print("3. Войдите как мастер (master_p1/master123)")
    print("4. Перейдите в раздел 'Мои сотрудники' через меню")
    print("5. Протестируйте добавление новых сотрудников")
    
    print("\n" + "=" * 60)
    
except Exception as e:
    print(f"\n✗ Ошибка: {e}")
    import traceback
    traceback.print_exc()