""" Модуль для работы с операциями
    Получение их через Tinkoff API
    Запись в ИС
"""
import collections
import datetime as dt
import logging

import dateutil.parser

from market.models import Currency, InstrumentType, Stock
from operations.models import Operation, PayInOperation, PayOutOperation, PurchaseOperation, SaleOperation, \
    DividendOperation, ServiceCommissionOperation, MarginCommissionOperation
from tinkoff_api import TinkoffProfile

logger = logging.getLogger(__name__)


def get_operations_from_tinkoff_api(token: str, from_datetime: dt.datetime,
                                    to_datetime: dt.datetime):
    """ Получение списка операций в заданном временном диапазоне
    :param token: Токен для доступа к Tinkoff API
    :param from_datetime: начало диапазона
    :param to_datetime: конец диапазона
    :return: список операций
    """
    # Получаем список операций в диапазоне
    # от даты последнего получения операций минус 12 часов до текущего момента
    with TinkoffProfile(token) as tp:
        operations = tp.operations(from_datetime, to_datetime)['payload']['operations']
    return operations


_model_by_operation_type = {
    Operation.Types.SELL: SaleOperation,
    Operation.Types.BUY: PurchaseOperation,
    Operation.Types.BUY_CARD: PurchaseOperation,
    Operation.Types.DIVIDEND: DividendOperation,
    Operation.Types.PAY_IN: PayInOperation,
    Operation.Types.PAY_OUT: PayOutOperation,
    Operation.Types.SERVICE_COMMISSION: ServiceCommissionOperation,
    Operation.Types.MARGIN_COMMISSION: MarginCommissionOperation
}

_model_by_instrument_type = {
    InstrumentType.Types.STOCK: Stock,
    InstrumentType.Types.CURRENCY: Currency
}


def generate_bulk_create_primary_operations(operations, timezone, investment_account_id):
    """ Генерирует список объектов Operation для первичных операций.
        для дальнейшей передачи в bulk_create.
        Первичные операции отличаются от вторичных тем, что вторичные операции
        ссылаются на первичные, т.е пока первичных операций нет,
        вторичные не могут быть созданы
    :param operations: список операций
    :param timezone: Временная зона
    :param investment_account_id: id ИС
    :return: словарь, в котором ключом является модель операций,
        а значением - список, который буден передан в bulk_create этой модели
    """

    # Все валюты и торговые инструменты
    currencies = Currency.objects.all()
    instruments = InstrumentType.objects.all()
    # Словарь, который будет возвращен
    # Для каждой модели, есть список, который потом будет передан в bulk_create
    final_operations = collections.defaultdict(list)

    for operation in operations:
        # Будем записывать только завершенные операции
        if operation['status'] != Operation.Statuses.DONE:
            continue

        operation_type = operation['operationType']
        # У каждой операции есть эти свойства, поэтому вынесем их
        base_operation_kwargs = {
            'investment_account_id': investment_account_id,
            'date': timezone.localize(dateutil.parser.isoparse(operation['date']).replace(tzinfo=None)),
            'is_margin_call': operation['isMarginCall'],
            'payment': operation['payment'],
            'currency': currencies.get(iso_code=operation['currency'])
        }
        if operation.get('instrumentType') is not None:
            base_operation_kwargs['instrument'] = (
                instruments
                .instance_of(_model_by_instrument_type[operation['instrumentType']])
                .get(figi=operation['figi'])
            )
        model = _model_by_operation_type[operation_type]

        # Операции, которым достаточно значений из base_operation_kwargs
        if operation_type in (Operation.Types.PAY_IN, Operation.Types.PAY_OUT, Operation.Types.DIVIDEND,
                              Operation.Types.SERVICE_COMMISSION, Operation.Types.MARGIN_COMMISSION,
                              Operation.Types.TAX, Operation.Types.TAX_BACK):
            final_operations[model].append(model(**base_operation_kwargs))
        # Операции покупки, покупки с карты и продажи, по сути, ничем не отличаются,
        # только значением в payment
        elif operation_type in (Operation.Types.BUY, Operation.Types.BUY_CARD, Operation.Types.SELL):
            # Некоторые операции могут быть без комиссии (например в первый месяц торгов)
            commission = operation.get('commission')
            commission = commission['value'] if isinstance(commission, dict) else 0
            if base_operation_kwargs['payment'] == 0:
                base_operation_kwargs['payment'] = sum(i['quantity'] * i['price'] for i in operation['trades'])
            obj = model(
                **base_operation_kwargs,
                quantity=operation['quantity'],
                commission=commission,
                _id=operation['id']
            )
            final_operations[model].append(obj)
