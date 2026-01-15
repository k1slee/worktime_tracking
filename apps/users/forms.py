from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model

User = get_user_model()

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
        
        if self.master:
            # Фильтруем пользователей: только без отдела и не привязанные к сотрудникам
            existing_employee_users = Employee.objects.values_list('user_id', flat=True)
            
            self.fields['employee'].queryset = User.objects.filter(
                department=None,
                is_active=True,
                role='master'  # Только обычные пользователи
            ).exclude(
                id__in=existing_employee_users
            ).exclude(
                role__in=['admin', 'planner']  # Исключаем админов и плановиков
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
        from .models import Employee
        
        # Создаем профиль сотрудника
        employee = Employee.objects.create(
            user=self.cleaned_data['employee'],
            master=self.master,
            hire_date=self.cleaned_data.get('hire_date'),
            is_active=True
        )
        
        # Привязываем пользователя к отделу мастера
        if self.master.department:
            employee.user.department = self.master.department
            employee.user.save()
        
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
    """Форма создания нового сотрудника (только ФИО, табельный и должность)"""
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
    
    def __init__(self, *args, **kwargs):
        self.master = kwargs.pop('master', None)
        super().__init__(*args, **kwargs)
    
    def clean_employee_id(self):
        employee_id = self.cleaned_data.get('employee_id')
        
        # Проверяем, что табельный номер уникален
        if User.objects.filter(employee_id=employee_id).exists():
            raise ValidationError('Пользователь с таким табельным номером уже существует')
        
        return employee_id
    
    def save(self, commit=True):
        from .models import Employee
        from datetime import datetime
        
        # Создаем пользователя
        username = f"emp_{self.cleaned_data['employee_id']}"
        
        # Проверяем уникальность username
        counter = 1
        original_username = username
        while User.objects.filter(username=username).exists():
            username = f"{original_username}_{counter}"
            counter += 1
        
        # Генерируем пароль (можно сделать его = табельному номеру)
        password = self.cleaned_data['employee_id']
        
        # Создаем пользователя с минимальными данными
        user = User.objects.create_user(
            username=username,
            password=password,
            employee_id=self.cleaned_data['employee_id'],
            first_name=self.cleaned_data['first_name'],
            last_name=self.cleaned_data['last_name'],
            middle_name=self.cleaned_data.get('middle_name', ''),
            position=self.cleaned_data['position'],
            department=self.master.department if self.master else None,
            role='master'  # Обычный пользователь
        )
        middle_name = self.cleaned_data.get('middle_name', '')
        if middle_name:
            # Если в модели User есть поле middle_name:
            # user.middle_name = middle_name
            # Или добавляем к first_name
            user.first_name = f"{user.first_name} {middle_name}"
            user.save()
        # Создаем профиль сотрудника
        employee = Employee.objects.create(
            user=user,
            master=self.master,
            hire_date=datetime.now().date(),
            is_active=True
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