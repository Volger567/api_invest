import datetime

import pytz
from django.contrib.auth.models import AbstractUser, Group
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver

from core import settings
from market.models import Operation, Currency
from tinkoff_api import TinkoffProfile


class Investor(AbstractUser):
    email = models.EmailField(verbose_name='Email', blank=True, unique=True)
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

    def __str__(self):
        return f'{self.creator} ({self.broker_account_id})'


@receiver(post_save, sender=InvestmentAccount)
def investment_account_post_save(sender, instance, created, *args, **kwargs):
    if created:
        creator: Investor = instance.creator
        creator.default_investment_account = instance
        creator.save(update_fields=('default_investment_account', ))

        # TODO: отдать это celery
        with TinkoffProfile(instance.token) as tp:
            project_timezone = pytz.timezone(settings.TIME_ZONE)
            from_datetime = project_timezone.localize(datetime.datetime(1900, 1, 1))
            to_datetime = datetime.datetime.now(tz=pytz.timezone(settings.TIME_ZONE))
            operations = tp.operations(from_datetime, to_datetime)['payload']['operations']
        bulk_create_operations = []
        currencies = Currency.objects.all()
        for operation in operations:
            # XXX: Тинькофф возвращает время в неправильном формате
            try:
                operation_date = project_timezone.localize(
                    datetime.datetime.fromisoformat(operation['date']).replace(tzinfo=None)
                )
            except ValueError:
                operation_date = project_timezone.localize(
                    datetime.datetime.fromisoformat(operation['date'][:19] + operation['date'][-6:]).replace(
                        tzinfo=None)
                )
            bulk_create_operations.append(
                Operation(
                    investment_account=instance, type=operation['operationType'],
                    date=operation_date, is_margin_call=operation['isMarginCall'],
                    payment=operation['payment'],
                    currency=currencies.get(iso_code__iexact=operation['currency']),
                    status=operation['status'], secondary_id=operation['id']
                )
            )
        Operation.objects.bulk_create(bulk_create_operations)
        instance.operations_sync_at = to_datetime
        instance.save(update_fields=('operations_sync_at', ))
