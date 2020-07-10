from django.contrib import admin
from django.db.models import Count

from market.models import Currency, Operation, Transaction, Deal, Stock


class CurrencyAdmin(admin.ModelAdmin):
    list_display = ('name', 'iso_code', 'abbreviation')


class OperationAdmin(admin.ModelAdmin):
    list_display = ('investment_account', 'type', 'date', 'payment', 'currency', 'status')


class TransactionAdmin(admin.ModelAdmin):
    list_display = ('date', 'quantity', 'price', 'secondary_id')


class DealAdmin(admin.ModelAdmin):
    list_display = ('investment_account', 'figi', 'operations_count', '_is_closed')

    def get_queryset(self, request):
        return (
            super().get_queryset(request)
            .with_closed_annotations()
            .annotate(operations_count=Count('operations'))
            .order_by('is_closed', 'figi')
        )

    def _is_closed(self, obj):
        return obj.is_closed
    _is_closed.admin_order_field = 'is_closed'
    _is_closed.short_description = 'Сделка закрыта?'
    _is_closed.boolean = True

    def operations_count(self, instance):
        return instance.operations_count
    operations_count.short_description = 'Количество операций'


class StockAdmin(admin.ModelAdmin):
    list_display = ('name', 'ticker', 'figi', 'isin', 'lot', 'currency')


admin.site.register(Currency, CurrencyAdmin)
admin.site.register(Operation, OperationAdmin)
admin.site.register(Transaction, TransactionAdmin)
admin.site.register(Deal, DealAdmin)
admin.site.register(Stock, StockAdmin)
