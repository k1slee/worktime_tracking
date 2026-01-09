import django_filters
from .models import Timesheet
from apps.users.models import User, Department

class TimesheetFilter(django_filters.FilterSet):
    """Фильтры для табелей"""
    date_from = django_filters.DateFilter(field_name='date', lookup_expr='gte')
    date_to = django_filters.DateFilter(field_name='date', lookup_expr='lte')
    master = django_filters.ModelChoiceFilter(
        queryset=User.objects.filter(role='master'),
        field_name='master'
    )
    department = django_filters.ModelChoiceFilter(
        queryset=Department.objects.all(),
        field_name='employee__department'
    )
    status = django_filters.ChoiceFilter(choices=Timesheet.STATUS_CHOICES)
    employee_name = django_filters.CharFilter(
        field_name='employee__user__last_name',
        lookup_expr='icontains'
    )
    
    class Meta:
        model = Timesheet
        fields = ['date', 'master', 'employee', 'status']
    
    @property
    def qs(self):
        queryset = super().qs
        
        # Для мастеров показываем только их табели
        user = self.request.user
        if user.is_authenticated and user.is_master:
            queryset = queryset.filter(master=user)
        
        return queryset