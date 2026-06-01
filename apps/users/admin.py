from django.contrib import admin
from django.contrib import messages
from django.contrib.auth.admin import UserAdmin
from django.http import HttpResponseRedirect
from django.urls import path, reverse
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from .models import User, Department, Employee

class ManagedEmployeeInline(admin.TabularInline):
    model = Employee
    fk_name = 'master'
    extra = 0
    fields = (
        'user',
        'last_name', 'first_name', 'middle_name',
        'employee_id_own',
        'is_active',
        'is_foundry', 'foundry_anchor_date',
        'ic_schedule_override', 'ic_weekdays', 'ic_dm_weekdays',
        'ic_is_disabled_group2',
        'ic_is_part_time', 'ic_hours_per_day',
        'is_itr_employee',
        'hire_date',
        'termination_date',
    )
    readonly_fields = ()
    show_change_link = True

class CustomUserAdmin(UserAdmin):
    """Кастомный админ-класс для пользователей"""
    change_form_template = 'admin/users/user/change_form.html'
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
                'allowed_masters',
                'shop_chief_name_override',
                'show_self_in_own_timesheet',
                'show_self_in_itr_timesheet',
                'is_foundry_master',
                'foundry_anchor_date',
                'is_ic_master',
                'ic_anchor_date',
                'is_itr_master',
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
    inlines = [ManagedEmployeeInline]
    
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

    def get_inline_instances(self, request, obj=None):
        inlines = super().get_inline_instances(request, obj)
        if obj is None:
            return []
        if getattr(obj, 'role', None) != 'master':
            return []
        return inlines
    
    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if obj.role == 'master':
            employee, created = Employee.objects.get_or_create(
                user=obj,
                defaults={
                    'master': obj,
                    'hire_date': obj.date_joined.date() if obj.date_joined else timezone.now().date(),
                    'is_active': True
                }
            )
            if not created:
                if employee.master != obj:
                    employee.master = obj
                    employee.save()
                if not employee.hire_date:
                    employee.hire_date = obj.date_joined.date() if obj.date_joined else timezone.now().date()
                    employee.save()

            from django.db.models import Q
            from .models import EmployeeAssignment
            today = timezone.now().date()
            employee_ids = list(
                EmployeeAssignment.objects.filter(
                    master=obj,
                    start_date__lte=today,
                ).filter(
                    Q(end_date__isnull=True) | Q(end_date__gte=today)
                ).values_list('employee_id', flat=True)
            )
            if employee_ids:
                Employee.objects.filter(id__in=employee_ids).exclude(master=obj).update(master=obj)

    def change_view(self, request, object_id, form_url='', extra_context=None):
        response = super().change_view(request, object_id, form_url, extra_context)
        try:
            obj = self.get_object(request, object_id)
            if obj and getattr(obj, 'role', None) == 'master':
                from django.db.models import Q
                from .models import EmployeeAssignment
                today = timezone.now().date()
                employee_ids = list(
                    EmployeeAssignment.objects.filter(
                        master=obj,
                        start_date__lte=today,
                    ).filter(
                        Q(end_date__isnull=True) | Q(end_date__gte=today)
                    ).values_list('employee_id', flat=True)
                )
                if employee_ids:
                    Employee.objects.filter(id__in=employee_ids).exclude(master=obj).update(master=obj)
        except Exception:
            pass
        return response

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                '<path:object_id>/reset-autofill/',
                self.admin_site.admin_view(self.reset_autofill_view),
                name='users_user_reset_autofill',
            ),
        ]
        return custom_urls + urls

    def reset_autofill_view(self, request, object_id):
        obj = self.get_object(request, object_id)
        if not obj or getattr(obj, 'role', None) != 'master':
            self.message_user(request, 'Доступно только для пользователей с ролью "Мастер"', level=messages.ERROR)
            return HttpResponseRedirect(reverse('admin:users_user_changelist'))

        if request.method != 'POST':
            return HttpResponseRedirect(reverse('admin:users_user_change', args=[obj.pk]))

        month_str = (request.POST.get('month') or '').strip()
        try:
            year_s, month_s = month_str.split('-', 1)
            year = int(year_s)
            month = int(month_s)
            if month < 1 or month > 12:
                raise ValueError
        except Exception:
            self.message_user(request, 'Некорректный месяц. Формат: ГГГГ-ММ', level=messages.ERROR)
            return HttpResponseRedirect(reverse('admin:users_user_change', args=[obj.pk]))

        from django.db import transaction
        from datetime import date
        import calendar
        from apps.timesheet.models import Timesheet, ItrTimesheet
        from apps.users.models import Employee, EmployeeAssignment
        from django.db.models import Q

        with transaction.atomic():
            deleted_main, _ = Timesheet.objects.filter(master=obj, date__year=year, date__month=month).delete()
            deleted_itr, _ = ItrTimesheet.objects.filter(master=obj, date__year=year, date__month=month).delete()

            month_start = date(year, month, 1)
            if month == 12:
                next_month_start = date(year + 1, 1, 1)
            else:
                next_month_start = date(year, month + 1, 1)
            month_end = next_month_start - date.resolution

            created_main = 0
            default_table = None
            try:
                from apps.timesheet.web_views import generate_default_table
                default_table = generate_default_table(year, month)
            except Exception:
                default_table = {}

            employees_main = Employee.objects.filter(is_active=True).filter(
                Q(termination_date__isnull=True) | Q(termination_date__gte=month_start)
            ).filter(
                (
                    Q(assignments__master=obj) &
                    (Q(assignments__end_date__isnull=True) | Q(assignments__end_date__gte=month_start)) &
                    Q(assignments__start_date__lte=month_end)
                ) | Q(master=obj)
            ).filter(is_itr_employee=False).distinct()

            _, last_day = calendar.monthrange(year, month)
            for emp in employees_main:
                hire_date = getattr(emp, 'hire_date', None)
                termination_date = getattr(emp, 'termination_date', None)
                legacy_ok = getattr(emp, 'master_id', None) == getattr(obj, 'id', None)
                for day in range(1, last_day + 1):
                    d = date(year, month, day)
                    if hire_date and d < hire_date:
                        continue
                    if termination_date and d > termination_date:
                        continue
                    if not legacy_ok:
                        has_assignment = EmployeeAssignment.objects.filter(
                            employee=emp, master=obj
                        ).filter(
                            Q(end_date__isnull=True) | Q(end_date__gte=d),
                            start_date__lte=d
                        ).exists()
                        if not has_assignment:
                            continue
                    Timesheet.objects.create(
                        date=d,
                        employee=emp,
                        master=obj,
                        value=default_table.get(day, '') or '',
                        status='draft'
                    )
                    created_main += 1

            created_itr = 0
            if getattr(obj, 'is_itr_master', False):
                employees_itr = Employee.objects.filter(is_active=True).filter(
                    Q(termination_date__isnull=True) | Q(termination_date__gte=month_start)
                ).filter(
                    (
                        Q(assignments__master=obj) &
                        (Q(assignments__end_date__isnull=True) | Q(assignments__end_date__gte=month_start)) &
                        Q(assignments__start_date__lte=month_end)
                    ) | Q(master=obj)
                ).filter(is_itr_employee=True).distinct()

                try:
                    from apps.timesheet.web_views import (
                        get_day_value,
                        get_foundry_anchor_for,
                        get_foundry_day_value,
                        get_ic_anchor_for,
                        get_ic_day_value,
                        parse_weekdays_csv,
                    )
                except Exception:
                    get_day_value = None

                for emp in employees_itr:
                    hire_date = getattr(emp, 'hire_date', None)
                    termination_date = getattr(emp, 'termination_date', None)
                    legacy_ok = getattr(emp, 'master_id', None) == getattr(obj, 'id', None)
                    row_user = getattr(emp, 'user', None)
                    for day in range(1, last_day + 1):
                        d = date(year, month, day)
                        if hire_date and d < hire_date:
                            continue
                        if termination_date and d > termination_date:
                            continue
                        if not legacy_ok:
                            has_assignment = EmployeeAssignment.objects.filter(
                                employee=emp, master=obj
                            ).filter(
                                Q(end_date__isnull=True) | Q(end_date__gte=d),
                                start_date__lte=d
                            ).exists()
                            if not has_assignment:
                                continue

                        holiday_value = get_day_value(d) if get_day_value else ''
                        value = default_table.get(day, '') or ''
                        schedule = None
                        if row_user and getattr(row_user, 'is_foundry_master', False):
                            schedule = 'foundry'
                        elif row_user and getattr(row_user, 'is_ic_master', False):
                            schedule = 'ic'
                        elif getattr(emp, 'is_foundry', False):
                            schedule = 'foundry'
                        else:
                            override = getattr(emp, 'ic_schedule_override', 'inherit') or 'inherit'
                            master = getattr(emp, 'master', None)
                            if override != 'inherit' or (master and getattr(master, 'is_ic_master', False)):
                                schedule = 'ic'

                        if schedule == 'foundry':
                            anchor = get_foundry_anchor_for(row_user, emp) if get_foundry_anchor_for else None
                            value = get_foundry_day_value(d, anchor) if get_foundry_day_value else value
                        elif schedule == 'ic':
                            anchor = get_ic_anchor_for(row_user, emp) if get_ic_anchor_for else None
                            override = getattr(emp, 'ic_schedule_override', 'inherit') or 'inherit'
                            force_always_8 = override == 'always_8'
                            invert_week = override == 'opposite'
                            hour_delta = -1 if getattr(emp, 'ic_is_disabled_group2', False) else 0
                            hours_per_day = None
                            if getattr(emp, 'ic_is_part_time', False):
                                hours_per_day = getattr(emp, 'ic_hours_per_day', None)
                            allowed_weekdays = None
                            if override == 'weekdays' and parse_weekdays_csv:
                                allowed_weekdays = parse_weekdays_csv(getattr(emp, 'ic_weekdays', '') or '')
                            dm_weekdays = parse_weekdays_csv(getattr(emp, 'ic_dm_weekdays', '') or '') if parse_weekdays_csv else set()
                            value = get_ic_day_value(
                                d,
                                anchor,
                                holiday_value,
                                force_always_8,
                                allowed_weekdays,
                                hours_per_day=hours_per_day,
                                weekdays_always_8=(override == 'weekdays'),
                                dm_weekdays=dm_weekdays,
                                invert_week=invert_week,
                                hour_delta=hour_delta
                            ) if get_ic_day_value else value
                        else:
                            value = holiday_value or value

                        ItrTimesheet.objects.create(
                            date=d,
                            employee=emp,
                            master=obj,
                            value=value or '',
                            status='draft'
                        )
                        created_itr += 1

        self.message_user(
            request,
            f'Сброшено табелей за {month_str}: удалено обычный={deleted_main}, ИТР={deleted_itr}; создано обычный={created_main}, ИТР={created_itr}',
        )
        return HttpResponseRedirect(reverse('admin:users_user_change', args=[obj.pk]))

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
    list_display = ('get_full_name', 'employee_id', 'master', 'hire_date', 'termination_date', 'is_active', 'is_foundry', 'department')
    list_filter = ('master', 'is_active', 'hire_date', 'termination_date', 'is_foundry', 'ic_schedule_override', 'ic_is_part_time', 'is_itr_employee')
    fieldsets = (
        (None, {
            'fields' : (
                'user', 
                'last_name', 'first_name', 'middle_name',
                'employee_id_own', 'position_own', 'department_own',
                'master',
                'is_foundry',
                'foundry_anchor_date',
                'ic_schedule_override',
                'ic_weekdays',
                'ic_dm_weekdays',
                'ic_is_disabled_group2',
                'ic_is_part_time',
                'ic_hours_per_day',
                'is_itr_employee',
                'is_active'
            )
        }),
        ('Дополнительно', {
            'fields': ('hire_date', 'termination_date'),
            'classes': ('collapse',)
        }),
    )


    search_fields = (
        'user__last_name', 'user__first_name', 'user__employee_id', 'user__middle_name',
        'last_name', 'first_name', 'middle_name', 'employee_id_own'
    )
    raw_id_fields = ('user', 'master')
    ordering = ('last_name', 'first_name', 'user__last_name', 'user__first_name')
    
    def get_full_name(self, obj):
        return obj.full_name
    get_full_name.short_description = 'ФИО'
    get_full_name.admin_order_field = 'last_name'
    
    def employee_id(self, obj):
        return obj.employee_id
    employee_id.short_description = 'Табельный номер'
    employee_id.admin_order_field = 'employee_id_own'
    
    def department(self, obj):
        return obj.department
    department.short_description = 'Отдел'
    department.admin_order_field = 'department_own'

    def save_model(self, request, obj, form, change):
        """При сохранении сотрудника в админке: если указан мастер — создать назначение на текущую дату"""
        super().save_model(request, obj, form, change)
        from .models import EmployeeAssignment
        from django.db.models import Q
        from django.utils import timezone
        today = timezone.now().date()
        if obj.master:
            has_overlap = EmployeeAssignment.objects.filter(
                employee=obj, master=obj.master
            ).filter(
                Q(end_date__isnull=True) | Q(end_date__gte=today),
                start_date__lte=today
            ).exists()
            if not has_overlap:
                EmployeeAssignment.objects.create(
                    employee=obj,
                    master=obj.master,
                    start_date=obj.hire_date or today,
                    end_date=None
                )
            # Привязка отдела пользователя к отделу мастера (если есть учетная запись)
            if obj.user and obj.master.department and obj.user.department != obj.master.department:
                obj.user.department = obj.master.department
                obj.user.save()

# Регистрируем модели
admin.site.register(User, CustomUserAdmin)
admin.site.register(Department, DepartmentAdmin)
admin.site.register(Employee, EmployeeAdmin)
