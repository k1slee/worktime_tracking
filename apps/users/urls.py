from django.urls import path
from . import views

app_name = 'users'

urlpatterns = [
    # Управление сотрудниками для мастера
    path('employees/', views.EmployeeListView.as_view(), name='employee_list'),
    path('employees/add/', views.AddEmployeeView.as_view(), name='add_employee'),
    path('employees/create/', views.CreateEmployeeView.as_view(), name='create_employee'),
    path('employees/<int:pk>/', views.employee_detail, name='employee_detail'),
    path('employees/<int:pk>/toggle/', views.toggle_employee_status, name='toggle_employee'),
    path('employees/<int:pk>/remove/', views.remove_employee, name='remove_employee'),
    
    # API
    path('api/search-users/', views.search_users_api, name='search_users_api'),
     # Профиль
    path('profile/', views.profile_view, name='profile'),
    path('profile/edit/', views.profile_edit_view, name='profile_edit'),
]