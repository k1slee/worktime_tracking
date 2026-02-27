from django import forms
from .models import Timesheet
from apps.users.models import Employee
from django.utils import timezone
from datetime import datetime
import calendar
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
from apps.users.models import User, Employee, Department
from .models import MonthlyTimesheet, Timesheet
class MonthlyTimesheetForm(forms.Form):
    """Форма для создания месячного табеля"""
    month = forms.CharField(
        label='Месяц',
        widget=forms.TextInput(attrs={
            'type': 'month',
            'class': 'form-control',
            'placeholder': 'ГГГГ-ММ'
        }),
        help_text='Выберите месяц для создания табеля'
    )
    
    default_value = forms.ChoiceField(
        label='Значение по умолчанию',
        choices=Timesheet.CODE_CHOICES,
        initial='В',
        widget=forms.Select(attrs={'class': 'form-control'}),
        help_text='Значение, которое будет установлено для всех дней'
    )
    
    include_weekends = forms.BooleanField(
        label='Включать выходные',
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text='Создавать записи для выходных дней'
    )
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Устанавливаем текущий месяц по умолчанию
        if not self.initial.get('month'):
            today = timezone.now().date()
            self.initial['month'] = today.strftime('%Y-%m')
    
    def clean_month(self):
        month_str = self.cleaned_data['month']
        
        try:
            # Преобразуем строку "ГГГГ-ММ" в дату (первый день месяца)
            from datetime import datetime
            month_date = datetime.strptime(month_str, '%Y-%m').date()
            
            # Убедимся, что это первый день месяца
            return month_date.replace(day=1)
        except ValueError:
            raise forms.ValidationError('Пожалуйста, выберите правильный месяц в формате ГГГГ-ММ')
    
    def create_monthly_timesheet(self):
        """Создать табели на весь месяц"""
        month = self.cleaned_data['month']  # Это уже datetime.date объект
        default_value = self.cleaned_data['default_value']
        include_weekends = self.cleaned_data['include_weekends']
        
        # Получаем сотрудников, назначенных этому мастеру в выбранном месяце
        from apps.users.models import Employee, EmployeeAssignment
        from django.db.models import Q
        month_start = month
        year = month.year
        month_num = month.month
        import calendar
        _, last_day = calendar.monthrange(year, month_num)
        month_end = datetime(year, month_num, last_day).date()
        # Основной способ: по назначениям; плюс обратная совместимость: поле master
        employees = Employee.objects.filter(is_active=True).filter(
            (
                Q(assignments__master=self.user) &
                (Q(assignments__end_date__isnull=True) | Q(assignments__end_date__gte=month_start)) &
                Q(assignments__start_date__lte=month_end)
            ) | Q(master=self.user)
        ).distinct()
        
        if not employees.exists():
            raise ValueError('У вас нет активных сотрудников')
        
        # Получаем первый и последний день месяца
        import calendar
        year = month.year
        month_num = month.month
        _, last_day = calendar.monthrange(year, month_num)
        
        created_count = 0
        errors = []
        
        # Создаем табели для каждого сотрудника на каждый день месяца
        for employee in employees:
            for day in range(1, last_day + 1):
                date = datetime(year, month_num, day).date()
                
                # Пропускаем дни до даты приема сотрудника
                hire_date = getattr(employee, 'hire_date', None)
                if hire_date and date < hire_date:
                    continue
                
                # Пропускаем выходные, если не включены
                if not include_weekends and date.weekday() >= 5:  # 5=суббота, 6=воскресенье
                    continue
                
                # Проверяем, не существует ли уже табель
                if not Timesheet.objects.filter(date=date, employee=employee).exists():
                    # Проверяем назначение на эту дату (или legacy-связь master)
                    assigned = EmployeeAssignment.objects.filter(
                        employee=employee, master=self.user
                    ).filter(
                        Q(end_date__isnull=True) | Q(end_date__gte=date),
                        start_date__lte=date
                    ).exists()
                    if not assigned and getattr(employee, 'master_id', None) != getattr(self.user, 'id', None):
                        continue
                    try:
                        Timesheet.objects.create(
                            date=date,
                            employee=employee,
                            master=self.user,
                            value=default_value,
                            status='draft'
                        )
                        created_count += 1
                    except Exception as e:
                        errors.append(f"Ошибка для сотрудника {employee} на дату {date}: {str(e)}")
        
        if errors:
            raise ValueError(f"Создано {created_count} записей, но были ошибки: {'; '.join(errors[:5])}")
        
        return created_count

class BulkTimesheetForm(forms.Form):
    """Форма для массового редактирования табелей"""
    date = forms.DateField(
        label='Дата',
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        })
    )
    
    value = forms.CharField(
        label='Значение',
        max_length=10,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Часы или код'
        }),
        help_text='Часы работы (1-24) или условное обозначение'
    )
    
    employee_ids = forms.CharField(
        widget=forms.HiddenInput(),
        required=False
    )
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if not self.initial.get('date'):
            self.initial['date'] = timezone.now().date()
    
    def clean_value(self):
        value = self.cleaned_data.get('value')
        
        # Валидация значения
        allowed_codes = dict(Timesheet.CODE_CHOICES).keys()
        
        if value.isdigit():
            hours = int(value)
            if hours < 1 or hours > 24:
                raise forms.ValidationError('Количество часов должно быть от 1 до 24')
        elif value not in allowed_codes:
            raise forms.ValidationError(
                f'Недопустимое условное обозначение. Допустимые: {", ".join(allowed_codes)}'
            )
        
        return value
    
    def update_timesheets(self):
        """Обновить или создать табели для выбранных сотрудников"""
        date = self.cleaned_data['date']
        value = self.cleaned_data['value']
        employee_ids = self.cleaned_data.get('employee_ids', '')
        
        if not employee_ids:
            return 0
        
        # Получаем ID сотрудников
        ids = [int(id) for id in employee_ids.split(',') if id]
        
        from apps.users.models import Employee, EmployeeAssignment
        from django.db.models import Q
        # По назначениям на дату или legacy master
        employees = Employee.objects.filter(id__in=ids, is_active=True).filter(
            (
                Q(assignments__master=self.user) &
                (Q(assignments__end_date__isnull=True) | Q(assignments__end_date__gte=date)) &
                Q(assignments__start_date__lte=date)
            ) | Q(master=self.user)
        ).distinct()
        
        updated_count = 0
        
        for employee in employees:
            # Ищем существующий табель
            timesheet, created = Timesheet.objects.get_or_create(
                date=date,
                employee=employee,
                defaults={
                    'master': self.user,
                    'value': value,
                    'status': 'draft'
                }
            )
            
            # Если табель уже существует и не утвержден, обновляем его
            if not created and timesheet.can_edit:
                timesheet.value = value
                timesheet.save()
            
            updated_count += 1
        
        return updated_count
class TimesheetForm(forms.ModelForm):
    class Meta:
        model = Timesheet
        fields = ['date', 'employee', 'value']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'employee': forms.Select(attrs={'class': 'form-control'}),
            'value': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Часы или код'}),
        }
        help_texts = {
            'value': 'Введите количество часов (1-24) или условное обозначение',
        }
        labels = {
            'date': 'Дата',
            'employee': 'Сотрудник',
            'value': 'Значение (часы или код)',
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Ограничиваем выбор сотрудников для мастера (по текущей дате)
        if self.user and self.user.is_master:
            from django.utils import timezone
            from django.db.models import Q
            today = timezone.now().date()
            self.fields['employee'].queryset = Employee.objects.filter(is_active=True).filter(
                (
                    Q(assignments__master=self.user) &
                    Q(assignments__start_date__lte=today) &
                    (Q(assignments__end_date__isnull=True) | Q(assignments__end_date__gte=today))
                ) | Q(master=self.user)
            ).select_related('user').distinct()
    
    def clean(self):
        cleaned_data = super().clean()
        
        # Мастер может создавать табели только для сотрудников, назначенных ему на указанную дату
        if self.user and self.user.is_master:
            from django.db.models import Q
            from apps.users.models import EmployeeAssignment
            employee = cleaned_data.get('employee')
            date = cleaned_data.get('date')
            if employee and date:
                assigned = EmployeeAssignment.objects.filter(
                    employee=employee, master=self.user
                ).filter(
                    Q(end_date__isnull=True) | Q(end_date__gte=date),
                    start_date__lte=date
                ).exists()
                if not assigned and getattr(employee, 'master_id', None) != getattr(self.user, 'id', None):
                    raise forms.ValidationError(
                        'Сотрудник не назначен вам на эту дату'
                    )
        
        return cleaned_data
    
    def clean_value(self):
        value = self.cleaned_data.get('value')
        
        # Валидация значения
        allowed_codes = dict(Timesheet.CODE_CHOICES).keys()
        
        if value.isdigit():
            hours = int(value)
            if hours < 1 or hours > 24:
                raise forms.ValidationError('Количество часов должно быть от 1 до 24')
        elif value not in allowed_codes:
            raise forms.ValidationError(
                f'Недопустимое условное обозначение. Допустимые: {", ".join(allowed_codes)}'
            )
        
        return value
