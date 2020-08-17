from django import template
from django.utils import timezone

from core.utils import word2declension

register = template.Library()


@register.simple_tag(takes_context=True)
def expected_profit(context, figi):
    portfolio = context['portfolio']
    for asset in portfolio:
        if figi == asset['figi']:
            expected = asset['expectedYield']['value']
            if expected > 0:
                return f'+{expected}'
            else:
                return expected


@register.simple_tag(takes_context=True)
def expected_percent_profit(context, figi):
    portfolio = context['portfolio']
    for asset in portfolio:
        if figi == asset['figi']:
            price = asset['averagePositionPrice']['value'] * asset['balance']
            expected_price = price + asset['expectedYield']['value']
            if price < expected_price:
                income = ((expected_price / price)-1) * 100
                return f'+{income:.2f}'
            elif price > expected_price:
                expense = (1-(expected_price / price)) * 100
                return f'-{expense:.2f}'
            return 0


@register.simple_tag(takes_context=AttributeError)
def sync_time_ago(context):
    sync_at = context['request'].user.default_investment_account.sync_at
    now = timezone.now()
    delta = (now - sync_at).seconds
    hours = delta // 3600
    minutes = (delta - hours * 3600) // 60
    seconds = delta - hours * 3600 - minutes * 60
    res = []
    if hours:
        res.append(f'{str(hours).zfill(2)} + {word2declension(hours, "час", "часа", "часов")}')
    if minutes:
        res.append(f'{str(minutes).zfill(2)} + {word2declension(minutes, "минута", "минуты", "минут")}')
    if seconds:
        res.append(f'{str(seconds).zfill(2)} + {word2declension(seconds, "секунда", "секунды", "секунд")}')
    res.append('назад')
    return ' '.join(res)
