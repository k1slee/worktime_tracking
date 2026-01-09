import logging
import time
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger('apps')

class LoggingMiddleware(MiddlewareMixin):
    """Middleware для логирования действий пользователей"""
    
    def process_request(self, request):
        request.start_time = time.time()
        return None
    
    def process_response(self, request, response):
        # Логируем только аутентифицированных пользователей
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
            
            # Логируем изменение данных
            if request.method in ['POST', 'PUT', 'PATCH', 'DELETE']:
                logger.info(f"Action: {log_data}")
            elif request.method == 'GET' and duration > 2.0:  # Долгие запросы
                logger.warning(f"Slow request: {log_data}")
        
        return response