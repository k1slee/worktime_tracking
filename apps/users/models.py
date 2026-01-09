from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator, MaxValueValidator

class Department(models.Model):
    """Отдел предприятия"""
    name = models.CharField('Название отдела', max_length=200)
    code = models.CharField('Код отдела', max_length=10, unique=True)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, 
                             null=True, blank=True, 
                             verbose_name='Родительский отдел')
    
    class Meta:
        verbose_name = 'Отдел'
        verbose_name_plural = 'Отделы'
        ordering = ['name']
    
    def __str__(self):
        return self.name

class User(AbstractUser):
    """Пользователь системы"""
    ROLE_CHOICES = [
        ('admin', 'Администратор'),
        ('master', 'Мастер'),
        ('planner', 'Плановый отдел'),
    ]
    
    employee_id = models.CharField('Табельный номер', max_length=50, unique=True)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, 
                                 null=True, blank=True, verbose_name='Отдел')
    role = models.CharField('Роль', max_length=20, choices=ROLE_CHOICES, default='master')
    phone = models.CharField('Телефон', max_length=20, blank=True)
    position = models.CharField('Должность', max_length=200, blank=True)
    
    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'
    
    def __str__(self):
        return f"{self.get_full_name()} ({self.employee_id})"
    
    @property
    def is_administrator(self):
        return self.role == 'admin'
    
    @property
    def is_master(self):
        return self.role == 'master'
    
    @property
    def is_planner(self):
        return self.role == 'planner'
    
    def get_managed_employees(self):
    
        if self.is_master:
            # Импортируем здесь, чтобы избежать циклического импорта
            from django.apps import apps
            Employee = apps.get_model('users', 'Employee')
            return Employee.objects.filter(master=self)
        return Employee.objects.none()

class Employee(models.Model):
    """Сотрудник"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, 
                               related_name='employee_profile', verbose_name='Пользователь')
    master = models.ForeignKey(User, on_delete=models.SET_NULL, 
                             null=True, blank=True, 
                             related_name='managed_employees', 
                             verbose_name='Мастер', limit_choices_to={'role': 'master'})
    hire_date = models.DateField('Дата приема', null=True, blank=True)
    is_active = models.BooleanField('Активен', default=True)
    
    class Meta:
        verbose_name = 'Сотрудник'
        verbose_name_plural = 'Сотрудники'
    
    def __str__(self):
        return str(self.user)
    
    @property
    def full_name(self):
        return self.user.get_full_name()
    
    @property
    def employee_id(self):
        return self.user.employee_id
    
    @property
    def position(self):
        return self.user.position
    
    @property
    def department(self):
        return self.user.department