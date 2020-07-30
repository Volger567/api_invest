""" Модуль для работы с операциями
    Получение их через Tinkoff API
    Запись в ИС
"""
import datetime as dt
import logging
from typing import List, NoReturn

from market.models import Currency, Operation
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


def generate_bulk_create_operations(operations: TOperationsPayloadOperations, investment_account_id) -> List[Operation]:
    """ Генерирует список объектов Operation
        для дальнейшей передачи в bulk_create
    :param operations: список операций
    :param investment_account_id: id ИС
    :return: список с объектами Operation
    """
    currencies = Currency.objects.all()
    # TODO
