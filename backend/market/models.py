from django.db import models
from django.db.models import Sum, F, Q, Case, When
from django.db.models.functions import Coalesce

from core.utils import ProxyInheritanceManager, ProxyQ
from market.models_constraints import InstrumentTypeConstraints, InstrumentTypeTypes
from market.services.income_calculation import SmartInvestorSet
from operations.models import SaleOperation, PurchaseOperation, DividendOperation


class InstrumentType(models.Model):
    Types = InstrumentTypeTypes

    class Meta:
        verbose_name = 'Торговый инструмент'
        verbose_name_plural = 'Торговые инструменты'
        constraints = InstrumentTypeConstraints.ALL_CONSTRAINTS

    objects = ProxyInheritanceManager()
    proxy_constraints = InstrumentTypeConstraints

    # Общие поля
    figi = models.CharField(verbose_name='FIGI', max_length=32, primary_key=True)
    name = models.CharField(verbose_name='Название', max_length=200)
    ticker = models.CharField(verbose_name='Ticker', max_length=16, unique=True)
    type = models.CharField(verbose_name='Тип', max_length=30, choices=Types.choices)

    # Для валют
    iso_code = models.CharField(verbose_name='Код', max_length=3, default='')
    abbreviation = models.CharField(verbose_name='Знак', max_length=16, default='')

    # Для ценных бумаг
    isin = models.CharField(verbose_name='ISIN', max_length=32, default='')
    min_price_increment = models.DecimalField(verbose_name='Шаг цены', max_digits=10, decimal_places=4, default=0)
    lot = models.PositiveIntegerField(verbose_name='шт/лот', default=0)
    currency = models.ForeignKey('operations.Currency', verbose_name='Валюта', on_delete=models.CASCADE, null=True)

    def __str__(self):
        return str(self.name)


class CurrencyInstrument(InstrumentType):
    """ Валюты, которые можно купить на бирже """
    class Meta:
        verbose_name = 'Валюта'
        verbose_name_plural = 'Валюты'
        proxy = True


class StockInstrument(InstrumentType):
    """ Ценная акция на рынке """
    class Meta:
        verbose_name = 'Акция'
        verbose_name_plural = 'Акции'
        proxy = True


class DealQuerySet(models.QuerySet):
    _sale_filter = ProxyQ(proxy_instance_of=SaleOperation)
    _purchase_filter = ProxyQ(proxy_instance_of=PurchaseOperation)

    def _with_quantity_annotation_by_operation_type(self):
        return self.annotate(
            sold_quantity=Coalesce(Sum('operations__quantity', filter=self._sale_filter), 0),
            bought_quantity=Coalesce(Sum('operations__quantity', filter=self._purchase_filter), 0)
        )

    def opened(self):
        return (
            self._with_quantity_annotation_by_operation_type()
            .filter(~Q(sold_quantity=F('bought_quantity')) | Q(bought_quantity=0) | Q(sold_quantity=0))
        )

    def closed(self):
        return (
            self._with_quantity_annotation_by_operation_type()
            .filter(Q(sold_quantity=F('bought_quantity')) & ~Q(bought_quantity=0) & ~Q(sold_quantity=0))
        )

    def with_closed_annotations(self):
        return self._with_quantity_annotation_by_operation_type().annotate(
            is_closed=Case(
                When(Q(sold_quantity=F('bought_quantity')) & ~Q(buys=0) & ~Q(sells=0), then=True),
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

    instrument = models.ForeignKey(InstrumentType, verbose_name='Ценная бумага', on_delete=models.PROTECT)
    investment_account = models.ForeignKey(
        'users.InvestmentAccount', verbose_name='Инвестиционный счет', on_delete=models.CASCADE,
        related_name='deals'
    )

    def recalculation_income(self):
        """ Перерасчет дохода со сделки для каждого участника """
        # XXX
        # Получаем все операции покупки/продажи и операции получения дивидендов
        operations = (
            self.operations
            .filter(proxy_instance_of=(PurchaseOperation, SaleOperation))
            .prefetch_related('shares')
        )
        dividends = self.operations.filter(proxy_instance_of=DividendOperation).all()
        # Для расчета дохода каждого инвестора от сделки используется этот класс
        smart_investors_set = SmartInvestorSet()
        smart_investors_set.add_operations(operations)
        smart_investors_set.add_operations(dividends)

        DealIncome.objects.exclude(co_owner__in=smart_investors_set.investors).delete()
        DealIncome.objects.bulk_create(
            [DealIncome(deal=self, co_owner=i) for i in smart_investors_set.investors],
            ignore_conflicts=True
        )
        deal_income_set = DealIncome.objects.filter(deal=self).select_related('co_owner')
        deal_income_bulk_update = []
        for deal_income in deal_income_set:
            deal_income.value = smart_investors_set[deal_income.co_owner].capital
            deal_income_bulk_update.append(deal_income)
        DealIncome.objects.bulk_update(deal_income_bulk_update, fields=['value'])


class DealIncome(models.Model):
    """ Доход со сделки для каждого участника """
    class Meta:
        verbose_name = 'Доход за сделку'
        verbose_name_plural = 'Доходы за сделку'
        constraints = [
            models.UniqueConstraint(fields=('deal', 'co_owner'), name='unique_deal_co-owner')
        ]

    deal = models.ForeignKey(Deal, verbose_name='Сделка', on_delete=models.CASCADE)
    co_owner = models.ForeignKey(
        'users.CoOwner', verbose_name='Совладелец', on_delete=models.CASCADE,
        related_name='deal_income_set'
    )
    # Сколько совладелец заработал с конкретной сделки
    value = models.DecimalField(verbose_name='Доход', max_digits=20, decimal_places=4, default=0)

    def __str__(self):
        return f'{self.deal}: {self.co_owner} ({self.value})'
