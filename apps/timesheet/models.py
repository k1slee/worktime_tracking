from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.users.models import User, Employee
class MonthlyTimesheet(models.Model):
    """Месячный табель - для массового создания записей"""
    month = models.DateField('Месяц', help_text='Первый день месяца')
    master = models.ForeignKey(User, on_delete=models.CASCADE, 
                              verbose_name='Мастер', limit_choices_to={'role': 'master'})
    created_at = models.DateTimeField('Создан', auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, 
                                  related_name='created_monthly_timesheets',
                                  verbose_name='Создал')
    
    class Meta:
        verbose_name = 'Месячный табель'
        verbose_name_plural = 'Месячные табели'
        unique_together = ['month', 'master']
    
    def __str__(self):
        return f"{self.month.strftime('%B %Y')} - {self.master}"
    
    def create_daily_entries(self, default_value='В'):
        """Создать дневные записи для всех дней месяца"""
        from datetime import datetime, timedelta
        
        # Получаем первый и последний день месяца
        year = self.month.year
        month = self.month.month
        
        # Сотрудники мастера
        employees = Employee.objects.filter(master=self.master, is_active=True)
        
        # Создаем записи для каждого дня месяца
        days_created = 0
        for employee in employees:
            # Для каждого дня месяца
            day = 1
            while True:
                try:
                    date = datetime(year, month, day).date()
                except ValueError:
                    break  # Конец месяца
                
                # Проверяем, не существует ли уже запись
                if not Timesheet.objects.filter(date=date, employee=employee).exists():
                    Timesheet.objects.create(
                        date=date,
                        employee=employee,
                        master=self.master,
                        value=default_value,
                        status='draft'
                    )
                    days_created += 1
                
                day += 1
        
        return days_created
class Timesheet(models.Model):
    """Табель учета рабочего времени"""
    
    # Фиксированные условные обозначения
    CODE_CHOICES = [
        ('В', 'В - Выходной'),
        ('К', 'К - Командировка'),
        ('О', 'О - Основной отпуск'),
        ('Б', 'Б - Больничный'),
        ('Р', 'Р - Отпуск по уходу за ребенком'),
        ('ОЖ', 'ОЖ - Отпуск по уходу за ребенком (неоплачиваемый)'),
        ('М', 'М - Учебный отпуск'),
        ('Т', 'Т - Неявка по невыясненной причине'),
        ('Н', 'Н - Ночные часы'),
        ('ОС', 'ОС - Отпуск без содержания'),
        ('П', 'П - Прогул'),
        ('ЦП', 'ЦП - Целосменный прогул'),
        ('Ч', 'Ч - Часы работы'),
    ]
    
    STATUS_CHOICES = [
        ('draft', 'Черновик'),
        ('approved', 'Утвержден'),
        ('submitted', 'Сдан мастером'),
    ]
    
    date = models.DateField('Дата', db_index=True)
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, 
                                verbose_name='Сотрудник', related_name='timesheets')
    master = models.ForeignKey(User, on_delete=models.CASCADE, 
                              verbose_name='Мастер', limit_choices_to={'role': 'master'})
    value = models.CharField('Значение', max_length=10, 
                           help_text='Часы работы (1-24) или условное обозначение')
    status = models.CharField('Статус', max_length=20, 
                            choices=STATUS_CHOICES, default='draft')
    created_at = models.DateTimeField('Создано', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлено', auto_now=True)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, 
                                  null=True, blank=True, 
                                  related_name='approved_timesheets', 
                                  verbose_name='Утверждено')
    approved_at = models.DateTimeField('Дата утверждения', null=True, blank=True)
    
    class Meta:
        verbose_name = 'Табель'
        verbose_name_plural = 'Табели'
        ordering = ['-date', 'employee']
        unique_together = ['date', 'employee']
        indexes = [
            models.Index(fields=['date', 'employee']),
            models.Index(fields=['status', 'date']),
        ]
    
    def __str__(self):
        return f"{self.date} - {self.employee} - {self.value}"
    
    def clean(self):
        from django.core.exceptions import ValidationError
        
        # Проверка, что значение является либо числом от 1 до 24, либо допустимым кодом
        if self.value.isdigit():
            hours = int(self.value)
            if hours < 1 or hours > 24:
                raise ValidationError({
                    'value': 'Количество часов должно быть от 1 до 24'
                })
        elif self.value not in dict(self.CODE_CHOICES).keys():
            raise ValidationError({
                'value': f'Недопустимое условное обозначение. Допустимые: {", ".join(dict(self.CODE_CHOICES).keys())}'
            })
    
    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
    
    @property
    def is_approved(self):
        return self.status == 'approved'
    
    @property
    def can_edit(self):
        """Может ли табель быть отредактирован"""
        return not self.is_approved
    
    @property
    def display_value(self):
        """Отображаемое значение"""
        if self.value.isdigit():
            return f"{self.value} ч"
        return self.value

    @property
    def is_submitted(self):
        return self.status == 'submitted'
    
    @property
    def can_edit(self):
        """Может ли табель быть отредактирован мастером"""
        return self.status == 'draft'
    
    @property
    def can_submit(self):
        """Может ли мастер сдать табель"""
        return self.status == 'draft'
    
    @property
    def can_approve(self):
        """Может ли плановый отдел утвердить табель"""
        return self.status in ['submitted', 'draft'] and not self.is_approved
    
    def submit(self, user):
        """Сдать табель мастером"""
        if not self.can_submit:
            raise ValueError('Табель нельзя сдать')
        
        self.status = 'submitted'
        self.submitted_by = user
        self.submitted_at = timezone.now()
        self.save()
    
    def approve(self, user):
        """Утвердить табель плановым отделом"""
        if not self.can_approve:
            raise ValueError('Табель нельзя утвердить')
        
        self.status = 'approved'
        self.approved_by = user
        self.approved_at = timezone.now()
        self.save()