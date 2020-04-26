import threading

import sys
from django.contrib import admin
from .models import TelegramClient, ChannelTunnel, Message
# from .apps import processor

from bot_processor import Processor

processor = None


class ChannelTunnelInline(admin.StackedInline):
    model = ChannelTunnel
    extra = 0
    ordering = ('-to_id', )
    readonly_fields = ('from_id', )
    # exclude = ('client', )


@admin.register(TelegramClient)
class TelegramClientAdmin(admin.ModelAdmin):
    list_display = ('phone', 'status', 'last_launched', 'last_modified', 'date_created')
    fieldsets = (
        ('Login codes', {'fields': ('active', 'code', 'password')}),
        ('Client info', {'fields': ('phone', 'api_id', 'api_hash')}),
        ('User Info', {'fields': ('username', 'user_id', 'status')}),
    )
    inlines = (ChannelTunnelInline,)

    # Удаляем удаленный клиент из списка
    def delete_model(self, request, obj):
        # processor = apps.processor
        if processor:
            processor.stop_client(obj)
        return super(TelegramClientAdmin, self).delete_model(request, obj)

    def save_related(self, request, form, formsets, change):
        print('in save_related')
        # print(form.instance)
        # print(formsets)
        # print(dir(formsets[0]))
        # for formset in formsets:
        #     print(formset.forms)
        #     print(formset.queryset)
        #     print(formset.instance)
        super(TelegramClientAdmin, self).save_related(request, form, formsets, change)
        if processor:
            processor.reload_client_channels(form.instance)
        # if processor:
        #     processor.reload_client()
        # return super(TelegramClientAdmin, self).save_related(request, form, formsets, change)

    def save_model(self, request, obj, form, change):
        # processor = apps.processor
        # При создании нового клиента объект этого клиента надо добавить в processor
        if processor:
            # print(processor.clients)
            if obj.active:
                processor.add_client(obj)
            else:
                processor.stop_client(obj)

            if obj.code:
                print(obj.code)
                processor.send_code_to_client(obj)

            if obj.password:
                print(obj.password)
                processor.send_password_to_client(obj)

        obj.code = None
        obj.password = None
        return super(TelegramClientAdmin, self).save_model(request, obj, form, change)


# TODO: Для отладки. Потом убрать
@admin.register(ChannelTunnel)
class ChannelTunnelAdmin(admin.ModelAdmin):
    pass


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    pass


print(sys.argv)
if ('manage.py' in sys.argv and 'runserver' in sys.argv and '--noreload' in sys.argv or
        'manage.py' not in sys.argv):
    clients = [client for client in TelegramClient.objects.all() if client.active]
    processor = Processor(clients=clients)
    t = threading.Thread(target=processor.go_processor, daemon=True)
    t.start()
