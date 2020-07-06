from django.contrib import admin

from market.models import Currency, Operation, Transaction, Deal, Stock


class CurrencyAdmin(admin.ModelAdmin):
    list_display = ('name', 'iso_code', 'abbreviation')


class OperationAdmin(admin.ModelAdmin):
    list_display = ('investment_account', 'type', 'date', 'payment', 'currency', 'status')


class TransactionAdmin(admin.ModelAdmin):
    list_display = ('date', 'quantity', 'price', 'secondary_id')


class DealAdmin(admin.ModelAdmin):
    list_display = ('investment_account', 'figi', 'operations_count', 'is_closed')
    ordering = ('is_closed', 'figi')

    def operations_count(self, instance):
        return instance.operation_set.count()
    operations_count.short_description = 'Количество операций'


class StockAdmin(admin.ModelAdmin):
    list_display = ('name', 'ticker', 'figi', 'isin', 'lot', 'currency')


admin.site.register(Currency, CurrencyAdmin)
admin.site.register(Operation, OperationAdmin)
admin.site.register(Transaction, TransactionAdmin)
admin.site.register(Deal, DealAdmin)
admin.site.register(Stock, StockAdmin)
