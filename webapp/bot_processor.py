import traceback
from datetime import datetime, timezone
from time import sleep
import os
import multiprocessing as mp
import threading
import django
import sys

from bot import start_bot

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
# django.setup()


# Запускать только в окружении Django
class Processor:
    client_processes = {}

    def __init__(self, verbose=True):
        django.setup()
        from interface.models import TelegramClient
        self.TelegramClient = TelegramClient
        django.db.close_old_connections()
        self.load_clients()
        # self.clients = {client.phone: {'client': client} for client in TelegramClient.objects.all() if client.active}
        # self.clients = list(clients)
        self.verbose = verbose
        self.vprint('Запущен процессор')
        self.listener = threading.Thread(target=self.listener_thread)
        self.listener.start()

    def vprint(self, *args, **kwargs):
        if self.verbose:
            print(*args, **kwargs)

    # Основной процесс для запуска клиентов
    def go_processor(self):
        while True:
            # print(self.clients)
            # print(self.client_processes)
            for client_phone in self.clients:
                client = self.clients[client_phone]['client']
                try:
                    self.process_client(client)
                except Exception:
                    traceback.print_exc(file=sys.stdout)
                    print('bot_processor Ошибка клиента', client)
            sleep(10)

    # Обработка клиентов. Запуск и перезапуск
    def process_client(self, client):
        # Если процесс уже был запущен, проверяем его состояние
        if client.phone in self.client_processes:
            self.check_client(client)
        # Если процесс не запущен, то запускем
        if client.phone not in self.client_processes:
            self.start_new_client(client)
            # sleep(2)

    # Проверяет состояние запущенного процесса клиента
    def check_client(self, client):
        client_process = self.client_processes.get(client.phone)
        if client_process is None:
            self.vprint(client.phone, 'не найден в запущенных процессах!')
            return

        if client_process['process'].is_alive():
            # self.vprint(client.phone, 'жив')
            pass
        else:
            self.vprint(client.phone, 'процесс найден, но он мертв', client_process['process'].exitcode)
            self.vprint(client.phone, 'удаляю процесс из списка для перезапуска')
            self.client_processes.pop(client.phone)

    # Запуск нового клиента
    def start_new_client(self, client):
        django.db.close_old_connections()
        r1, t1 = mp.Pipe(duplex=False)
        r2, t2 = mp.Pipe(duplex=False)
        self.client_processes[client.phone] = {'send_to_child': t2}

        self.client_processes[client.phone]['process'] = mp.Process(
            target=start_bot,
            args=(client.api_id, client.api_hash, client.phone, t1, r2),
            daemon=True
        )
        self.client_processes[client.phone]['process'].start()

        self.client_processes[client.phone]['listener_thread'] = threading.Thread(
            target=self.child_listener,
            args=(client, r1),
            daemon=True
        )
        self.client_processes[client.phone]['listener_thread'].start()
        self.vprint(client.phone, 'запущен новый процесс')
        client.last_launched = datetime.now(tz=timezone.utc)
        client.save()

    def load_clients(self):
        self.clients = {client.phone: {'client': client}
                        for client in self.TelegramClient.objects.all() if client.active}

    # Добавление нового клиента в список
    def add_client(self, client_phone):
        client = self.TelegramClient.objects.get(phone=client_phone)
        if client.phone not in self.clients:
            self.vprint('Добавлен новый клиент в список', client)
            # self.clients.append(client)
            self.clients[client.phone] = {'client': client}

    # Остановка клиента
    def stop_client(self, client_phone, status='stopped'):
        self.vprint(client_phone, 'остановка клиента')
        # Убираем клиента из списка
        if client_phone in self.clients:
            # self.clients.remove(client)
            self.clients.pop(client_phone)
            self.vprint(client_phone, 'stop_client клиент удален из списка клиентов')
        else:
            self.vprint(client_phone, 'stop_client клиент не найден в списке клиентов')

        # Убиваем процесс
        if client_phone in self.client_processes:
            django.db.close_old_connections()
            client_process = self.client_processes.pop(client_phone)
            client_process['process'].terminate()
            client_process['listener_thread'].join()

            client = self.TelegramClient.objects.get(phone=client_phone)
            client.status = status
            client.active = False
            client.save()

            self.vprint(client_phone, 'stop_client процесс клиента остановлен')
        else:
            self.vprint(client_phone, 'stop_client процесс клиента не найден')

    # Перезапуск процесса клиента
    def reload_client(self, client):
        # Убиваем процесс. Он перезагрузится
        client_process = self.client_processes.get(client.phone)
        if client_process:
            client_process['process'].terminate()
            self.vprint(client.phone, 'reload_client процесс клиента остановлен')
            # client.status = status
            # client.save()
        else:
            self.vprint(client.phone, 'reload_client процесс клиента не найден')

    # Обновляет список каналов у клиента
    def reload_client_channels(self, client_phone):
        client_process = self.client_processes.get(client_phone)
        if client_process:
            client_process['send_to_child'].send(
                'load_channels(5);'
            )
        else:
            self.vprint(client_phone, 'reload_client_channels процесс клиента не найден')

    # Отправка кода авторизации клиенту
    def send_code_to_client(self, client_phone, client_code):
        if client_code:
            if client_phone in self.client_processes:
                self.client_processes[client_phone]['send_to_child'].send(f'tg.code = "{client_code}"')
                self.vprint(client_phone, 'отправлен код авторизации', client_code)
            else:
                self.vprint(client_phone, 'send_code_to_client процесс клиента не найден')
        else:
            self.vprint(client_phone, 'вызван send_code_to_client но код не получен')

    # Отправка пароля аутентификации клиенту
    def send_password_to_client(self, client_phone, client_password):
        if client_password:
            if client_phone in self.client_processes:
                self.client_processes[client_phone]['send_to_child'].send(f'tg.password = "{client_password}"')
                self.vprint(client_phone, 'отправлен пароль аутентификации', client_password)
            else:
                self.vprint(client_phone, 'send_password_to_client процесс клиента не найден')
        else:
            self.vprint(client_phone, 'вызван send_password_to_client но пароль не получен')

    # Слушает сообщение от дочернего процесса. Получает имя изображения, отправляет его в ТГ
    def child_listener(self, client, conn):
        while True:
            try:
                exec(conn.recv())
            except EOFError:
                print(client.phone, 'Канал закрылся')
                return
            except Exception as err:
                traceback.print_exc(file=sys.stdout)
                print('Ошибка от дочернего')

    # В этом потоке будут слушаться запросы от сервера
    def listener_thread(self):
        with mp.connection.Listener(('localhost', 60000), authkey=b'testauthkey') as listener:
            with listener.accept() as conn:
                while True:
                    try:
                        exec(conn.recv())
                    except KeyboardInterrupt:
                        print('KeyboardInterrupt')
                        return
                    except Exception as err:
                        traceback.print_exc(file=sys.stdout)
                        print('Ошибка листенера')


if __name__ == '__main__':
    processor = Processor()
    processor.go_processor()
