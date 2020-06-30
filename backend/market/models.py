from typing import Optional

from django.db import models
from django.db.models import Min, Max, Sum

from users.models import InvestmentAccount


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
        InvestmentAccount, verbose_name='Инвестиционный счет', on_delete=models.CASCADE
    )
    type = models.CharField(verbose_name='Тип', max_length=30, choices=Types.choices)
    date = models.DateTimeField(verbose_name='Дата')
    is_margin_call = models.BooleanField(default=False)
    # Integer - потому что в наименьшей валюте (копейки/центы)
    payment = models.IntegerField(verbose_name='Оплата')
    currency = models.ForeignKey(Currency, verbose_name='Валюта', on_delete=models.SET_NULL, null=True)

    status = models.CharField(verbose_name='Статус', choices=Statuses.choices, max_length=16)
    secondary_id = models.CharField(verbose_name='ID', max_length=32)


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
    # Integer, в наименьшей валюте
    price = models.PositiveIntegerField(verbose_name='Цена/шт.')


class Deal(models.Model):
    """
        Набор операций для одной компании/фонда и т.д.
    Сделка считается открытой при покупке ценной бумаги,
    а закрытой при продаже всех лотов этой ценной бумаги
    """
    class Meta:
        verbose_name = 'Сделка'
        verbose_name_plural = 'Сделки'

    operations = models.ForeignKey(Operation, verbose_name='Операции', on_delete=models.CASCADE)
    is_closed = models.BooleanField(verbose_name='Закрыта?', default=False)
    investment_account = models.ForeignKey(
        InvestmentAccount, verbose_name='Инвестиционный счет', on_delete=models.CASCADE
    )

    @property
    def opened_at(self) -> Optional['datetime.datetime']:
        return self.operations.objects.filter(type=Operation.Types.BUY).aggregate(res=Min('date'))['res']

    @property
    def closed_at(self) -> Optional['datetime.datetime']:
        if self.is_closed:
            return self.operations.objects.filter(type=Operation.Types.SELL).aggregate(res=Max('date'))['res']

    @property
    def profit(self) -> float:
        """
            Чистая прибыль.
        Высчитывается как разность между суммой всех доходов (продажа ценных бумаг/дивиденды)
        и суммой всех расходов (покупка ценных бумаг/покупка ценных бумаг с карты/комиссия брокера)
        """
        income = self.operations.objects.filter(type__in=(
            Operation.Types.SELL, Operation.Types.DIVIDEND,
            Operation.Types.BUY, Operation.Types.BUY_CARD, Operation.Types.BROKER_COMMISSION
        )).aggregate(s=Sum('payment'))['s']
        return income


class Stock(models.Model):
    class Meta:
        verbose_name = 'Акция'
        verbose_name_plural = 'Акции'

    figi = models.CharField(verbose_name='FIGI', max_length=32, unique=True)
    ticker = models.CharField(verbose_name='Ticker', max_length=16, unique=True)
    isin = models.CharField(verbose_name='ISIN', max_length=32)
    # В субвалюте
    min_price_increment = models.PositiveSmallIntegerField(verbose_name='Шаг цены', null=True)
    lot = models.PositiveIntegerField(verbose_name='шт/лот')
    currency = models.ForeignKey(Currency, verbose_name='Валюта', on_delete=models.CASCADE)
    name = models.CharField(verbose_name='Название', max_length=250)
