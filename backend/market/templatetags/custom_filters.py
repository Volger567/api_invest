from django import template
from django.db.models import Sum

from market.models import Operation

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


# FIXME: Отпимизировать запрос и считать на бэке
@register.filter
def percent_profit_format(operations):
    tmp_income = (
        operations
        .filter(type__in=(Operation.Types.SELL, Operation.Types.DIVIDEND))
        .aggregate(income=Sum('payment'), expense=Sum('commission'))
    )
    income = tmp_income['income']
    expense = tmp_income['expense']
    tmp_expense = (
        operations
        .filter(type__in=(Operation.Types.BUY, Operation.Types.BUY_CARD, Operation.Types.TAX_DIVIDEND))
        .aggregate(expense=Sum('payment'), commission=Sum('commission'))
    )
    expense += tmp_expense['expense'] + tmp_expense['commission']
    expense = abs(expense)
    if income > expense:
        percent_profit = ((income/expense)-1)*100
        return f'+{percent_profit:.2f}'
    elif income < expense:
        percent_profit = (1-(expense/income))*100
        return f'{percent_profit:.2f}'
    return 0
