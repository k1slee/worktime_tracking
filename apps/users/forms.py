from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import User

class CustomUserCreationForm(UserCreationForm):
    class Meta:
        model = User
        fields = ('username', 'employee_id', 'email', 'first_name', 'last_name', 
                 'department', 'role', 'position', 'phone')

class CustomUserChangeForm(UserChangeForm):
    class Meta:
        model = User
        fields = ('username', 'employee_id', 'email', 'first_name', 'last_name',
                 'department', 'role', 'position', 'phone', 'is_active')