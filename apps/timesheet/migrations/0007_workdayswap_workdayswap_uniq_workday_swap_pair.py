from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('timesheet', '0006_itrtimesheet'),
    ]

    operations = [
        migrations.CreateModel(
            name='WorkdaySwap',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date_a', models.DateField(verbose_name='День A')),
                ('date_b', models.DateField(verbose_name='День B')),
                ('is_active', models.BooleanField(default=True, verbose_name='Активен')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Создано')),
            ],
            options={
                'verbose_name': 'Перенос рабочего дня',
                'verbose_name_plural': 'Переносы рабочих дней',
                'ordering': ['-date_a', '-date_b'],
            },
        ),
        migrations.AddConstraint(
            model_name='workdayswap',
            constraint=models.UniqueConstraint(fields=('date_a', 'date_b'), name='uniq_workday_swap_pair'),
        ),
    ]
