from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.db.models import Q

class Department(models.Model):
    """Отдел предприятия"""
    name = models.CharField('Название отдела', max_length=200)
    code = models.CharField('Код отдела', max_length=10, unique=True)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, 
                             null=True, blank=True, 
                             verbose_name='Родительский отдел')
    shop_chief_name = models.CharField(
        'Начальник цеха (ФИО)',
        max_length=200,
        blank=True,
        default='С.В. Ефременко',
        help_text='ФИО начальника цеха, например: С.В. Ефременко')
    
    class Meta:
        verbose_name = 'Отдел'
        verbose_name_plural = 'Отделы'
        ordering = ['name']
    
    def __str__(self):
        return self.name

class User(AbstractUser):
    """Пользователь системы"""
    ROLE_CHOICES = [
        ('admin', 'Администратор'),
        ('master', 'Мастер'),
        ('planner', 'Плановый отдел'),
        ('tb', 'ТБ'),
        ('worker', 'Работник'),
    ]
    
    employee_id = models.CharField('Табельный номер', max_length=50, unique=True)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, 
                                 null=True, blank=True, verbose_name='Отдел')
    role = models.CharField('Роль', max_length=20, choices=ROLE_CHOICES, default='worker')
    phone = models.CharField('Телефон', max_length=20, blank=True)
    position = models.CharField('Должность', max_length=200, blank=True)
    middle_name = models.CharField('Отчество', max_length=150, blank=True)
    shop_chief_name_override = models.CharField(
        'Начальник цеха (ФИО) для печати',
        max_length=200,
        blank=True,
        help_text='Если указано, переопределяет ФИО начальника цеха из отдела в печатной форме'
    )
    show_self_in_own_timesheet = models.BooleanField(
        'Показывать себя в своём табеле',
        default=True,
        help_text='Если выключено — ваша строка не будет отображаться в вашем табеле'
    )
    show_self_in_itr_timesheet = models.BooleanField(
        'Показывать себя в табеле ИТР',
        default=True,
        help_text='Если выключено — ваша строка не будет отображаться в вашем табеле ИТР'
    )
    is_foundry_master = models.BooleanField(
        'Мастер литейного графика',
        default=False,
        help_text='Если включено — все сотрудники этого мастера работают по литейному графику'
    )
    foundry_anchor_date = models.DateField(
        'Якорь литейного графика',
        null=True,
        blank=True,
        help_text='Дата, с которой начинается цикл литейного графика для сотрудников мастера'
    )
    is_ic_master = models.BooleanField(
        'Мастер ИЦ',
        default=False,
        help_text='Если включено — сотрудники мастера работают по графику ИЦ (неделя 8 / неделя 8/2)'
    )
    ic_anchor_date = models.DateField(
        'Якорь графика ИЦ',
        null=True,
        blank=True,
        help_text='Дата, с которой начинается недельный цикл графика ИЦ'
    )
    is_itr_master = models.BooleanField(
        'Мастер ИТР',
        default=False,
        help_text='Если включено — доступен отдельный табель ИТР'
    )
    allowed_masters = models.ManyToManyField(
        'self',
        verbose_name='Доступные мастера (для планового отдела)',
        related_name='permitted_planners',
        symmetrical=False,
        blank=True,
        limit_choices_to={'role': 'master'}
    )
    
    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'
        ordering = ['last_name', 'first_name']
    
    def get_full_name(self):
        """Возвращает полное ФИО с отчеством"""
        full_name = f"{self.last_name} {self.first_name}"
        if self.middle_name:
            full_name += f" {self.middle_name}"
        return full_name.strip()
    
    def __str__(self):
        return f"{self.get_full_name()} ({self.employee_id})"
    
    @property
    def is_administrator(self):
        return self.role == 'admin'
    
    @property
    def is_master(self):
        return self.role == 'master'
    
    @property
    def is_planner(self):
        return self.role == 'planner'
    
    @property
    def is_tb(self):
        return self.role == 'tb'
    
    def get_managed_employees(self):
        """Получить сотрудников, назначенных мастеру на текущую дату"""
        if not self.is_master:
            return Employee.objects.none()
        from django.utils import timezone
        today = timezone.now().date()
        return Employee.objects.filter(
            is_active=True,
            assignments__master=self
        ).filter(
            Q(assignments__end_date__isnull=True) | Q(assignments__end_date__gte=today),
            assignments__start_date__lte=today
        ).distinct()

class Employee(models.Model):
    """Сотрудник"""
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='employee_profile',
        verbose_name='Пользователь',
        null=True,
        blank=True,
    )
    master = models.ForeignKey(User, on_delete=models.SET_NULL, 
                             null=True, blank=True, 
                             related_name='managed_employees', 
                             verbose_name='Мастер', limit_choices_to={'role': 'master'})
    hire_date = models.DateField('Дата приема', null=True, blank=True)
    is_active = models.BooleanField('Активен', default=True)
    is_foundry = models.BooleanField('Литейщик', default=False, help_text='Работает по литейному графику')
    foundry_anchor_date = models.DateField(
        'Литейщик: якорь графика',
        null=True,
        blank=True,
        help_text='Если задано — Первый день "8" в табеле (8 8 8 8 8 В В  7/3 7/3 7/3 7/3 В 8/2 8/2 8/2 8/2 В)'
    )
    IC_SCHEDULE_OVERRIDE_CHOICES = [
        ('inherit', 'Наследовать от мастера'),
        ('opposite', 'Противоположный мастеру'),
        ('always_8', 'Всегда 8'),
        ('weekdays', 'Только выбранные дни недели'),
    ]
    ic_schedule_override = models.CharField(
        'ИЦ: режим',
        max_length=20,
        choices=IC_SCHEDULE_OVERRIDE_CHOICES,
        default='inherit',
        blank=False,
    )
    ic_weekdays = models.CharField(
        'ИЦ: дни недели',
        max_length=50,
        blank=True,
        help_text='Через запятую: 0..6 (0=Пн). Пример: 0,2,4'
    )
    ic_dm_weekdays = models.CharField(
        'ИЦ: дни ДМ',
        max_length=50,
        blank=True,
        help_text='Через запятую: 0..6 (0=Пн). Пример: 0,2,4'
    )
    ic_is_part_time = models.BooleanField(
        'ИЦ: совместитель',
        default=False
    )
    ic_hours_per_day = models.PositiveIntegerField(
        'ИЦ: часов в день',
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(24)]
    )
    is_itr_employee = models.BooleanField(
        'ИТР: показывать в табеле ИТР',
        default=False,
        help_text='Если включено — сотрудник будет в отдельном табеле ИТР своего мастера'
    )
    # Поля для сотрудников без учетной записи
    last_name = models.CharField('Фамилия', max_length=150, blank=True)
    first_name = models.CharField('Имя', max_length=150, blank=True)
    middle_name = models.CharField('Отчество', max_length=150, blank=True)
    employee_id_own = models.CharField('Табельный номер', max_length=50, blank=True, unique=False)
    position_own = models.CharField('Должность', max_length=200, blank=True)
    department_own = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Отдел (сотрудник без учетной записи)',
        related_name='employees_without_user'
    )
    class Meta:
        verbose_name = 'Сотрудник'
        verbose_name_plural = 'Сотрудники'
        ordering = ['last_name', 'first_name', 'user__last_name', 'user__first_name']
    
    def __str__(self):
        return self.full_name or (str(self.user) if self.user else 'Сотрудник')
    
    def clean(self):
        """Гарантируем уникальность табельного номера среди пользователей и сотрудников без учетной записи"""
        emp_id = self.employee_id
        if emp_id:
            # Конфликт с пользователем
            if User.objects.filter(employee_id=emp_id).exists():
                # Допустим, если привязан к этому же пользователю с таким employee_id — ок
                if not (self.user and self.user.employee_id == emp_id):
                    raise ValidationError({'employee_id_own': 'Табельный номер уже используется пользователем системы'})
            # Конфликт среди сотрудников без учетной записи
            qs = Employee.objects.filter(user__isnull=True).exclude(pk=self.pk)
            if qs.filter(employee_id_own=emp_id).exists():
                raise ValidationError({'employee_id_own': 'Табельный номер уже используется другим сотрудником'})
        if getattr(self, 'ic_is_part_time', False) and not getattr(self, 'ic_hours_per_day', None):
            raise ValidationError({'ic_hours_per_day': 'Укажите количество часов в день для совместителя'})
        if not getattr(self, 'ic_is_part_time', False) and getattr(self, 'ic_hours_per_day', None):
            raise ValidationError({'ic_is_part_time': 'Включите совместителя, чтобы указать часы в день'})
    
    @property
    def full_name(self):
        """Полное ФИО сотрудника"""
        if self.user:
            return self.user.get_full_name()
        parts = [self.last_name, self.first_name, self.middle_name]
        return " ".join([p for p in parts if p]).strip()
    
    @property
    def employee_id(self):
        """Табельный номер сотрудника"""
        return self.user.employee_id if self.user else self.employee_id_own
    
    @property
    def position(self):
        """Должность сотрудника"""
        return self.user.position if self.user else self.position_own
    
    @property
    def department(self):
        """Отдел сотрудника"""
        return self.user.department if self.user else self.department_own

    @property
    def short_fio(self):
        if self.user:
            last = self.user.last_name or ""
            fi = f" {self.user.first_name[0]}." if self.user.first_name else ""
            mi = f"{self.user.middle_name[0]}." if getattr(self.user, 'middle_name', '') else ""
            res = f"{last}{fi}{mi}".strip()
            return res if last else self.user.get_full_name()
        last = self.last_name or ""
        fi = f" {self.first_name[0]}." if self.first_name else ""
        mi = f"{self.middle_name[0]}." if self.middle_name else ""
        res = f"{last}{fi}{mi}".strip()
        if last:
            return res
        parts = [self.last_name, self.first_name, self.middle_name]
        return " ".join([p for p in parts if p]).strip()

class EmployeeAssignment(models.Model):
    """Назначение сотрудника мастеру в периоде"""
    employee = models.ForeignKey('Employee', on_delete=models.CASCADE, related_name='assignments', verbose_name='Сотрудник')
    master = models.ForeignKey(User, on_delete=models.CASCADE, related_name='employee_assignments', verbose_name='Мастер', limit_choices_to={'role': 'master'})
    start_date = models.DateField('Дата начала')
    end_date = models.DateField('Дата окончания', null=True, blank=True)
    class Meta:
        verbose_name = 'Назначение сотрудника'
        verbose_name_plural = 'Назначения сотрудников'
        indexes = [
            models.Index(fields=['master', 'start_date', 'end_date']),
            models.Index(fields=['employee', 'start_date', 'end_date']),
        ]
    def __str__(self):
        end = self.end_date.strftime('%d.%m.%Y') if self.end_date else 'по наст. время'
        return f"{self.employee} → {self.master} ({self.start_date.strftime('%d.%m.%Y')} - {end})"
