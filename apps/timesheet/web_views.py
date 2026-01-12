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
    
    # Получаем сотрудников
    if request.user.is_master:
        employees = Employee.objects.filter(master=request.user, is_active=True)
    elif request.user.is_planner or request.user.is_administrator:
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
    
    
    timesheets = Timesheet.objects.filter(
        date__year=year,
        date__month=month,
        employee__in=employees
    ).select_related('employee', 'employee__user', 'master')
    
    # Создаем структуру данных для таблицы
    table_data = []
    
    # Количество дней в месяце
    import calendar
    days_in_month = calendar.monthrange(year, month)[1]
    days = list(range(1, days_in_month + 1))
    
    # Создаем словарь для быстрого доступа к табелям по сотруднику и дню
    timesheet_dict = {}
    for ts in timesheets:
        day = ts.date.day
        if ts.employee_id not in timesheet_dict:
            timesheet_dict[ts.employee_id] = {}
        timesheet_dict[ts.employee_id][day] = {
            'id': ts.id,
            'value': ts.value,
            'display_value': ts.display_value,
            'status': ts.status,
            'can_edit': ts.can_edit,
            'is_submitted': ts.is_submitted,
            'is_approved': ts.is_approved,
            'css_class': 'approved' if ts.is_approved else 'submitted' if ts.is_submitted else 'draft'
        }
    
    
    for employee in employees:
        employee_timesheets = timesheet_dict.get(employee.id, {})
        
        
        day_cells = []
        for day in days:
            ts_data = employee_timesheets.get(day)
            if ts_data:
                day_cells.append({
                    'day': day,
                    'timesheet_id': ts_data['id'],
                    'value': ts_data['value'],
                    'display_value': ts_data['display_value'],
                    'status': ts_data['status'],
                    'can_edit': ts_data['can_edit'],
                    'css_class': ts_data['css_class']
                })
            else:
                day_cells.append({
                    'day': day,
                    'timesheet_id': None,
                    'value': '',
                    'display_value': '',
                    'status': 'draft',
                    'can_edit': True,
                    'css_class': 'empty'
                })
        
        
        row_has_timesheets = any(cell['timesheet_id'] for cell in day_cells)
        row_status = 'has_data' if row_has_timesheets else 'empty'
        
        table_data.append({
            'employee': employee,
            'days': day_cells,
            'row_status': row_status,
            'employee_id': employee.id
        })
    
    
    departments = []
    if request.user.is_planner or request.user.is_administrator:
        departments = Department.objects.all()
    
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
        'table_data': table_data,
        'days': days,
        'days_in_month': days_in_month,
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
        'total_employees': employees.count(),
        'days_range': range(1, days_in_month + 1),
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