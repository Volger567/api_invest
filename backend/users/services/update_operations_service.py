""" Модуль для работы с операциями
    Получение их через Tinkoff API
    Запись в ИС
"""
import collections
import datetime as dt
import logging
from typing import List, Dict

import dateutil.parser

from market.models import Currency
from operations.models import Operation, PayInOperation, PayOutOperation, PurchaseOperation, SaleOperation
from tinkoff_api import TinkoffProfile
from tinkoff_api.annotations import TOperationsPayloadOperations

logger = logging.getLogger(__name__)


def get_operations_from_tinkoff_api(token: str, from_datetime: dt.datetime,
                                    to_datetime: dt.datetime) -> TOperationsPayloadOperations:
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


def generate_bulk_create_operations(operations: TOperationsPayloadOperations,
                                    timezone,
                                    investment_account_id) -> Dict[Operation, List[Operation]]:
    """ Генерирует список объектов Operation
        для дальнейшей передачи в bulk_create
    :param operations: список операций
    :param timezone: Временная зона
    :param investment_account_id: id ИС
    :return: список с объектами Operation
    """
    currencies = Currency.objects.all()
    final_operations = collections.defaultdict(list)
    for operation in operations:
        operation_type = operation['operationType']
        base_operation_kwargs = {
            'investment_account_id': investment_account_id,
            'date': timezone.localize(dateutil.parser.isoparse(operation['date']).replace(tzinfo=None)),
            'is_margin_call': operation['isMarginCall'],
            'payment': operation['payment'],
            'currency': currencies.get(iso_code=operation['currency'])
        }

        if operation_type == Operation.Types.PAY_IN:
            final_operations[PayInOperation].append(PayInOperation(**base_operation_kwargs))
        elif operation_type == Operation.Types.PAY_OUT:
            final_operations[PayOutOperation].append(PayOutOperation(**base_operation_kwargs))
        elif operation_type in (Operation.Types.BUY, Operation.Types.BUY_CARD, Operation.Types.SELL):
            # Некоторые операции могут быть без комиссии (например в первый месяц торгов)
            commission = operation.get('commission')
            commission = commission['value'] if isinstance(commission, dict) else 0
            if operation_type == Operation.Types.SELL:
                model = SaleOperation
            else:
                model = PurchaseOperation
            obj = model(
                **base_operation_kwargs,
                quantity=operation['quantity'],
                commission=commission,
                _id=operation['id']
            )
            final_operations[model].append(obj)
        # TODO:

