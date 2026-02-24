from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify
from datetime import datetime, date
from apps.users.models import User, Employee, Department, EmployeeAssignment
from django.db.models import Q
import re
import os

RU_MONTHS = {
    'январь': 1, 'февраль': 2, 'март': 3, 'апрель': 4, 'май': 5, 'июнь': 6,
    'июль': 7, 'август': 8, 'сентябрь': 9, 'октябрь': 10, 'ноябрь': 11, 'декабрь': 12
}

def parse_fio(raw):
    if not raw:
        return "", "", ""
    clean = re.sub(r'\s+', ' ', str(raw)).strip()
    parts = clean.split()
    parts = parts[:3]
    last = parts[0] if len(parts) >= 1 else ""
    first = parts[1] if len(parts) >= 2 else ""
    middle = parts[2] if len(parts) >= 3 else ""
    return last, first, middle

def gen_unique_employee_id(prefix, base):
    base_slug = slugify(base)[:20] if base else ""
    ts = datetime.now().strftime("%Y%m%d%H%M%S%f")[-8:]
    return f"{prefix.upper()}-{base_slug}-{ts}".upper()

def find_or_create_department(name):
    if not name:
        return None
    name = str(name).strip()
    dep = Department.objects.filter(name__iexact=name).first()
    if dep:
        return dep
    code_base = slugify(name).upper()[:8] or "DEP"
    code = code_base
    i = 1
    while Department.objects.filter(code=code).exists():
        code = f"{code_base[:6]}{i:02d}"
        i += 1
    return Department.objects.create(name=name, code=code)

def find_or_create_master(last, first, middle, department=None):
    if not last and not first:
        return None
    qs = User.objects.filter(
        last_name__iexact=last,
        first_name__iexact=first
    )
    if middle:
        qs = qs.filter(middle_name__iexact=middle)
    master = qs.filter(role='master').first()
    if master:
        if department and master.department != department:
            master.department = master.department or department
            master.save(update_fields=['department'])
        return master
    username_base = slugify(f"{last}-{first}-{middle}") or slugify(f"{last}-{first}") or f"master"
    username = username_base
    i = 1
    while User.objects.filter(username=username).exists():
        username = f"{username_base}{i}"
        i += 1
    emp_id = gen_unique_employee_id("M", f"{last}{first}")
    password = User.objects.make_random_password()
    master = User.objects.create_user(
        username=username,
        password=password,
        first_name=first or "",
        last_name=last or "",
        middle_name=middle or "",
        role='master',
        employee_id=emp_id,
        department=department
    )
    return master

def get_month_period_from_filename(filename, year=None, month=None):
    if year and month:
        y = int(year)
        m = int(month)
        start = date(y, m, 1)
        if m == 12:
            end = date(y + 1, 1, 1).fromordinal(date(y + 1, 1, 1).toordinal() - 1)
        else:
            end = date(y, m + 1, 1).fromordinal(date(y, m + 1, 1).toordinal() - 1)
        return start, end
    base = os.path.basename(filename).lower()
    m = None
    y = None
    for name, mi in RU_MONTHS.items():
        if name in base:
            m = mi
            break
    years = re.findall(r'(20\d{2})', base)
    if years:
        y = int(years[0])
    if m and y:
        start = date(y, m, 1)
        if m == 12:
            end = date(y + 1, 1, 1).fromordinal(date(y + 1, 1, 1).toordinal() - 1)
        else:
            end = date(y, m + 1, 1).fromordinal(date(y, m + 1, 1).toordinal() - 1)
        return start, end
    today = date.today()
    return today.replace(day=1), today

class Command(BaseCommand):
    help = "Импорт сотрудников и мастеров из файла табеля Excel (.xls/.xlsx)"

    def add_arguments(self, parser):
        parser.add_argument("filename", type=str, help="Путь к Excel файлу")
        parser.add_argument("--year", type=int, help="Год табеля", default=None)
        parser.add_argument("--month", type=int, help="Месяц табеля (1-12)", default=None)
        parser.add_argument("--sheet", type=str, help="Имя листа", default=None)
        parser.add_argument("--header", type=int, help="Номер строки заголовка (0-индекс)", default=0)

    def handle(self, *args, **options):
        filename = options["filename"]
        year = options.get("year")
        month = options.get("month")
        sheet_name = options.get("sheet")
        header = options.get("header", 0)
        try:
            import pandas as pd
        except Exception as e:
            raise CommandError("Требуется библиотека pandas для импорта")
        engine = None
        if filename.lower().endswith(".xls"):
            engine = "xlrd"
        try:
            if sheet_name is None:
                sheet_name = 0
            df = pd.read_excel(filename, header=header, sheet_name=sheet_name, engine=engine)
        except Exception as e:
            raise CommandError(f"Не удалось прочитать файл: {e}")
        cols = list(df.columns)
        if len(cols) < 5:
            raise CommandError("Ожидалось минимум 5 колонок: табельный, ФИО, отдел, должность, ФИО мастера")
        start_date, end_date = get_month_period_from_filename(filename, year, month)
        created_users = []
        created_employees = 0
        created_assignments = 0
        with transaction.atomic():
            for i, row in df.iterrows():
                try:
                    employee_id_val = str(row.iloc[0]).strip() if not pd.isna(row.iloc[0]) else ""
                    fio_val = str(row.iloc[1]).strip() if not pd.isna(row.iloc[1]) else ""
                    department_val = str(row.iloc[2]).strip() if not pd.isna(row.iloc[2]) else ""
                    position_val = str(row.iloc[3]).strip() if not pd.isna(row.iloc[3]) else ""
                    master_raw = str(row.iloc[4]).strip() if not pd.isna(row.iloc[4]) else ""
                    if not employee_id_val and not fio_val:
                        continue
                    dep = find_or_create_department(department_val) if department_val else None
                    m_last, m_first, m_middle = parse_fio(master_raw)
                    master_user = find_or_create_master(m_last, m_first, m_middle, dep)
                    e_user = None
                    if employee_id_val:
                        e_user = User.objects.filter(employee_id=employee_id_val).first()
                    if e_user:
                        emp, _ = Employee.objects.get_or_create(user=e_user, defaults={"is_active": True})
                        if dep and e_user.department != dep:
                            e_user.department = e_user.department or dep
                            e_user.save(update_fields=['department'])
                    else:
                        e_last, e_first, e_middle = parse_fio(fio_val)
                        emp, created = Employee.objects.get_or_create(
                            user=None,
                            employee_id_own=employee_id_val or gen_unique_employee_id("E", f"{e_last}{e_first}"),
                            defaults={
                                "last_name": e_last,
                                "first_name": e_first,
                                "middle_name": e_middle,
                                "position_own": position_val or "",
                                "department_own": dep,
                                "is_active": True
                            }
                        )
                        if created:
                            created_employees += 1
                        else:
                            if position_val and not emp.position_own:
                                emp.position_own = position_val
                            if dep and not emp.department_own:
                                emp.department_own = dep
                            emp.save()
                    if position_val:
                        if emp.user and not emp.user.position:
                            emp.user.position = position_val
                            emp.user.save(update_fields=['position'])
                        elif not emp.user and not emp.position_own:
                            emp.position_own = position_val
                            emp.save(update_fields=['position_own'])
                    if master_user:
                        overlap = EmployeeAssignment.objects.filter(employee=emp, master=master_user).filter(
                            Q(end_date__isnull=True) | Q(end_date__gte=start_date)
                        ).exists()
                        if not overlap:
                            EmployeeAssignment.objects.create(
                                employee=emp,
                                master=master_user,
                                start_date=start_date,
                                end_date=None
                            )
                            created_assignments += 1
                except Exception as e:
                    raise
        self.stdout.write(self.style.SUCCESS(
            f"Импорт завершён. Сотрудники: +{created_employees}, назначений создано: {created_assignments}."
        ))
