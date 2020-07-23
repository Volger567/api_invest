import logging
import os

from django.contrib.auth import get_user_model
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
        """ Создает дефолтные записи в моделях валюты и ценных бумаг """

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
            },
            {
                'iso_code': 'EUR',
                'abbreviation': chr(8364),
                'number_to_basic': 100,
                'name': 'Евро'
            }
        )
        user_model = get_user_model()
        if not user_model.objects.filter(is_superuser=True, is_staff=True).exists():
            print('Супер-пользователь не существует, создаем')
            superuser = user_model.objects.create(
                username=os.getenv('PROJECT_SUPERUSER_USERNAME'),
                email=os.getenv('PROJECT_SUPERUSER_EMAIL'),
                is_staff=True,
                is_superuser=True
            )
            superuser.set_password(os.getenv('PROJECT_SUPERUSER_PASSWORD'))
            superuser.save()
        for c in currencies:
            obj, created = Currency.objects.get_or_create(
                iso_code=c['iso_code'],
                defaults=c
            )
            if created:
                print(f'Валюта {c["iso_code"]} была создана')
            else:
                print(f'Валюта {c["iso_code"]} уже существует')

        token = os.getenv('tinkoff_api_production_token') or os.getenv('tinkoff_api_sandbox_token')
        tp = TinkoffProfile(token)
        tp.auth()
        stocks = tp.market_stocks()
        db_currencies = Currency.objects.all()
        if options['with_update']:
            for stock in stocks['payload']['instruments']:
                # TODO: оптимизировать
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
                if stock['figi'] in new_figies:
                    result.append(Stock(**{
                        'figi': stock['figi'],
                        'ticker': stock['ticker'],
                        'isin': stock['isin'],
                        'min_price_increment': stock.get('minPriceIncrement', 0),
                        'lot': stock['lot'],
                        'currency': db_currencies.get(iso_code__iexact=stock['currency']),
                        'name': stock['name']
                    }))
            Stock.objects.bulk_create(result, ignore_conflicts=True)
