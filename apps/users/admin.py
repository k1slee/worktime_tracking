from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _
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

class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'parent')
    list_filter = ('parent',)
    search_fields = ('name', 'code')
    ordering = ('name',)

class EmployeeAdmin(admin.ModelAdmin):
    list_display = ('user', 'master', 'hire_date', 'is_active')
    list_filter = ('master', 'is_active', 'hire_date')
    search_fields = ('user__last_name', 'user__first_name', 'user__employee_id')
    raw_id_fields = ('user', 'master')
    ordering = ('user__last_name', 'user__first_name')

# Регистрируем модели
admin.site.register(User, CustomUserAdmin)
admin.site.register(Department, DepartmentAdmin)
admin.site.register(Employee, EmployeeAdmin)