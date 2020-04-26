# coding=utf-8
import os
import tempfile
# import threading
# from multiprocessing.dummy import Process
import datetime
# import logging
from time import sleep, monotonic
from urllib import request, error
from typing import Any, Dict, List, Type, Callable, Optional, DefaultDict, Tuple
import signal

from telegram.client import Telegram, logger
from telegram.utils import AsyncResult


opener = request.build_opener()


class User:
    error_info = None
    first_name = ''
    last_name = ''
    username = ''

    def __init__(self, user_id, client):
        self.id = user_id
        self.client = client
        self.get_user()

    def get_user(self):
        user_info = self.client.call_method('getUser', {'user_id': self.id})
        user_info.wait()
        self.error_info = user_info.error_info
        if user_info.update:
            self.first_name = user_info.update.get('first_name', '')
            self.last_name = user_info.update.get('last_name', '')
            self.username = user_info.update.get('username', '')
            return


class Chat:
    error_info = None
    username = ''
    title = ''
    type = ''
    supergroup_id = ''

    def __init__(self, chat_id, client):
        self.id = chat_id
        self.client = client
        self.get_chat()

    def get_chat(self):
        chat_info = self.client.call_method('getChat', {'chat_id': self.id})
        chat_info.wait()
        self.error_info = chat_info.error_info
        if chat_info.update:
            self.title = chat_info.update.get('title', '')
            chattype = chat_info.update.get('type', {}).get('@type', '')
            self.type = MyTelegram.chat_types.get(chattype, '')
            # self.type = 'private' if chattype == 'chatTypePrivate' else chattype
            if chattype == 'chatTypeSupergroup':
                self.supergroup_id = chat_info.update.get('type', {}).get('supergroup_id', None)
                self.get_supergroup()
            elif chattype == 'chatTypePrivate':
                pass
                # self.username = ''
            return

    def get_supergroup(self):
        supergroup_info = self.client.call_method('getSupergroup', {'supergroup_id': self.supergroup_id})
        supergroup_info.wait()
        self.error_info = supergroup_info.error_info
        if supergroup_info.update:
            self.type = 'channel' if supergroup_info.update.get('is_channel', False) else self.type
            self.username = supergroup_info.update.get('username', '')
            return


class InlineKeyboardButton:
    def __init__(self, btn):
        self.text = btn.get('text', '')
        self.type = btn.get('type', {}).get('@type', '')
        self.data = btn.get('type', {}).get('data', '')


class ReplyMarkup:
    def __init__(self, reply_markup):
        self.type = reply_markup.get('@type', '')
        rows = reply_markup.get('rows', [])
        self.buttons = []
        for row in rows:
            self.buttons.extend(
                [InlineKeyboardButton(btn) for btn in row]
            )


class Message:
    class NoneObj(str):
        def __getattr__(self, item):
            return self

        def __init__(self, *args, **kwargs):
            str.__init__(self, *args, **kwargs)

    new_chat_members = [NoneObj()]
    new_chat_member = NoneObj()
    left_chat_member = NoneObj()
    content_type = NoneObj()
    is_from_self = NoneObj()
    forward_from = NoneObj()
    forward_from_chat = NoneObj()
    reply_to_message = NoneObj()
    reply_markup = NoneObj()

    def __init__(self, update, client):
        message = update.get('message', {})
        content = message.get('content', {})
        self.message_id = message.get('id', '')
        self.text = content.get('text', {}).get('text', '')
        self.caption = content.get('caption', {}).get('text', '')
        self.date = datetime.datetime.fromtimestamp(message.get('date', 0))
        self.is_from_self = message.get('sender_user_id', client.me.id) == client.me.id
        self.get_content_type(content)

        user_id = message.get('sender_user_id', '')
        self.from_user = User(user_id, client)

        chat_id = message.get('chat_id', '')
        self.chat = Chat(chat_id, client)

        if 'reply_markup' in message:
            self.reply_markup = ReplyMarkup(message.get('reply_markup', {}))

        forward_from_user_id = message.get('forward_info', {}).get('origin', {}).get('sender_user_id')
        if forward_from_user_id:
            self.forward_from = User(forward_from_user_id, client)

        forward_from_chat_id = message.get('forward_info', {}).get('from_chat_id')
        if forward_from_chat_id:
            self.forward_from_chat = Chat(forward_from_chat_id, client)

        reply_to_message_id = message.get('reply_to_message_id', 0)
        if reply_to_message_id:
            upd = client.call_method('getMessage', {'chat_id': chat_id, 'message_id': reply_to_message_id})
            upd.wait()
            if upd.update:
                upd_ = {'message': upd.update}
                self.reply_to_message = Message(upd_, client)

        self.from_message_id = message.get('forward_info', {}).get('from_message_id')

        if 'new_chat_member' in self.content_type:
            for member_user_id in content.get('member_user_ids', []):
                self.new_chat_members.append(User(member_user_id, client))
            if len(self.new_chat_members) == 1:
                self.new_chat_member = self.new_chat_members[0]

        elif 'left_chat_member' in self.content_type:
            member_user_id = content.get('user_id', self.NoneObj())
            if member_user_id:
                self.left_chat_member = User(member_user_id, client)

        if 'private' in self.chat.type:
            self.chat.username = self.from_user.username

    def get_content_type(self, content):
        self.content_type = MyTelegram.message_types.get(content.get('@type', ''), '')


class MyTelegram(Telegram):
    # Словарь типов чатов в переводе на Bot API
    chat_types = {
        'chatTypePrivate': 'private',
        'chatTypeBasicGroup': 'group',
        'chatTypeSupergroup': 'supergroup',
        # 'channel'  # канал - это супергруппа со значение is_channel = True
    }
    # Словарь типов приходящих сообщений в переводе на Bot API. Список не полный.
    message_types = {
        'messageChatAddMembers': 'new_chat_member',
        'messageChatDeleteMember': 'left_chat_member',
        'messageChatChangePhoto': 'new_chat_photo',
        'messageChatChangeTitle': 'new_chat_title',
        'messageChatDeletePhoto': 'delete_chat_photo',
        'messageChatJoinByLink': 'new_chat_member',
        'messageChatUpgradeFrom': 'migrate_from_chat_id',
        'messageChatUpgradeTo': 'migrate_to_chat_id',
        'messageVoiceNote': 'voice',
        'messageVideoNote': 'video_note',
        'messagePinMessage': 'pinned_message',
        'messageText': 'text',
        'messageAnimation': 'animation',
        'messageAudio': 'audio',
        'messagePhoto': 'photo',
        'messageVideo': 'video',
        'messageDocument': 'document',
        'messageBasicGroupChatCreate': 'group_chat_created',
        'messageContact': 'contact',
        'messageContactRegistered': 'contact',
        'messageGame': 'game',
        'messageInvoice': 'invoice',
        'messageLocation': 'location',
        'messagePassportDataReceived': 'passport_data',
        'messagePassportDataSent': 'passport_data',
        'messagePaymentSuccessful': 'successful_payment',
        'messagePaymentSuccessfulBot': 'successful_payment',
        'messagePoll': 'poll',
        'messageSticker': 'sticker',
        'messageSupergroupChatCreate': 'supergroup_chat_created',
        'messageVenue': 'venue',
        'messageWebsiteConnected': 'connected_website'
    }

    # Переменные для хранения в памяти ответа на запросы, которые могли не дойти...
    user_info_dict = {}
    chat_info_dict = {}
    code = None
    password = None
    code_required = False
    password_required = False
    # def __init__(self, *args, **kwargs):
    #     super(MyTelegram, self).__init__(*args, **kwargs)

    def do_get_me(self):
        # Иногда ответ не приходит, таймер позволяет точно получить ответ
        timer = monotonic()
        while monotonic() - timer < 5:
            ans = self.get_me()
            sleep(0.3)  # За это время ответ уже должен прийти
            if ans.ok_received or ans.update:
                # print(ans.update)
                self.me = User(ans.update['id'], self)
                print(self.phone, self.me.id, self.me.username, self.me.first_name)
                return
            print(self.phone, ans.error_info)

    def send_photo_from_url(self, chat_id, url, caption_text):
        downloaded = False
        (fd, filename) = tempfile.mkstemp('.jpg')  # Создание временного файла
        try:
            # Скачиваем файл с интернета
            with opener.open(url) as r, open(filename, 'wb') as f:
                if 'image' in r.headers['Content-Type']:
                    f.write(r.read())
                    downloaded = True
            if downloaded:
                ans = self.send_photo_from_local(chat_id, filename, caption_text)
                # Ждем ответа или десять секунд,
                timer = monotonic()
                while monotonic() - timer < 10 and not ans.ok_received:
                    sleep(0.01)
        finally:
            # а потом удалем временный файл
            os.remove(filename)

    def send_photo_from_local(self, chat_id, filename, caption_text):
        return self.call_method(
            'sendMessage',
            {
                'chat_id': chat_id,
                'input_message_content': {
                    "@type": 'inputMessagePhoto',
                    'photo': {
                        "@type": 'inputFileLocal',
                        'path': filename
                    },
                    'caption': {
                        '@type': 'formattedText',
                        'text': caption_text
                    }
                }
            }
        )

    def send_photo(self, chat_id, filename, caption_text):
        if 'http' in filename:
            # threading.Thread(target=self.send_photo_from_url, args=(chat_id, filename, caption_text), daemon=True).start()
            self.send_photo_from_url(chat_id, filename, caption_text)
        else:
            # threading.Thread(target=self.send_photo_from_local, args=(chat_id, filename, caption_text), daemon=True).start()
            self.send_photo_from_local(chat_id, filename, caption_text)

    def parse_text_entities(self, text, parse_mode):
        parse_type = 'textParseModeHTML' if parse_mode == 'HTML' else 'textParseModeMarkdown'

        # В методе call_method используется асинхрон, из-за которого часто не появляется
        # возвращаемое значение. Поэтому используем синхронное выполнение метода.
        return self._tdjson.td_execute({
            '@type': 'parseTextEntities',
            'text': text,
            'parse_mode': {'@type': parse_type, 'version': 0}
        })

    def send_message(self, chat_id, text, parse_mode='', disable_web_page_preview=True, reply_to_message_id=0):
        formatted_text = {
            '@type': 'formattedText',
            'text': text
        }
        if parse_mode:
            formatted_text = self.parse_text_entities(text, parse_mode) or formatted_text

        return self.call_method('sendMessage', {
            'chat_id': chat_id,
            'reply_to_message_id': reply_to_message_id,
            'input_message_content': {
                '@type': 'inputMessageText',
                'text': formatted_text,
                'disable_web_page_preview': disable_web_page_preview
            }
        })

    def send_splitted_message(self, chat_id, text, part_len, parse_mode='', disable_web_page_preview=True, reply_to_message_id=0):
        # Если надо, по частям
        splitted_text = []
        while len(text) > part_len:
            splitted_text.append(text[:part_len])
            text = text[part_len:]
        else:
            splitted_text.append(text)

        return [self.send_message(chat_id=chat_id, text=text, parse_mode=parse_mode,
                                  disable_web_page_preview=disable_web_page_preview,
                                  reply_to_message_id=reply_to_message_id)
                for text in splitted_text]
        # for text in splitted_text:
        #     self.send_message(chat_id=chat_id, text=text, parse_mode=parse_mode,
        #                       disable_web_page_preview=disable_web_page_preview,
        #                       reply_to_message_id=reply_to_message_id)

    def delete_message(self, chat_id, message_id):
        self.call_method('deleteMessages', {'chat_id': chat_id, 'message_ids': [message_id], 'revoke': True})

    def ban_chat_member(self, chat_id, user_id):
        ans = self.call_method('setChatMemberStatus', {
            'chat_id': chat_id,
            'user_id': user_id,
            'status': {
                '@type': 'chatMemberStatusBanned',
                'banned_until_date': 0  # Навсегда
            }
        })
        ans.wait()
        if ans.ok_received:
            print('Запрос на бан получен сервером')
            return
        if ans.error_info:
            print('Ошибка бана:', ans.error_info)
            if 'USER_ADMIN_INVALID' in ans.error_info.get('message', '') or\
                    'USER_NOT_PARTICIPANT' in ans.error_info.get('message', ''):
                return

    # Переписанный метод
    def idle(
        self, loop=True, stop_signals: Tuple = (signal.SIGINT, signal.SIGTERM, signal.SIGABRT)
    ) -> None:
        """Blocks until one of the signals are received and stops"""

        # for sig in stop_signals:
        #     signal.signal(sig, self._signal_handler)

        self._is_enabled = True

        if loop:
            while self._is_enabled:
                sleep(0.1)

    # Переписанный метод, в оригинале был баг
    def _send_data(
            self, data: Dict[Any, Any], result_id: Optional[str] = None
    ) -> AsyncResult:
        if '@extra' not in data:
            data['@extra'] = {}

        if not result_id and 'request_id' in data['@extra']:
            result_id = data['@extra']['request_id']

        async_result = AsyncResult(client=self, result_id=result_id)
        async_result.request = data
        data['@extra']['request_id'] = async_result.id

        self._results[async_result.id] = async_result   # Поменял эти две строчки местами
        self._tdjson.send(data)                         # И все стало работать нормально...

        return async_result

    def _send_telegram_code(self) -> AsyncResult:
        self.code_required = True
        logger.info('Sending code')
        while self.code is None:
            sleep(0.01)
        data = {'@type': 'checkAuthenticationCode', 'code': str(self.code)}
        self.code = None
        return self._send_data(data, result_id='updateAuthorizationState')

    def _send_password(self) -> AsyncResult:
        self.password_required = True
        logger.info('Sending password')
        while self.password is None:
            sleep(0.01)
        # password = getpass.getpass('Password:')
        data = {'@type': 'checkAuthenticationPassword', 'password': self.password}
        self.password = None
        return self._send_data(data, result_id='updateAuthorizationState')

    # def _run_handlers(self, update: Dict[Any, Any]) -> None:
    #     update_type: str = update.get('@type', 'unknown')
    #     for handler in self._update_handlers[update_type]:
    #         self._workers_queue.put((handler, (update, self)), timeout=self._queue_put_timeout)
