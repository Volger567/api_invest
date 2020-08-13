import logging
import os

from django.contrib.auth import get_user_model
from django.core.management import BaseCommand

from market.models import StockInstrument
from operations.models import Currency
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
            ('RUB', chr(8381), 'Российский рубль'),
            ('USD', chr(36), 'Американский доллар'),
            ('EUR', chr(8364), 'Евро'),
            ('GBP', chr(163), 'Фунт стерлингов'),
            ('HKD', 'HK'+chr(36), 'Гонконгский доллар'),
            ('CHF', chr(8355), 'Швейцарский франк'),
            ('JPY', chr(165), 'Японская иена'),
            ('CNY', chr(165),  'Китайский юань'),
            ('TRY', chr(8378), 'Турецкая лира')
        )
        for iso_code, abbr, name in currencies:
            obj, created = Currency.objects.get_or_create(
                iso_code=iso_code,
                defaults={
                    'abbreviation': abbr,
                    'name': name
                }
            )
            if created:
                logger.info(f'Валюта "{iso_code}" создана')
            else:
                logger.info(f'Валюта "{iso_code}" уже существует')
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

        logger.info('Получаем список ценных бумаг')
        token = os.getenv('tinkoff_api_production_token') or os.getenv('tinkoff_api_sandbox_token')
        with TinkoffProfile(token) as tp:
            stocks = tp.market_stocks()

        # FIXME: оптимизировать
        currency_by_iso_code = Currency.objects.in_bulk()
        if options['with_update']:
            for stock in stocks['payload']['instruments']:
                StockInstrument.objects.update_or_create(
                    figi=stock['figi'],
                    defaults={
                        'figi': stock['figi'],
                        'ticker': stock['ticker'],
                        'isin': stock['isin'],
                        'min_price_increment': stock.get('minPriceIncrement'),
                        'lot': stock['lot'],
                        'currency': currency_by_iso_code[stock['currency']],
                        'name': stock['name']
                    }
                )
        else:
            existing_figies = set(StockInstrument.objects.all().values_list('figi', flat=True))
            result = []
            for stock in stocks['payload']['instruments']:
                if stock['figi'] not in existing_figies:
                    result.append(StockInstrument(**{
                        'figi': stock['figi'],
                        'ticker': stock['ticker'],
                        'isin': stock['isin'],
                        'min_price_increment': stock.get('minPriceIncrement', 0),
                        'lot': stock['lot'],
                        'currency': currency_by_iso_code[stock['currency']],
                        'name': stock['name']
                    }))
            StockInstrument.objects.pseudo_bulk_create(result)
        logger.info('Список бумаг получен и добавлен в БД')
