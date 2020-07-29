from typing import TypedDict, List, Union


class TBaseResponse(TypedDict):
    trackingId: str
    status: str


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


class TMarketStocks(TBaseResponse):
    payload: TMarketStocksPayload


class TUserAccountsPayloadAccount(TypedDict):
    brokerAccountType: str
    brokerAccountId: str


class TUserAccounts200Payload(TypedDict):
    accounts: List[TUserAccountsPayloadAccount]


class TUserAccounts200(TBaseResponse):
    payload: TUserAccounts200Payload


class TUserAccounts500Payload(TypedDict):
    message: str
    code: str


class TUserAccounts500(TBaseResponse):
    payload: TUserAccounts500Payload


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
    payment: int
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


class TOperationPayloadMarginCommission(TypedDict):
    """ Операция 'Комиссия за маржинальную торговлю' """
    operationType: str  # сегда MarginCommission
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


TOperationsPayloadOperations = List[Union[
    TOperationsPayloadPayOutOperation,  # Вывод средств с инвестиционного счета
    TOperationPayloadPayInOperation,  # Пополнение инвестиционного счета
    TOperationPayloadBuyOperation,  # Покупка ценных бумаг с инвестиционного счета
    TOperationPayloadBuyCardOperation,  # Покупка ценных бумаг с карты
    TOperationsPayloadSellOperation,  # Продажа
    TOperationPayloadDividendOperation,  # Дивиденды
    TOperationsPayloadBrokerCommissionOperation,  # Комиссия брокера
    TOperationPayloadServiceCommissionOperation,  # Комиссия за обслуживание
    TOperationPayloadMarginCommission,  # Комиссия за маржинальную торговлю
    TOperationPayloadTaxOperation,  # Налог
    TOperationPayloadTaxBackOperation,  # Налоговый вычет/корректировка налога
    TOperationPayloadTaxDividendOperation  # Налог на дивиденды
]]


class TOperationsPayload(TypedDict):
    operations: TOperationsPayloadOperations


class TOperations(TBaseResponse):
    """ Операции счета """
    payload: TOperationsPayload


class TPortfolioPayloadPositionExpectedYield(TypedDict):
    currency: str
    value: float


class TPortfolioPayloadPositionAveragePositionPrice(TypedDict):
    currency: str
    value: float


class TPortfolioPayloadPosition(TypedDict):
    figi: str
    ticker: str
    isin: str
    instrumentType: str
    balance: int
    lots: int
    expectedYield: TPortfolioPayloadPositionExpectedYield
    averagePositionPrice: TPortfolioPayloadPositionAveragePositionPrice
    name: str


class TPortfolioPayload(TypedDict):
    positions: List[TPortfolioPayloadPosition]


class TPortfolio(TBaseResponse):
    """ Портфолио """
    payload: TPortfolioPayload


class TPortfolioCurrenciesPayloadCurrencies(TypedDict):
    currency: str
    balance: float


class TPortfolioCurrenciesPayload(TypedDict):
    currencies: List[TPortfolioCurrenciesPayloadCurrencies]


class TPortfolioCurrencies(TBaseResponse):
    """ Валютные активы """
    payload: TPortfolioCurrenciesPayload
