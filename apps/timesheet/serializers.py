from rest_framework import serializers
from django.core.exceptions import ValidationError
from .models import Timesheet
from apps.users.models import Employee, User

class TimesheetSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    master_name = serializers.CharField(source='master.get_full_name', read_only=True)
    department_name = serializers.CharField(source='employee.department.name', read_only=True)
    can_edit = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = Timesheet
        fields = [
            'id', 'date', 'employee', 'employee_name', 'master', 'master_name',
            'department_name', 'value', 'status', 'can_edit', 'created_at',
            'updated_at', 'approved_by', 'approved_at'
        ]
        read_only_fields = ['status', 'approved_by', 'approved_at']
    
    def validate(self, data):
        user = self.context['request'].user
        employee = data.get('employee')
        master = data.get('master')
        
        # Мастер может работать только со своими сотрудниками
        if user.is_master:
            if employee.master != user:
                raise ValidationError({
                    'employee': 'Вы можете работать только со своими сотрудниками'
                })
            if master != user:
                raise ValidationError({
                    'master': 'Вы можете создавать табели только за себя'
                })
        
        # Проверка уникальности табеля на дату и сотрудника
        if self.instance is None:  # Создание нового
            if Timesheet.objects.filter(date=data['date'], employee=data['employee']).exists():
                raise ValidationError({
                    'employee': 'Табель для этого сотрудника на эту дату уже существует'
                })
        
        return data
    
    def validate_value(self, value):
        # Проверка допустимости значения
        allowed_codes = dict(Timesheet.CODE_CHOICES).keys()
        
        if value.isdigit():
            hours = int(value)
            if hours < 1 or hours > 24:
                raise ValidationError('Количество часов должно быть от 1 до 24')
        elif value not in allowed_codes:
            raise ValidationError(
                f'Недопустимое условное обозначение. Допустимые: {", ".join(allowed_codes)}'
            )
        
        return value

class TimesheetApproveSerializer(serializers.Serializer):
    """Сериализатор для утверждения табелей"""
    timesheet_ids = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=1
    )
    approve = serializers.BooleanField(default=True)
    
    def validate_timesheet_ids(self, value):
        # Проверка существования табелей
        from .models import Timesheet
        existing_ids = Timesheet.objects.filter(
            id__in=value
        ).values_list('id', flat=True)
        
        if len(existing_ids) != len(value):
            raise ValidationError('Некоторые табели не найдены')
        
        return value

class ExportSerializer(serializers.Serializer):
    """Сериализатор для экспорта"""
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    master_id = serializers.IntegerField(required=False, allow_null=True)
    department_id = serializers.IntegerField(required=False, allow_null=True)
    status = serializers.ChoiceField(
        choices=[('all', 'Все'), ('draft', 'Черновик'), ('approved', 'Утвержден')],
        default='all'
    )