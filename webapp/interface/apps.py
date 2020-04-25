from django.apps import AppConfig
import threading

from bot_processor import Processor

processor = None


class InterfaceConfig(AppConfig):
    name = 'interface'

    # Тут запускаем процессор, который управляет запуском клиентов
    def ready(self):
        global processor
        if processor is None:
            from .models import TelegramClient
            processor = Processor(clients=list(TelegramClient.objects.all()))
            t = threading.Thread(target=processor.go_processor, daemon=True)
            t.start()
            print('Запущен процессор ботов')
