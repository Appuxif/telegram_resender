from time import sleep

# import django
import os
import multiprocessing as mp

# from interface.models import TelegramClient

from bot import start_bot

# os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')
# django.setup()


class Processor:
    client_processes = {}

    def __init__(self, clients, verbose=True):
        self.clients = list(clients)
        self.verbose = verbose
        self.parent_conn, self.child_conn = mp.Pipe()
        self.vprint('Запущен процессор')

    def vprint(self, *args, **kwargs):
        if self.verbose:
            print(*args, **kwargs)

    # Основной процесс для запуска клиентов
    def go_processor(self):
        while True:
            print(self.clients)
            print(self.client_processes)
            for client in self.clients:
                self.process_client(client)
            sleep(10)

    # Обработка клиентов. Запуск и перезапуск
    def process_client(self, client):
        # Если процесс уже был запущен, проверяем его состояние
        if client.phone in self.client_processes:
            self.check_client(client)
        # Если процесс не запущен, то запускем
        else:
            self.start_new_client(client)

    # Проверяет состояние запущенного процесса клиента
    def check_client(self, client):
        client_process = self.client_processes.get(client.phone)
        if client_process is None:
            self.vprint(client.phone, 'не найден в запущенных процессах!')
            return

        if client_process['process'].is_alive():
            self.vprint(client.phone, 'жив')
        else:
            self.vprint(client.phone, 'процесс найден, но он мертв', client_process['process'].exitcode)
            self.vprint(client.phone, 'удаляю процесс из списка для перезапуска')
            self.client_processes.pop(client.phone)

    # Запуск нового клиента
    def start_new_client(self, client):
        parent_conn, child_conn = mp.Pipe()
        self.client_processes[client.phone] = {'parent_conn': parent_conn, 'child_conn': child_conn}
        self.client_processes[client.phone]['process'] = mp.Process(
            target=start_bot,
            args=(client.api_id, client.api_hash, client.phone, parent_conn, child_conn)
        )
        # p = mp.Process(
        #     target=start_bot,
        #     args=(client.api_id, client.api_hash, client.phone, parent_conn, child_conn)
        # )
        # p.exitcode
        self.client_processes[client.phone]['process'].start()
        self.vprint(client.phone, 'запущен новый процесс')


    # Остановка клиента
    def stop_client(self, client):
        self.vprint(client.phone, 'остановка клиента')
        # Убираем клиента из списка
        if client in self.clients:
            self.clients.remove(client)
            self.vprint(client.phone, 'stop_client клиент удален из списка клиентов')
        else:
            self.vprint(client.phone, 'stop_client клиент не найден в списке клиентов')

        # Убиваем процесс
        if client.phone in self.client_processes:
            client_process = self.client_processes.pop(client.phone)
            client_process['process'].terminate()
            self.vprint(client.phone, 'stop_client процесс клиента остановлен')
        else:
            self.vprint(client.phone, 'stop_client процесс клиента не найден')

    # Отправка кода авторизации клиенту
    def send_code_to_client(self, client):
        if client.code:
            if client.phone in self.client_processes:
                self.client_processes[client.phone]['parent_conn'].send(f'tg.code = {client.code}')
                self.vprint(client.phone, 'отправлен код авторизации', client.code)
            else:
                self.vprint(client.phone, 'send_code_to_client процесс клиента не найден')
        else:
            self.vprint(client.phone, 'вызван send_code_to_client но код не получен')

    # Отправка пароля аутентификации клиенту
    def send_password_to_client(self, client):
        if client.password:
            if client.phone in self.client_processes:
                self.client_processes[client.phone]['parent_conn'].send(f'tg.password = {client.password}')
                self.vprint(client.phone, 'отправлен пароль аутентификации', client.password)
            else:
                self.vprint(client.phone, 'send_password_to_client процесс клиента не найден')
        else:
            self.vprint(client.phone, 'вызван send_password_to_client но пароль не получен')

