import csv
from datetime import datetime
from django.http import HttpResponse
from django.db.models import Q
from rest_framework import viewsets, generics, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone

from .models import Timesheet
from .serializers import TimesheetSerializer, TimesheetApproveSerializer, ExportSerializer
from .filters import TimesheetFilter
from apps.users.permissions import (
    IsAdministrator, IsMaster, IsPlanner, 
    IsMasterOrPlanner, TimesheetEditPermission
)

class TimesheetViewSet(viewsets.ModelViewSet):
    """ViewSet для работы с табелями"""
    queryset = Timesheet.objects.select_related(
        'employee', 'employee__user', 'master', 'approved_by'
    ).all()
    serializer_class = TimesheetSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = TimesheetFilter
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [IsAuthenticated, TimesheetEditPermission]
        elif self.action in ['approve', 'bulk_approve']:
            permission_classes = [IsAuthenticated, IsPlanner]
        else:
            permission_classes = [IsAuthenticated, IsMasterOrPlanner]
        return [permission() for permission in permission_classes]
    
    def get_queryset(self):
        user = self.request.user
        
        # Администраторы видят все
        if user.is_authenticated and user.is_administrator:
            return self.queryset
        
        # Мастера видят только свои табели
        if user.is_authenticated and user.is_master:
            return self.queryset.filter(master=user)
        
        # Плановый отдел видит все
        if user.is_authenticated and user.is_planner:
            return self.queryset
        
        return Timesheet.objects.none()
    
    def perform_create(self, serializer):
        # Автоматически устанавливаем мастера для новых записей
        if self.request.user.is_authenticated and self.request.user.is_master:
            serializer.save(master=self.request.user)
        else:
            serializer.save()
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Утвердить табель"""
        timesheet = self.get_object()
        
        if timesheet.is_approved:
            return Response(
                {'error': 'Табель уже утвержден'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        timesheet.status = 'approved'
        timesheet.approved_by = request.user
        timesheet.approved_at = datetime.now()
        timesheet.save()
        
        # Логирование действия
        import logging
        logger = logging.getLogger('apps')
        logger.info(f'Табель {timesheet.id} утвержден пользователем {request.user}')
        
        return Response({'status': 'approved'})
    
    @action(detail=False, methods=['post'])
    def bulk_approve(self, request):
        """Массовое утверждение табелей"""
        serializer = TimesheetApproveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        timesheet_ids = serializer.validated_data['timesheet_ids']
        approve = serializer.validated_data['approve']
        
        queryset = self.get_queryset().filter(id__in=timesheet_ids)
        
        if approve:
            updated = queryset.filter(status='draft').update(
                status='approved',
                approved_by=request.user,
                approved_at=datetime.now()
            )
            message = f'Утверждено табелей: {updated}'
        else:
            updated = queryset.filter(status='approved').update(
                status='draft',
                approved_by=None,
                approved_at=None
            )
            message = f'Снято с утверждения табелей: {updated}'
        
        # Логирование
        import logging
        logger = logging.getLogger('apps')
        logger.info(f'{message} пользователем {request.user}')
        
        return Response({'message': message})
    
    @action(detail=False, methods=['post'])
    def export(self, request):
        """Экспорт табелей в CSV"""
        serializer = ExportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        data = serializer.validated_data
        queryset = self.filter_queryset(self.get_queryset())
        
        # Применяем фильтры из запроса
        if data['start_date']:
            queryset = queryset.filter(date__gte=data['start_date'])
        if data['end_date']:
            queryset = queryset.filter(date__lte=data['end_date'])
        if data['master_id']:
            queryset = queryset.filter(master_id=data['master_id'])
        if data['department_id']:
            queryset = queryset.filter(employee__department_id=data['department_id'])
        if data['status'] != 'all':
            queryset = queryset.filter(status=data['status'])
        
        # Создаем CSV-ответ
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="timesheet_{datetime.now():%Y%m%d_%H%M%S}.csv"'
        
        writer = csv.writer(response, delimiter=';')
        
        # Заголовки
        writer.writerow([
            'Дата', 'Табельный номер', 'ФИО', 'Должность', 'Отдел',
            'Мастер', 'Значение', 'Статус', 'Утверждено', 'Дата утверждения'
        ])
        
        # Данные
        for timesheet in queryset.select_related(
            'employee', 'employee__user', 'employee__user__department',
            'master', 'approved_by'
        ):
            writer.writerow([
                timesheet.date.strftime('%d.%m.%Y'),
                timesheet.employee.employee_id,
                timesheet.employee.full_name,
                timesheet.employee.position or '',
                str(timesheet.employee.department) if timesheet.employee.department else '',
                timesheet.master.get_full_name(),
                timesheet.value,
                timesheet.get_status_display(),
                timesheet.approved_by.get_full_name() if timesheet.approved_by else '',
                timesheet.approved_at.strftime('%d.%m.%Y %H:%M') if timesheet.approved_at else '',
            ])
        
        # Логирование
        import logging
        logger = logging.getLogger('apps')
        logger.info(f'Экспорт табелей ({queryset.count()} записей) пользователем {request.user}')
        
        return response