from typing import TypedDict, List, Union


class TMarketStocksPayloadInstruments(TypedDict):
    figi: str
    ticker: str
    isin: str
    minPriceIncrement: float
    lot: int
    currency: str
    name: str
    type: str


class TMarketStocksPayload(TypedDict):
    instruments: List[TMarketStocksPayloadInstruments]
    total: int


class TMarketStocks(TypedDict):
    trackingId: str
    payload: TMarketStocksPayload
    status: str


class TUserAccountsPayloadAccounts(TypedDict):
    brokerAccountType: str
    brokerAccountId: str


class TUserAccounts200Payload(TypedDict):
    accounts: List[TUserAccountsPayloadAccounts]


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
