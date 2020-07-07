from django import template


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
