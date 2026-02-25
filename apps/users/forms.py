from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model

User = get_user_model()

class EmployeeMasterEditForm(forms.Form):
    """Форма редактирования сотрудника для мастера (минимально: должность, дата приема)"""
    position = forms.CharField(
        max_length=200,
        label='Должность',
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Должность'})
    )
    hire_date = forms.DateField(
        required=False,
        label='Дата приема на работу',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    def __init__(self, *args, **kwargs):
        self.employee = kwargs.pop('employee', None)
        super().__init__(*args, **kwargs)
        if self.employee:
            self.fields['position'].initial = self.employee.position or ''
            self.fields['hire_date'].initial = self.employee.hire_date
    def save(self):
        emp = self.employee
        if not emp:
            raise ValidationError('Сотрудник не найден')
        position = self.cleaned_data.get('position', '').strip()
        hire_date = self.cleaned_data.get('hire_date')
        if emp.user:
            # У сотрудника есть учетная запись — обновляем должность в User
            emp.user.position = position
            emp.user.save(update_fields=['position'])
        else:
            emp.position_own = position
        emp.hire_date = hire_date
        emp.full_clean()
        emp.save()
        return emp

class AddEmployeeForm(forms.ModelForm):
    """Форма добавления сотрудника для мастера"""
    employee = forms.ModelChoiceField(
        queryset=User.objects.none(),
        label='Пользователь',
        help_text='Выберите существующего пользователя без отдела',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    def __init__(self, *args, **kwargs):
        self.master = kwargs.pop('master', None)
        super().__init__(*args, **kwargs)
        
        # Ленивый импорт для избежания циклических импортов
        from .models import Employee
        existing_employee_users = Employee.objects.values_list('user_id', flat=True)
        if self.master:
            # Фильтруем пользователей: только без отдела и не привязанные к сотрудникам
            existing_employee_users = Employee.objects.values_list('user_id', flat=True)
            
            self.fields['employee'].queryset = User.objects.filter(
                department=None,
                is_active=True,
                role='worker'  
            ).exclude(
                id__in=existing_employee_users
            ).exclude(
                role__in=['admin', 'planner', 'master']  # Исключаем админов и плановиков
            )
    
    def clean_employee(self):
        employee_user = self.cleaned_data['employee']
        
        # Проверяем, что у пользователя нет отдела
        if employee_user.department:
            raise ValidationError('У выбранного пользователя уже есть отдел')
        
        # Проверяем, что пользователь не привязан к другому мастеру
        from .models import Employee
        if Employee.objects.filter(user=employee_user).exists():
            raise ValidationError('Этот пользователь уже является сотрудником')
        
        return employee_user
    
    def save(self, commit=True):
        from .models import Employee, EmployeeAssignment
        
        employee, created = Employee.objects.get_or_create(
            user=self.cleaned_data['employee'],
            defaults={
                'hire_date': self.cleaned_data.get('hire_date'),
                'is_active': True
            }
        )
        if not created:
            if self.cleaned_data.get('hire_date') and not employee.hire_date:
                employee.hire_date = self.cleaned_data['hire_date']
                employee.save()
        
        # Привязываем пользователя к отделу мастера
        if self.master.department:
            employee.user.department = self.master.department
            employee.user.save()
        
        # Создаем назначение сотрудника мастеру
        from datetime import date
        EmployeeAssignment.objects.create(
            employee=employee,
            master=self.master,
            start_date=self.cleaned_data.get('hire_date') or date.today(),
            end_date=None
        )
        
        return employee
    
    class Meta:
        from .models import Employee
        model = Employee
        fields = ['hire_date']
        widgets = {
            'hire_date': forms.DateInput(
                attrs={
                    'type': 'date',
                    'class': 'form-control',
                    'placeholder': 'Дата приема на работу'
                }
            )
        }
        labels = {
            'hire_date': 'Дата приема на работу'
        }

class CreateEmployeeForm(forms.Form):
    """Форма создания нового сотрудника без учетной записи (ФИО, табельный, должность)"""
    first_name = forms.CharField(
        max_length=150, 
        label='Имя', 
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Имя'})
    )
    last_name = forms.CharField(
        max_length=150, 
        label='Фамилия', 
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Фамилия'})
    )
    middle_name = forms.CharField(
        max_length=150, 
        label='Отчество', 
        required=True, 
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Отчество'})
    )
    employee_id = forms.CharField(
        max_length=50,
        label='Табельный номер',
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Табельный номер'})
    )
    position = forms.CharField(
        max_length=200, 
        label='Должность', 
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Должность'})
    )
    hire_date = forms.DateField(
        required=False,
        label='Дата приема на работу',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    
class EmployeeAssignmentForm(forms.Form):
    """Форма назначения сотрудника мастеру на период"""
    master = forms.ModelChoiceField(
        queryset=User.objects.filter(role='master'),
        label='Мастер',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    start_date = forms.DateField(
        label='Дата начала',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    end_date = forms.DateField(
        required=False,
        label='Дата окончания',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    def __init__(self, *args, **kwargs):
        self.employee = kwargs.pop('employee', None)
        self.current_user = kwargs.pop('current_user', None)
        super().__init__(*args, **kwargs)
        if self.current_user and getattr(self.current_user, 'is_master', False):
            # Мастер может выбирать любого мастера (для простоты)
            self.fields['master'].queryset = User.objects.filter(role='master')
    def clean(self):
        cleaned = super().clean()
        start = cleaned.get('start_date')
        end = cleaned.get('end_date')
        if end and end < start:
            raise ValidationError('Дата окончания не может быть раньше даты начала')
        if self.employee and start:
            from .models import EmployeeAssignment
            from django.db.models import Q
            qs = EmployeeAssignment.objects.filter(employee=self.employee)
            # Проверяем пересечения периодов
            # Новый период [start, end_or_inf)
            if end:
                conflict = qs.filter(
                    Q(end_date__isnull=True, start_date__lte=end) |
                    Q(end_date__isnull=False, start_date__lte=end, end_date__gte=start)
                ).exists()
            else:
                conflict = qs.filter(
                    Q(end_date__isnull=True) |
                    Q(end_date__isnull=False, end_date__gte=start)
                ).exists()
            if conflict:
                raise ValidationError('Период пересекается с существующим назначением')
        return cleaned
    def save(self):
        from .models import EmployeeAssignment
        return EmployeeAssignment.objects.create(
            employee=self.employee,
            master=self.cleaned_data['master'],
            start_date=self.cleaned_data['start_date'],
            end_date=self.cleaned_data.get('end_date')
        )
    def __init__(self, *args, **kwargs):
        self.master = kwargs.pop('master', None)
        super().__init__(*args, **kwargs)
    
    def clean_employee_id(self):
        employee_id = self.cleaned_data.get('employee_id')
        
        # Проверяем, что табельный номер уникален среди пользователей и сотрудников без учетной записи
        if User.objects.filter(employee_id=employee_id).exists():
            raise ValidationError('Пользователь с таким табельным номером уже существует')
        from .models import Employee
        if Employee.objects.filter(user__isnull=True, employee_id_own=employee_id).exists():
            raise ValidationError('Сотрудник с таким табельным номером уже существует')
        
        return employee_id
    
    def save(self, commit=True):
        from .models import Employee, EmployeeAssignment
        from datetime import date
        # Создаем сотрудника без учетной записи
        employee = Employee(
            user=None,
            hire_date=self.cleaned_data.get('hire_date') or date.today(),
            is_active=True,
            last_name=self.cleaned_data['last_name'],
            first_name=self.cleaned_data['first_name'],
            middle_name=self.cleaned_data.get('middle_name', ''),
            employee_id_own=self.cleaned_data['employee_id'],
            position_own=self.cleaned_data['position'],
            department_own=self.master.department if self.master else None,
        )
        if commit:
            employee.full_clean()
            employee.save()
            if self.master:
                EmployeeAssignment.objects.create(
                    employee=employee,
                    master=self.master,
                    start_date=employee.hire_date or date.today(),
                    end_date=None
                )
        return employee

class EmployeeFilterForm(forms.Form):
    """Форма фильтрации сотрудников"""
    search = forms.CharField(
        required=False,
        label='Поиск',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'ФИО, табельный номер...'
        })
    )
    is_active = forms.ChoiceField(
        required=False,
        label='Статус',
        choices=[('', 'Все'), ('active', 'Активные'), ('inactive', 'Неактивные')],
        widget=forms.Select(attrs={'class': 'form-select'})
    )
