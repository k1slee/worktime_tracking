from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, CreateView, UpdateView, DetailView
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.db.models import Q
import csv
from datetime import datetime
from .models import Timesheet
from .forms import TimesheetForm
from apps.users.permissions import IsMaster, IsPlanner
from .utils import generate_csv_report
from .forms import MonthlyTimesheetForm, BulkTimesheetForm
from django.utils import timezone 
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
        employee_ids = request.GET.get('employee_ids', '')
        date = request.GET.get('date', '')
        
        initial = {}
        if employee_ids:
            initial['employee_ids'] = employee_ids
        if date:
            try:
                from datetime import datetime
                initial['date'] = datetime.strptime(date, '%Y-%m-%d').date()
            except:
                pass
        
        form = BulkTimesheetForm(initial=initial, user=request.user)
    
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
            queryset = queryset.filter(employee__department_id=department_id)
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

def monthly_table_view(request):
    """Табличное представление табеля за месяц"""
    if not request.user.is_authenticated:
        return redirect('login')
    
    # Импорт внутри функции, чтобы избежать циклических импортов
    from apps.users.models import Department, Employee
    from .models import Timesheet
    
    # Получаем параметры месяца
    today = timezone.now().date()
    
    try:
        year = int(request.GET.get('year', today.year))
        month = int(request.GET.get('month', today.month))
        month_date = datetime(year, month, 1).date()
    except (ValueError, TypeError):
        month_date = today.replace(day=1)
        year = month_date.year
        month = month_date.month
    
    # Получаем сотрудников
    if request.user.is_master:
        employees = Employee.objects.filter(master=request.user, is_active=True)
    elif request.user.is_planner or request.user.is_administrator:
        # Плановики и администраторы видят всех сотрудников выбранного отдела
        department_id = request.GET.get('department')
        if department_id:
            employees = Employee.objects.filter(
                user__department_id=department_id,
                is_active=True
            )
        else:
            employees = Employee.objects.filter(is_active=True)
    else:
        employees = Employee.objects.none()
    
    # Получаем количество дней в месяце
    import calendar
    _, last_day = calendar.monthrange(year, month)
    
    # Получаем все табели за месяц для этих сотрудников
    timesheets = Timesheet.objects.filter(
        date__year=year,
        date__month=month,
        employee__in=employees
    ).select_related('employee', 'employee__user')
    
    # Создаем словарь для быстрого доступа к табелям
    timesheet_dict = {}
    for ts in timesheets:
        key = (ts.employee.id, ts.date.day)
        timesheet_dict[key] = {
            'id': ts.id,
            'value': ts.value,
            'display_value': ts.display_value,
            'status': ts.status,
            'can_edit': ts.can_edit,
            'is_approved': ts.is_approved,
            'css_class': 'approved' if ts.is_approved else 'draft'
        }
    
    # Создаем список дней месяца
    days = list(range(1, last_day + 1))
    
    # Получаем отделы для фильтра (для плановиков и администраторов)
    departments = []
    if request.user.is_planner or request.user.is_administrator:
        departments = Department.objects.all()
    
    # Рассчитываем статистику
    total_employees = employees.count()
    total_days = last_day
    total_cells = total_employees * total_days
    
    # Подготавливаем данные для таблицы
    table_data = []
    for employee in employees:
        row = {
            'employee': employee,
            'days': [],
            'stats': {
                'work_days': 0,
                'weekend_days': 0,
                'other_days': 0
            }
        }
        
        for day in days:
            date = datetime(year, month, day).date()
            key = (employee.id, day)
            
            if key in timesheet_dict:
                timesheet = timesheet_dict[key]
                row['days'].append(timesheet)
                
                # Считаем статистику
                value = timesheet['value']
                if value == 'В':
                    row['stats']['weekend_days'] += 1
                elif value.isdigit():
                    row['stats']['work_days'] += 1
                else:
                    row['stats']['other_days'] += 1
            else:
                # Нет табеля на этот день
                is_weekend = date.weekday() >= 5
                row['days'].append({
                    'id': None,
                    'value': '',
                    'display_value': '',
                    'status': '',
                    'can_edit': True,
                    'is_approved': False,
                    'css_class': 'weekend' if is_weekend else 'empty',
                    'is_empty': True,
                    'is_weekend': is_weekend
                })
                
                if is_weekend:
                    row['stats']['weekend_days'] += 1
        
        table_data.append(row)
    
    # Навигация по месяцам
    prev_month = month - 1 if month > 1 else 12
    prev_year = year if month > 1 else year - 1
    next_month = month + 1 if month < 12 else 1
    next_year = year if month < 12 else year + 1
    
    context = {
        'title': f'Табель за {month_date.strftime("%B %Y")}',
        'year': year,
        'month': month,
        'month_date': month_date,
        'month_name': month_date.strftime('%B %Y'),
        'days': days,
        'table_data': table_data,
        'departments': departments,
        'selected_department': request.GET.get('department'),
        
        # Навигация
        'prev_month': prev_month,
        'prev_year': prev_year,
        'next_month': next_month,
        'next_year': next_year,
        
        # Права доступа
        'is_master': request.user.is_master,
        'is_planner': request.user.is_planner,
        'is_admin': request.user.is_administrator,
        
        # Статистика
        'total_employees': total_employees,
        'total_days': total_days,
        'total_cells': total_cells,
    }
    
    return render(request, 'timesheet/monthly_table.html', context)


def quick_edit_timesheet(request):
    """Быстрое редактирование табеля через AJAX"""
    if not request.method == 'POST' or not request.user.is_authenticated:
        return JsonResponse({'error': 'Неверный запрос'}, status=400)
    
    timesheet_id = request.POST.get('timesheet_id')
    date_str = request.POST.get('date')
    employee_id = request.POST.get('employee_id')
    value = request.POST.get('value', '').strip()
    action = request.POST.get('action', 'save')
    
    try:
        if action == 'delete':
            # Удаление табеля
            if not timesheet_id:
                return JsonResponse({'error': 'Не указан ID табеля'}, status=400)
            
            timesheet = Timesheet.objects.get(id=timesheet_id)
            
            # Проверка прав
            if timesheet.is_approved:
                return JsonResponse({'error': 'Нельзя удалить утвержденный табель'}, status=403)
            
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
                return JsonResponse({'error': 'Табель утвержден и не может быть изменен'}, status=403)
            
            if request.user.is_master and timesheet.master != request.user:
                return JsonResponse({'error': 'Нет прав на редактирование этого табеля'}, status=403)
            
            # Если значение пустое, удаляем табель
            if not value:
                timesheet.delete()
                return JsonResponse({'success': True, 'deleted': True})
            
            timesheet.value = value
            timesheet.save()
            
        else:
            # Создание нового табеля
            from datetime import datetime
            date = datetime.strptime(date_str, '%Y-%m-%d').date()
            employee = Employee.objects.get(id=employee_id)
            
            # Проверка прав для мастера
            if request.user.is_master and employee.master != request.user:
                return JsonResponse({'error': 'Нет прав на создание табеля для этого сотрудника'}, status=403)
            
            # Если значение пустое, ничего не делаем
            if not value:
                return JsonResponse({'success': True})
            
            # Проверяем, не существует ли уже табель
            timesheet, created = Timesheet.objects.get_or_create(
                date=date,
                employee=employee,
                defaults={
                    'master': employee.master,
                    'value': value,
                    'status': 'draft'
                }
            )
            
            if not created and not timesheet.can_edit:
                return JsonResponse({'error': 'Табель уже существует и утвержден'}, status=403)
            
            if not created:
                timesheet.value = value
                timesheet.save()
        
        return JsonResponse({
            'success': True,
            'display_value': timesheet.display_value,
            'status': timesheet.status,
            'can_edit': timesheet.can_edit,
            'is_approved': timesheet.is_approved
        })
        
    except Timesheet.DoesNotExist:
        return JsonResponse({'error': 'Табель не найден'}, status=404)
    except Employee.DoesNotExist:
        return JsonResponse({'error': 'Сотрудник не найден'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

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