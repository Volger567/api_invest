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
    ALL_PROXY_CONSTRAINTS = reduce(
        operator.or_, map(operator.attrgetter('constraints'), ALL_INSTRUMENT_TYPES)
    )
    ALL_PROXY_CONSTRAINTS |= Q(type=InstrumentTypeTypes.UNKNOWN)
    ALL_CONSTRAINTS = [
        models.UniqueConstraint(fields=('investment_account', 'type', 'date'), name='unique_%(class)s'),
        models.UniqueConstraint(fields=('_id',), condition=~Q(_id=''), name='unique_id_$(class)s'),
        models.CheckConstraint(
            name='%(class)s_restrict_property_set_by_type',
            check=(ALL_PROXY_CONSTRAINTS, )
        )
    ]
