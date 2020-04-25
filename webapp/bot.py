import threading
from mytelegram import MyTelegram, Message

# В этой переменной будет объект телеграма
tg = None


# Слушает сообщение от родительского процесса. Передает код авторизации
def parent_listener(conn):
    while True:
        try:
            exec(conn.recv())
        except Exception as err:
            print('Ошибка от родителя')
            print(err)


# Для запуска другим в отдельном процессе
def start_bot(api_id, api_hash, phone, parent_conn=None, child_conn=None):
    global tg
    tg = MyTelegram(
        api_id=api_id,
        api_hash=api_hash,
        phone=phone,
        database_encryption_key='mytestkeyshouldbechanged',
        files_directory=f'../{phone}/',
        library_path='../libtdjson.so.1.6.0',
        tdlib_verbosity=2,
    )

    # Запуск слушателя родительского процесса
    if child_conn is not None:
        threading.Thread(target=parent_listener, args=(child_conn, ), daemon=True).start()

    tg.parent_conn = parent_conn
    tg.login()
    tg.do_get_me()
    tg.send_message(tg.me.id, 'Запустился')
    tg.add_message_handler(message_handler)
    tg.parent_conn.send('print("BOT LOADED")')
    tg.idle()


# Обработчик всех входящих сообщений
def message_handler(update):
    print(update)
