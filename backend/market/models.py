from django.db import models
from django.db.models import Sum, F, Q, Case, When
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
        TAX = 'Tax', 'Налог'
        TAX_BACK = 'TaxBack', 'Налоговый вычет/корректировка налога'
        TAX_DIVIDEND = 'TaxDividend', 'Налог на дивиденды'

    investment_account = models.ForeignKey(
        'users.InvestmentAccount', verbose_name='Инвестиционный счет', on_delete=models.CASCADE
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

    deal = models.ForeignKey('Deal', verbose_name='Сделка', on_delete=models.SET_NULL, null=True)

    @property
    def friendly_type_format(self):
        return dict(Operation.Types.choices)[self.type]

    def __str__(self):
        return f'{self.friendly_type_format} ({self.investment_account} - {self.date})'


class Transaction(models.Model):
    """
        В одной операции покупки/продажи может быть несколько транзакций,
    так бывает когда заявки реализуются по частям, а не сразу
    """
    class Meta:
        verbose_name = 'Транзакции'
        verbose_name_plural = 'Транзакции'

    secondary_id = models.CharField(verbose_name='ID', max_length=32)
    date = models.DateTimeField(verbose_name='Дата')
    quantity = models.PositiveIntegerField(verbose_name='Количество шт.')
    price = models.DecimalField(verbose_name='Цена/шт.', max_digits=20, decimal_places=4)


class DealQuerySet(models.QuerySet):
    _sell_filter = Q(operation__type=Operation.Types.SELL)
    _buy_filter = Q(operation__type__in=(Operation.Types.BUY, Operation.Types.BUY_CARD))

    def _with_buys_sells_annotations(self):
        return self.annotate(
            sells=Coalesce(Sum('operation__quantity', filter=self._sell_filter), 0),
            buys=Coalesce(Sum('operation__quantity', filter=self._buy_filter), 0)
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
    """
        Набор операций для одной компании/фонда и т.д.
    Сделка считается открытой при покупке ценной бумаги,
    а закрытой при продаже всех лотов этой ценной бумаги
    """
    class Meta:
        verbose_name = 'Сделка'
        verbose_name_plural = 'Сделки'

    objects = DealManager()

    figi = models.ForeignKey('Stock', verbose_name='Ценная бумага', on_delete=models.PROTECT)
    investment_account = models.ForeignKey(
        'users.InvestmentAccount', verbose_name='Инвестиционный счет', on_delete=models.CASCADE
    )

    def __str__(self):
        return str(self.figi)


class Stock(models.Model):
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
