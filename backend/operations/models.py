from django.core.validators import MaxValueValidator
from django.db import models
from polymorphic.models import PolymorphicModel

from market.models import Currency


class DealMixin(models.Model):
    class Meta:
        abstract = True

    deal = models.ForeignKey('Deal', verbose_name='Сделка', on_delete=models.PROTECT,
                             null=True, related_name='operations')


class InstrumentMixin(models.Model):
    class Meta:
        abstract = True

    instrument_type = models.CharField(verbose_name='Тип инструмента', max_length=32)
    # TODO: Stock -> Figi
    figi = models.ForeignKey('Stock', verbose_name='Ценная бумага', on_delete=models.PROTECT)


class PositivePaymentMixin(models.Model):
    class Meta:
        abstract = True


class Operation(PolymorphicModel):
    """ Базовая модель операции, все виды операций наследуются от нее """
    class Meta:
        verbose_name = 'Операция'
        verbose_name_plural = 'Операции'
        ordering = ('date', )
        constraints = [
            models.UniqueConstraint(fields=('type', 'date', 'investment_account'), name='unique operation')
        ]

    class Statuses(models.TextChoices):
        DONE = 'Done', 'Выполнено'
        DECLINE = 'Decline', 'Отказано'
        PROGRESS = 'Progress', 'В процессе'

    class Types(models.TextChoices):
        PAY_OUT = 'PayOut', 'Вывод средств'
        PAY_IN = 'PayIn', 'Пополнение счета'
        BUY = 'Buy', 'Покупка ценных бумаг'
        BUY_CARD = 'BuyCard', 'Покупка ценных бумаг с банковской карты'
        SELL = 'Sell', 'Продажа ценных бумаг'
        DIVIDEND = 'Dividend', 'Получение дивидендов'
        BROKER_COMMISSION = 'BrokerCommission', 'Комиссия брокера'
        SERVICE_COMMISSION = 'ServiceCommission', 'Комиссия за обслуживание'
        MARGIN_COMMISSION = 'MarginCommission', 'Комиссия за маржинальную торговлю'
        TAX = 'Tax', 'Налог'
        TAX_BACK = 'TaxBack', 'Налоговый вычет/корректировка налога'
        TAX_DIVIDEND = 'TaxDividend', 'Налог на дивиденды'
        UNKNOWN = 'Unknown', 'Неизвестен'

    investment_account = models.ForeignKey(
        'users.InvestmentAccount', verbose_name='Инвестиционный счет', on_delete=models.CASCADE,
        related_name='operations'
    )
    type = models.CharField(verbose_name='Тип', max_length=30, choices=Types.choices, default=Types.UNKNOWN)
    date = models.DateTimeField(verbose_name='Дата')
    is_margin_call = models.BooleanField(default=False)
    payment = models.DecimalField(verbose_name='Оплата', max_digits=20, decimal_places=4)
    currency = models.ForeignKey(Currency, verbose_name='Валюта', on_delete=models.PROTECT)


class PurchaseAndSaleOperation(Operation, InstrumentMixin, DealMixin):
    """ Первичные операции - покупка/продажа """
    quantity = models.PositiveIntegerField(verbose_name='Количество', default=0)
    commission = models.CharField(verbose_name='Комиссия', max_digits=16, decimal_places=4, default=0)
    _id = models.CharField(verbose_name='ID', max_length=32)

    def __str__(self):
        return f'{self.friendly_type_format} ({self.investment_account} - {self.date})'


class PurchaseOperation(PurchaseAndSaleOperation):
    class Meta:
        verbose_name = 'Покупка'
        verbose_name_plural = 'Покупки'


class SaleOperation(PurchaseAndSaleOperation):
    class Meta:
        verbose_name = 'Продажа'
        verbose_name_plural = 'Продажи'


class Transaction(models.Model):
    """ В одной операции покупки/продажи может быть несколько транзакций,
        так бывает когда заявки реализуются по частям, а не сразу
    """
    class Meta:
        verbose_name = 'Транзакции'
        verbose_name_plural = 'Транзакции'

    _id = models.CharField(verbose_name='ID', max_length=32, unique=True)
    operation = models.ForeignKey(PurchaseAndSaleOperation, verbose_name='Операция', on_delete=models.CASCADE)
    date = models.DateTimeField(verbose_name='Дата')
    quantity = models.PositiveIntegerField(verbose_name='Количество шт.')
    price = models.DecimalField(verbose_name='Цена/шт.', max_digits=20, decimal_places=4)


class DividendOperation(Operation, InstrumentMixin, DealMixin):
    class Meta:
        verbose_name = 'Дивиденды'
        verbose_name_plural = 'Дивиденды'

    tax = models.IntegerField(
        'Налог', validators=[MaxValueValidator(0, 'Налог должен быть отрицательным числом или 0')],
        default=0
    )
    tax_date = models.DateTimeField('Дата налога')


class CommissionOperation(Operation):
    class Meta:
        verbose_name = 'Комиссия'
        verbose_name_plural = 'Комиссии'


class ServiceCommissionOperation(CommissionOperation):
    class Meta:
        verbose_name = 'Сервисная комиссия'
        verbose_name_plural = 'Сервисные комиссии'


class MarginCommissionOperation(CommissionOperation):
    class Meta:
        verbose_name = 'Комиссия за маржинальную торговлю'
        verbose_name_plural = 'Комиссии за маржинальную торговлю'


class PayInOperation(Operation):
    class Meta:
        verbose_name = 'Пополнение средств'
        verbose_name_plural = 'Пополнения средств'


class PayOutOperation(Operation):
    class Meta:
        verbose_name = 'Вывод средств'
        verbose_name_plural = 'Выводы средств'


class TaxOperation(Operation):
    class Meta:
        verbose_name = 'Налог'
        verbose_name_plural = 'Налоги'


class TaxBackOperation(Operation):
    class Meta:
        verbose_name = 'Возврат налога'
        verbose_name_plural = 'Возвраты налога'


class Share(models.Model):
    """ Отражает долю совладельца в каждой операции """
    class Meta:
        verbose_name = 'Доля в операции'
        verbose_name_plural = 'Доли в операциях'
        constraints = [
            models.UniqueConstraint(fields=('operation', 'co_owner'), name='unique_co_owner_op')
        ]
        ordering = ['pk']

    operation = models.ForeignKey(PurchaseAndSaleOperation, verbose_name='Операция',
                                  on_delete=models.CASCADE, related_name='shares')
    co_owner = models.ForeignKey('users.CoOwner', verbose_name='Совладелец',
                                 on_delete=models.CASCADE, related_name='shares')
    value = models.DecimalField(verbose_name='Доля', max_digits=9, decimal_places=8)

    def __str__(self):
        return f'{self.co_owner.investor.username} ({self.value})'
