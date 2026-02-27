from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, View
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from django.db.models import Q
from django.http import JsonResponse, Http404

from .models import Employee
from .forms import AddEmployeeForm, CreateEmployeeForm, EmployeeFilterForm, EmployeeAssignmentForm, EmployeeMasterEditForm

class MasterMixin(UserPassesTestMixin):
    """Миксин для проверки, что пользователь мастер"""
    def test_func(self):
        return self.request.user.is_master
    
    def handle_no_permission(self):
        messages.error(self.request, 'Только мастера могут управлять сотрудниками')
        return redirect('timesheet:list')

class EmployeeListView(MasterMixin, ListView):
    """Список сотрудников мастера"""
    model = Employee
    template_name = 'users/employee_list.html'
    context_object_name = 'employees'
    paginate_by = 20
    
    def get_queryset(self):
        from django.utils import timezone
        today = timezone.now().date()
        # Современный способ: по назначениям на текущую дату
        by_assignments = Q(
            assignments__master=self.request.user,
            assignments__start_date__lte=today
        ) & (Q(assignments__end_date__isnull=True) | Q(assignments__end_date__gte=today))
        # Обратная совместимость: если сотруднику выставлен master напрямую
        legacy_master = Q(master=self.request.user)
        queryset = Employee.objects.filter(is_active=True).filter(
            by_assignments | legacy_master
        ).distinct()
        
        search = self.request.GET.get('search')
        is_active = self.request.GET.get('is_active')
        
        if search:
            queryset = queryset.filter(
                Q(user__first_name__icontains=search) |
                Q(user__last_name__icontains=search) |
                Q(user__employee_id__icontains=search) |
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(middle_name__icontains=search) |
                Q(employee_id_own__icontains=search)
            )
        
        if is_active == 'active':
            queryset = queryset.filter(is_active=True)
        elif is_active == 'inactive':
            queryset = queryset.filter(is_active=False)
        
        return queryset.select_related('user').prefetch_related('assignments').order_by('last_name', 'first_name', 'user__last_name', 'user__first_name')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter_form'] = EmployeeFilterForm(self.request.GET or None)
        context['total_active'] = Employee.objects.filter(
            master=self.request.user, 
            is_active=True
        ).count()
        context['total_inactive'] = Employee.objects.filter(
            master=self.request.user, 
            is_active=False
        ).count()
        return context

class AddEmployeeView(MasterMixin, View):
    """Добавление существующего пользователя как сотрудника"""
    template_name = 'users/add_employee.html'
    
    def get(self, request):
        form = AddEmployeeForm(master=request.user)
        return render(request, self.template_name, {'form': form, 'action': 'add'})
    
    def post(self, request):
        form = AddEmployeeForm(request.POST, master=request.user)
        if form.is_valid():
            employee = form.save()
            messages.success(request, f'Сотрудник {employee.full_name} успешно добавлен')
            return redirect('users:employee_list')
        
        return render(request, self.template_name, {'form': form, 'action': 'add'})

class CreateEmployeeView(MasterMixin, View):
    """Создание нового пользователя и сотрудника"""
    template_name = 'users/add_employee.html'
    
    def get(self, request):
        form = CreateEmployeeForm(master=request.user)
        return render(request, self.template_name, {'form': form, 'action': 'create'})
    
    def post(self, request):
        form = CreateEmployeeForm(request.POST, master=request.user)
        if form.is_valid():
            employee = form.save()
            messages.success(request, f'Новый сотрудник {employee.full_name} успешно создан')
            return redirect('users:employee_list')
        
        return render(request, self.template_name, {'form': form, 'action': 'create'})

@login_required
def toggle_employee_status(request, pk):
    """Активация/деактивация сотрудника"""
    if not request.user.is_master:
        messages.error(request, 'Только мастера могут управлять сотрудниками')
        return redirect('timesheet:list')
    
    employee = get_object_or_404(Employee, pk=pk, master=request.user)
    
    if employee.is_active:
        employee.is_active = False
        action = 'деактивирован'
    else:
        employee.is_active = True
        action = 'активирован'
    
    employee.save()
    
    messages.success(request, f'Сотрудник {employee.full_name} {action}')
    return redirect('users:employee_list')

@login_required
def remove_employee(request, pk):
    """Удаление сотрудника из отдела мастера"""
    if not request.user.is_master:
        messages.error(request, 'Только мастера могут удалять сотрудников')
        return redirect('timesheet:list')
    from django.utils import timezone
    from django.db.models import Q
    today = timezone.now().date()
    employee = get_object_or_404(
        Employee.objects.filter(
            Q(master=request.user) |
            (Q(assignments__master=request.user) &
             Q(assignments__start_date__lte=today) &
             (Q(assignments__end_date__isnull=True) | Q(assignments__end_date__gte=today)))
        ).distinct(),
        pk=pk
    )
    employee_name = employee.full_name
    
    # Удаляем связь сотрудника с отделом (для сотрудников с учеткой)
    if employee.user and employee.user.department == request.user.department:
        employee.user.department = None
        employee.user.save()
    
    # Удаляем сотрудника
    employee.delete()
    
    messages.success(request, f'Сотрудник {employee_name} удален из вашего отдела')
    return redirect('users:employee_list')


@login_required
def employee_detail(request, pk):
    """Карточка сотрудника временно недоступна"""
    raise Http404("Страница временно недоступна")

@login_required
def employee_edit_master(request, pk):
    """Редактирование сотрудника мастером (должность, дата приема)"""
    if not request.user.is_master:
        messages.error(request, 'Недостаточно прав')
        return redirect('timesheet:list')
    from django.utils import timezone
    from django.db.models import Q
    today = timezone.now().date()
    employee = get_object_or_404(
        Employee.objects.filter(
            Q(master=request.user) |
            (Q(assignments__master=request.user) &
             Q(assignments__start_date__lte=today) &
             (Q(assignments__end_date__isnull=True) | Q(assignments__end_date__gte=today)))
        ).distinct(),
        pk=pk
    )
    if request.method == 'POST':
        form = EmployeeMasterEditForm(request.POST, employee=employee)
        if form.is_valid():
            form.save()
            messages.success(request, 'Данные сотрудника обновлены')
            return redirect('users:employee_list')
    else:
        form = EmployeeMasterEditForm(employee=employee)
    return render(request, 'users/employee_edit.html', {
        'form': form,
        'employee': employee,
        'title': 'Редактирование сотрудника'
    })

@login_required
def assignment_add(request, pk):
    """Добавить назначение сотрудника мастеру на период"""
    employee = get_object_or_404(Employee, pk=pk)
    if not (request.user.is_master or request.user.is_planner or request.user.is_administrator):
        messages.error(request, 'Недостаточно прав для назначения мастера')
        return redirect('users:employee_list')
    if request.method == 'POST':
        form = EmployeeAssignmentForm(request.POST, employee=employee, current_user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Назначение успешно добавлено')
            return redirect('users:employee_list')
    else:
        form = EmployeeAssignmentForm(employee=employee, current_user=request.user)
    return render(request, 'users/assignment_form.html', {
        'form': form,
        'employee': employee,
        'title': 'Назначение мастера'
    })

@login_required
def assignment_close(request, assignment_id):
    """Закрыть назначение (установить дату окончания сегодня)"""
    from .models import EmployeeAssignment
    assignment = get_object_or_404(EmployeeAssignment, pk=assignment_id)
    if not (request.user.is_master or request.user.is_planner or request.user.is_administrator):
        messages.error(request, 'Недостаточно прав для изменения назначения')
        return redirect('users:employee_list')
    from django.utils import timezone
    assignment.end_date = timezone.now().date()
    assignment.save()
    messages.success(request, 'Назначение закрыто')
    return redirect('users:employee_list')

@login_required
def search_users_api(request):
    """API для поиска пользователей без отдела"""
    if not request.user.is_master:
        return JsonResponse({'error': 'Нет прав доступа'}, status=403)
    
    search_term = request.GET.get('q', '')
    if len(search_term) < 2:
        return JsonResponse({'results': []})
    
    from django.contrib.auth import get_user_model
    User = get_user_model()
    from .models import Employee
    
    # Ищем пользователей без отдела и не привязанных к сотрудникам
    existing_employee_users = Employee.objects.values_list('user_id', flat=True)
    
    users = User.objects.filter(
        Q(first_name__icontains=search_term) |
        Q(last_name__icontains=search_term) |
        Q(username__icontains=search_term) |
        Q(employee_id__icontains=search_term)
    ).filter(
        department=None,
        is_active=True
    ).exclude(
        id__in=existing_employee_users
    ).exclude(
        role='master'
    )[:10]
    
    results = []
    for user in users:
        results.append({
            'id': user.id,
            'text': f"{user.get_full_name()} ({user.employee_id}) - {user.position or 'Без должности'}"
        })
    
    return JsonResponse({'results': results})

@login_required
def profile_view(request):
    """Профиль пользователя"""
    user = request.user
    
    # Получаем статистику в зависимости от роли
    context = {
        'user': user,
        'title': 'Мой профиль'
    }
    
    if user.is_master:
        from django.db.models import Q
        from django.utils import timezone
        today = timezone.now().date()
        base_qs = Employee.objects.filter(
            assignments__master=user,
            assignments__start_date__lte=today
        ).filter(
            Q(assignments__end_date__isnull=True) | Q(assignments__end_date__gte=today)
        ).distinct()
        context['employee_count'] = base_qs.count()
        context['active_employee_count'] = base_qs.filter(is_active=True).count()
        # Статистика по табелям за последний месяц
        from apps.timesheet.models import Timesheet
        from django.utils import timezone
        today = timezone.now().date()
        month_start = today.replace(day=1)
        context['timesheets_this_month'] = Timesheet.objects.filter(
            master=user,
            date__gte=month_start
        ).count()
    
    return render(request, 'users/profile.html', context)

@login_required
def profile_edit_view(request):
    """Редактирование профиля"""
    if request.method == 'POST':
        # Здесь можно добавить форму редактирования
        messages.success(request, 'Профиль обновлен')
        return redirect('users:profile')
    
    return render(request, 'users/profile_edit.html', {
        'user': request.user,
        'title': 'Редактирование профиля'
    })
