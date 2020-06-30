from django.contrib import admin

from market.models import Currency, Operation, Transaction, Deal, Stock


class CurrencyAdmin(admin.ModelAdmin):
    list_display = ('name', 'iso_code', 'abbreviation')


class OperationAdmin(admin.ModelAdmin):
    list_display = ('investment_account', 'type', 'date', 'payment', 'currency', 'status')


class TransactionAdmin(admin.ModelAdmin):
    list_display = ('date', 'quantity', 'price', 'secondary_id')


class DealAdmin(admin.ModelAdmin):
    list_display = ('investment_account', 'is_closed')


class StockAdmin(admin.ModelAdmin):
    list_display = ('name', 'ticker', 'figi', 'isin', 'lot', 'currency')


admin.site.register(Currency, CurrencyAdmin)
admin.site.register(Operation, OperationAdmin)
admin.site.register(Transaction, TransactionAdmin)
admin.site.register(Deal, DealAdmin)
admin.site.register(Stock, StockAdmin)
