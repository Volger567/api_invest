import operator
from functools import reduce

from django.db import models
from django.db.models import Q


class OperationTypes(models.TextChoices):
    PAY_IN = 'PayIn', 'Пополнение счета'
    PAY_OUT = 'PayOut', 'Вывод средств'
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


class OperationConstraints:
    class PayInOperation:
        possible_types = (OperationTypes.PAY_IN, )
        constraints = (
            Q(type__in=possible_types, is_margin_call=False, payment__gt=0,
              instrument__isnull=True, quantity=0, commission=0, deal__isnull=True,
              dividend_tax=0, dividend_tax_date__isnull=True) & ~Q(_id='-1')
        )

    class PayOutOperation:
        possible_types = (OperationTypes.PAY_OUT, )
        constraints = (
            Q(type__in=possible_types, is_margin_call=False, payment__lt=0,
              instrument__isnull=True, quantity=0, commission=0, deal__isnull=True,
              dividend_tax=0, dividend_tax_date__isnull=True) & ~Q(_id='-1')
        )

    class PurchaseOperation:
        possible_types = (OperationTypes.BUY, OperationTypes.BUY_CARD)
        constraints = (
            Q(type__in=possible_types, payment__lt=0,
              instrument__isnull=False, quantity__ge=1,
              dividend_tax=0, dividend_tax_date__isnull=True) & ~Q(_id='-1')
        )

    class SaleOperation:
        possible_types = (OperationTypes.SELL, )
        constraints = (
            Q(type__in=possible_types, payment__gt=0,
              instrument__isnull=False, quantity__ge=1,
              dividend_tax=0, dividend_tax_date__isnull=True) & ~Q(_id='-1')
        )

    class DividendOperation:
        possible_types = (OperationTypes.DIVIDEND, )
        constraints = (
            Q(type__in=possible_types, is_margin_call=False, payment__gt=0,
              instrument__isnull=False, quantity=0, commission=0,
              dividend_tax__le=0) & ~Q(_id='-1')
        )

    class ServiceCommissionOperation:
        possible_types = (OperationTypes.SERVICE_COMMISSION, )
        constraints = (
            Q(type__in=possible_types, is_margin_call=False, payment__lt=0,
              instrument__isnull=True, quantity=0, commission=0, deal__isnull=True,
              dividend_tax=0, dividend_tax_date__isnull=True) & ~Q(_id='-1')
        )

    class MarginCommissionOperation:
        possible_types = (OperationTypes.MARGIN_COMMISSION, )
        constraints = (
            Q(type__in=possible_types, is_margin_call=False, payment__lt=0,
              instrument__isnull=True, quantity=0, commission=0, deal__isnull=True,
              dividend_tax=0, dividend_tax_date__isnull=True) & ~Q(_id='-1')
        )

    class TaxOperation:
        possible_types = (OperationTypes.TAX, )
        constraints = (
            Q(type__in=possible_types, is_margin_call=False, payment__lt=0,
              instrument__isnull=True, quantity=0, commission=0,
              deal__isnull=True, dividend_tax=0, dividend_tax_date__isnull=True) & ~Q(_id='-1')
        )

    class TaxBackOperation:
        possible_types = (OperationTypes.TAX_BACK, )
        constraints = (
            Q(type__in=possible_types, is_margin_call=False, payment__gt=0,
              instrument__isnull=True, quantity=0, commission=0,
              deal__isnull=True, dividend_tax=0, dividend_tax_date__isnull=True) & ~Q(_id='-1')
        )
    ALL_OPERATIONS = (
        PayInOperation, PayOutOperation, PurchaseOperation, SaleOperation,
        DividendOperation, ServiceCommissionOperation, MarginCommissionOperation,
        TaxOperation, TaxBackOperation
    )
    ALL_CONSTRAINTS = reduce(operator.or_, map(operator.attrgetter('constraints'), ALL_OPERATIONS))
    ALL_CONSTRAINTS |= Q(type=OperationTypes.UNKNOWN)
