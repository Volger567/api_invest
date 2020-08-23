import decimal
from typing import DefaultDict


# Тип - id капитала
T_CAPITAL_ID = str
T_CAPITAL_ID_INT = int
# Тип - название поля capital (default_share, value...)
T_CAPITAL_FIELD_NAME = str
# Тип - ISO code валюты (RUB, USD, EUR)
T_CURRENCY_ISO_CODE = str


# Тип - описание строения ValidatedData
class TValidatedDataByCurrency(DefaultDict):
    """ Каждое значение это сумма всех прошедших валидацию default_share и value определенной валюты """
    total_default_share: decimal.Decimal
    total_capital_value: decimal.Decimal
