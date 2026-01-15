from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, View
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from django.db.models import Q
from django.http import JsonResponse

from .models import Employee
from .forms import AddEmployeeForm, CreateEmployeeForm, EmployeeFilterForm

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
        queryset = Employee.objects.filter(master=self.request.user)
        
        search = self.request.GET.get('search')
        is_active = self.request.GET.get('is_active')
        
        if search:
            queryset = queryset.filter(
                Q(user__first_name__icontains=search) |
                Q(user__last_name__icontains=search) |
                Q(user__employee_id__icontains=search)
            )
        
        if is_active == 'active':
            queryset = queryset.filter(is_active=True)
        elif is_active == 'inactive':
            queryset = queryset.filter(is_active=False)
        
        return queryset.select_related('user').order_by('user__last_name')
    
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
            messages.success(request, f'Сотрудник {employee.user.get_full_name()} успешно добавлен')
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
            messages.success(request, f'Новый сотрудник {employee.user.get_full_name()} успешно создан')
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
    
    messages.success(request, f'Сотрудник {employee.user.get_full_name()} {action}')
    return redirect('users:employee_list')

@login_required
def remove_employee(request, pk):
    """Удаление сотрудника из отдела мастера"""
    if not request.user.is_master:
        messages.error(request, 'Только мастера могут удалять сотрудников')
        return redirect('timesheet:list')
    
    employee = get_object_or_404(Employee, pk=pk, master=request.user)
    employee_name = employee.user.get_full_name()
    
    # Удаляем связь сотрудника с отделом
    if employee.user.department == request.user.department:
        employee.user.department = None
        employee.user.save()
    
    # Удаляем сотрудника
    employee.delete()
    
    messages.success(request, f'Сотрудник {employee_name} удален из вашего отдела')
    return redirect('users:employee_list')

@login_required
def employee_detail(request, pk):
    """Просмотр деталей сотрудника"""
    if not request.user.is_master:
        messages.error(request, 'Только мастера могут просматривать детали сотрудников')
        return redirect('timesheet:list')
    
    employee = get_object_or_404(Employee, pk=pk, master=request.user)
    
    # Получаем статистику по табелям
    from apps.timesheet.models import Timesheet
    from django.utils import timezone
    
    today = timezone.now().date()
    month_start = today.replace(day=1)
    
    timesheet_stats = {
        'total_this_month': Timesheet.objects.filter(
            employee=employee,
            date__gte=month_start
        ).count(),
        'approved_this_month': Timesheet.objects.filter(
            employee=employee,
            date__gte=month_start,
            status='approved'
        ).count(),
        'submitted_this_month': Timesheet.objects.filter(
            employee=employee,
            date__gte=month_start,
            status='submitted'
        ).count(),
        'total_hours_this_month': 0,
    }
    
    return render(request, 'users/employee_detail.html', {
        'employee': employee,
        'timesheet_stats': timesheet_stats
    })

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
        context['employee_count'] = Employee.objects.filter(master=user).count()
        context['active_employee_count'] = Employee.objects.filter(master=user, is_active=True).count()
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