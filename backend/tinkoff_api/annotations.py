from typing import TypedDict, List, Union


class TMarketStocksPayloadInstrument(TypedDict):
    figi: str
    ticker: str
    isin: str
    minPriceIncrement: float
    lot: int
    currency: str
    name: str
    type: str


class TMarketStocksPayload(TypedDict):
    instruments: List[TMarketStocksPayloadInstrument]
    total: int


class TMarketStocks(TypedDict):
    trackingId: str
    payload: TMarketStocksPayload
    status: str


class TUserAccountsPayloadAccount(TypedDict):
    brokerAccountType: str
    brokerAccountId: str


class TUserAccounts200Payload(TypedDict):
    accounts: List[TUserAccountsPayloadAccount]


class TUserAccounts200(TypedDict):
    trackingId: str
    payload: TUserAccounts200Payload
    status: str


class TUserAccounts500Payload(TypedDict):
    message: str
    code: str


class TUserAccounts500(TypedDict):
    trackingId: str
    payload: TUserAccounts500Payload
    status: str


TUserAccounts = Union[TUserAccounts200, TUserAccounts500]


class TOperationsPayloadOperationCommission(TypedDict):
    """
        Комиссия операции
    Не как отдельная операция, а именно в покупке/продаже, как один из ключей словаря)
    """
    currency: str
    value: float


class TOperationsPayloadOperationTrade(TypedDict):
    """
        При покупке/продаже информация о купленных/проданных лотах
    Если, например, при продаже 10 лотов, сначала покупается 5, потом еще 5,
    операция будет засчитана как одна, но в 'trades' операции будет информации о том,
    сколько лотов и когда было продано
    """
    tradeId: str
    date: str
    quantity: int
    price: float


class TOperationsPayloadPayOutOperation(TypedDict):
    """ Операция 'Вывод средств с инвестиционного счета' """
    operationType: str  # Всегда PayOut
    date: str
    isMarginCall: bool
    payment: float
    currency: str
    status: str
    id: str


class TOperationPayloadPayInOperation(TypedDict):
    """ Операция 'Пополнение инвестиционного счета' """
    operationType: str  # Всегда PayIn
    date: str
    isMarginCall: bool
    payment: int
    currency: str
    status: str
    id: str


class TOperationPayloadBuyOperation(TypedDict):
    """ Операция 'Покупка ценных бумаг' """
    # Для покупок с инвестиционного счета Buy,
    # для покупока с карты - BuyCard
    operationType: str
    date: str
    isMarginCall: bool
    instrumentType: str
    figi: str
    quantity: int
    price: float
    payment: float
    currency: str
    # В отличие от продажи, комиссия для покупки расчитывается отдельно
    # поэтому ключа commission нет
    trades: List[TOperationsPayloadOperationTrade]
    status: str
    id: str


TOperationPayloadBuyCardOperation = TOperationPayloadBuyOperation


class TOperationsPayloadSellOperation(TypedDict):
    """ Операции 'Продажа' """
    operationType: str  # Вседга Sell
    date: str
    isMarginCall: bool
    instrumentType: str
    figi: str
    quantity: int
    price: float
    payment: float
    currency: str
    commission: TOperationsPayloadOperationCommission
    trades: List[TOperationsPayloadOperationTrade]
    status: str
    id: str


class TOperationPayloadDividendOperation(TypedDict):
    """ Операция 'Получение дивидендов' """
    operationType: str  # Всегда Dividend
    date: str
    isMarginCall: bool
    instrumentType: str
    figi: str
    quantity: int
    # TODO: пока непонятно, могут ли быть дивиденды не целым числом
    payment: Union[int, float]
    currency: str
    status: str
    id: str


class TOperationsPayloadBrokerCommissionOperation(TypedDict):
    """ Операциия 'Комиссия брокера' """
    operationType: str  # Всегда BrokerCommission
    date: str
    isMarginCall: bool
    instrumentType: str
    figi: str
    payment: float
    currency: str
    status: str
    id: str


class TOperationPayloadServiceCommissionOperation(TypedDict):
    """ Операция 'Комиссия за обслуживание' """
    operationType: str  # Всегда ServiceCommission
    date: str
    isMarginCall: bool
    quantity: int
    payment: int
    currency: str
    status: str
    id: str


class TOperationPayloadTaxOperation(TypedDict):
    """ Операция 'Налог' """
    operationType: str  # Всегда Tax
    date: str
    isMarginCall: bool
    quantity: int
    payment: int
    currency: str
    status: str
    id: str


class TOperationPayloadTaxBackOperation(TypedDict):
    """ Операция 'Налоговый вычет/корректировка налога' """
    operationType: str  # Всегда TaxBack
    date: str
    isMarginCall: bool
    payment: int
    currency: str
    status: str
    id: str


class TOperationPayloadTaxDividendOperation(TypedDict):
    """ Операция 'Налог на дивиденды' """
    operationType: str
    date: str
    isMarginCall: bool
    instrumentType: str
    figi: str
    quantity: int
    payment: int
    currency: str
    status: str
    id: str


class TOperationsPayload(TypedDict):
    # Существует несколько типов операций
    operations: List[Union[
        TOperationsPayloadPayOutOperation,  # Вывод средств с инвестиционного счета
        TOperationPayloadPayInOperation,  # Пополнение инвестиционного счета
        TOperationPayloadBuyOperation,  # Покупка ценных бумаг с инвестиционного счета
        TOperationPayloadBuyCardOperation,  # Покупка ценных бумаг с карты
        TOperationsPayloadSellOperation,  # Продажа
        TOperationPayloadDividendOperation,  # Дивиденды
        TOperationsPayloadBrokerCommissionOperation,  # Комиссия брокера
        TOperationPayloadServiceCommissionOperation,  # Комиссия за обслуживание
        TOperationPayloadTaxOperation,  # Налог
        TOperationPayloadTaxBackOperation,  # Налоговый вычет/корректировка налога
        TOperationPayloadTaxDividendOperation  # Налог на дивиденды
    ]]


class TOperations(TypedDict):
    """ Операции счета """
    trackingId: str
    payload: TOperationsPayload
    status: str
