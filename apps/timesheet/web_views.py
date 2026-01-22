from django.urls import reverse_lazy
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.db.models import Q
from django.utils import timezone
import csv
from datetime import datetime, date, timedelta
import calendar
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import ListView, CreateView, UpdateView, DetailView

from .models import MonthlyTimesheet, Timesheet, Holiday
from .forms import MonthlyTimesheetForm, BulkTimesheetForm, TimesheetForm
from apps.users.models import Employee, Department, User
from apps.users.permissions import IsMaster, IsPlanner


# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================

def get_day_value(day_date):
    """Получение кода дня для автозаполнения с правильной логикой предпраздничных дней"""
    # Проверяем, является ли день праздником
    if Holiday.objects.filter(date=day_date, type="holiday").exists():
        return "В"
    
    # Проверяем, является ли день предпраздничным
    next_day = day_date + timedelta(days=1)
    is_next_day_holiday = Holiday.objects.filter(date=next_day, type="holiday").exists()
    
    # Условия для предпраздничного дня:
    # 1. Следующий день должен быть праздником
    # 2. Текущий день должен быть рабочим (пн-пт)
    if is_next_day_holiday and day_date.weekday() in (0, 1, 2, 3, 4):
        return "7"
    
    # Суббота/воскресенье - всегда выходные
    if day_date.weekday() in (5, 6):
        return 'В'
    
    # Все остальные дни - обычные рабочие
    return "8"
def generate_default_table(year: int, month: int) -> dict:
    """
    Автозаполнение табеля с правильной логикой:
    - 'В' для праздников и выходных (сб/вс)
    - '7' для рабочего дня перед праздником (даже если праздник в субботу)
    - '8' для рабочих дней
    """
    default_table = {}
    cal = calendar.Calendar()
    month_days = cal.monthdatescalendar(year, month)
    
    # Получаем все праздники за месяц
    holidays = Holiday.objects.filter(
        date__year=year,
        date__month=month,
        type="holiday"
    ).values_list('date', flat=True)
    
    for week in month_days:
        for day_date in week:
            if day_date.month == month:
                day_number = day_date.day
                
                # Проверяем, является ли день праздником
                if day_date in holidays:
                    default_table[day_number] = "В"
                    continue
                
                # Проверяем, является ли день предпраздничным
                next_day = day_date + timedelta(days=1)
                is_next_day_holiday = next_day in holidays
                
                # Условия для предпраздничного дня:
                # 1. Следующий день - праздник
                # 2. Текущий день - рабочий (пн-пт)
                if is_next_day_holiday and day_date.weekday() in (0, 1, 2, 3, 4):
                    default_table[day_number] = "7"
                    continue
                
                # Суббота/воскресенье - всегда выходные
                if day_date.weekday() in (5, 6):
                    default_table[day_number] = "В"
                    continue
                
                # Все остальные дни - обычные рабочие
                default_table[day_number] = "8"
    
    return default_table

def get_monthly_data(request, year, month, print_mode=False):
    """
    Общая функция для получения данных табеля за месяц.
    print_mode: True - для печатной формы, False - для веб-интерфейса
    """
    # Получаем выбранного мастера/отдел
    master_id = request.GET.get('master')
    department_id = request.GET.get('department')
    master_user = None
    
    # Инициализация переменных
    employees = Employee.objects.none()
    timesheets = Timesheet.objects.none()
    
    # === ЛОГИКА ДЛЯ МАСТЕРА ===
    if request.user.is_master:
        master_user = request.user
        department_id = request.user.department_id

        # Получаем или создаем запись мастера как сотрудника
        Employee.objects.get_or_create(
            user=request.user,
            defaults={
                'master': request.user,
                'hire_date': request.user.date_joined.date() if request.user.date_joined else date.today(),
                'is_active': True
            }
        )

        employees = Employee.objects.filter(
            Q(master=request.user) | Q(user=request.user),
            is_active=True
        ).distinct()

        timesheets = Timesheet.objects.filter(
            date__year=year,
            date__month=month,
            employee__in=employees
        ).select_related('employee', 'employee__user', 'master')

    # === ЛОГИКА ДЛЯ ПЛАНОВИКА И АДМИНИСТРАТОРА ===
    elif request.user.is_planner or request.user.is_administrator:
        employees = Employee.objects.filter(is_active=True)

        if master_id:
            employees = employees.filter(master_id=master_id)

        if print_mode:
            # Для печатной формы - только табели со статусом submitted/approved
            timesheets = Timesheet.objects.filter(
                date__year=year,
                date__month=month,
                employee__in=employees,
                status__in=['submitted', 'approved']
            ).select_related('employee', 'employee__user', 'master')

            if master_id:
                timesheets = timesheets.filter(master_id=master_id)

            employee_ids_from_timesheets = timesheets.values_list('employee_id', flat=True).distinct()
            if employee_ids_from_timesheets:
                employees = employees.filter(id__in=employee_ids_from_timesheets)
        else:
            # Для веб-интерфейса - все табели
            timesheets = Timesheet.objects.filter(
                date__year=year,
                date__month=month,
                employee__in=employees
            ).select_related('employee', 'employee__user', 'master')

        if not master_user and timesheets.exists():
            first_timesheet = timesheets.first()
            if first_timesheet and first_timesheet.master:
                master_user = first_timesheet.master
                department_id = master_user.department_id if master_user else None

    # Упорядочиваем сотрудников
    employees = employees.order_by('user__last_name', 'user__first_name')

    return {
        'employees': employees,
        'timesheets': timesheets,
        'master_user': master_user,
        'department_id': department_id,
    }


def update_statistics(stats, employee_id, day, value_str, is_weekend, 
                     total_hours_formats, evening_formats, night_formats, overtime_formats):
    """Обновление статистики для одного дня"""
    if not value_str:
        return stats
    
    # Подсчет общего количества часов
    if value_str in total_hours_formats:
        hours = total_hours_formats[value_str]
        stats['total_hours'][employee_id] = stats['total_hours'].get(employee_id, 0) + hours
        if is_weekend:
            stats['weekend_hours'][employee_id] = stats['weekend_hours'].get(employee_id, 0) + hours
    elif value_str.replace(',', '', 1).replace('.', '', 1).isdigit():
        try:
            hours = float(value_str.replace(',', '.'))
            if hours > 0:
                stats['total_hours'][employee_id] = stats['total_hours'].get(employee_id, 0) + hours
                if is_weekend:
                    stats['weekend_hours'][employee_id] = stats['weekend_hours'].get(employee_id, 0) + hours
        except (ValueError, TypeError):
            pass
    
    # Вечерние часы
    if value_str in evening_formats:
        stats['evening_hours'][employee_id] = stats['evening_hours'].get(employee_id, 0) + 6.5
    
    # Ночные часы
    if value_str in night_formats:
        stats['night_hours'][employee_id] = stats['night_hours'].get(employee_id, 0) + night_formats[value_str]
    
    # Сверхурочные часы
    if value_str in overtime_formats:
        stats['overtime_hours'][employee_id] = stats['overtime_hours'].get(employee_id, 0) + overtime_formats[value_str]
    
    # Подсчет категорий
    if value_str not in ['В', 'О', 'Б', 'К', 'ЦП', 'П', 'Н', 'ОС', 'Р', 'Г', 'ДМ', 'ОЖ', 'А']:
        stats['attendance'][employee_id] = stats['attendance'].get(employee_id, 0) + 1
    
    # Маппинг категорий
    category_map = {
        'ЦП': 'downtime',
        'О': 'vacation',
        'Б': 'illness',
        'Р': 'illness',
        'П': 'absence',
        'Г': 'other_absence',
        'ДМ': 'other_absence',
        'ОЖ': 'other_absence',
        'ОС': 'other_absence',
        'А': 'admin_permission',
    }
    
    if value_str in category_map:
        key = category_map[value_str]
        stats[key][employee_id] = stats[key].get(employee_id, 0) + 1
    
    return stats


def process_timesheet_data(request, year, month, employees, timesheets):
    """Обработка данных табелей и подсчет статистики"""
    days_in_month = calendar.monthrange(year, month)[1]
    days = list(range(1, days_in_month + 1))
    
    # Генерируем данные по выходным и автозаполнению
    weekend_days_dict = {}
    default_table = generate_default_table(year, month)
    
    for day in days:
        day_date = date(year, month, day)
        weekend_days_dict[day] = Holiday.objects.filter(
            date=day_date, type="holiday"
        ).exists() or day_date.weekday() in (5, 6)
    
    # Подготовка словарей для статистики
    stats = {
        'attendance': {},
        'downtime': {},
        'vacation': {},
        'illness': {},
        'other_absence': {},
        'admin_permission': {},
        'absence': {},
        'evening_hours': {},
        'night_hours': {},
        'weekend_hours': {},
        'overtime_hours': {},
        'total_hours': {},
    }
    
    # Форматы для подсчета часов
    total_hours_formats = {
        '7/3': 7.0, '7/2': 7.0, '8/2': 8.0, '8': 8.0, '7': 7.0,
        '4': 4.0, '10': 10.0, '10/2': 10.0, '3,5': 3.5, '9': 9.0,
        '9/2': 9.0, '6': 6.0, '6/2': 6.0, '5': 5.0, '5/2': 5.0,
    }
    
    evening_formats = ['8/2', '7/2', '9/2', '10/2', '6/2']
    night_formats = {'7/3': 7.0, '8/2': 1.5, '9/2': 1.5, '10/2': 1.5, '6/2': 1.5}
    overtime_formats = {'9': 1, '10': 2, '9/2': 1, '10/2': 2}
    
    # Группировка табелей по сотрудникам
    timesheet_dict = {}
    for ts in timesheets:
        if ts.employee_id not in timesheet_dict:
            timesheet_dict[ts.employee_id] = {}
        timesheet_dict[ts.employee_id][ts.date.day] = {
            'id': ts.id,
            'value': ts.value,
            'display_value': ts.display_value,  # Используем свойство модели
            'status': ts.status,
            'css_class': ts.css_class,  # Используем свойство модели
            'can_edit': ts.can_edit,  # Используем свойство модели
        }
    
    # Формирование таблицы и подсчет статистики
    table_data = []
    
    for employee in employees:
        employee_id = employee.id
        employee_timesheets = timesheet_dict.get(employee_id, {})
        
        # Ячейки дней
        day_cells = []
        for day in days:
            day_date = date(year, month, day)
            ts_data = employee_timesheets.get(day)
            holiday_value = get_day_value(day_date)
            
            if ts_data:
                display_value = (
                    ts_data.get('display_value') or 
                    ts_data.get('value') or 
                    holiday_value or 
                    default_table.get(day, "")
                )
                day_cells.append({
                    'day': day,
                    'timesheet_id': ts_data.get('id'),
                    'value': ts_data.get('value', ''),
                    'display_value': display_value,
                    'status': ts_data.get('status', 'draft'),
                    'can_edit': ts_data.get('can_edit', False),
                    'css_class': ts_data.get('css_class', 'draft'),
                })
            else:
                display_value = holiday_value or default_table.get(day, "")
                day_cells.append({
                    'day': day,
                    'timesheet_id': None,
                    'value': '',
                    'display_value': display_value,
                    'status': 'empty',
                    'can_edit': request.user.is_master,
                    'css_class': 'empty',
                })
            
            # Подсчет статистики для этого дня
            value_str = day_cells[-1]['value'] or day_cells[-1]['display_value']
            stats = update_statistics(
                stats, employee_id, day, value_str, weekend_days_dict.get(day, False),
                total_hours_formats, evening_formats, night_formats, overtime_formats
            )
        
        # Проверяем, есть ли данные у сотрудника
        row_has_timesheets = any(cell['timesheet_id'] for cell in day_cells)
        
        table_data.append({
            'employee': employee,
            'days': day_cells,
            'employee_id': employee_id,
            'row_status': 'has_data' if row_has_timesheets else 'empty',
            'attendance_days': stats.get('attendance', {}).get(employee_id, 0),
            'downtime_days': stats.get('downtime', {}).get(employee_id, 0),
            'vacation_days': stats.get('vacation', {}).get(employee_id, 0),
            'illness_days': stats.get('illness', {}).get(employee_id, 0),
            'other_absence_days': stats.get('other_absence', {}).get(employee_id, 0),
            'admin_permission_days': stats.get('admin_permission', {}).get(employee_id, 0),
            'absence_days': stats.get('absence', {}).get(employee_id, 0),
            'total_hours': round(stats.get('total_hours', {}).get(employee_id, 0), 1),
            'evening_hours': round(stats.get('evening_hours', {}).get(employee_id, 0), 1),
            'night_hours': round(stats.get('night_hours', {}).get(employee_id, 0), 1),
            'weekend_hours': round(stats.get('weekend_hours', {}).get(employee_id, 0), 1),
            'overtime_hours': round(stats.get('overtime_hours', {}).get(employee_id, 0), 1),
        })
    
    return {
        'table_data': table_data,
        'days': days,
        'days_in_month': days_in_month,
        'weekend_days': weekend_days_dict,
        'default_table': default_table,
    }

def get_shop_chief_name(request, master_user=None, department_id=None):
    """Получение имени начальника цеха"""
    default_name = "С.В. Ефременко"
    
    if master_user and master_user.department and master_user.department.shop_chief_name:
        return master_user.department.shop_chief_name
    
    if department_id:
        try:
            department = Department.objects.get(id=department_id)
            if department.shop_chief_name:
                return department.shop_chief_name
        except Department.DoesNotExist:
            pass
    
    if request.user.is_master and request.user.department and request.user.department.shop_chief_name:
        return request.user.department.shop_chief_name
    
    return default_name


def get_composer_fio(master_user):
    """Получение ФИО составителя табеля"""
    default_name = "Н.А. Долгошей"
    
    if not master_user:
        return default_name
    
    full_name = master_user.get_full_name()
    if not full_name:
        return default_name
    
    parts = full_name.split()
    if len(parts) >= 3:
        last_name = parts[0]
        first_initial = parts[1][0] + '.' if parts[1] else ''
        middle_initial = parts[2][0] + '.' if len(parts) > 2 and parts[2] else ''
        return f"{first_initial}{middle_initial} {last_name}"
    elif len(parts) == 2:
        last_name = parts[0]
        first_initial = parts[1][0] + '.' if parts[1] else ''
        return f"{first_initial} {last_name}"
    
    return full_name


# ==================== ОСНОВНЫЕ VIEW ФУНКЦИИ ====================

@login_required
def monthly_table_view(request):
    """Табличное представление табеля за месяц"""
    # Получаем параметры месяца
    today = timezone.now().date()
    
    try:
        year = int(request.GET.get('year', today.year))
        month = int(request.GET.get('month', today.month))
    except (ValueError, TypeError):
        year = today.year
        month = today.month
    
    # Получаем данные
    data = get_monthly_data(request, year, month, print_mode=False)
    
    if not data['employees'].exists():
        messages.info(request, 'Нет данных для отображения')
        return render(request, 'timesheet/monthly_table.html', {
            'title': f'Табель за {month:02d}.{year}',
            'year': year,
            'month': month,
            'table_data': [],
        })
    
    # Обрабатываем данные табелей
    processed_data = process_timesheet_data(request, year, month, data['employees'], data['timesheets'])
    
    # Подготовка контекста
    departments = []
    masters = []
    
    if request.user.is_planner or request.user.is_administrator:
        departments = Department.objects.all()
        masters = User.objects.filter(role='master', is_active=True).order_by('last_name', 'first_name')
    
    # Навигация по месяцам
    prev_month = month - 1 if month > 1 else 12
    prev_year = year if month > 1 else year - 1
    next_month = month + 1 if month < 12 else 1
    next_year = year if month < 12 else year + 1
    
    context = {
        'title': f'Табель за {month:02d}.{year}',
        'year': year,
        'month': month,
        'month_name': f'{month:02d}.{year}',
        'departments': departments,
        'masters': masters,
        'selected_department': request.GET.get('department'),
        'selected_master': request.GET.get('master'),
        'prev_month': prev_month,
        'prev_year': prev_year,
        'next_month': next_month,
        'next_year': next_year,
        'is_master': request.user.is_master,
        'is_planner': request.user.is_planner,
        'is_admin': request.user.is_administrator,
        'total_employees': data['employees'].count(),
        'shop_chief_name': get_shop_chief_name(request, data['master_user'], data['department_id']),
        **processed_data,
    }
    
    return render(request, 'timesheet/monthly_table.html', context)


@login_required
def print_monthly_table(request):
    """Печатная форма табеля за месяц"""
    # Получаем параметры месяца
    today = timezone.now().date()
    
    try:
        year = int(request.GET.get('year', today.year))
        month = int(request.GET.get('month', today.month))
    except (ValueError, TypeError):
        year = today.year
        month = today.month
    
    # Получаем данные (в режиме печати)
    data = get_monthly_data(request, year, month, print_mode=True)
    
    if not data['employees'].exists():
        messages.info(request, 'Нет данных для печати')
        return redirect('timesheet:monthly-table')
    
    # Обрабатываем данные табелей
    processed_data = process_timesheet_data(request, year, month, data['employees'], data['timesheets'])
    
    context = {
        'title': f'Табель за {month:02d}.{year}',
        'year': year,
        'month': month,
        'shop_chief_name': get_shop_chief_name(request, data['master_user'], data['department_id']),
        'composer_fio': get_composer_fio(data['master_user']),
        'is_master': request.user.is_master,
        'is_planner': request.user.is_planner,
        'is_admin': request.user.is_administrator,
        **processed_data,
    }
    
    return render(request, 'timesheet/print_monthly_table.html', context)


@login_required
def monthly_create_view(request):
    """Создание табелей на весь месяц"""
    if not request.user.is_master:
        messages.error(request, 'Только мастера могут создавать месячные табели')
        return redirect('timesheet:list')
    
    if request.method == 'POST':
        form = MonthlyTimesheetForm(request.POST, user=request.user)
        if form.is_valid():
            try:
                created_count = form.create_monthly_timesheet()
                messages.success(
                    request, 
                    f'Создано {created_count} записей табеля на месяц {form.cleaned_data["month"].strftime("%B %Y")}'
                )
                return redirect('timesheet:list')
            except Exception as e:
                messages.error(request, f'Ошибка при создании табелей: {str(e)}')
    else:
        form = MonthlyTimesheetForm(user=request.user)
    
    return render(request, 'timesheet/monthly_create.html', {
        'form': form,
        'title': 'Создание месячного табеля'
    })


@login_required
def bulk_edit_view(request):
    """Массовое редактирование табелей"""
    if not request.user.is_master:
        messages.error(request, 'Только мастера могут редактировать табели')
        return redirect('timesheet:list')
    
    if request.method == 'POST':
        form = BulkTimesheetForm(request.POST, user=request.user)
        if form.is_valid():
            try:
                updated_count = form.update_timesheets()
                messages.success(
                    request,
                    f'Обновлено {updated_count} записей табеля'
                )
                return redirect('timesheet:list')
            except Exception as e:
                messages.error(request, f'Ошибка при обновлении табелей: {str(e)}')
    else:
        form = BulkTimesheetForm(user=request.user)
    
    # Получаем информацию о выбранных сотрудниках
    employee_info = []
    if request.GET.get('employee_ids'):
        ids = [int(id) for id in request.GET.get('employee_ids').split(',') if id]
        
        # Включаем мастера в выборку
        employees = Employee.objects.filter(
            Q(id__in=ids) & (Q(master=request.user) | Q(user=request.user))
        )
        
        employee_info = [
            {'id': emp.id, 'name': emp.full_name, 'employee_id': emp.employee_id}
            for emp in employees
        ]
    
    return render(request, 'timesheet/bulk_edit.html', {
        'form': form,
        'employee_info': employee_info,
        'title': 'Массовое редактирование табелей'
    })


class TimesheetListView(LoginRequiredMixin, ListView):
    """Список табелей для веб-интерфейса"""
    model = Timesheet
    template_name = 'timesheet/timesheet_list.html'
    context_object_name = 'timesheets'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = Timesheet.objects.all()
        user = self.request.user
        
        if user.is_master:
            queryset = queryset.filter(master=user)
        
        # Фильтрация по параметрам
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')
        status = self.request.GET.get('status')
        master_id = self.request.GET.get('master')
        department_id = self.request.GET.get('department')
        
        if date_from:
            queryset = queryset.filter(date__gte=date_from)
        if date_to:
            queryset = queryset.filter(date__lte=date_to)
        if status and status != 'all':
            queryset = queryset.filter(status=status)
        if master_id and (user.is_planner or user.is_administrator):
            queryset = queryset.filter(master_id=master_id)
        if department_id and (user.is_planner or user.is_administrator):
            queryset = queryset.filter(employee__department_id=department_id)
        
        return queryset.select_related(
            'employee', 'employee__user', 'master', 'approved_by'
        ).order_by('-date', 'employee__user__last_name')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_master'] = self.request.user.is_master
        context['is_planner'] = self.request.user.is_planner
        context['is_admin'] = self.request.user.is_administrator
        
        # Для фильтров
        from apps.users.models import User, Department
        context['masters'] = User.objects.filter(role='master') if (self.request.user.is_planner or self.request.user.is_administrator) else []
        context['departments'] = Department.objects.all() if (self.request.user.is_planner or self.request.user.is_administrator) else []
        
        return context


class TimesheetCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """Создание табеля"""
    model = Timesheet
    form_class = TimesheetForm
    template_name = 'timesheet/timesheet_form.html'
    success_url = reverse_lazy('timesheet:list')
    
    def test_func(self):
        # Только мастера могут создавать табели
        return self.request.user.is_master
    
    def form_valid(self, form):
        form.instance.master = self.request.user
        messages.success(self.request, 'Табель успешно создан')
        return super().form_valid(form)
    
    def form_invalid(self, form):
        messages.error(self.request, 'Пожалуйста, исправьте ошибки в форме')
        return super().form_invalid(form)
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Создание табеля'
        return context


class TimesheetUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """Редактирование табеля"""
    model = Timesheet
    form_class = TimesheetForm
    template_name = 'timesheet/timesheet_form.html'
    success_url = reverse_lazy('timesheet:list')
    
    def test_func(self):
        # Проверка прав на редактирование
        timesheet = self.get_object()
        return timesheet.can_edit and (
            self.request.user.is_master and timesheet.master == self.request.user or
            self.request.user.is_planner or
            self.request.user.is_administrator
        )
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        messages.success(self.request, 'Табель успешно обновлен')
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Редактирование табеля'
        return context


class TimesheetDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """Просмотр табеля"""
    model = Timesheet
    template_name = 'timesheet/timesheet_detail.html'
    context_object_name = 'timesheet'
    
    def test_func(self):
        # Проверка прав на просмотр
        timesheet = self.get_object()
        user = self.request.user
        
        if user.is_administrator or user.is_planner:
            return True
        if user.is_master:
            return timesheet.master == user
        return False


@login_required
def approve_timesheet(request, pk):
    """Утверждение табеля"""
    timesheet = get_object_or_404(Timesheet, pk=pk)
    
    if not request.user.is_planner and not request.user.is_administrator:
        messages.error(request, 'У вас нет прав для утверждения табелей')
        return redirect('timesheet:list')
    
    if timesheet.is_approved:
        messages.warning(request, 'Табель уже утвержден')
        return redirect('timesheet:detail', pk=pk)
    
    timesheet.status = 'approved'
    timesheet.approved_by = request.user
    timesheet.approved_at = datetime.now()
    timesheet.save()
    
    messages.success(request, 'Табель успешно утвержден')
    return redirect('timesheet:detail', pk=pk)


@login_required
def bulk_approve_view(request):
    """Массовое утверждение табелей"""
    if not request.user.is_planner and not request.user.is_administrator:
        messages.error(request, 'У вас нет прав для массового утверждения')
        return redirect('timesheet:list')
    
    if request.method == 'POST':
        timesheet_ids = request.POST.getlist('timesheet_ids')
        action = request.POST.get('action')
        
        if not timesheet_ids:
            messages.error(request, 'Не выбраны табели для обработки')
            return redirect('timesheet:list')
        
        queryset = Timesheet.objects.filter(id__in=timesheet_ids)
        
        if action == 'approve':
            updated = queryset.filter(status='draft').update(
                status='approved',
                approved_by=request.user,
                approved_at=datetime.now()
            )
            messages.success(request, f'Утверждено табелей: {updated}')
        elif action == 'unapprove':
            updated = queryset.filter(status='approved').update(
                status='draft',
                approved_by=None,
                approved_at=None
            )
            messages.success(request, f'Снято с утверждения табелей: {updated}')
    
    return redirect('timesheet:list')


@login_required
def export_view(request):
    """Экспорт табелей в CSV"""
    if not request.user.is_planner and not request.user.is_administrator:
        messages.error(request, 'У вас нет прав для экспорта')
        return redirect('timesheet:list')
    
    if request.method == 'POST':
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        master_id = request.POST.get('master')
        department_id = request.POST.get('department')
        status = request.POST.get('status', 'all')
        
        queryset = Timesheet.objects.all()
        
        if start_date:
            queryset = queryset.filter(date__gte=start_date)
        if end_date:
            queryset = queryset.filter(date__lte=end_date)
        if master_id:
            queryset = queryset.filter(master_id=master_id)
        if department_id:
            queryset = queryset.filter(employee__user__department_id=department_id)
        if status != 'all':
            queryset = queryset.filter(status=status)
        
        # Генерация CSV
        csv_data = generate_csv_report(queryset)
        
        response = HttpResponse(csv_data, content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="timesheet_export_{datetime.now():%Y%m%d_%H%M%S}.csv"'
        
        return response
    
    # GET запрос - показываем форму
    from apps.users.models import User, Department
    masters = User.objects.filter(role='master')
    departments = Department.objects.all()
    
    return render(request, 'timesheet/export.html', {
        'masters': masters,
        'departments': departments
    })


def generate_csv_report(queryset):
    """Генерация CSV отчета"""
    import csv
    from io import StringIO
    
    output = StringIO()
    writer = csv.writer(output)
    
    # Заголовок
    writer.writerow([
        'ID', 'Дата', 'Табельный номер', 'Сотрудник', 'Значение',
        'Статус', 'Мастер', 'Утверждено', 'Утвердил', 'Дата утверждения'
    ])
    
    # Данные
    for ts in queryset.select_related('employee', 'employee__user', 'master', 'approved_by'):
        writer.writerow([
            ts.id,
            ts.date.strftime('%d.%m.%Y'),
            ts.employee.employee_id,
            ts.employee.full_name,
            ts.value,
            ts.get_status_display(),
            ts.master.get_full_name() if ts.master else '',
            'Да' if ts.is_approved else 'Нет',
            ts.approved_by.get_full_name() if ts.approved_by else '',
            ts.approved_at.strftime('%d.%m.%Y %H:%M') if ts.approved_at else ''
        ])
    
    return output.getvalue()


@login_required
def quick_edit_timesheet(request):
    """Быстрое редактирование дневного табеля через AJAX"""
    if not request.method == 'POST' or not request.user.is_authenticated:
        return JsonResponse({'error': 'Неверный запрос'}, status=400)
    
    timesheet_id = request.POST.get('timesheet_id')
    monthly_timesheet_id = request.POST.get('monthly_timesheet_id')
    employee_id = request.POST.get('employee_id')
    date_str = request.POST.get('date')
    value = request.POST.get('value', '').strip()
    action = request.POST.get('action', 'save')
    
    try:
        from apps.users.models import Employee
        from .models import MonthlyTimesheet, Timesheet
        
        if action == 'delete':
            # Удаление табеля
            if not timesheet_id:
                return JsonResponse({'error': 'Не указан ID табеля'}, status=400)
            
            timesheet = Timesheet.objects.get(id=timesheet_id)
            
            # Проверка прав
            if not timesheet.can_edit:
                return JsonResponse({'error': 'Нельзя удалить сданный или утвержденный табель'}, status=403)
            
            if request.user.is_master and timesheet.master != request.user:
                return JsonResponse({'error': 'Нет прав на удаление этого табеля'}, status=403)
            
            timesheet.delete()
            
            return JsonResponse({'success': True})
        
        # Сохранение или создание
        if timesheet_id:
            # Редактирование существующего табеля
            timesheet = Timesheet.objects.get(id=timesheet_id)
            
            # Проверка прав
            if not timesheet.can_edit:
                return JsonResponse({'error': 'Табель сдан или утвержден и не может быть изменен'}, status=403)
            
            if request.user.is_master and timesheet.master != request.user:
                return JsonResponse({'error': 'Нет прав на редактирование этого табеля'}, status=403)
            
            # Если значение пустое, удаляем запись
            if not value:
                timesheet.delete()
                return JsonResponse({'success': True, 'deleted': True})
            
            timesheet.value = value
            timesheet.save()
            
        else:
            # Создание новой записи
            if not date_str or not employee_id:
                return JsonResponse({'error': 'Не указаны обязательные параметры'}, status=400)
            
            date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
            employee = Employee.objects.get(id=employee_id)
            
            # Проверка прав для мастера
            if request.user.is_master and employee.master != request.user:
                return JsonResponse({'error': 'Нет прав на создание табеля для этого сотрудника'}, status=403)
            
            # Если значение пустое, ничего не делаем
            if not value:
                return JsonResponse({'success': True})
            
            # Проверяем, не существует ли уже запись на эту дату
            timesheet, created = Timesheet.objects.get_or_create(
                date=date_obj,
                employee=employee,
                defaults={
                    'master': employee.master,
                    'value': value,
                    'status': 'draft'
                }
            )
            
            if not created and not timesheet.can_edit:
                return JsonResponse({'error': 'Запись уже существует и табель сдан или утвержден'}, status=403)
            
            if not created:
                timesheet.value = value
                timesheet.save()
        
        return JsonResponse({
            'success': True,
            'display_value': timesheet.display_value,
            'value': timesheet.value,
            'id': timesheet.id,
            'status': timesheet.status,
            'can_edit': timesheet.can_edit
        })
        
    except Timesheet.DoesNotExist:
        return JsonResponse({'error': 'Табель не найден'}, status=404)
    except Employee.DoesNotExist:
        return JsonResponse({'error': 'Сотрудник не найден'}, status=404)
    except Exception as e:
        import traceback
        return JsonResponse({'error': str(e), 'traceback': traceback.format_exc()}, status=500)


@login_required
def submit_timesheet(request, pk):
    """Сдать табель мастером"""
    timesheet = get_object_or_404(Timesheet, pk=pk)
    
    if not request.user.is_master:
        return JsonResponse({'error': 'Только мастера могут сдавать табели'}, status=403)
    
    if timesheet.master != request.user:
        return JsonResponse({'error': 'Вы можете сдавать только свои табели'}, status=403)
    
    try:
        timesheet.submit(request.user)
        
        # Логирование
        import logging
        logger = logging.getLogger('apps')
        logger.info(f'Табель {timesheet.id} сдан мастером {request.user}')
        
        return JsonResponse({'success': True})
        
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required
def bulk_submit_view(request):
    """Массовая сдача табелей"""
    if not request.user.is_master:
        messages.error(request, 'Только мастера могут сдавать табели')
        return redirect('timesheet:list')
    
    if request.method == 'POST':
        timesheet_ids = request.POST.getlist('timesheet_ids')
        action = request.POST.get('action')
        
        if not timesheet_ids:
            messages.error(request, 'Не выбраны табели для обработки')
            return redirect('timesheet:list')
        
        queryset = Timesheet.objects.filter(
            id__in=timesheet_ids,
            master=request.user,
            status='draft'
        )
        
        if action == 'submit':
            updated_count = 0
            for timesheet in queryset:
                try:
                    timesheet.submit(request.user)
                    updated_count += 1
                except ValueError:
                    pass
            
            messages.success(request, f'Сдано табелей: {updated_count}')
        
        elif action == 'unsubmit':
            # Возврат в черновики (только если не утверждено)
            updated = queryset.filter(
                status='submitted'
            ).update(
                status='draft',
                submitted_by=None,
                submitted_at=None
            )
            messages.success(request, f'Возвращено в черновики: {updated}')
    
    return redirect('timesheet:list')


@login_required
def submit_month(request):
    """Сдать все табели за месяц"""
    if not request.user.is_master:
        return JsonResponse({'error': 'Только мастера могут сдавать табели'}, status=403)
    
    year = request.GET.get('year')
    month = request.GET.get('month')
    
    if not year or not month:
        return JsonResponse({'error': 'Не указан месяц'}, status=400)
    
    try:
        year = int(year)
        month = int(month)
        
        # Получаем все табели мастера за месяц
        timesheets = Timesheet.objects.filter(
            master=request.user,
            date__year=year,
            date__month=month,
            status='draft'
        )
        
        submitted_count = 0
        for timesheet in timesheets:
            try:
                timesheet.submit(request.user)
                submitted_count += 1
            except ValueError:
                pass
        
        return JsonResponse({
            'success': True,
            'submitted_count': submitted_count,
            'message': f'Сдано {submitted_count} табелей'
        })
        
    except (ValueError, TypeError) as e:
        return JsonResponse({'error': 'Ошибка в параметрах месяца'}, status=400)