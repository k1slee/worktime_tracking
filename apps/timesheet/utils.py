import csv
from io import StringIO
from datetime import datetime

def generate_csv_report(queryset):
    """Генерация CSV отчета из QuerySet"""
    output = StringIO()
    writer = csv.writer(output, delimiter=';')
    
    # Заголовки
    writer.writerow([
        'Дата', 'Табельный номер', 'ФИО', 'Должность', 'Отдел',
        'Мастер', 'Значение', 'Статус', 'Создано', 'Обновлено', 'Утверждено'
    ])
    
    # Данные
    for timesheet in queryset:
        writer.writerow([
            timesheet.date.strftime('%d.%m.%Y'),
            timesheet.employee.employee_id,
            timesheet.employee.full_name,
            timesheet.employee.position or '',
            str(timesheet.employee.department) if timesheet.employee.department else '',
            timesheet.master.get_full_name(),
            timesheet.display_value,
            timesheet.get_status_display(),
            timesheet.created_at.strftime('%d.%m.%Y %H:%M'),
            timesheet.updated_at.strftime('%d.%m.%Y %H:%M'),
            timesheet.approved_by.get_full_name() if timesheet.approved_by else ''
        ])
    
    return output.getvalue()

def validate_timesheet_value(value):
    """Валидация значения табеля"""
    from .models import Timesheet
    
    allowed_codes = dict(Timesheet.CODE_CHOICES).keys()
    
    if value.isdigit():
        hours = int(value)
        if hours < 1 or hours > 24:
            return False, 'Количество часов должно быть от 1 до 24'
    elif value not in allowed_codes:
        return False, f'Недопустимое условное обозначение. Допустимые: {", ".join(allowed_codes)}'
    
    return True, ''

def get_timesheet_stats(queryset):
    """Получение статистики по табелям"""
    stats = {
        'total': queryset.count(),
        'draft': queryset.filter(status='draft').count(),
        'approved': queryset.filter(status='approved').count(),
        'by_department': {},
        'by_master': {},
    }
    
    return stats

def create_monthly_timesheets(master, year, month, default_value='В', include_weekends=True):
    """Создать табели на весь месяц для всех сотрудников мастера"""
    from .models import Timesheet
    from apps.users.models import Employee
    import calendar
    
    employees = Employee.objects.filter(master=master, is_active=True)
    _, last_day = calendar.monthrange(year, month)
    
    created_count = 0
    
    for employee in employees:
        for day in range(1, last_day + 1):
            date = datetime(year, month, day).date()
            
            # Пропускаем выходные, если не включены
            if not include_weekends and date.weekday() >= 5:
                continue
            
            # Создаем табель, если еще не существует
            if not Timesheet.objects.filter(date=date, employee=employee).exists():
                Timesheet.objects.create(
                    date=date,
                    employee=employee,
                    master=master,
                    value=default_value,
                    status='draft'
                )
                created_count += 1
    
    return created_count

def get_master_employees_with_timesheets(master, date):
    """Получить сотрудников мастера с информацией о табелях на дату"""
    from apps.users.models import Employee
    
    employees = Employee.objects.filter(master=master, is_active=True)
    result = []
    
    for employee in employees:
        timesheet = Timesheet.objects.filter(date=date, employee=employee).first()
        result.append({
            'employee': employee,
            'timesheet': timesheet,
            'has_timesheet': timesheet is not None,
            'can_edit': timesheet.can_edit if timesheet else True
        })
    
    return result