import threading

import sys
import traceback

from django.contrib import admin
from .models import TelegramClient, ChannelTunnel, Message
from multiprocessing.connection import Client
# from .apps import processor

# from bot_processor import Processor

# processor = None


class ChannelTunnelInline(admin.StackedInline):
    model = ChannelTunnel
    extra = 0
    ordering = ('-to_id', )
    readonly_fields = ('from_id', 'from_name')
    fields = ('from_id', 'from_name', 'to_id', 'to_name', 'active')


@admin.register(TelegramClient)
class TelegramClientAdmin(admin.ModelAdmin):
    list_display = ('phone', 'status', 'last_launched', 'last_modified', 'date_created', 'active')
    fieldsets = (
        ('Login codes', {'fields': ('active', 'status', 'code', 'password'),
                         'description': 'Вводить только по требованию'}),
        ('Client info', {'fields': ('phone', 'api_id', 'api_hash')}),
        ('User Info', {'fields': ('username', 'user_id')}),
    )
    readonly_fields = ('phone', 'api_id', 'api_hash', 'username', 'user_id', 'status')
    inlines = (ChannelTunnelInline,)

    def get_fieldsets(self, request, obj=None):
        if request.path == '/admin/interface/telegramclient/add/':
            return (
                ('Client info', {'fields': ('phone', 'api_id', 'api_hash')}),
            )
        return super(TelegramClientAdmin, self).get_fieldsets(request, obj)

    def get_inlines(self, request, obj):
        if request.path == '/admin/interface/telegramclient/add/':
            return ()
        return super(TelegramClientAdmin, self).get_inlines(request, obj)

    def get_readonly_fields(self, request, obj=None):
        if request.path == '/admin/interface/telegramclient/add/':
            return []
        return super(TelegramClientAdmin, self).get_readonly_fields(request, obj)

    # Удаляем удаленный клиент из списка
    def delete_model(self, request, obj):
        try:
            with Client('/home/ubuntu/telegram_resender/webapp/processor.sock') as conn:
                conn.send(f'self.stop_client("{obj.phone}")')
        except FileNotFoundError:
            print('delete_model Сокет не найден')
        except:
            print('delete_model Ошибка подключения')
            traceback.print_exc(file=sys.stdout)
        # if processor:
        #     processor.stop_client(obj)
        return super(TelegramClientAdmin, self).delete_model(request, obj)

    def save_related(self, request, form, formsets, change):
        super(TelegramClientAdmin, self).save_related(request, form, formsets, change)
        try:
            with Client('/home/ubuntu/telegram_resender/webapp/processor.sock') as conn:
                conn.send(f'self.reload_client_channels("{form.instance.phone}")')
        except FileNotFoundError:
            print('save_related Сокет не найден')
        except:
            print('save_related Ошибка подключения')
            traceback.print_exc(file=sys.stdout)
        # if processor:
        #     processor.reload_client_channels(form.instance)

    def save_model(self, request, obj, form, change):
        try:
            with Client('/home/ubuntu/telegram_resender/webapp/processor.sock') as conn:
            # if processor:
                if obj.active:
                    # processor.add_client(obj)
                    conn.send(f'self.load_clients()')
                else:
                    conn.send(f'self.stop_client("{obj.phone}")')
                    # processor.stop_client(obj)

                if obj.code:
                    print(obj.code)
                    conn.send(f'self.send_code_to_client("{obj.phone}", "{obj.code}")')
                    # processor.send_code_to_client(obj)

                if obj.password:
                    print(obj.password)
                    conn.send(f'self.send_code_to_client("{obj.phone}", "{obj.password}")')
                    # processor.send_password_to_client(obj)
        except FileNotFoundError:
            print('save_model Сокет не найден')
        except:
            print('save_model Ошибка подключения')
            traceback.print_exc(file=sys.stdout)

        obj.code = None
        obj.password = None
        return super(TelegramClientAdmin, self).save_model(request, obj, form, change)


# TODO: Для отладки. Потом убрать
@admin.register(ChannelTunnel)
class ChannelTunnelAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'client', 'from_id', 'to_id', 'active')
    search_fields = ('from_name', 'from_id')
    list_display_links = None


# @admin.register(Message)
# class MessageAdmin(admin.ModelAdmin):
#     list_display_links = None


# print(sys.argv)
# if ('manage.py' in sys.argv and 'runserver' in sys.argv and '--noreload' in sys.argv or
#         'manage.py' not in sys.argv):
#     clients = [client for client in TelegramClient.objects.all() if client.active]
#     processor = Processor(clients=clients)
#     t = threading.Thread(target=processor.go_processor, daemon=True)
#     t.start()
