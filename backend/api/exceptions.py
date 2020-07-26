from rest_framework import status
from rest_framework.exceptions import APIException


class TotalCapitalGrowThanMaxCapital(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_code = 'total_capital_grow_than_max_capital'
    default_detail = 'Сумма капиталов совладельцев больше максимального возможного капитала'


class TotalDefaultShareGrowThan100(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_code = 'total_default_share_grow_than_100'
    default_detail = 'Сумма всех долей, должна быть не больше 100'
