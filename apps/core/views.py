from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseNotFound, HttpResponseServerError

@login_required
def dashboard_view(request):
    user = request.user
    
    if user.is_administrator:
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
        from apps.timesheet.models import Timesheet
        from apps.users.models import Employee
        from django.utils import timezone
        from django.db.models import Q
        today = timezone.now().date()
        managed_employees = Employee.objects.filter(
            is_active=True,
            assignments__master=user,
            assignments__start_date__lte=today
        ).filter(
            Q(assignments__end_date__isnull=True) | Q(assignments__end_date__gte=today)
        ).distinct().count()
        recent_timesheets = Timesheet.objects.filter(master=user).order_by('-date')[:10]
        
        context = {
            'managed_employees': managed_employees,
            'recent_timesheets': recent_timesheets,
        }
    elif user.is_planner:
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


def error_400(request, exception):
    return render(request, '400.html', status=400)


def error_403(request, exception):
    return render(request, '403.html', status=403)


def error_404(request, exception):
    return render(request, '404.html', status=404)


def error_500(request):
    return render(request, '500.html', status=500)
