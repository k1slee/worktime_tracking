from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from .models import User
from .permissions import IsAdministrator

@login_required
def profile_view(request):
    """Профиль пользователя"""
    return render(request, 'users/profile.html', {
        'user': request.user
    })

@staff_member_required
def user_list_view(request):
    """Список пользователей (только для администраторов)"""
    if not IsAdministrator().has_permission(request, None):
        messages.error(request, 'У вас нет прав для просмотра этой страницы')
        return redirect('home')
    
    users = User.objects.all().select_related('department')
    return render(request, 'users/user_list.html', {
        'users': users
    })