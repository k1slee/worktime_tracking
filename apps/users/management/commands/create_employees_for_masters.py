from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.users.models import User, Employee

class Command(BaseCommand):
    help = 'Создает записи Employee для всех мастеров без записи'

    def handle(self, *args, **kwargs):
        self.stdout.write("Поиск мастеров без записи Employee...")
        
        # Находим всех мастеров
        masters = User.objects.filter(role='master')
        self.stdout.write(f"Всего мастеров в системе: {masters.count()}")
        
        created_count = 0
        fixed_count = 0
        
        for master in masters:
            # Пытаемся найти существующую запись
            employee = Employee.objects.filter(user=master).first()
            
            if not employee:
                # Создаем новую запись
                Employee.objects.create(
                    user=master,
                    master=master,
                    hire_date=master.date_joined.date() if master.date_joined else timezone.now().date(),
                    is_active=True
                )
                created_count += 1
                self.stdout.write(self.style.SUCCESS(
                    f'Создана запись Employee для мастера: {master.get_full_name()}'
                ))
            else:
                # Проверяем и исправляем существующую запись
                needs_fix = False
                
                # Проверяем, что мастер назначен сам себе
                if employee.master != master:
                    employee.master = master
                    needs_fix = True
                
                # Проверяем дату приема
                if not employee.hire_date:
                    employee.hire_date = master.date_joined.date() if master.date_joined else timezone.now().date()
                    needs_fix = True
                
                # Проверяем активность
                if not employee.is_active:
                    employee.is_active = True
                    needs_fix = True
                
                if needs_fix:
                    employee.save()
                    fixed_count += 1
                    self.stdout.write(self.style.WARNING(
                        f'Исправлена запись Employee для мастера: {master.get_full_name()}'
                    ))
                else:
                    self.stdout.write(
                        f'Запись Employee уже существует для мастера: {master.get_full_name()}'
                    )
        
        self.stdout.write(self.style.SUCCESS(
            f'\nИтог: создано {created_count}, исправлено {fixed_count} записей'
        ))