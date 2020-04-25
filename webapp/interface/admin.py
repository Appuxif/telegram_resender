from django.contrib import admin
from .models import TelegramClient, ChannelTunnel, Message
# from .apps import processor
from . import apps
# Register your models here.


class ChannelTunnelInline(admin.StackedInline):
    model = ChannelTunnel
    extra = 0
    # exclude = ('client', )


@admin.register(TelegramClient)
class TelegramClientAdmin(admin.ModelAdmin):
    list_display = ('phone', 'status', 'last_activity', 'date_created')
    fieldsets = (
        (None, {'fields': ('phone', 'api_id', 'api_hash')}),
        (None, {'fields': ('username', 'user_id', 'status')}),
        ('Login codes', {'fields': ('code', 'password')}),
    )
    inlines = (ChannelTunnelInline, )

    # Удаляем удаленный клиент из списка
    def delete_model(self, request, obj):
        processor = apps.processor
        if processor:
            processor.stop_client(obj)
        return super(TelegramClientAdmin, self).delete_model(request, obj)

    def save_model(self, request, obj, form, change):
        processor = apps.processor
        print('Into save_model')
        print(change)
        print(f"processor = '{processor}'")
        # При создании нового клиента объект этого клиента надо добавить в processor
        if processor and not change:
            processor.clients.append(obj)

        if processor:
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
