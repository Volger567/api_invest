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
        logger.info('Создаем валюты')
        currencies = (
            ('RUB', chr(8381), 'Российский рубль', ''),
            ('USD', chr(36), 'Американский доллар', 'BBG0013HGFT4'),
            ('EUR', chr(8364), 'Евро', 'BBG0013HJJ31', ''),
            ('GBP', chr(163), 'Фунт стерлингов', ''),
            ('HKD', 'HK'+chr(36), 'Гонконгский доллар', ''),
            ('CHF', chr(8355), 'Швейцарский франк', ''),
            ('JPY', chr(165), 'Японская иена', ''),
            ('CNY', chr(165),  'Китайский юань', ''),
            ('TRY', chr(8378), 'Турецкая лира', '')
        )
        currencies = [
            Currency(iso_code=iso, abbreviation=abbr, name=name, figi=figi)
            for iso, abbr, name, figi in currencies
        ]
        Currency.objects.bulk_create(currencies, ignore_conflicts=True)
        Currency.objects.bulk_update(currencies)
        logger.info('Валюты созданы')

        logger.info('Создаем супер-пользователя')
        user_model = get_user_model()
        # Создаем суперпользователя из конфига, если такого не существует
        if user_model.objects.filter(is_superuser=True, is_staff=True).exists():
            logger.info('Супер-пользователь уже существует')
        else:
            superuser = user_model.objects.create(
                username=os.getenv('PROJECT_SUPERUSER_USERNAME'),
                email=os.getenv('PROJECT_SUPERUSER_EMAIL'),
                is_staff=True,
                is_superuser=True
            )
            superuser.set_password(os.getenv('PROJECT_SUPERUSER_PASSWORD'))
            superuser.save()
            logger.info(f'Супер-пользователь "{superuser.username}" создан')

        token = os.getenv('tinkoff_api_production_token') or os.getenv('tinkoff_api_sandbox_token')
        with TinkoffProfile(token) as tp:
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
