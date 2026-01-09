from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Employee, Department

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'parent']
    list_filter = ['parent']
    search_fields = ['name', 'code']
    ordering = ['name']

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ['username', 'employee_id', 'get_full_name', 'department', 'role', 'is_active']
    list_filter = ['role', 'is_active', 'department']  # department уже поле ForeignKey, это правильно
    search_fields = ['username', 'employee_id', 'first_name', 'last_name']
    ordering = ['last_name', 'first_name']
    
    fieldsets = UserAdmin.fieldsets + (
        ('Дополнительная информация', {
            'fields': ('employee_id', 'department', 'role', 'phone', 'position')
        }),
    )

@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ['employee_id', 'full_name', 'get_department', 'master', 'hire_date', 'is_active']
    list_filter = ['is_active', 'user__department', 'master']  # Изменено здесь
    search_fields = ['user__employee_id', 'user__first_name', 'user__last_name']
    raw_id_fields = ['user', 'master']
    
    def employee_id(self, obj):
        return obj.employee_id
    employee_id.short_description = 'Табельный номер'
    
    def full_name(self, obj):
        return obj.full_name
    full_name.short_description = 'ФИО'
    
    def get_department(self, obj):
        return obj.department
    get_department.short_description = 'Отдел'