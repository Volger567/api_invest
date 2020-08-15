import operator
from functools import reduce

from django.db import models
from django.db.models import Q


class InstrumentTypeTypes(models.TextChoices):
    STOCK = 'Stock', 'Акция'
    CURRENCY = 'Currency', 'Валюта'
    UNKNOWN = 'Unknown', 'Неизвестен'
    # TODO: Еще Bond, Etf


class InstrumentTypeConstraints:
    class InstrumentType:
        possible_types = [i[0] for i in InstrumentTypeTypes.choices]
        is_abstract = True

    class CurrencyInstrument:
        possible_types = (InstrumentTypeTypes.CURRENCY, )
        constraints = (
            Q(type__in=possible_types, lot__gte=1, isin='')
        )

    class StockInstrument:
        possible_types = (InstrumentTypeTypes.STOCK, )
        constraints = (
            Q(type__in=possible_types, lot__gte=1) & ~Q(isin='')
        )

    ALL_INSTRUMENT_TYPES = (InstrumentType, CurrencyInstrument, StockInstrument)
    ALL_PROXY_CONSTRAINTS = reduce(
        operator.or_, map(lambda x: getattr(x, 'constraints', Q()), ALL_INSTRUMENT_TYPES)
    )
    ALL_PROXY_CONSTRAINTS |= Q(type=InstrumentTypeTypes.UNKNOWN)
    ALL_CONSTRAINTS = [
        models.CheckConstraint(
            name='%(class)s_restrict_property_set_by_type',
            check=ALL_PROXY_CONSTRAINTS
        )
    ]
