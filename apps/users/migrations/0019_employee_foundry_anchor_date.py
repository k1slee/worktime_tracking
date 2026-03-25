from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0018_employee_ic_dm_weekdays'),
    ]

    operations = [
        migrations.AddField(
            model_name='employee',
            name='foundry_anchor_date',
            field=models.DateField(blank=True, help_text='Если задано — используется как индивидуальный якорь литейного графика (перекрывает якорь мастера)', null=True, verbose_name='Литейщик: якорь графика'),
        ),
    ]
