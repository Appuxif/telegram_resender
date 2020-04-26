import threading
import traceback
from time import sleep

import django
import os

import sys

from mytelegram import MyTelegram, Message


os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')

# В этой переменной будет объект телеграма
tg = None


# Слушает сообщение от родительского процесса. Передает код авторизации
def parent_listener(conn):
    while True:
        try:
            exec(conn.recv())
        except EOFError:
            print(tg.phone, 'Канал закрылся')
            return
        except Exception as err:
            print('Ошибка от родителя')
            print(err)


# def exec_on_parent(conn):
#     conn.send()
    # client.status = status
    # client.save()

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
    tg.add_update_handler('updateAuthorizationState', updateauthorizationstate_handler)  # https://core.telegram.org/tdlib/docs/classtd_1_1td__api_1_1update_authorization_state.html

    tg.login()
    tg.do_get_me()
    tg.add_message_handler(message_handler)

    tg.add_update_handler('updateMessageContent', another_update_hander)  # https://core.telegram.org/tdlib/docs/classtd_1_1td__api_1_1update_message_content.html
    tg.add_update_handler('updateMessageEdited', another_update_hander)  # https://core.telegram.org/tdlib/docs/classtd_1_1td__api_1_1update_message_edited.html
    tg.add_update_handler('updateMessageSendAcknowledged', another_update_hander)  # https://core.telegram.org/tdlib/docs/classtd_1_1td__api_1_1update_message_send_acknowledged.html
    tg.add_update_handler('updateMessageSendFailed', another_update_hander)  # https://core.telegram.org/tdlib/docs/classtd_1_1td__api_1_1update_message_send_failed.html
    # tg.add_update_handler('updateDeleteMessages', another_update_hander)  # https://core.telegram.org/tdlib/docs/classtd_1_1td__api_1_1update_delete_messages.html
    # tg.add_update_handler('updateNewChat', another_update_hander)  # https://core.telegram.org/tdlib/docs/classtd_1_1td__api_1_1update_new_chat.html
    # tg.add_update_handler('updateUser', another_update_hander)  # https://core.telegram.org/tdlib/docs/classtd_1_1td__api_1_1update_user.html

    tg.parent_conn.send('client.status = "started";'
                        f'client.user_id = "{tg.me.id}";'
                        f'client.username = "{tg.me.username}";'
                        'client.save();')
    # django.setup()
    django.db.close_old_connections()

    from interface.models import ChannelTunnel, TelegramClient, Message as TelegramMessage
    tg.ChannelTunnel = ChannelTunnel
    tg.TelegramMessage = TelegramMessage

    tg.client = TelegramClient.objects.get(phone=tg.phone)
    # Загрузка каналов в список tg.channels
    tg.channels = {}
    load_channels()

    tg.idle()


def process_message_update(update):
    msg = Message(update, tg)
    print(f'{tg.phone} {msg.chat.title}:{msg.chat.username}:{msg.from_user.first_name} '
          f'[{msg.chat.id}:{msg.from_user.id}]: {msg.content_type}:\n{msg.text}\n')

    msg_chat_id = str(msg.chat.id)
    # Проверка канала в списке
    if msg_chat_id not in tg.channels:
        # Если канала в списке нет, до добавляем его в БД и список
        add_new_channel_to_db(msg)

    elif tg.channels[msg_chat_id].active and tg.channels[msg_chat_id].to_id:
        # Если канал есть в списке и требуется пересылка, то производим пересылку сообщения в другой канал
        resend_message(update, msg)


# Обработчик всех входящих сообщений
def message_handler(update):
    print('message_handler', update, '\n')
    try:
        process_message_update(update)
    except Exception as err:
        traceback.print_exc(file=sys.stdout)
        print(tg.phone, 'Ошибка с обновлением\n', update)


# Обработчик остальных обновлений
def another_update_hander(update):
    print('another_update_hander', update)


# Обработчик состояния авторизации. Для получения состояния о закрытой сессии и о запросах кодов и паролей.
def updateauthorizationstate_handler(update):
    print('updateAuthorizationState', update)
    if 'authorizationStateWaitCode' in update.get('authorization_state', {}).get('@type', ''):
        print('code required')
        tg.parent_conn.send('client.status = "code required";'
                            'client.save();')
    elif 'authorizationStateWaitPassword' in update.get('authorization_state', {}).get('@type', ''):
        print('password required')
        tg.parent_conn.send('client.status = "password required";'
                            'client.save();')
    elif 'authorizationStateLoggingOut' in update.get('authorization_state', {}).get('@type', ''):
        print('Завершение сессии')
    elif 'authorizationStateClosed' in update.get('authorization_state', {}).get('@type', ''):
        print('session closed')
        tg.parent_conn.send(
            'self.stop_client(client, "session closed");'
        )


def load_channels(sleep_time=0):
    if tg is None:
        return
    if sleep_time:
        sleep(sleep_time)
    tg.channels = {channel.from_id: channel
                   for channel in tg.ChannelTunnel.objects.filter(client=tg.client)}
    print(tg.phone, 'Список каналов загружен')
    # TODO: Для отладки. Потом удалить
    for channel in tg.channels:
        channel = tg.channels[channel]
        print(channel.from_id, channel.from_name, channel.to_id, channel.to_name, channel.active)
    print()


def add_new_channel_to_db(msg):
    print('Новый канал!\n')
    msg_chat_id = str(msg.chat.id)
    new_channel = tg.ChannelTunnel(client=tg.client, from_id=msg_chat_id, from_name=msg.chat.title)
    new_channel.save()
    tg.channels[msg_chat_id] = new_channel


def resend_message(update, msg):
    # Проверяем наличие реплая
    print('msg.reply_to_message', msg.reply_to_message, '\n')
    msg_chat_id = str(msg.chat.id)

    # Отправка копии сообщения во второй канал
    if msg.content_type == 'text':
        mes = resend_text(update, msg)

    elif msg.content_type == 'photo':
        mes = resend_photo(update, msg)

    mes.wait(timeout=5)
    print(mes.update, '\n')

    # Сохраняем связку ID сообщений для последующей возможности реплая
    if mes.update:
        msg2 = Message({'message': mes.update}, tg)
        new_message = tg.TelegramMessage(channel=tg.channels[msg_chat_id],
                                         from_message_id=msg.message_id,
                                         to_message_id=msg2.message_id)
        new_message.save()


# Переотправляет обычный текст
def resend_text(update, msg):
    message = update.get('message', {})
    content = message.get('content', {})
    text = content.get('text', {})

    reply_to_message_id = 0
    msg_chat_id = str(msg.chat.id)
    # Если есть реплай, то нужно достать из БД ID копии сообщения этого реплая
    if msg.reply_to_message:
        from_message_id = msg.reply_to_message.message_id
        message_from_db = tg.TelegramMessage.objects.filter(channel=tg.channels[msg_chat_id],
                                                            from_message_id=from_message_id).first()
        print('message_from_db', message_from_db, '\n')
        if message_from_db:
            reply_to_message_id = message_from_db.to_message_id

    return tg.call_method('sendMessage', {
            'chat_id': msg.chat.id,
            'reply_to_message_id': reply_to_message_id,
            'input_message_content': {
                '@type': 'inputMessageText',
                'text': text,
                'disable_web_page_preview': True
            }
        })


    # return tg.send_message(tg.channels[msg_chat_id].to_id, msg.text, reply_to_message_id=reply_to_message_id)


# Переотправляет обычный фото
def resend_photo(update, msg):
    message = update.get('message', {})
    content = message.get('content', {})

    photo = content.get('photo', {})
    caption = content.get('caption', {})


# TODO: Обработчик закрытой сессии
#  Отправлять статус о закрытой сессии. Отключать клиента.
