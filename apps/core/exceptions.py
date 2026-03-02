from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404

def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is not None:
        data = {
            'success': False,
            'error': 'Ошибка обработки запроса',
            'detail': response.data,
        }
        return Response(data, status=response.status_code)
    
    if isinstance(exc, Http404):
        return Response({'success': False, 'error': 'Ресурс не найден'}, status=status.HTTP_404_NOT_FOUND)
    if isinstance(exc, PermissionDenied):
        return Response({'success': False, 'error': 'Доступ запрещен'}, status=status.HTTP_403_FORBIDDEN)
    if isinstance(exc, ValidationError):
        return Response({'success': False, 'error': 'Некорректные данные'}, status=status.HTTP_400_BAD_REQUEST)
    
    return Response({'success': False, 'error': 'Внутренняя ошибка сервера'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
