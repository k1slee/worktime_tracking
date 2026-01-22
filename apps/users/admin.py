from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from .models import User, Department, Employee

class CustomUserAdmin(UserAdmin):
    """Кастомный админ-класс для пользователей"""
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        (_('Personal info'), {
            'fields': (
                'last_name', 
                'first_name', 
                'middle_name',  # Добавляем отчество
                'email', 
                'phone'
            )
        }),
        (_('Work info'), {
            'fields': (
                'employee_id',
                'position',
                'department',
                'role',
            )
        }),
        (_('Permissions'), {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'username',
                'password1',
                'password2',
                'last_name',
                'first_name',
                'middle_name',  # Добавляем отчество при создании
                'email',
                'employee_id',
                'position',
                'department',
                'role',
                'phone',
            ),
        }),
    )
    
    list_display = (
        'username',
        'employee_id',
        'get_full_name',
        'position',
        'department',
        'role',
        'is_active',
        'is_staff',
    )
    
    list_filter = ('role', 'department', 'is_active', 'is_staff', 'is_superuser')
    search_fields = ('username', 'employee_id', 'last_name', 'first_name', 'middle_name', 'email')
    ordering = ('last_name', 'first_name')
    
    def get_full_name(self, obj):
        return obj.get_full_name()
    get_full_name.short_description = 'ФИО'
    get_full_name.admin_order_field = 'last_name'
    
    def save_model(self, request, obj, form, change):
        """Сохраняем пользователя и создаем запись Employee для мастера"""
        # Сохраняем пользователя
        super().save_model(request, obj, form, change)
        
        # Если это мастер, создаем/обновляем запись Employee
        if obj.role == 'master':
            employee, created = Employee.objects.get_or_create(
                user=obj,
                defaults={
                    'master': obj,  # Мастер сам себе мастер
                    'hire_date': obj.date_joined.date() if obj.date_joined else timezone.now().date(),
                    'is_active': True
                }
            )
            
            # Если запись уже существовала, обновляем
            if not created:
                # Обновляем мастера, если он не сам себе
                if employee.master != obj:
                    employee.master = obj
                    employee.save()
                
                # Обновляем дату приема, если не установлена
                if not employee.hire_date:
                    employee.hire_date = obj.date_joined.date() if obj.date_joined else timezone.now().date()
                    employee.save()

class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'parent')
    list_filter = ('parent',)
    search_fields = ('name', 'code')
    ordering = ('name',)
    fieldsets = (
        ('Основная информация', {
            'fields': ('name', 'code', 'parent')
        }),
        ('Дополнительно', {
            'fields': ('shop_chief_name',),
            'classes': ('collapse',)
        }),
    )

class EmployeeAdmin(admin.ModelAdmin):
    list_display = ('get_full_name', 'employee_id', 'master', 'hire_date', 'is_active', 'department')
    list_filter = ('master', 'is_active', 'hire_date')
    fieldsets = (
        (None, {
            'fields' : ('user', 'master', 'is_active')
        }),
        ('Дополнительно', {
            'fields': ('hire_date',),
            'classes': ('collapse',)
        }),
    )


    search_fields = ('user__last_name', 'user__first_name', 'user__employee_id', 'user__middle_name')
    raw_id_fields = ('user', 'master')
    ordering = ('user__last_name', 'user__first_name')
    
    def get_full_name(self, obj):
        return obj.full_name
    get_full_name.short_description = 'ФИО'
    get_full_name.admin_order_field = 'user__last_name'
    
    def employee_id(self, obj):
        return obj.employee_id
    employee_id.short_description = 'Табельный номер'
    employee_id.admin_order_field = 'user__employee_id'
    
    def department(self, obj):
        return obj.department
    department.short_description = 'Отдел'
    department.admin_order_field = 'user__department'

# Регистрируем модели
admin.site.register(User, CustomUserAdmin)
admin.site.register(Department, DepartmentAdmin)
admin.site.register(Employee, EmployeeAdmin)