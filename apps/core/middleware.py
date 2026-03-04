import logging
import time
from django.utils.deprecation import MiddlewareMixin
from django.http import JsonResponse
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404
from django.conf import settings

logger = logging.getLogger('apps')

class LoggingMiddleware(MiddlewareMixin):
    def process_request(self, request):
        request.start_time = time.time()
        return None
    
    def process_response(self, request, response):
        if hasattr(request, 'user') and request.user.is_authenticated:
            duration = time.time() - request.start_time
            
            log_data = {
                'user': request.user.username,
                'employee_id': request.user.employee_id,
                'role': request.user.role,
                'method': request.method,
                'path': request.path,
                'status_code': response.status_code,
                'duration': round(duration, 3),
                'ip': request.META.get('REMOTE_ADDR'),
            }
            
            if request.method in ['POST', 'PUT', 'PATCH', 'DELETE']:
                logger.info(f"Action: {log_data}")
            elif request.method == 'GET' and duration > 2.0:  # Долгие запросы
                logger.warning(f"Slow request: {log_data}")
        
        return response


class ExceptionHandlingMiddleware(MiddlewareMixin):
    def _wants_json(self, request):
        accept = request.META.get('HTTP_ACCEPT', '')
        xrw = request.META.get('HTTP_X_REQUESTED_WITH', '')
        return 'application/json' in accept or xrw == 'XMLHttpRequest' or request.path.startswith('/timesheet/api')
    
    def process_exception(self, request, exception):
        if not self._wants_json(request):
            return None
        
        if isinstance(exception, Http404):
            status_code = 404
            message = 'Ресурс не найден'
        elif isinstance(exception, PermissionDenied):
            status_code = 403
            message = 'Доступ запрещен'
        elif isinstance(exception, ValidationError):
            status_code = 400
            message = 'Некорректные данные'
        else:
            status_code = 500
            message = 'Внутренняя ошибка сервера'
        
        payload = {
            'success': False,
            'error': message,
        }
        if settings.DEBUG and status_code == 500:
            payload['detail'] = str(exception)
        
        logger.exception(f"Handled exception on {request.method} {request.path}: {exception}")
        return JsonResponse(payload, status=status_code)


class RoleRestrictionMiddleware(MiddlewareMixin):
    def process_request(self, request):
        user = getattr(request, 'user', None)
        if not (user and user.is_authenticated):
            return None
        # Разрешаем только окно талонов для роли ТБ
        if getattr(user, 'is_tb', False):
            path = request.path or '/'
            allowed_prefixes = (
                '/timesheet/milk-vouchers',
                '/logout',
                '/static/',
                '/favicon.ico',
            )
            # Разрешаем саму страницу и печать
            if path == '/' or not path.startswith(allowed_prefixes):
                from django.shortcuts import redirect
                return redirect('timesheet:milk_vouchers')
        return None
