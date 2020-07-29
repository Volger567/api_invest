import collections
from decimal import Decimal

from django.db import models
from django.db.models import Sum, F, Q, Case, When, ExpressionWrapper, Avg
from django.db.models.functions import Coalesce


class Currency(models.Model):
    """ Валюты, в которых могут проводиться операции """
    class Meta:
        verbose_name = 'Валюта'
        verbose_name_plural = 'Валюты'

    # iso_code не primary_key потому что у валют он может меняться
    iso_code = models.CharField(verbose_name='Код', max_length=3, unique=True)
    abbreviation = models.CharField(verbose_name='Знак', max_length=16)
    # Можно было бы выражать в степенях 10,
    # но не во всех валютах количество субвалюты в валюте можно выразить в виде степени 10
    number_to_basic = models.PositiveSmallIntegerField(
        verbose_name='Количество меньшей валюты в большей', default=100
    )
    name = models.CharField(verbose_name='Название', max_length=120)

    def save(self, *args, **kwargs):
        iso_code = self.iso_code
        if not iso_code.isupper():
            self.iso_code = iso_code.upper()
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Operation(models.Model):
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

    investment_account = models.ForeignKey(
        'users.InvestmentAccount', verbose_name='Инвестиционный счет', on_delete=models.CASCADE,
        related_name='operations'
    )
    type = models.CharField(verbose_name='Тип', max_length=30, choices=Types.choices)
    date = models.DateTimeField(verbose_name='Дата')
    is_margin_call = models.BooleanField(default=False)
    payment = models.DecimalField(verbose_name='Оплата', max_digits=20, decimal_places=4)
    currency = models.ForeignKey(Currency, verbose_name='Валюта', on_delete=models.SET_NULL, null=True)

    status = models.CharField(verbose_name='Статус', choices=Statuses.choices, max_length=16)
    secondary_id = models.CharField(verbose_name='ID', max_length=32)

    # Для операций покупки, продажи и комиссии
    instrument_type = models.CharField(verbose_name='Тип инструмента', max_length=32, blank=True)
    quantity = models.PositiveIntegerField(verbose_name='Количество', default=0)
    figi = models.ForeignKey('Stock', verbose_name='Ценная бумага', on_delete=models.PROTECT, null=True)

    commission = models.DecimalField(verbose_name='Комиссия', max_digits=16, decimal_places=4, null=True)

    deal = models.ForeignKey(
        'Deal', verbose_name='Сделка', on_delete=models.SET_NULL,
        null=True, related_name='operations')

    @property
    def friendly_type_format(self):
        return dict(Operation.Types.choices)[self.type]

    def __str__(self):
        return f'{self.friendly_type_format} ({self.investment_account} - {self.date})'


class Share(models.Model):
    """ Отражает долю совладельца в каждой операции """
    class Meta:
        verbose_name = 'Доля в операции'
        verbose_name_plural = 'Доли в операциях'
        constraints = [
            models.UniqueConstraint(fields=('operation', 'co_owner'), name='unique_co_owner_op')
        ]
        ordering = ['pk']

    operation = models.ForeignKey(
        Operation, verbose_name='Операция', on_delete=models.CASCADE, related_name='shares')
    co_owner = models.ForeignKey(
        'users.CoOwner', verbose_name='Совладелец', on_delete=models.CASCADE, related_name='shares')
    value = models.DecimalField(verbose_name='Доля', max_digits=9, decimal_places=8)

    def __str__(self):
        return f'{self.co_owner.investor.username} ({self.value})'


class Transaction(models.Model):
    """ В одной операции покупки/продажи может быть несколько транзакций,
        так бывает когда заявки реализуются по частям, а не сразу
    """
    class Meta:
        verbose_name = 'Транзакции'
        verbose_name_plural = 'Транзакции'
        constraints = [
            models.UniqueConstraint(fields=['secondary_id'], condition=~Q(secondary_id='-1'), name='unique_sec_id')
        ]

    secondary_id = models.CharField(verbose_name='ID', max_length=32)
    date = models.DateTimeField(verbose_name='Дата')
    quantity = models.PositiveIntegerField(verbose_name='Количество шт.')
    price = models.DecimalField(verbose_name='Цена/шт.', max_digits=20, decimal_places=4)


class DealQuerySet(models.QuerySet):
    _sell_filter = Q(operations__type=Operation.Types.SELL)
    _buy_filter = Q(operations__type__in=(Operation.Types.BUY, Operation.Types.BUY_CARD))

    def _with_buys_sells_annotations(self):
        return self.annotate(
            sells=Coalesce(Sum('operations__quantity', filter=self._sell_filter), 0),
            buys=Coalesce(Sum('operations__quantity', filter=self._buy_filter), 0)
        )

    def opened(self):
        return self._with_buys_sells_annotations().filter(~Q(sells=F('buys')) | Q(buys=0) | Q(sells=0))

    def closed(self):
        return self._with_buys_sells_annotations().filter(Q(sells=F('buys')) & ~Q(buys=0) & ~Q(sells=0))

    def with_closed_annotations(self):
        return self._with_buys_sells_annotations().annotate(
            is_closed=Case(
                When(Q(sells=F('buys')) & ~Q(buys=0) & ~Q(sells=0), then=True),
                default=False, output_field=models.BooleanField()
            )
        )


class DealManager(models.Manager):
    def get_queryset(self):
        return DealQuerySet(self.model, using=self._db)

    def closed(self):
        return self.get_queryset().closed()

    def opened(self):
        return self.get_queryset().opened()

    def with_closed_annotations(self):
        return self.get_queryset().with_closed_annotations()


class Deal(models.Model):
    """ Набор операций для одной компании/фонда и т.д.
        Сделка считается открытой если количество проданных лотов < чем купленных,
        а закрытой при продаже всех лотов этой ценной бумаги
    """
    class Meta:
        verbose_name = 'Сделка'
        verbose_name_plural = 'Сделки'

    objects = DealManager()

    figi = models.ForeignKey('Stock', verbose_name='Ценная бумага', on_delete=models.PROTECT)
    investment_account = models.ForeignKey(
        'users.InvestmentAccount', verbose_name='Инвестиционный счет', on_delete=models.CASCADE,
        related_name='deals'
    )

    def __str__(self):
        return str(self.figi)

    def recalculation_income(self):
        """ Перерасчет дохода со сделки для каждого участника """
        operations = (
            self.operations
            .prefetch_related('shares')
            .annotate(
                total_shares=Sum('shares__value'),
                price=ExpressionWrapper(F('payment')/F('quantity'), output_field=models.DecimalField())
            ).order_by('date')
        )

        total_shares = collections.Counter()
        tmp_buy = (
            operations
            .filter(type__in=(Operation.Types.BUY, Operation.Types.BUY_CARD))
            .aggregate(q=Sum('quantity'))
        )
        total_bought_quantity = tmp_buy['q']
        total_bought_commission = collections.Counter()
        total_paid = collections.Counter()
        tmp_sell = (
            operations
            .filter(type=Operation.Types.SELL)
            .aggregate(avg=Avg('price'), q=Sum('quantity'), commission=Sum('commission'))
        )
        average_sell_price = tmp_sell['avg']
        total_sold_quantity = tmp_sell['q']
        total_sold_commission = tmp_sell['commission']
        dividend_income = (
            operations
            .filter(type__in=(Operation.Types.DIVIDEND, Operation.Types.TAX_DIVIDEND))
            .aggregate(income=Coalesce(Sum('payment'), 0))['income']
        )
        for operation in operations.filter(type__in=(Operation.Types.BUY, Operation.Types.BUY_CARD)):
            for share in operation.shares.all():
                total_shares[share.co_owner] += Decimal(share.value/operation.total_shares*operation.quantity)
                total_paid[share.co_owner] += Decimal(share.value/operation.total_shares*operation.quantity) * operation.price
                total_bought_commission[share.co_owner] += operation.commission * share.value/operation.total_shares

        DealIncome.objects.exclude(co_owner__in=total_shares).delete()
        bulk_creates = [DealIncome(deal=self, co_owner=co_owner) for co_owner in total_shares]
        DealIncome.objects.bulk_create(bulk_creates, ignore_conflicts=True)
        deal_income = DealIncome.objects.filter(deal=self).all()
        bulk_updates = []
        if average_sell_price is None:
            deal_income.update(value=0)
        else:
            for co_owner, share in total_shares.items():
                average_buy_price = total_paid[co_owner]/share
                income = (average_buy_price + average_sell_price) * total_sold_quantity
                # income *= Decimal(total_sold_quantity/total_bought_quantity)
                income *= Decimal(share/total_bought_quantity)
                income += total_bought_commission[co_owner]
                income += share/total_bought_quantity * total_sold_commission
                income += share/total_bought_quantity * dividend_income
                deal = deal_income.get(co_owner=co_owner)
                deal.value = income
                bulk_updates.append(deal)

            DealIncome.objects.bulk_update(bulk_updates, ['value'])


class DealIncome(models.Model):
    """ Доход со сделки для каждого участника """
    class Meta:
        verbose_name = 'Доход за сделку'
        verbose_name_plural = 'Доходы за сделку'
        constraints = [
            models.UniqueConstraint(fields=('deal', 'co_owner'), name='unique deal co-owner')
        ]

    deal = models.ForeignKey(Deal, verbose_name='Сделка', on_delete=models.CASCADE)
    co_owner = models.ForeignKey('users.CoOwner', verbose_name='Совладелец', on_delete=models.CASCADE)
    # Сколько совладелец заработал с конкретной сделки
    value = models.DecimalField(verbose_name='Доход', max_digits=20, decimal_places=4, default=0)

    def __str__(self):
        return f'{self.deal}: {self.co_owner} ({self.value})'


class Stock(models.Model):
    """ Ценная акция на рынке """
    class Meta:
        verbose_name = 'Акция'
        verbose_name_plural = 'Акции'

    figi = models.CharField(verbose_name='FIGI', max_length=32, unique=True)
    ticker = models.CharField(verbose_name='Ticker', max_length=16, unique=True)
    isin = models.CharField(verbose_name='ISIN', max_length=32)
    min_price_increment = models.DecimalField(verbose_name='Шаг цены', max_digits=10, decimal_places=4, default=0)
    lot = models.PositiveIntegerField(verbose_name='шт/лот')
    currency = models.ForeignKey(Currency, verbose_name='Валюта', on_delete=models.CASCADE)
    name = models.CharField(verbose_name='Название', max_length=250)

    def __str__(self):
        return self.name
