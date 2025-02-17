import threading
import traceback
from time import sleep, monotonic

import django
import os

import sys

from mytelegram import MyTelegram, Message, Chat


os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webapp.settings')

# В этой переменной будет объект телеграма
tg = None


def status_polling():
    # timer = monotonic()
    timer = monotonic()
    while True:
        # Обновлять статус каждые пять минут
        if monotonic() - timer > 300:
            timer = monotonic()
            tg.client.status = "working"
            tg.client.save()
            # tg.parent_conn.send('client.status = "working";'
            #                     'client.save();')
        sleep(10)


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

    # django.setup()
    django.db.close_old_connections()

    from interface.models import ChannelTunnel, TelegramClient, Message as TelegramMessage
    tg.ChannelTunnel = ChannelTunnel
    tg.TelegramMessage = TelegramMessage
    tg.client = TelegramClient.objects.filter(phone=tg.phone).first()

    if tg.client is None:
        return

    try:
        tg.login()
    except RuntimeError:
        tg.client.status = 'CODE OR PASSWORD INVALID'
        tg.client.save()
        return
    tg.do_get_me()
    tg.add_message_handler(message_handler)

    # tg.add_update_handler('updateMessageContent', another_update_hander)  # https://core.telegram.org/tdlib/docs/classtd_1_1td__api_1_1update_message_content.html
    # tg.add_update_handler('updateMessageEdited', another_update_hander)  # https://core.telegram.org/tdlib/docs/classtd_1_1td__api_1_1update_message_edited.html
    tg.add_update_handler('updateMessageSendAcknowledged', another_update_hander)  # https://core.telegram.org/tdlib/docs/classtd_1_1td__api_1_1update_message_send_acknowledged.html
    tg.add_update_handler('updateMessageSendFailed', another_update_hander)  # https://core.telegram.org/tdlib/docs/classtd_1_1td__api_1_1update_message_send_failed.html
    # tg.add_update_handler('updateDeleteMessages', another_update_hander)  # https://core.telegram.org/tdlib/docs/classtd_1_1td__api_1_1update_delete_messages.html
    # tg.add_update_handler('updateNewChat', another_update_hander)  # https://core.telegram.org/tdlib/docs/classtd_1_1td__api_1_1update_new_chat.html
    # tg.add_update_handler('updateUser', another_update_hander)  # https://core.telegram.org/tdlib/docs/classtd_1_1td__api_1_1update_user.html
    tg.add_update_handler('updateChatIsMarkedAsUnread', updateChatIsMarkedAsUnread_handler)  # https://core.telegram.org/tdlib/docs/classtd_1_1td__api_1_1update_chat_is_marked_as_unread.html

    # Загрузка каналов в список tg.channels
    tg.channels = {}
    load_channels()

    tg.client.status = "working"
    tg.client.user_id = tg.me.id
    tg.client.username = tg.me.username
    tg.client.save()

    # tg.parent_conn.send('client.status = "working";'
    #                     f'client.user_id = "{tg.me.id}";'
    #                     f'client.username = "{tg.me.username}";'
    #                     'client.save();')
    threading.Thread(target=status_polling, daemon=True).start()

    tg.idle()


def process_message_update(update):
    msg = Message(update, tg)
    print(f'{tg.phone} {msg.chat.title}:{msg.chat.username}:{msg.from_user.first_name} '
          f'[{msg.chat.id}:{msg.from_user.id}]: {msg.content_type}:\n{msg.text}\n')

    msg_chat_id = str(msg.chat.id)

    if msg_chat_id in tg.channels and tg.channels[msg_chat_id].active and tg.channels[msg_chat_id].to_id:
        # Если канал есть в списке и требуется пересылка, то производим пересылку сообщения в другой канал
        resend_message(update, msg)


# Обработчик всех входящих сообщений
def message_handler(update):
    # print('message_handler', update, '\n')
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
    django.db.close_old_connections()
    # print('updateAuthorizationState', update)
    if 'authorizationStateWaitCode' in update.get('authorization_state', {}).get('@type', ''):
        print(tg.phone, 'code required')
        tg.client.status = 'code required'
        tg.client.save()
        # tg.parent_conn.send('client.status = "code required";'
        #                     'client.save();')

    elif 'authorizationStateWaitPassword' in update.get('authorization_state', {}).get('@type', ''):
        print(tg.phone, 'password required')
        tg.client.status = 'password required'
        tg.client.save()
        # tg.parent_conn.send('client.status = "password required";'
        #                     'client.save();')
    elif 'authorizationStateLoggingOut' in update.get('authorization_state', {}).get('@type', ''):
        print(tg.phone, 'Завершение сессии')
    elif 'authorizationStateClosed' in update.get('authorization_state', {}).get('@type', ''):
        print(tg.phone, 'session closed')
        tg.parent_conn.send(f'self.stop_client("{tg.phone}", "session closed")')


# Добавляем чаты в БД по отметке "Не прочитанные"
def updateChatIsMarkedAsUnread_handler(update):
    # print('updateChatIsMarkedAsUnread_handler', update)
    chat = Chat(update.get('chat_id'), tg)
    msg_chat_id = str(chat.id)
    # Проверка канала в списке
    if msg_chat_id not in tg.channels:
        # Если канала в списке нет, до добавляем его в БД и список
        add_new_channel_to_db(chat)
    # else:
    #     print(tg.phone, 'Чат уже в списке')


def load_channels(sleep_time=0):
    if tg is None or not tg._is_enabled:
        return
    if sleep_time:
        sleep(sleep_time)
    tg.channels = {channel.from_id: channel
                   for channel in tg.ChannelTunnel.objects.filter(client=tg.client)}
    # print(tg.phone, 'Список каналов загружен')
    # TODO: Для отладки. Потом удалить
    for channel in tg.channels:
        channel = tg.channels[channel]
        print(channel.from_id, channel.from_name, channel.to_id, channel.to_name, channel.active)
    print()


def add_new_channel_to_db(chat):
    print('Новый канал!\n')
    msg_chat_id = str(chat.id)
    new_channel = tg.ChannelTunnel(client=tg.client, from_id=msg_chat_id, from_name=chat.title)
    new_channel.save()
    tg.channels[msg_chat_id] = new_channel


def resend_message(update, msg):
    # Проверяем наличие реплая
    # print('msg.reply_to_message', msg.reply_to_message, '\n')
    msg_chat_id = str(msg.chat.id)

    # Отправка копии сообщения во второй канал
    try:
        mes = resend_dict[msg.content_type](update, msg)
    except KeyError:
        mes = None

    if mes is None:
        print('mes is None')
        return
    mes.wait(timeout=5)
    # print('mes.update', mes.update, '\n')
    if mes.error_info:
        print(tg.phone, 'mes.error_info', mes.error_info, '\n')

    # Сохраняем связку ID сообщений для последующей возможности реплая
    if mes.update:
        msg2 = Message({'message': mes.update}, tg)
        new_message = tg.TelegramMessage(channel=tg.channels[msg_chat_id],
                                         from_message_id=msg.message_id,
                                         to_message_id=msg2.message_id)
        new_message.save()


# Возвращает ID сообщения для реплая
def get_reply_to_message_id(msg):
    # Если есть реплай, то нужно достать из БД ID копии сообщения этого реплая
    reply_to_message_id = 0
    if msg.reply_to_message:
        from_message_id = msg.reply_to_message.message_id
        message_from_db = tg.TelegramMessage.objects.filter(channel=tg.channels[str(msg.chat.id)],
                                                            from_message_id=from_message_id).first()
        # print('message_from_db', message_from_db, '\n')
        if message_from_db:
            reply_to_message_id = message_from_db.to_message_id
    return reply_to_message_id


# Переотправляет обычный текст
def resend_text(update, msg):
    msg_chat_id = str(msg.chat.id)

    message = update.get('message', {})
    content = message.get('content', {})
    text = content.get('text', {})

    return tg.call_method('sendMessage', {
        'chat_id': tg.channels[msg_chat_id].to_id,
        'reply_to_message_id': get_reply_to_message_id(msg),
        'input_message_content': {
            '@type': 'inputMessageText',
            'text': text,
            'disable_web_page_preview': True
        }
    })


# Переотправляет обычный фото
def resend_photo(update, msg):
    msg_chat_id = str(msg.chat.id)
    message = update.get('message', {})
    content = message.get('content', {})
    photo = content.get('photo', {}).get('sizes', [])
    if photo:
        photo_id = photo[-1]['photo']['remote']['id']
        # print('photo_id', photo_id)

        caption = content.get('caption', {})
        return tg.call_method('sendMessage', {
            'chat_id': tg.channels[msg_chat_id].to_id,
            'reply_to_message_id': get_reply_to_message_id(msg),
            'input_message_content': {
                "@type": 'inputMessagePhoto',
                'photo': {
                    '@type': 'inputFileRemote',
                    'id': photo_id
                },
                'caption': caption
            }
        })
    return None


# Переотправляет документ
def resend_document(update, msg):
    msg_chat_id = str(msg.chat.id)
    message = update.get('message', {})
    content = message.get('content', {})
    document_id = content.get('document', {}).get('document', {}).get('remote', {}).get('id')
    # print('document_id', document_id)

    if document_id:
        caption = content.get('caption', {})
        return tg.call_method('sendMessage', {
            'chat_id': tg.channels[msg_chat_id].to_id,
            'reply_to_message_id': get_reply_to_message_id(msg),
            'input_message_content': {
                "@type": 'inputMessageDocument',
                'document': {
                    '@type': 'inputFileRemote',
                    'id': document_id
                },
                'caption': caption
            }
        })
    return None


# Переотправляет видео
def resend_video(update, msg):
    msg_chat_id = str(msg.chat.id)
    message = update.get('message', {})
    content = message.get('content', {})
    video_id = content.get('video', {}).get('video', {}).get('remote', {}).get('id')
    # print('video_id', video_id)

    if video_id:
        caption = content.get('caption', {})
        return tg.call_method('sendMessage', {
            'chat_id': tg.channels[msg_chat_id].to_id,
            'reply_to_message_id': get_reply_to_message_id(msg),
            'input_message_content': {
                "@type": 'inputMessageVideo',
                'video': {
                    '@type': 'inputFileRemote',
                    'id': video_id
                },
                'caption': caption
            }
        })
    return None


# Переотправляет стикер
def resend_sticker(update, msg):
    msg_chat_id = str(msg.chat.id)
    message = update.get('message', {})
    content = message.get('content', {})
    sticker_id = content.get('sticker', {}).get('sticker', {}).get('remote', {}).get('id')
    # print('sticker_id', sticker_id)

    if sticker_id:
        return tg.call_method('sendMessage', {
            'chat_id': tg.channels[msg_chat_id].to_id,
            'reply_to_message_id': get_reply_to_message_id(msg),
            'input_message_content': {
                "@type": 'inputMessageSticker',
                'sticker': {
                    '@type': 'inputFileRemote',
                    'id': sticker_id
                },
            }
        })
    return None


# Переотправляет гифку
def resend_animation(update, msg):
    msg_chat_id = str(msg.chat.id)
    message = update.get('message', {})
    content = message.get('content', {})
    animation_id = content.get('animation', {}).get('animation', {}).get('remote', {}).get('id')
    # print('animation_id', animation_id)

    if animation_id:
        caption = content.get('caption', {})
        return tg.call_method('sendMessage', {
            'chat_id': tg.channels[msg_chat_id].to_id,
            'reply_to_message_id': get_reply_to_message_id(msg),
            'input_message_content': {
                "@type": 'inputMessageAnimation',
                'animation': {
                    '@type': 'inputFileRemote',
                    'id': animation_id
                },
                'caption': caption
            }
        })
    return None


# Переотправляет аудио
def resend_audio(update, msg):
    msg_chat_id = str(msg.chat.id)
    message = update.get('message', {})
    content = message.get('content', {})
    audio_id = content.get('audio', {}).get('audio', {}).get('remote', {}).get('id')
    # print('audio_id', audio_id)

    if audio_id:
        caption = content.get('caption', {})
        return tg.call_method('sendMessage', {
            'chat_id': tg.channels[msg_chat_id].to_id,
            'reply_to_message_id': get_reply_to_message_id(msg),
            'input_message_content': {
                "@type": 'inputMessageAudio',
                'audio': {
                    '@type': 'inputFileRemote',
                    'id': audio_id
                },
                'caption': caption
            }
        })
    return None


# Переотправляет видео запись
def resend_video_note(update, msg):
    msg_chat_id = str(msg.chat.id)
    message = update.get('message', {})
    content = message.get('content', {})
    video_note_id = content.get('video_note', {}).get('video', {}).get('remote', {}).get('id')
    # print('video_note_id', video_note_id)

    if video_note_id:
        caption = content.get('caption', {})
        return tg.call_method('sendMessage', {
            'chat_id': tg.channels[msg_chat_id].to_id,
            'reply_to_message_id': get_reply_to_message_id(msg),
            'input_message_content': {
                "@type": 'inputMessageVideoNote',
                'video_note': {
                    '@type': 'inputFileRemote',
                    'id': video_note_id
                },
                'caption': caption
            }
        })
    return None


# Переотправляет войс
def resend_voice_note(update, msg):
    msg_chat_id = str(msg.chat.id)
    message = update.get('message', {})
    content = message.get('content', {})
    voice_note_id = content.get('voice_note', {}).get('voice', {}).get('remote', {}).get('id')
    # print('voice_note_id', voice_note_id)

    if voice_note_id:
        caption = content.get('caption', {})
        return tg.call_method('sendMessage', {
            'chat_id': tg.channels[msg_chat_id].to_id,
            'reply_to_message_id': get_reply_to_message_id(msg),
            'input_message_content': {
                "@type": 'inputMessageVoiceNote',
                'voice_note': {
                    '@type': 'inputFileRemote',
                    'id': voice_note_id
                },
                'caption': caption
            }
        })
    return None


resend_dict = {
    'text': resend_text,
    'photo': resend_photo,
    'document': resend_document,
    'video': resend_video,
    'sticker': resend_sticker,
    'animation': resend_animation,
    'audio': resend_audio,
    'video_note': resend_video_note,
    'voice': resend_voice_note
}


# TODO: Обработчик закрытой сессии
#  Отправлять статус о закрытой сессии. Отключать клиента.
