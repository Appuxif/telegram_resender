from django.db import models

# Create your models here.


# Объект клиента для запуска приложения в отдельном процессе
class TelegramClient(models.Model):
    api_id = models.CharField(max_length=20)
    api_hash = models.CharField(max_length=50)
    phone = models.CharField('Номер телефона', max_length=20, unique=True)

    code = models.CharField('Код авторизации', max_length=20, null=True, blank=True)
    password = models.CharField('Пароль двухфакторной авторизации', max_length=255, null=True, blank=True)

    username = models.CharField(max_length=50, null=True, blank=True)
    user_id = models.CharField(max_length=50, null=True, blank=True)
    status = models.CharField(max_length=50, null=True, blank=True)

    last_modified = models.DateTimeField('Дата последней активности', auto_now=True)
    last_launched = models.DateTimeField('Дата последнего запуска', null=True)
    date_created = models.DateTimeField('Дата создания', auto_now_add=True)

    active = models.BooleanField('Запущен', default=True)

    def __str__(self):
        return str(self.phone)


# Каналы для преадресации
class ChannelTunnel(models.Model):
    client = models.ForeignKey(TelegramClient, on_delete=models.CASCADE)

    from_id = models.CharField('ID первого канала', max_length=50)
    from_name = models.CharField('Имя первого канала', max_length=50, null=True, blank=True)

    to_id = models.CharField('ID второго канала', max_length=50, null=True, blank=True)
    to_name = models.CharField('Имя второго канала', max_length=50, null=True, blank=True)

    active = models.BooleanField(default=False)

    def __str__(self):
        return str(self.from_id) + ' - ' + str(self.to_id)


# Объект для соответствия сообщений с одного канала в другой. Нужно для реплаев
class Message(models.Model):
    channel = models.ForeignKey(ChannelTunnel, on_delete=models.CASCADE)
    from_message_id = models.CharField('ID оригинального сообщения', max_length=50)
    to_message_id = models.CharField('ID копии сообщения', max_length=50)

    def __str__(self):
        return str(self.from_message_id) + ' - ' + str(self.to_message_id)
