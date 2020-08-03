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


class OperationsHandler:
    """ Получение операций от Tinkoff API,
        обработка их и добавление в базу данных
    """

    # Получение модели операции по типу операции (в строковом эквиваленте)
    model_by_operation_type = {
        Operation.Types.SELL: SaleOperation,
        Operation.Types.BUY: PurchaseOperation,
        Operation.Types.BUY_CARD: PurchaseOperation,
        Operation.Types.DIVIDEND: DividendOperation,
        Operation.Types.PAY_IN: PayInOperation,
        Operation.Types.PAY_OUT: PayOutOperation,
        Operation.Types.SERVICE_COMMISSION: ServiceCommissionOperation,
        Operation.Types.MARGIN_COMMISSION: MarginCommissionOperation
    }

    # Получение типа инструмента по строчному эквиваленту
    model_by_instrument_type = {
        InstrumentType.Types.STOCK: Stock,
        InstrumentType.Types.CURRENCY: Currency
    }

    def __init__(self, token: str, from_datetime: dt.datetime, to_datetime: dt.datetime, investment_account_id: int):
        """ Инициализатор
        :param token: токен от Tinkoff API
        :param from_datetime: с какой даты получать операции
        :param to_datetime: до какой даты получать операции
        :param investment_account_id: id ИС
        """
        self._token = token
        self.tinkoff_profile = TinkoffProfile(token)
        self.tinkoff_profile.auth()
        # Проверяет корректность переданных дат, в том числе наличие у них tzinfo
        self.tinkoff_profile.check_date_range(from_datetime, to_datetime)
        self.from_datetime = from_datetime
        self.to_datetime = to_datetime
        self.timezone = from_datetime.tzinfo
        self.investment_account_id = investment_account_id
        self.operations = []
        # Флаг, становится True когда проходит обработка первичных операций
        self._is_processed_primary_operations = False
        # Флаг, становится True когда проходит обработка вторичных операций
        self._is_processed_secondary_operations = False
        # Операции, после первичной обработки
        self.processed_primary_operations = {}
        # Все валюты и торговые инструменты
        self.currencies = Currency.objects.all()
        self.instruments = InstrumentType.objects.all()

    @property
    def is_processed_primary_operations(self):
        return self._is_processed_primary_operations

    @property
    def is_processed_secondary_operations(self):
        return self._is_processed_secondary_operations

    def get_operations_from_tinkoff_api(self) -> None:
        """ Получение списка операций в заданном временном диапазоне """
        # Получаем список операций в диапазоне
        self.operations = self.tinkoff_profile.operations(
            self.from_datetime, self.to_datetime
        )['payload']['operations']
        self._is_processed_primary_operations = False
        self._is_processed_secondary_operations = False

    def process_primary_operations(self) -> None:
        """ Генерирует список объектов Operation для первичных операций.
            Создает первичные операции через bulk_create.
            Первичные операции отличаются от вторичных тем, что вторичные операции
            ссылаются на первичные, т.е пока первичных операций нет,
            вторичные не могут быть созданы.
        """
        # Если была пройдена обработка первичных или вторичных операций, выходим
        if self.is_processed_primary_operations or self.is_processed_secondary_operations:
            return

        # Словарь, который будет возвращен
        # Для каждой модели, есть список, который потом будет передан в bulk_create
        final_operations = collections.defaultdict(list)

        for operation in self.operations.copy():
            # Будем записывать только завершенные операции
            if operation['status'] != Operation.Statuses.DONE:
                self.operations.remove(operation)
                continue

            operation_type = operation['operationType']
            # У каждой операции есть эти свойства, поэтому вынесем их
            base_operation_kwargs = {
                'investment_account_id': self.investment_account_id,
                'date': self.timezone.localize(dateutil.parser.isoparse(operation['date']).replace(tzinfo=None)),
                'is_margin_call': operation['isMarginCall'],
                'payment': operation['payment'],
                'currency': self.currencies.get(iso_code=operation['currency'])
            }
            if operation.get('instrumentType') is not None:
                base_operation_kwargs['instrument'] = (
                    self.instruments
                    .instance_of(self.model_by_instrument_type[operation['instrumentType']])
                    .get(figi=operation['figi'])
                )
            model = self.model_by_operation_type[operation_type]

            # Операции, которым достаточно значений из base_operation_kwargs
            if operation_type in (Operation.Types.PAY_IN, Operation.Types.PAY_OUT, Operation.Types.DIVIDEND,
                                  Operation.Types.SERVICE_COMMISSION, Operation.Types.MARGIN_COMMISSION,
                                  Operation.Types.TAX, Operation.Types.TAX_BACK):
                final_operations[model].append(model(**base_operation_kwargs))
                self.operations.remove(operation)
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
                self.operations.remove(operation)

        for model, bulk_create in final_operations:
            model.objects.bulk_create(bulk_create, ignore_conflicts=True)

        # Обработанные операции
        self.processed_primary_operations = final_operations
        # Первичные операции обработаны
        self._is_processed_primary_operations = True

    def process_secondary_operations(self) -> None:
        """ Обработка вторичных операций и запись вторичных операций.
            Вторичные операции - это те операции, для создания которых
            необходимо существование первичных операций
        """

        # Если обработка вторичных операций уже была - выходим
        if self.is_processed_secondary_operations:
            return
        # Если первичные операции еще не обработаны - ошибка
        if not self.is_processed_primary_operations:
            raise ValueError('Сначала вызовите обработку первичных операций')

        # TODO: добавление транзакций в операции
        for operation in self.operations.copy():
            operation_type = operation['operationType']
            operation_date = self.timezone.localize(dateutil.parser.isoparse(operation['date']).replace(tzinfo=None))

            # Для налога на дивиденды находим последнюю ценную бумагу без налога по figi
            if operation_type == Operation.Types.TAX_DIVIDEND:
                (
                    DividendOperation.objects
                    .filter(instrument__figi=operation['figi'], date__lte=operation_date, tax_date__isnull=True)
                    .order_by('-date')[0].update(tax=operation['payment'], tax_date=operation_date)
                )
                self.operations.remove(operation)
        self._is_processed_secondary_operations = True
