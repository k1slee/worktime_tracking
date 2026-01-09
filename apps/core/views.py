from django.shortcuts import render
from django.contrib.auth.decorators import login_required

@login_required
def dashboard_view(request):
    """Главная страница"""
    user = request.user
    
    if user.is_administrator:
        # Статистика для администратора
        from apps.timesheet.models import Timesheet
        from apps.users.models import User, Employee
        
        total_users = User.objects.count()
        total_employees = Employee.objects.filter(is_active=True).count()
        total_timesheets = Timesheet.objects.count()
        
        context = {
            'total_users': total_users,
            'total_employees': total_employees,
            'total_timesheets': total_timesheets,
        }
    elif user.is_master:
        # Данные для мастера
        from apps.timesheet.models import Timesheet
        from apps.users.models import Employee
        
        managed_employees = Employee.objects.filter(master=user, is_active=True).count()
        recent_timesheets = Timesheet.objects.filter(master=user).order_by('-date')[:10]
        
        context = {
            'managed_employees': managed_employees,
            'recent_timesheets': recent_timesheets,
        }
    elif user.is_planner:
        # Данные для планового отдела
        from apps.timesheet.models import Timesheet
        from apps.timesheet.utils import get_timesheet_stats
        
        stats = get_timesheet_stats(Timesheet.objects.all())
        
        context = {
            'stats': stats,
        }
    else:
        context = {}
    
    context['user'] = user
    return render(request, 'core/dashboard.html', context)