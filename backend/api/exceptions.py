from rest_framework import status
from rest_framework.exceptions import APIException


class TotalCapitalGrowThanMaxCapital(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_code = 'total_capital_grow_than_max_capital'
    default_detail = 'Сумма капиталов совладельцев больше максимального возможного капитала'
