from django import template
from django.db import models
from django.db.models import Sum, ExpressionWrapper

from operations.models import SaleOperation, DividendOperation, PurchaseOperation

register = template.Library()


@register.filter
def abs_value(value):
    return abs(value)


@register.filter
def payment_format(value):
    if value < 0:
        return round(value, 2)
    elif value > 0:
        return f'+{value:.2f}'
    else:
        return round(value, 2)


@register.filter
def div(value, arg):
    return value // arg


@register.filter
def divide(value, arg):
    return value / arg


# FIXME: Отпимизировать запрос и считать на бэке
@register.filter
def percent_profit_format(operations):
    income = (
        operations
        .filter(proxy_instance_of=(SaleOperation, DividendOperation))
        .aggregate(income=ExpressionWrapper(
            Sum('payment') + Sum('commission') + Sum('dividend_tax'), output_field=models.DecimalField())
        )
    )['income']
    expense = (
        operations
        .filter(proxy_instance_of=PurchaseOperation)
        .aggregate(expense=Sum('payment') + Sum('commission'))
    )['expense']
    expense = abs(expense)
    if income > expense:
        percent_profit = ((income/expense)-1)*100
        return f'+{percent_profit:.2f}'
    elif income < expense:
        percent_profit = (1-(expense/income))*100
        return f'{percent_profit:.2f}'
    return 0
