import datetime

import dateutil.parser
import pytz
from django.contrib.auth.models import AbstractUser, Group
from django.db import models
from django.db.models import Sum, Min
from django.db.models.signals import post_save
from django.dispatch import receiver

from core import settings
from market.models import Operation, Currency, Stock, Deal
from tinkoff_api import TinkoffProfile


class Investor(AbstractUser):
    # email = models.EmailField(verbose_name='Email', blank=True, unique=True)
    default_investment_account = models.ForeignKey(
        'InvestmentAccount', verbose_name='Инвестиционный счет по умолчанию', on_delete=models.SET_NULL, null=True
    )


class InvestorGroup(Group):
    class Meta:
        proxy = True
        verbose_name = 'Группа пользователей'
        verbose_name_plural = 'Группы пользователей'


class InvestmentAccount(models.Model):
    class Meta:
        verbose_name = 'Инвестиционный счет'
        verbose_name_plural = 'Инвестиционные счета'

    class CapitalSharingPrinciples(models.TextChoices):
        ABSOLUTE = 'abs', 'Абсолютный'
        RELATIVE = 'rel', 'Относительный'

    name = models.CharField(verbose_name='Название счета', max_length=256)
    creator = models.ForeignKey(
        Investor, verbose_name='Создатель счета', on_delete=models.CASCADE,
        related_name='owned_investor_accounts'
    )
    token = models.CharField(verbose_name='Токен для торговли', max_length=128)
    broker_account_id = models.CharField(verbose_name='ID инвестиционного счета', max_length=50)
    operations_sync_at = models.DateTimeField(verbose_name='Время последней синхронизации', null=True)
    co_owners = models.ManyToManyField(
        Investor, verbose_name='Совладельцы',
        related_name='co_owned_investor_accounts'
    )
    capital_sharing_principle = models.CharField(
        verbose_name='Принцип разделения капитала',
        choices=CapitalSharingPrinciples.choices,
        max_length=16
    )

    def update_operations(self):
        """ Обновление списка операций и сделок """
        # TODO: отдать это celery
        with TinkoffProfile(self.token) as tp:
            project_timezone = pytz.timezone(settings.TIME_ZONE)
            if self.operations_sync_at is None:
                from_datetime = project_timezone.localize(datetime.datetime(1900, 1, 1))
            else:
                from_datetime = self.operations_sync_at
            to_datetime = datetime.datetime.now(tz=pytz.timezone(settings.TIME_ZONE))
            operations = tp.operations(from_datetime, to_datetime)['payload']['operations']
            self.operations_sync_at = to_datetime
        pre_bulk_create_operations = []
        commissions = {}
        currencies = Currency.objects.all()

        for operation in operations:
            operation_date = project_timezone.localize(
                dateutil.parser.isoparse(operation['date']).replace(tzinfo=None)
            )
            if operation['operationType'] == 'BrokerCommission' and operation['status'] == Operation.Statuses.DONE:
                commissions[operation_date] = operation
            elif operation['status'] == Operation.Statuses.DONE:
                pre_bulk_create_operations.append(
                    dict(
                        investment_account=self, type=operation['operationType'],
                        date=operation_date, is_margin_call=operation['isMarginCall'],
                        payment=operation['payment'],
                        currency=currencies.get(iso_code__iexact=operation['currency']),
                        status=operation['status'], secondary_id=operation['id'],
                        instrument_type=operation.get('operationType', ''),
                        quantity=operation.get('quantity', 0),
                        figi=None if operation.get('figi') is None else Stock.objects.get(figi=operation['figi'])
                    )
                )
        bulk_create_operations = []
        for operation in pre_bulk_create_operations:
            commission = commissions.get(operation['date'], 0)
            if commission:
                commission = commission['payment']
            bulk_create_operations.append(
                Operation(**operation, commission=commission)
            )

        Operation.objects.bulk_create(bulk_create_operations)
        self.save(update_fields=('operations_sync_at', ))

        # Создание сделок
        operations = Operation.objects.filter(
            investment_account=self,
            date__range=(from_datetime, to_datetime),
            deal__isnull=True,
            type__in=(
                Operation.Types.BUY, Operation.Types.BUY_CARD, Operation.Types.TAX_DIVIDEND,
                Operation.Types.DIVIDEND, Operation.Types.SELL,
            )
        ).order_by('date')
        for operation in operations:
            if operation.type in (Operation.Types.BUY, Operation.Types.BUY_CARD):
                deal, _ = Deal.objects.opened().get_or_create(
                    investment_account=self,
                    figi=operation.figi
                )
                deal.operation_set.add(operation)
            elif operation.type == Operation.Types.SELL:
                deal = Deal.objects.opened().get(investment_account=self, figi=operation.figi)
                deal.operation_set.add(operation)
            else:
                deal = (
                    Deal.objects
                    .filter(investment_account=self, figi=operation.figi)
                    .annotate(opened_at=Min('operation__date'))
                    .order_by('-opened_at')[0]
                )
                deal.operation_set.add(operation)

    def update_currency_assets(self):
        """ Обновить валютные активы в портфеле"""
        with TinkoffProfile(self.token) as tp:
            currency_actives = tp.portfolio_currencies()['payload']['currencies']
        self.currency_assets.exclude(currency__iso_code__in=[c['currency'] for c in currency_actives]).delete()
        for currency in currency_actives:
            obj, created = CurrencyAsset.objects.get_or_create(
                investment_account=self,
                currency=Currency.objects.get(iso_code__iexact=currency['currency']),
                defaults={
                    'value': currency['balance']
                }
            )
            if not created:
                obj.value = currency['balance']
                obj.save(update_fields=['value'])

    def update_all(self, now):
        update_frequency = datetime.timedelta(seconds=60)
        if now - self.operations_sync_at > update_frequency:
            self.update_currency_assets()
            self.update_operations()

    def __str__(self):
        return f'{self.name} ({self.creator})'


class CurrencyAsset(models.Model):
    """ Валютный актив в портфеле """
    class Meta:
        verbose_name = 'Валютный актив'
        verbose_name_plural = 'Валютные активы'
        ordering = ('currency', )

    investment_account = models.ForeignKey(
        InvestmentAccount, verbose_name='Инвестиционный счет', on_delete=models.CASCADE, related_name='currency_assets')
    currency = models.ForeignKey(Currency, verbose_name='Валюта', on_delete=models.PROTECT)
    value = models.DecimalField(verbose_name='Количество', max_digits=20, decimal_places=4, default=0)


@receiver(post_save, sender=InvestmentAccount)
def investment_account_post_save(**kwargs):
    if kwargs.get('created'):
        instance = kwargs['instance']
        creator: Investor = instance.creator
        creator.default_investment_account = instance
        creator.save(update_fields=('default_investment_account', ))

        instance.update_operations()
