""" Модуль для обновления операций, сделок, валютных активов
    Получение через Tinkoff API
    Запись в ИС
"""
import collections
import datetime as dt
import logging
from typing import Optional, List, Dict

import dateutil.parser
from django.apps import apps
from django.db.models import Min

from core.utils import is_proxy_instance
from market.models import CurrencyInstrument, InstrumentType, StockInstrument, Deal
from operations.models import Operation, SaleOperation, DividendOperation, \
    Transaction, PurchaseOperation, Share
from tinkoff_api import TinkoffProfile

logger = logging.getLogger(__name__)


class Updater:
    """ Получение валютных активов.
        Получение операций от Tinkoff API,
        обработка их и добавление в базу данных,
        Создание и дополнение сделок на основе полученных операций
    """

    # Получение типа инструмента по строчному эквиваленту
    model_by_instrument_type = {
        InstrumentType.Types.STOCK: StockInstrument,
        InstrumentType.Types.CURRENCY: CurrencyInstrument
    }

    def __init__(self, from_datetime: dt.datetime, to_datetime: dt.datetime, investment_account_id: int,
                 token: Optional[str] = None, tinkoff_profile: Optional[TinkoffProfile] = None):
        """ Инициализатор
        :param from_datetime: с какой даты получать операции
        :param to_datetime: до какой даты получать операции
        :param investment_account_id: id ИС
        :param token: токен от Tinkoff API, если None, будет использоваться tinkoff_profile
        :param tinkoff_profile: профиль Tinkoff API, если None, будет использоваться token
        """
        logger.info('Инициализация Updater')
        if token is None and tinkoff_profile is None:
            raise ValueError('Надо передать token или tinkoff_profile')
        if token:
            self.tinkoff_profile = TinkoffProfile(token)
        else:
            self.tinkoff_profile = tinkoff_profile
        self.tinkoff_profile.auth()
        # Проверяет корректность переданных дат, в том числе наличие у них tzinfo
        self.tinkoff_profile.check_date_range(from_datetime, to_datetime)
        self.from_datetime = from_datetime
        self.to_datetime = to_datetime
        self.timezone = from_datetime.tzinfo
        self.investment_account_id = investment_account_id
        self.operations = []
        self.transactions = collections.defaultdict(list)
        # Флаг, становится True когда проходит обработка первичных операций
        self._is_processed_primary_operations = False
        # Флаг, становится True когда проходит обработка вторичных операций
        self._is_processed_secondary_operations = False
        # Операции, после первичной обработки
        self.processed_primary_operations = {}
        # Все валюты и торговые инструменты
        self.instruments = InstrumentType.objects.all()

    @property
    def is_processed_primary_operations(self):
        return self._is_processed_primary_operations

    @property
    def is_processed_secondary_operations(self):
        return self._is_processed_secondary_operations

    def get_operations_from_tinkoff_api(self) -> None:
        """ Получение списка операций в заданном временном диапазоне """
        logger.info(f'Получение операций от {self.from_datetime.isoformat()} до {self.to_datetime.isoformat()}')
        # Получаем список операций в диапазоне
        self.operations = self.tinkoff_profile.operations(
            self.from_datetime, self.to_datetime
        )['payload']['operations'][::-1]
        logger.info('Операции получены')
        self._is_processed_primary_operations = False
        self._is_processed_secondary_operations = False

    def process_primary_operations(self) -> None:
        """ Генерирует список объектов Operation для первичных операций.
            Создает первичные операции через bulk_create.
            Первичные операции отличаются от вторичных тем, что вторичные операции
            ссылаются на первичные, т.е пока первичных операций нет,
            вторичные не могут быть созданы.
        """
        logger.info('Обработка первичных операций')
        # Типы пе
        primary_operation_type = (
            Operation.Types.PAY_IN, Operation.Types.PAY_OUT,
            Operation.Types.SERVICE_COMMISSION, Operation.Types.MARGIN_COMMISSION,
            Operation.Types.BUY, Operation.Types.BUY_CARD, Operation.Types.SELL
        )
        # Если была пройдена обработка первичных или вторичных операций, выходим
        if self.is_processed_primary_operations or self.is_processed_secondary_operations:
            logger.warning('Первичные операции уже обработаны')
            return

        # Словарь, который будет возвращен.
        # Ключ - модель, значение - список, который потом будет передан в bulk_create
        final_operations: Dict[Operation, List[Operation]] = collections.defaultdict(list)

        for operation in self.operations.copy():
            logger.info(f'Операция: {operation}')
            # Будем записывать только завершенные операции
            if operation['status'] != Operation.Statuses.DONE:
                logger.info('Статус != DONE, пропускаем')
                self.operations.remove(operation)
                continue

            operation_type = operation['operationType']
            # У каждой операции есть эти свойства, поэтому вынесем их
            base_operation_kwargs = {
                'investment_account_id': self.investment_account_id,
                'date': self.timezone.localize(dateutil.parser.isoparse(operation['date']).replace(tzinfo=None)),
                'is_margin_call': operation['isMarginCall'],
                'payment': operation['payment'],
                'currency_id': operation['currency'],
                '_id': operation['id']
            }
            if operation_type in primary_operation_type:
                base_operation_kwargs['type'] = operation_type
            if operation.get('instrumentType') is not None:
                base_operation_kwargs['instrument'] = (
                    self.model_by_instrument_type[operation['instrumentType']].objects.get(figi=operation['figi'])
                )
                logger.info(f'У операции указан инструмент ({base_operation_kwargs["instrument"]})')
            model = Operation.get_operation_model_by_type(operation_type)
            logger.info(f'Модель операции: {model}')

            # Операции, которым достаточно значений из base_operation_kwargs
            if operation_type in (Operation.Types.PAY_IN, Operation.Types.PAY_OUT, Operation.Types.DIVIDEND,
                                  Operation.Types.SERVICE_COMMISSION, Operation.Types.MARGIN_COMMISSION,
                                  Operation.Types.TAX, Operation.Types.TAX_BACK):
                logger.info('Добавляется экземпляр на основе только base_operation_kwargs')
                final_operations[model].append(model(**base_operation_kwargs))
                self.operations.remove(operation)
            # Операции покупки, покупки с карты и продажи, по сути, ничем не отличаются,
            # только значением в payment
            elif operation_type in (Operation.Types.BUY, Operation.Types.BUY_CARD, Operation.Types.SELL):
                # Некоторые операции могут быть без комиссии (например в первый месяц торгов)
                commission = operation.get('commission')
                commission = commission['value'] if isinstance(commission, dict) else 0
                logger.info(f'Комиссия: {commission}')
                # Добавляем транзакции по операции
                for transaction in operation['trades']:
                    self.transactions[operation['id']].append({
                        'id': transaction['tradeId'],
                        'date': self.timezone.localize(
                            dateutil.parser.isoparse(transaction['date']).replace(tzinfo=None)
                        ),
                        'quantity': transaction['quantity'],
                        'price': transaction['price']
                    })
                # Иногда Tinkoff не считает payment, вычисляем из trades
                if base_operation_kwargs['payment'] == 0:
                    base_operation_kwargs['payment'] = sum(i['quantity'] * -i['price'] for i in operation['trades'])
                    logger.warning(f'payment не указан, вычислили из trades: {base_operation_kwargs["payment"]}')
                obj = model(
                    **base_operation_kwargs,
                    quantity=operation['quantity'],
                    commission=commission
                )
                final_operations[model].append(obj)
                self.operations.remove(operation)
            elif operation_type == Operation.Types.BROKER_COMMISSION:
                logger.info('Комиссия брокера')
                self.operations.remove(operation)
            else:
                logger.info('Операция не является первичной')

        for model, bulk_create in final_operations.items():
            logger.info(f'Создаем операции модели {model.__name__} через bulk_create')
            model.objects.bulk_create(bulk_create, ignore_conflicts=True)
            logger.info(f'Операции модели {model.__name__} созданы через bulk_create')
        # Обработанные операции
        self.processed_primary_operations = final_operations
        # Первичные операции обработаны
        self._is_processed_primary_operations = True
        logger.info('Обработка первичных операций завершена')

    def process_secondary_operations(self) -> None:
        """ Обработка вторичных операций и запись вторичных операций.
            Вторичные операции - это те операции, для создания которых
            необходимо существование первичных операций
        """
        logger.info('Обработка вторичных операций')
        # Если обработка вторичных операций уже была - выходим
        if self.is_processed_secondary_operations:
            logger.warning('Вторичные операции уже обработаны')
            return
        # Если первичные операции еще не обработаны - ошибка
        if not self.is_processed_primary_operations:
            raise ValueError('Сначала вызовите обработку первичных операций')

        logger.info('Обновляем транзакции')
        # Словарь операций, которым принадлежат транзакции
        # Ключ - id в БД, значение id в Tinkoff API
        operation_by_tinkoff_api_operation_id = dict(
            Operation.objects.filter(_id__in=self.transactions).values_list('_id', 'id')
        )
        bulk_create_transactions = []
        for operation_id, transactions in self.transactions.items():
            for transaction in transactions:
                bulk_create_transactions.append(Transaction(
                    **transaction,
                    operation_id=operation_by_tinkoff_api_operation_id[operation_id]
                ))
        Transaction.objects.bulk_create(bulk_create_transactions, ignore_conflicts=True)
        logger.info('Транзакции обновлены')

        for operation in self.operations.copy():
            logger.info(f'Операция: {operation}')
            operation_type = operation['operationType']
            operation_date = self.timezone.localize(dateutil.parser.isoparse(operation['date']).replace(tzinfo=None))

            # Для налога на дивиденды находим последнюю ценную бумагу без налога по figi
            if operation_type == Operation.Types.TAX_DIVIDEND:
                logger.info('Операция "Налог на дивиденды"')
                (
                    DividendOperation.objects
                    .filter(instrument__figi=operation['figi'], date__lte=operation_date, tax_date__isnull=True)
                    .order_by('-date')[0].update(tax=operation['payment'], tax_date=operation_date)
                )
                self.operations.remove(operation)
        if self.operations:
            logger.warning(f'Оставшиеся операции после вторичной обработки: {self.operations}')
        else:
            logger.info('После вторичной обработки операций не осталось')
        self._is_processed_secondary_operations = True
        logger.info(f'Обработка вторичных операций завершена')

    def update_operations(self) -> None:
        """ Обновление операций """
        self.get_operations_from_tinkoff_api()
        self.process_primary_operations()
        self.process_secondary_operations()

    def update_deals(self) -> None:
        """ Обновление сделок """
        investment_account_model = apps.get_model('users', 'InvestmentAccount')
        logger.info('Обновление сделок')
        operations = (
            Operation.objects
            .filter(proxy_instance_of=(PurchaseOperation, SaleOperation, DividendOperation),
                    deal__isnull=True, investment_account_id=self.investment_account_id)
            .order_by('date')
        )

        # Сделки, у которых надо пересчитать доход
        recalculation_income_deals = set()
        # Список всех совладельцев счета
        co_owners = (
            investment_account_model(id=self.investment_account_id).co_owners.all()
            .values_list('pk', 'default_share', named=True)
        )
        logger.info(f'Список совладельцев: {co_owners}')
        bulk_create_share = []
        for operation in operations:
            logger.info(f'Операция: {operation}')
            if is_proxy_instance(operation, (PurchaseOperation, SaleOperation)):
                for co_owner in co_owners:
                    logger.info(f'Добавление доли операции для {co_owner}')
                    bulk_create_share.append(
                        Share(operation=operation, co_owner_id=co_owner.pk, value=co_owner.default_share)
                    )
                deal, created = (
                    Deal.objects.opened()
                    .get_or_create(instrument=operation.instrument,
                                   investment_account_id=self.investment_account_id)
                )
                if created:
                    logger.info('Сделка создана')
                else:
                    logger.info('Сделка существовала')
                deal.operations.add(operation)
                recalculation_income_deals.add(deal)
            elif is_proxy_instance(operation, DividendOperation):
                logger.info('Дивиденды')
                (
                    Deal.objects
                    .filter(instrument=operation.instrument, investment_account_id=self.investment_account_id)
                    .annotate(opened_date=Min('operations__date'))
                    .filter(opened_date__lte=operation.date).last('opened_date').operations.add(operation)
                )
        Share.objects.bulk_create(bulk_create_share, ignore_conflicts=True)
        for deal in recalculation_income_deals:
            logger.info(f'Пересчет прибыли у {deal}')
            deal.recalculation_income()
        logger.info('Обновление сделок завершено')

    def update_currency_assets(self):
        """ Обновление валютных активов портфеля """
        logger.info('Обновление валютных активов')
        investment_account_model = apps.get_model('users', 'InvestmentAccount')
        currency_asset_model = apps.get_model('users', 'CurrencyAsset')
        currency_actives = self.tinkoff_profile.portfolio_currencies()['payload']['currencies']
        (
            investment_account_model.objects
            .get(id=self.investment_account_id).currency_assets
            .exclude(currency__in=[c['currency'] for c in currency_actives]).delete()
        )
        for currency in currency_actives:
            obj, created = currency_asset_model.objects.get_or_create(
                investment_account_id=self.investment_account_id,
                currency_id=currency['currency'],
                defaults={
                    'value': currency['balance']
                }
            )
            if not created:
                obj.value = currency['balance']
                obj.save(update_fields=['value'])
        logger.info('Обновление валютных активов завершено')
