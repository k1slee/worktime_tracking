from rest_framework import permissions

class IsAdministrator(permissions.BasePermission):
    """Только администраторы"""
    def has_permission(self, request, view):
        return request.user.is_authenticated and getattr(request.user, 'role', None) == 'admin'
    
    def has_object_permission(self, request, view, obj):
        return self.has_permission(request, view)

class IsMaster(permissions.BasePermission):
    """Только мастера"""
    def has_permission(self, request, view):
        return request.user.is_authenticated and getattr(request.user, 'role', None) == 'master'
    
    def has_object_permission(self, request, view, obj):
        if not self.has_permission(request, view):
            return False
        
        # Мастер может работать только со своими сотрудниками
        if hasattr(obj, 'master'):
            return obj.master == request.user
        if hasattr(obj, 'employee'):
            # Проверяем, что сотрудник принадлежит этому мастеру
            return obj.employee.master == request.user
        return False

class IsPlanner(permissions.BasePermission):
    """Только плановый отдел"""
    def has_permission(self, request, view):
        return request.user.is_authenticated and getattr(request.user, 'role', None) == 'planner'
    
    def has_object_permission(self, request, view, obj):
        return self.has_permission(request, view)

class IsMasterOrPlanner(permissions.BasePermission):
    """Мастер или плановый отдел"""
    def has_permission(self, request, view):
        return request.user.is_authenticated and (
            getattr(request.user, 'role', None) == 'master' or 
            getattr(request.user, 'role', None) == 'planner'
        )
    
    def has_object_permission(self, request, view, obj):
        if not self.has_permission(request, view):
            return False
        
        # Плановый отдел имеет доступ ко всем объектам
        if getattr(request.user, 'role', None) == 'planner':
            return True
        
        # Мастер может работать только со своими объектами
        if getattr(request.user, 'role', None) == 'master':
            if hasattr(obj, 'master'):
                return obj.master == request.user
            if hasattr(obj, 'employee'):
                return obj.employee.master == request.user
            return False
        
        return False

class IsAdministratorOrPlanner(permissions.BasePermission):
    """Администратор или плановый отдел"""
    def has_permission(self, request, view):
        return request.user.is_authenticated and (
            getattr(request.user, 'role', None) == 'admin' or 
            getattr(request.user, 'role', None) == 'planner'
        )

class TimesheetEditPermission(permissions.BasePermission):
    """Разрешение на редактирование табеля"""
    def has_object_permission(self, request, view, obj):
        # Разрешаем безопасные методы (GET, HEAD, OPTIONS)
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Нельзя редактировать утвержденный табель
        if hasattr(obj, 'is_approved') and obj.is_approved:
            return False
        
        user = request.user
        user_role = getattr(user, 'role', None)
        
        # Мастер может редактировать только свои табели
        if user_role == 'master':
            return hasattr(obj, 'master') and obj.master == user
        
        # Плановый отдел и администраторы могут редактировать все
        if user_role in ['planner', 'admin']:
            return True
        
        return False