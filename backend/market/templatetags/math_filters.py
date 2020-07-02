from django import template

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
        return value
