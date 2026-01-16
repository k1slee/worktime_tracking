from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from . import web_views

router = DefaultRouter()
router.register(r'timesheets', views.TimesheetViewSet, basename='api-timesheet')

app_name = 'timesheet'

urlpatterns = [
    # Web views
    path('', web_views.TimesheetListView.as_view(), name='list'),
    path('create/', web_views.TimesheetCreateView.as_view(), name='create'),
    path('<int:pk>/', web_views.TimesheetDetailView.as_view(), name='detail'),
    path('<int:pk>/edit/', web_views.TimesheetUpdateView.as_view(), name='edit'),
    path('<int:pk>/approve/', web_views.approve_timesheet, name='approve'),
    path('export/', web_views.export_view, name='export'),
    path('bulk-approve/', web_views.bulk_approve_view, name='bulk_approve'),
    
    # API
    path('api/', include(router.urls)),

    path('monthly-create/', web_views.monthly_create_view, name='monthly_create'),
    path('bulk-edit/', web_views.bulk_edit_view, name='bulk_edit'),

    path('monthly-table/', web_views.monthly_table_view, name='monthly_table'),
    path('quick-edit/', web_views.quick_edit_timesheet, name='quick_edit'),
    path('submit/<int:timesheet_id>/', views.submit_timesheet, name='submit_timesheet'),
    path('submit-month/', views.submit_month, name='submit_month'),
    path('approve/<int:timesheet_id>/', views.approve_timesheet, name='approve_timesheet'),
    path('<int:pk>/submit/', web_views.submit_timesheet, name='submit'),
    path('bulk-submit/', web_views.bulk_submit_view, name='bulk_submit'),
    path('submit-month/', web_views.submit_month, name='submit_month'),
    path('print-monthly-table/', web_views.print_monthly_table, name='print_monthly_table'),
]