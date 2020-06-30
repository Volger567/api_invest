import logging
import os

from django.core.management import BaseCommand

from market.models import Currency, Stock
from tinkoff_api import TinkoffProfile

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            '-u', '--with-update',
            action='store_true',
            default=False,
            help='Обновлять уже существующие акции?'
        )

    def handle(self, *args, **options):
        """ Создает дефолтные записи в моделях """

        currencies = (
            {
                'iso_code': 'RUB',
                'abbreviation': chr(8381),
                'number_to_basic': 100,
                'name': 'Российский рубль'
            },
            {
                'iso_code': 'USD',
                'abbreviation': chr(36),
                'number_to_basic': 100,
                'name': 'Американский доллар'
            }
        )

        for c in currencies:
            Currency.objects.get_or_create(
                iso_code=c['iso_code'],
                defaults=c
            )

        tp = TinkoffProfile(os.getenv('tinkoff_api_production_token'))
        tp.auth()
        stocks = tp.market_stocks()
        db_currencies = Currency.objects.all()
        if options['with_update']:
            for stock in stocks['payload']['instruments']:
                Stock.objects.update_or_create(
                    figi=stock['figi'],
                    defaults={
                        'figi': stock['figi'],
                        'ticker': stock['ticker'],
                        'isin': stock['isin'],
                        'min_price_increment': stock.get('minPriceIncrement'),
                        'lot': stock['lot'],
                        'currency': db_currencies.get(iso_code__iexact=stock['currency']),
                        'name': stock['name']
                    }
                )
        else:
            figies = set(Stock.objects.all().values_list('figi', flat=True))
            new_figies = set(i['figi'] for i in stocks['payload']['instruments'])
            new_figies -= figies
            result = []
            for stock in stocks['payload']['instruments']:
                print(stock)
                if stock['figi'] in new_figies:
                    result.append(Stock(**{
                        'figi': stock['figi'],
                        'ticker': stock['ticker'],
                        'isin': stock['isin'],
                        'min_price_increment': stock.get('minPriceIncrement'),
                        'lot': stock['lot'],
                        'currency': db_currencies.get(iso_code__iexact=stock['currency']),
                        'name': stock['name']
                    }))
            Stock.objects.bulk_create(result)
