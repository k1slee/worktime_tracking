from django.urls import reverse_lazy
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.db.models import Q
from django.utils import timezone
import csv
from datetime import datetime
import calendar
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import ListView, CreateView, UpdateView, DetailView
from .models import MonthlyTimesheet, Timesheet
from .forms import MonthlyTimesheetForm, BulkTimesheetForm, TimesheetForm
from apps.users.models import Employee, Department
from apps.users.permissions import IsMaster, IsPlanner
from django.utils import timezone
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from apps.users.models import User, Employee, Department
from .models import Timesheet
import calendar
from django.db.models import Q
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
        # Получаем выбранных сотрудников из GET параметра
        employee_info = []
    if request.GET.get('employee_ids'):
        from apps.users.models import Employee
        from django.db.models import Q
        ids = [int(id) for id in request.GET.get('employee_ids').split(',') if id]
        
        # Включаем мастера в выборку
        employees = Employee.objects.filter(
            Q(id__in=ids) & (Q(master=request.user) | Q(user=request.user))
        )
        
        employee_info = [
            {'id': emp.id, 'name': emp.full_name, 'employee_id': emp.employee_id}
            for emp in employees
        ]
    
    # Получаем информацию о выбранных сотрудниках
    employee_info = []
    if request.GET.get('employee_ids'):
        from apps.users.models import Employee
        ids = [int(id) for id in request.GET.get('employee_ids').split(',') if id]
        employees = Employee.objects.filter(id__in=ids, master=request.user)
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
def print_monthly_table(request):
    """Печатная форма табеля за месяц"""
    # Получаем параметры месяца (та же логика, что и в monthly_table_view)
    today = timezone.now().date()
    
    try:
        year = int(request.GET.get('year', today.year))
        month = int(request.GET.get('month', today.month))
    except (ValueError, TypeError):
        year = today.year
        month = today.month
    
    # Инициализация переменных
    employees = Employee.objects.none()
    timesheets = Timesheet.objects.none()
    
    # === ЛОГИКА ДЛЯ МАСТЕРА ===
    if request.user.is_master:
        # 1. Получаем или создаем запись мастера как сотрудника
        master_employee, created = Employee.objects.get_or_create(
            user=request.user,
            defaults={
                'master': request.user,
                'hire_date': request.user.date_joined.date() if request.user.date_joined else today,
                'is_active': True
            }
        )
        
        # 2. Получаем всех сотрудников мастера (включая самого мастера)
        employees = Employee.objects.filter(
            Q(master=request.user) | Q(user=request.user),
            is_active=True
        ).distinct()
        
        # 3. Получаем ВСЕ табели сотрудников мастера
        timesheets = Timesheet.objects.filter(
            date__year=year,
            date__month=month,
            employee__in=employees
        ).select_related('employee', 'employee__user', 'master')
    
    # === ЛОГИКА ДЛЯ ПЛАНОВИКА И АДМИНИСТРАТОРА ===
    elif request.user.is_planner or request.user.is_administrator:
        department_id = request.GET.get('department')
        master_id = request.GET.get('master')
        
        # 1. Получаем ВСЕХ сотрудников (для списка)
        employees = Employee.objects.filter(is_active=True)
        
        # 2. Применяем фильтры к сотрудникам
        if department_id:
            employees = employees.filter(user__department_id=department_id)
        if master_id:
            employees = employees.filter(master_id=master_id)
        
        employees = employees.order_by('user__last_name', 'user__first_name')
        
        # 3. Получаем утвержденные табели
        timesheets = Timesheet.objects.filter(
            date__year=year,
            date__month=month,
            employee__in=employees,
            status__in=['submitted', 'approved']
        ).select_related('employee', 'employee__user', 'master')
        
        # 4. Применяем те же фильтры к табелям
        if department_id:
            timesheets = timesheets.filter(employee__user__department_id=department_id)
        if master_id:
            timesheets = timesheets.filter(master_id=master_id)
        
        # 5. Получаем сотрудников ИЗ табелей
        employee_ids_from_timesheets = timesheets.values_list('employee_id', flat=True).distinct()
        if employee_ids_from_timesheets:
            employees = employees.filter(id__in=employee_ids_from_timesheets)
    
    employees = employees.order_by('user__last_name', 'user__first_name')
    
    # === ПОДГОТОВКА ДАННЫХ ДЛЯ ТАБЛИЦЫ ===
    import calendar
    days_in_month = calendar.monthrange(year, month)[1]
    days = list(range(1, days_in_month + 1))
    
    # Определяем выходные дни
    weekend_days_dict = {}
    cal = calendar.Calendar()
    month_days = cal.monthdatescalendar(year, month)
    
    for week in month_days:
        for day_date in week:
            if day_date.month == month:
                is_weekend = day_date.weekday() >= 5
                weekend_days_dict[day_date.day] = is_weekend
    
    # Словари для подсчета статистики (как в вашем коде)
    timesheet_dict = {}
    attendance_counts = {}
    downtime_counts = {}
    vacation_counts = {}
    illness_counts = {}
    other_absence_counts = {}
    admin_permission_counts = {}
    absence_counts = {}
    evening_hours_counts = {}
    night_hours_counts = {}
    weekend_hours_counts = {}
    overtime_hours_counts = {}
    total_hours_counts = {}
    
    # Форматы для подсчета часов (как в вашем коде)
    total_hours_formats = {
        '7/3': 7.0, '7/2': 7.0, '8/2': 8.0, '8': 8.0, '7': 7.0,
        '4': 4.0, '10': 10.0, '10/2': 10.0, '3,5': 3.5, '9': 9.0,
        '9/2': 9.0, '6': 6.0, '6/2': 6.0, '5': 5.0, '5/2': 5.0,
    }
    
    evening_formats = ['8/2', '7/2', '9/2', '10/2', '6/2']
    
    night_formats = {
        '7/3': 7.0, '8/2': 1.5, '9/2': 1.5, '10/2': 1.5, '6/2': 1.5,
    }
    
    overtime_formats = {'9': 1, '10': 2, '9/2': 1, '10/2': 2}
    
    # === ОБРАБОТКА ТАБЕЛЕЙ (как в вашем коде) ===
    for ts in timesheets:
        day = ts.date.day
        employee_id = ts.employee_id
        
        if employee_id not in timesheet_dict:
            timesheet_dict[employee_id] = {}
        
        timesheet_dict[employee_id][day] = {
            'value': ts.value,
            'display_value': ts.display_value,
        }
        
        value_str = str(ts.value) if ts.value else ""
        
        # Подсчет общего количества часов
        if value_str in total_hours_formats:
            hours = total_hours_formats[value_str]
            total_hours_counts[employee_id] = total_hours_counts.get(employee_id, 0) + hours
            
            # Подсчет часов в выходные дни
            if weekend_days_dict.get(day, False):
                weekend_hours_counts[employee_id] = weekend_hours_counts.get(employee_id, 0) + hours
        
        # Если значение не в форматах, но это число
        elif ts.value and value_str.replace(',', '', 1).replace('.', '', 1).isdigit():
            try:
                hours = float(value_str.replace(',', '.')) if ',' in value_str else float(value_str)
                if hours > 0:
                    total_hours_counts[employee_id] = total_hours_counts.get(employee_id, 0) + hours
                    if weekend_days_dict.get(day, False):
                        weekend_hours_counts[employee_id] = weekend_hours_counts.get(employee_id, 0) + hours
            except (ValueError, TypeError):
                pass
        
        # Подсчет вечерних часов
        if value_str in evening_formats:
            evening_hours_counts[employee_id] = evening_hours_counts.get(employee_id, 0) + 6.5
        
        # Подсчет ночных часов
        if value_str in night_formats:
            night_hours_counts[employee_id] = night_hours_counts.get(employee_id, 0) + night_formats[value_str]
        
        # Подсчет сверхурочных часов
        if value_str in overtime_formats:
            overtime_hours_counts[employee_id] = overtime_hours_counts.get(employee_id, 0) + overtime_formats[value_str]
        
        # Подсчет дней явок
        if ts.value and ts.value not in ['В', 'О', 'Б', 'К', 'ЦП', 'П', 'Н', 'ОС', 'Р', 'Г', 'ДМ', 'ОЖ', 'А']:
            attendance_counts[employee_id] = attendance_counts.get(employee_id, 0) + 1
        
        # Подсчет других категорий
        if ts.value == 'ЦП':
            downtime_counts[employee_id] = downtime_counts.get(employee_id, 0) + 1
        elif ts.value == 'О':
            vacation_counts[employee_id] = vacation_counts.get(employee_id, 0) + 1
        elif ts.value in ['Б', 'Р']:
            illness_counts[employee_id] = illness_counts.get(employee_id, 0) + 1
        elif ts.value == 'П':
            absence_counts[employee_id] = absence_counts.get(employee_id, 0) + 1
        elif ts.value in ['Г', 'ДМ', 'ОЖ', 'ОС']:
            other_absence_counts[employee_id] = other_absence_counts.get(employee_id, 0) + 1
        elif ts.value == 'А':
            admin_permission_counts[employee_id] = admin_permission_counts.get(employee_id, 0) + 1
    
    # === ФОРМИРОВАНИЕ ТАБЛИЦЫ ===
    table_data = []
    
    for employee in employees:
        employee_timesheets = timesheet_dict.get(employee.id, {})
        
        # Формируем ячейки дней
        day_cells = []
        for day in days:
            ts_data = employee_timesheets.get(day)
            if ts_data:
                day_cells.append({
                    'day': day,
                    'value': ts_data['value'],
                    'display_value': ts_data['display_value'],
                })
            else:
                day_cells.append({
                    'day': day,
                    'value': '',
                    'display_value': '',
                })
        
        # Получаем статистику
        row_has_timesheets = any(cell['value'] for cell in day_cells)
        
        table_data.append({
            'employee': employee,
            'days': day_cells,
            'attendance_days': attendance_counts.get(employee.id, 0),
            'downtime_days': downtime_counts.get(employee.id, 0),
            'vacation_days': vacation_counts.get(employee.id, 0),
            'illness_days': illness_counts.get(employee.id, 0),
            'other_absence_days': other_absence_counts.get(employee.id, 0),
            'admin_permission_days': admin_permission_counts.get(employee.id, 0),
            'absence_days': absence_counts.get(employee.id, 0),
            'total_hours': round(total_hours_counts.get(employee.id, 0), 1),
            'evening_hours': round(evening_hours_counts.get(employee.id, 0), 1),
            'night_hours': round(night_hours_counts.get(employee.id, 0), 1),
            'weekend_hours': round(weekend_hours_counts.get(employee.id, 0), 1),
            'overtime_hours': round(overtime_hours_counts.get(employee.id, 0), 1),
            'row_status': 'has_data' if row_has_timesheets else 'empty',
            'employee_id': employee.id
        })
     # === ПОЛУЧАЕМ ИМЯ НАЧАЛЬНИКА ЦЕХА ИЗ ОТДЕЛА ===
    shop_chief_name = "С.В. Ефременко"  # значение по умолчанию
    
    # Определяем отдел для которого формируем табель
    department_id = None
    
    # Если мастер - берем его отдел
    if request.user.is_master:
        department_id = request.user.department_id if request.user.department else None
    
    # Если плановик/админ - берем выбранный отдел из фильтра
    elif request.user.is_planner or request.user.is_administrator:
        department_id = request.GET.get('department')
    
    # Если отдел определен, получаем начальника цеха
    if department_id:
        try:
            department = Department.objects.get(id=department_id)
            if department.shop_chief_name:
                shop_chief_name = department.shop_chief_name
        except Department.DoesNotExist:
            pass

    context = {
        'title': f'Табель за {month:02d}.{year}',
        'year': year,
        'month': month,
        'days': days,
        'table_data': table_data,
        'weekend_days': weekend_days_dict,
        'is_master': request.user.is_master,
        'is_planner': request.user.is_planner,
        'is_admin': request.user.is_administrator,
        'user': request.user,
        'shop_chief_name': shop_chief_name,
    }
    
    return render(request, 'timesheet/print_monthly_table.html', context)
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


    from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Q
from apps.timesheet.models import Timesheet
from apps.users.models import Employee, Department

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
    
    # Инициализация переменных
    employees = Employee.objects.none()
    timesheets = Timesheet.objects.none()
    
    # === ЛОГИКА ДЛЯ МАСТЕРА ===
    if request.user.is_master:
        # 1. Получаем или создаем запись мастера как сотрудника
        master_employee, created = Employee.objects.get_or_create(
            user=request.user,
            defaults={
                'master': request.user,
                'hire_date': request.user.date_joined.date() if request.user.date_joined else today,
                'is_active': True
            }
        )
        
        # 2. Получаем всех сотрудников мастера (включая самого мастера)
        employees = Employee.objects.filter(
            Q(master=request.user) | Q(user=request.user),
            is_active=True
        ).distinct()
        
        # 3. Получаем ВСЕ табели сотрудников мастера
        timesheets = Timesheet.objects.filter(
            date__year=year,
            date__month=month,
            employee__in=employees
        ).select_related('employee', 'employee__user', 'master')
    
    # === ЛОГИКА ДЛЯ ПЛАНОВИКА И АДМИНИСТРАТОРА ===
    elif request.user.is_planner or request.user.is_administrator:
        department_id = request.GET.get('department')
        master_id = request.GET.get('master')
        
        # 1. Получаем ВСЕХ сотрудников (для списка)
        employees = Employee.objects.filter(is_active=True)
        
        # 2. Применяем фильтры к сотрудникам
        if department_id:
            employees = employees.filter(user__department_id=department_id)
        if master_id:
            employees = employees.filter(master_id=master_id)
        
        employees = employees.order_by('user__last_name', 'user__first_name')
        
        # 3. Получаем утвержденные табели
        # Сначала получаем все утвержденные табели
        timesheets = Timesheet.objects.filter(
            date__year=year,
            date__month=month,
            employee__in=employees,
            status__in=['submitted', 'approved']  # И сданные, и утвержденные
        ).select_related('employee', 'employee__user', 'master')
        
        # 4. Применяем те же фильтры к табелям
        if department_id:
            timesheets = timesheets.filter(employee__user__department_id=department_id)
        if master_id:
            timesheets = timesheets.filter(master_id=master_id)
        
        # 5. ОБЯЗАТЕЛЬНО: получаем сотрудников ИЗ табелей
        # Это гарантирует, что мы видим только сотрудников с утвержденными табелями
        employee_ids_from_timesheets = timesheets.values_list('employee_id', flat=True).distinct()
        if employee_ids_from_timesheets:
            # Если есть табели - показываем только этих сотрудников
            employees = employees.filter(id__in=employee_ids_from_timesheets)
    
    # Упорядочиваем сотрудников
    employees = employees.order_by('user__last_name', 'user__first_name')
    
    # === ПОДГОТОВКА ДАННЫХ ДЛЯ ТАБЛИЦЫ ===
    import calendar
    days_in_month = calendar.monthrange(year, month)[1]
    days = list(range(1, days_in_month + 1))
    
    # Определяем выходные дни
    weekend_days_dict = {}
    cal = calendar.Calendar()
    month_days = cal.monthdatescalendar(year, month)
    
    for week in month_days:
        for day_date in week:
            if day_date.month == month:
                is_weekend = day_date.weekday() >= 5
                weekend_days_dict[day_date.day] = is_weekend
    
    # Словари для подсчета статистики
    timesheet_dict = {}
    attendance_counts = {}
    downtime_counts = {}
    vacation_counts = {}
    illness_counts = {}
    other_absence_counts = {}
    admin_permission_counts = {}
    absence_counts = {}
    evening_hours_counts = {}
    night_hours_counts = {}
    weekend_hours_counts = {}
    overtime_hours_counts = {}
    total_hours_counts = {}
    
    # Форматы для подсчета часов
    total_hours_formats = {
        '7/3': 7.0, '7/2': 7.0, '8/2': 8.0, '8': 8.0, '7': 7.0,
        '4': 4.0, '10': 10.0, '10/2': 10.0, '3,5': 3.5, '9': 9.0,
        '9/2': 9.0, '6': 6.0, '6/2': 6.0, '5': 5.0, '5/2': 5.0,
    }
    
    evening_formats = ['8/2', '7/2', '9/2', '10/2', '6/2']
    
    night_formats = {
        '7/3': 7.0, '8/2': 1.5, '9/2': 1.5, '10/2': 1.5, '6/2': 1.5,
    }
    
    overtime_formats = {'9': 1, '10': 2, '9/2': 1, '10/2': 2}
    
    # === ОБРАБОТКА ТАБЕЛЕЙ ===
    for ts in timesheets:
        day = ts.date.day
        employee_id = ts.employee_id
        
        if employee_id not in timesheet_dict:
            timesheet_dict[employee_id] = {}
        
        timesheet_dict[employee_id][day] = {
            'id': ts.id,
            'value': ts.value,
            'display_value': ts.display_value,
            'status': ts.status,
            'can_edit': ts.can_edit,
            'is_submitted': ts.is_submitted,
            'is_approved': ts.is_approved,
            'css_class': 'approved' if ts.is_approved else 'submitted' if ts.is_submitted else 'draft'
        }
        
        value_str = str(ts.value) if ts.value else ""
        
        # Подсчет общего количества часов
        if value_str in total_hours_formats:
            hours = total_hours_formats[value_str]
            total_hours_counts[employee_id] = total_hours_counts.get(employee_id, 0) + hours
            
            # Подсчет часов в выходные дни
            if weekend_days_dict.get(day, False):
                weekend_hours_counts[employee_id] = weekend_hours_counts.get(employee_id, 0) + hours
        
        # Если значение не в форматах, но это число
        elif ts.value and value_str.replace(',', '', 1).replace('.', '', 1).isdigit():
            try:
                hours = float(value_str.replace(',', '.')) if ',' in value_str else float(value_str)
                if hours > 0:
                    total_hours_counts[employee_id] = total_hours_counts.get(employee_id, 0) + hours
                    if weekend_days_dict.get(day, False):
                        weekend_hours_counts[employee_id] = weekend_hours_counts.get(employee_id, 0) + hours
            except (ValueError, TypeError):
                pass
        
        # Подсчет вечерних часов
        if value_str in evening_formats:
            evening_hours_counts[employee_id] = evening_hours_counts.get(employee_id, 0) + 6.5
        
        # Подсчет ночных часов
        if value_str in night_formats:
            night_hours_counts[employee_id] = night_hours_counts.get(employee_id, 0) + night_formats[value_str]
        
        # Подсчет сверхурочных часов
        if value_str in overtime_formats:
            overtime_hours_counts[employee_id] = overtime_hours_counts.get(employee_id, 0) + overtime_formats[value_str]
        
        # Подсчет дней явок
        if ts.value and ts.value not in ['В', 'О', 'Б', 'К', 'ЦП', 'П', 'Н', 'ОС', 'Р', 'Г', 'ДМ', 'ОЖ', 'А']:
            attendance_counts[employee_id] = attendance_counts.get(employee_id, 0) + 1
        
        # Подсчет других категорий
        if ts.value == 'ЦП':
            downtime_counts[employee_id] = downtime_counts.get(employee_id, 0) + 1
        elif ts.value == 'О':
            vacation_counts[employee_id] = vacation_counts.get(employee_id, 0) + 1
        elif ts.value in ['Б', 'Р']:
            illness_counts[employee_id] = illness_counts.get(employee_id, 0) + 1
        elif ts.value == 'П':
            absence_counts[employee_id] = absence_counts.get(employee_id, 0) + 1
        elif ts.value in ['Г', 'ДМ', 'ОЖ', 'ОС']:
            other_absence_counts[employee_id] = other_absence_counts.get(employee_id, 0) + 1
        elif ts.value == 'А':
            admin_permission_counts[employee_id] = admin_permission_counts.get(employee_id, 0) + 1
    
    # === ФОРМИРОВАНИЕ ТАБЛИЦЫ ===
    table_data = []
    
    for employee in employees:
        employee_timesheets = timesheet_dict.get(employee.id, {})
        
        # Формируем ячейки дней
        day_cells = []
        for day in days:
            ts_data = employee_timesheets.get(day)
            if ts_data:
                can_edit = ts_data['can_edit'] if request.user.is_master else False
                day_cells.append({
                    'day': day,
                    'timesheet_id': ts_data['id'],
                    'value': ts_data['value'],
                    'display_value': ts_data['display_value'],
                    'status': ts_data['status'],
                    'can_edit': can_edit,
                    'css_class': ts_data['css_class']
                })
            else:
                can_edit = True if request.user.is_master else False
                day_cells.append({
                    'day': day,
                    'timesheet_id': None,
                    'value': '',
                    'display_value': '',
                    'status': 'draft',
                    'can_edit': can_edit,
                    'css_class': 'empty'
                })
        
        # Получаем статистику
        row_has_timesheets = any(cell['timesheet_id'] for cell in day_cells)
        
        table_data.append({
            'employee': employee,
            'days': day_cells,
            'attendance_days': attendance_counts.get(employee.id, 0),
            'downtime_days': downtime_counts.get(employee.id, 0),
            'vacation_days': vacation_counts.get(employee.id, 0),
            'illness_days': illness_counts.get(employee.id, 0),
            'other_absence_days': other_absence_counts.get(employee.id, 0),
            'admin_permission_days': admin_permission_counts.get(employee.id, 0),
            'absence_days': absence_counts.get(employee.id, 0),
            'total_hours': round(total_hours_counts.get(employee.id, 0), 1),
            'evening_hours': round(evening_hours_counts.get(employee.id, 0), 1),
            'night_hours': round(night_hours_counts.get(employee.id, 0), 1),
            'weekend_hours': round(weekend_hours_counts.get(employee.id, 0), 1),
            'overtime_hours': round(overtime_hours_counts.get(employee.id, 0), 1),
            'row_status': 'has_data' if row_has_timesheets else 'empty',
            'employee_id': employee.id
        })
    
    # === ПОДГОТОВКА КОНТЕКСТА ===
    departments = []
    if request.user.is_planner or request.user.is_administrator:
        departments = Department.objects.all()
    
    # Навигация по месяцам
    prev_month = month - 1 if month > 1 else 12
    prev_year = year if month > 1 else year - 1
    next_month = month + 1 if month < 12 else 1
    next_year = year if month < 12 else year + 1
    
     # === ПОЛУЧАЕМ ИМЯ НАЧАЛЬНИКА ЦЕХА ИЗ ОТДЕЛА ===
    shop_chief_name = "С.В. Ефременко"
    department_id = request.GET.get('department')
    
    if department_id:
        try:
            department = Department.objects.get(id=department_id)
            if department.shop_chief_name:
                shop_chief_name = department.shop_chief_name
        except Department.DoesNotExist:
            pass
    elif request.user.is_master and request.user.department:
        # Для мастера без выбранного отдела берем его отдел
        if request.user.department.shop_chief_name:
            shop_chief_name = request.user.department.shop_chief_name
    context = {
        'title': f'Табель за {month:02d}.{year}',
        'year': year,
        'month': month,
        'month_name': f'{month:02d}.{year}',
        'table_data': table_data,
        'days': days,
        'days_in_month': days_in_month,
        'departments': departments,
        'selected_department': request.GET.get('department'),
        'prev_month': prev_month,
        'prev_year': prev_year,
        'next_month': next_month,
        'next_year': next_year,
        'is_master': request.user.is_master,
        'is_planner': request.user.is_planner,
        'is_admin': request.user.is_administrator,
        'total_employees': employees.count(),
        'days_range': range(1, days_in_month + 1),
        'weekend_days': weekend_days_dict,
        'shop_chief_name': shop_chief_name,
    }
    
    return render(request, 'timesheet/monthly_table.html', context)
@login_required
def quick_edit_timesheet(request):
    """Быстрое редактирование дневного табеля через AJAX"""
    if not request.method == 'POST' or not request.user.is_authenticated:
        return JsonResponse({'error': 'Неверный запрос'}, status=400)
    
    timesheet_id = request.POST.get('timesheet_id')  # это daily_id
    monthly_timesheet_id = request.POST.get('monthly_timesheet_id')
    employee_id = request.POST.get('employee_id')
    date = request.POST.get('date')  # дата в формате YYYY-MM-DD
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
            if not date or not employee_id:
                return JsonResponse({'error': 'Не указаны обязательные параметры'}, status=400)
            
            from datetime import datetime
            date_obj = datetime.strptime(date, '%Y-%m-%d').date()
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