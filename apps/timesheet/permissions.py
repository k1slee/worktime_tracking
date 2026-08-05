from rest_framework import permissions

class IsAdministrator(permissions.BasePermission):
    """Только администраторы"""
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_administrator

class IsMaster(permissions.BasePermission):
    """Только мастера"""
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_master
    
    def has_object_permission(self, request, view, obj):
        # Мастер может работать только со своими сотрудниками
        if hasattr(obj, 'master'):
            return obj.master == request.user
        if hasattr(obj, 'employee'):
            return obj.employee.master == request.user
        return False

class IsPlanner(permissions.BasePermission):
    """Только плановый отдел"""
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_planner

class IsMasterOrPlanner(permissions.BasePermission):
    """Мастер или плановый отдел"""
    def has_permission(self, request, view):
        return request.user.is_authenticated and (
            request.user.is_master or request.user.is_planner
        )

class TimesheetEditPermission(permissions.BasePermission):
    """Разрешение на редактирование табеля"""
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Мастер может редактировать только свои табели
        if request.user.is_master:
            return obj.master == request.user
        
        # Плановый отдел и администратор могут редактировать все
        if request.user.is_planner or request.user.is_administrator:
            return True
        
        return False