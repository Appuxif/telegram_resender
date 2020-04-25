# Generated by Django 3.0.5 on 2020-04-25 10:55

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('interface', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='channeltunnel',
            name='active',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='telegramclient',
            name='code',
            field=models.CharField(blank=True, max_length=20, null=True, verbose_name='Код авторизации'),
        ),
        migrations.AddField(
            model_name='telegramclient',
            name='password',
            field=models.CharField(blank=True, max_length=255, null=True, verbose_name='Пароль двухфакторной авторизации'),
        ),
        migrations.AlterField(
            model_name='channeltunnel',
            name='to_id',
            field=models.CharField(blank=True, max_length=50, null=True, verbose_name='ID второго канала'),
        ),
        migrations.AlterField(
            model_name='telegramclient',
            name='date_created',
            field=models.DateTimeField(auto_now_add=True, verbose_name='Дата создания'),
        ),
    ]
