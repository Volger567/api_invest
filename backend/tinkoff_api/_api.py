from functools import wraps
from typing import Optional, Dict, Any
from urllib.parse import urljoin

import requests

from backend.tinkoff_api.exceptions import PermissionDeniedError, WrongToken, UnauthorizedError, UnknownError


T_JSON = Dict[Any, Any]


def only_with_production_token(func):
    """ Ограничивает доступ к функциям, для которых нужен trading_token """
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if getattr(self, 'is_production_token_valid', False):
            return func(self, *args, **kwargs)
        raise PermissionDeniedError('Авторизуйтесь через production_token')
    return wrapper


def only_authorized(func):
    """ Только для авторизованных пользователей """
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if getattr(self, 'is_authorized', False):
            return func(self, *args, **kwargs)
        raise UnauthorizedError('Авторизуйтесь, используя метод .auth()')
    return wrapper


class TinkoffApiUrl:
    production_rest = 'https://api-invest.tinkoff.ru/openapi'
    production_streaming = 'wss://api-invest.tinkoff.ru/openapi/md/v1/md-openapi/ws'

    # Операции в sandbox
    sandbox_rest = 'https://api-invest.tinkoff.ru/openapi/sandbox'
    sandbox_rest_base_sandbox = urljoin(sandbox_rest, '/sandbox')
    sandbox_rest_register = urljoin(sandbox_rest_base_sandbox, '/register')
    sandbox_rest_currencies_balance = urljoin(sandbox_rest_base_sandbox, '/currencies/balance')
    sandbox_rest_positions_balance = urljoin(sandbox_rest_base_sandbox, '/positions/balance')
    sandbox_rest_remove = urljoin(sandbox_rest_base_sandbox, '/remove')
    sandbox_rest_clear = urljoin(sandbox_rest_base_sandbox, '/clear')

    # Операции заявок
    sandbox_rest_orders = urljoin(sandbox_rest, '/orders')
    sandbox_rest_orders_limit_order = urljoin(sandbox_rest_orders, '/limit-order')
    sandbox_rest_orders_market_order = urljoin(sandbox_rest_orders, '/market-order')
    sandbox_rest_orders_cancel = urljoin(sandbox_rest_orders, '/cancel')

    # Операции с портфелем пользователя
    sandbox_rest_portfolio = urljoin(sandbox_rest, '/portfolio')
    sandbox_rest_portfolio_currencies = urljoin(sandbox_rest_portfolio, '/currencies')

    # Получение информации по бумагам
    sandbox_rest_market = urljoin(sandbox_rest, '/market')
    sandbox_rest_market_stocks = urljoin(sandbox_rest_market, '/stocks')
    sandbox_rest_market_bonds = urljoin(sandbox_rest_market, '/bonds')
    sandbox_rest_market_etfs = urljoin(sandbox_rest_market, '/etfs')
    sandbox_rest_market_currencies = urljoin(sandbox_rest_market, '/currencies')
    sandbox_rest_market_candles = urljoin(sandbox_rest_market, '/candles')
    sandbox_rest_market_by_figi = urljoin(sandbox_rest_market, '/by-figi')
    sandbox_rest_market_by_ticker = urljoin(sandbox_rest_market, '/by-ticker')

    # Получение информации по операциям
    sandbox_rest_operations = urljoin(sandbox_rest, '/operations')


class TinkoffProfile:
    def __init__(self, production_token: Optional[str], sandbox_token: Optional[str]):
        if bool(production_token) == bool(sandbox_token):
            raise WrongToken.OnlyOneError('Только один токен должен быть указан')
        self._session = requests.session()
        self.production_token: str = production_token
        self.is_production_token_valid: bool = False
        self.sandbox_token: str = sandbox_token
        self.is_sandbox_token_valid: bool = False

        self.tracking_id: Optional[str] = None
        self.broker_account_id: Optional[str] = None

    def auth(self) -> bool:
        """ Авторизация по токену """
        # TODO: сделать для production_token
        if self.sandbox_token:
            response = self._session.post(
                TinkoffApiUrl.sandbox_rest_register,
                headers={'Authorization': f'Bearer {self.sandbox_token}'}
            )
            if response.status_code == requests.status_codes.codes.ok:
                self.is_sandbox_token_valid = True
                self.tracking_id = response.json()['trackingId']
                self.broker_account_id = response.json()['payload']['brokerAccountId']
                self._session.headers.update({
                    'Authorization': f'Bearer {self.sandbox_token}'
                })
                return True
            elif response.status_code == requests.status_codes.codes.unauthorized:
                raise UnauthorizedError('Неверный sandbox_token')
            else:
                raise UnknownError(
                    'Неизвестная ошибка во время попытки авторизации,'
                    f'status_code={response.status_code}, content={response.content}'
                )
        else:
            raise UnauthorizedError('Авторизация по токенам не удалась')

    @property
    def is_authorized(self) -> bool:
        return self.is_sandbox_token_valid or self.is_production_token_valid

    @only_authorized
    def market_stocks(self) -> T_JSON:
        if self.is_sandbox_token_valid:
            response = self._session.get(TinkoffApiUrl.sandbox_rest_market_stocks)
            if response.status_code == requests.status_codes.codes.ok:
                return response.json()
        else:
            # TODO: Для production_token
            pass
