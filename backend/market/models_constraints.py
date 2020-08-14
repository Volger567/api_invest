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
    class CurrencyInstrument:
        possible_types = (InstrumentTypeTypes.CURRENCY, )
        constraints = (
            Q(type=possible_types, isin='', min_price_increment=0, lot=0) &
            ~Q(iso_code='') & ~Q(abbreviation='')
        )

    class StockInstrument:
        possible_types = (InstrumentTypeTypes.STOCK, )
        constraints = (
            Q(type=InstrumentTypeTypes.STOCK, iso_code='', abbreviation='',
              lot__ge=1, currency__isnull=False) & ~Q(isin='')
        )

    ALL_INSTRUMENT_TYPES = (CurrencyInstrument, StockInstrument)
    ALL_CONSTRAINTS = reduce(
        operator.or_, map(operator.attrgetter('constraints'), ALL_INSTRUMENT_TYPES)
    )
