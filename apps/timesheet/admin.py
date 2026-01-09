from django.contrib import admin
from .models import Timesheet

@admin.register(Timesheet)
class TimesheetAdmin(admin.ModelAdmin):
    list_display = ['date', 'employee', 'master', 'value', 'status', 'approved_by', 'approved_at']
    list_filter = ['status', 'date', 'master', 'employee__user__department']  # Изменено здесь
    search_fields = ['employee__user__first_name', 'employee__user__last_name', 'employee__user__employee_id']
    readonly_fields = ['created_at', 'updated_at', 'approved_at']
    date_hierarchy = 'date'
    actions = ['approve_selected', 'unapprove_selected']
    
    def approve_selected(self, request, queryset):
        """Утвердить выбранные табели"""
        updated = queryset.filter(status='draft').update(
            status='approved',
            approved_by=request.user
        )
        self.message_user(request, f'Утверждено табелей: {updated}')
    approve_selected.short_description = 'Утвердить выбранные'
    
    def unapprove_selected(self, request, queryset):
        """Снять утверждение с выбранных табелей"""
        updated = queryset.filter(status='approved').update(
            status='draft',
            approved_by=None,
            approved_at=None
        )
        self.message_user(request, f'Снято с утверждения табелей: {updated}')
    unapprove_selected.short_description = 'Снять утверждение с выбранных'