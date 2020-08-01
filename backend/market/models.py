import collections
from decimal import Decimal

from django.db import models
from django.db.models import Sum, F, Q, Case, When, ExpressionWrapper, Avg
from django.db.models.functions import Coalesce
from polymorphic.models import PolymorphicModel

from operations.models import Sale, Purchase, Dividend


class InstrumentType(PolymorphicModel):
    class Meta:
        verbose_name = 'Торговый инструмент'
        verbose_name_plural = 'Торговые инструменты'


class Currency(InstrumentType):
    """ Валюты, в которых могут проводиться операции """
    class Meta:
        verbose_name = 'Валюта'
        verbose_name_plural = 'Валюты'

    # iso_code не primary_key потому что у валют он может меняться
    iso_code = models.CharField(verbose_name='Код', max_length=3, unique=True)
    abbreviation = models.CharField(verbose_name='Знак', max_length=16)
    name = models.CharField(verbose_name='Название', max_length=120)

    def save(self, *args, **kwargs):
        iso_code = self.iso_code
        if not iso_code.isupper():
            self.iso_code = iso_code.upper()
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Stock(InstrumentType):
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


class DealQuerySet(models.QuerySet):
    _sell_filter = Q(instance_of=Sale)
    _buy_filter = Q(instance_of=Purchase)

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
            .instance_of(Purchase)
            .aggregate(q=Sum('quantity'))
        )
        total_bought_quantity = tmp_buy['q']
        total_bought_commission = collections.Counter()
        total_paid = collections.Counter()
        tmp_sell = (
            operations
            .instance_of(Sale)
            .aggregate(avg=Avg('price'), q=Sum('quantity'), commission=Sum('commission'))
        )
        average_sell_price = tmp_sell['avg']
        total_sold_quantity = tmp_sell['q']
        total_sold_commission = tmp_sell['commission']
        dividend_income = (
            operations
            .instance_of(Dividend)
            .aggregate(income=Coalesce(Sum('payment') + Sum('tax'), 0))['income']
        )
        for operation in operations.instance_of(Purchase):
            for share in operation.shares.all():
                total_shares[share.co_owner] += Decimal(share.value/operation.total_shares*operation.quantity)
                total_paid[share.co_owner] += \
                    Decimal(share.value/operation.total_shares*operation.quantity) * operation.price
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
