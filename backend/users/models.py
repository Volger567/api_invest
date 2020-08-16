import datetime
import logging
import os

import pytz
from django.contrib.auth.models import AbstractUser, Group
from django.db import models
from django.db.models import Sum, Case, When, Q, F, ExpressionWrapper, Avg
from django.db.models.functions import Coalesce
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from core.utils import ProxyQ
from market.models import Deal, DealIncome
from operations.models import PurchaseOperation, SaleOperation, PayOperation, ServiceCommissionOperation
from tinkoff_api.exceptions import InvalidTokenError
from users.services.update_service import Updater

logger = logging.getLogger(__name__)


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
        constraints = [
            models.UniqueConstraint(fields=('name', 'creator'), name='unique_inv_name'),
            models.UniqueConstraint(fields=('creator', 'token'), name='unique_token')
        ]

    class CapitalSharingPrinciples(models.TextChoices):
        ABSOLUTE = 'abs', 'Абсолютный'
        RELATIVE = 'rel', 'Относительный'

    name = models.CharField(verbose_name='Название счета', max_length=256)
    creator = models.ForeignKey(
        Investor, verbose_name='Создатель счета', on_delete=models.CASCADE,
        related_name='owned_investment_accounts'
    )
    token = models.CharField(verbose_name='Токен для торговли', max_length=128)
    broker_account_id = models.CharField(verbose_name='ID инвестиционного счета', max_length=50)
    sync_at = models.DateTimeField(
        verbose_name='Время последней синхронизации',
        default=datetime.datetime(1990, 1, 1, tzinfo=pytz.timezone('UTC'))
    )

    @property
    def prop_total_income(self):
        """ Расчет дохода инвестиционного счета """
        total_income_of_closed_deals = (
            self.deals.closed()
            .annotate(_income=Sum('operations__payment')+Sum('operations__commission'))
            .aggregate(s=Sum('_income'))['s']
        )

        f_price = ExpressionWrapper(
            (F('operations__payment')+F('operations__commission'))/F('operations__quantity'),
            output_field=models.DecimalField()
        )
        q_purchase = ProxyQ(proxy_instance_of=PurchaseOperation)
        q_sale = ProxyQ(proxy_instance_of=SaleOperation)
        avg_sum = Avg(f_price, filter=q_purchase) + Avg(f_price, filter=q_sale)
        pieces_sold = Sum('operations__quantity', filter=q_sale)
        total_income_of_opened_deals = (
            Deal.objects.opened()
            .annotate(_income=Coalesce(ExpressionWrapper(avg_sum*pieces_sold, output_field=models.DecimalField()), 0))
        ).aggregate(s=Sum('_income'))['s']
        return total_income_of_closed_deals + total_income_of_opened_deals

    @property
    def prop_total_capital(self):
        """ Расчет общего капитала для всего ИС """
        # XXX
        return 0

    def update_portfolio(self, now=None):
        """ Обновление всего портфеля.
            Включает в себя обновление операций, сделок, валютных активов
        :param now: Текущий момент времени, до которого будут обновляться операции
        """
        logger.info(f'Обновление портфеля "{self}"')
        if now is None:
            now = timezone.now()
        update_frequency = datetime.timedelta(minutes=float(os.getenv('PROJECT_OPERATIONS_UPDATE_FREQUENCY', 1)))
        try:
            if now - self.sync_at > update_frequency:
                from_datetime = self.sync_at - datetime.timedelta(hours=6)
                to_datetime = now
                updater = Updater(from_datetime, to_datetime, self.id, token=self.token)
                updater.update_currency_assets()
                updater.update_operations()
                updater.update_deals()
                self.sync_at = to_datetime
                self.save()
                logger.info('Обновление портфеля завершено')
            else:
                logger.info('Портфель обновлялся недавно')
        except InvalidTokenError:
            logger.warning('Обновление портфеля не удалось, токен невалидный')

    def __str__(self):
        return f'{self.name} ({self.creator})'


class CoOwnerQuerySet(models.QuerySet):
    def with_is_creator_annotations(self):
        return self.annotate(is_creator=Case(
            When(Q(investor=F('investment_account__creator')), then=True),
            default=False, output_field=models.BooleanField()
        ))

    def without_creator(self):
        return self.exclude(investor=F('investment_account__creator'))


class CoOwnerManager(models.Manager):
    def get_queryset(self):
        return CoOwnerQuerySet(self.model, using=self._db)

    def with_is_creator_annotations(self):
        return self.get_queryset().with_is_creator_annotations()

    def without_creator(self):
        return self.get_queryset().without_creator()


class CoOwner(models.Model):
    """ Совладелец счета """
    class Meta:
        verbose_name = 'Совладелец'
        verbose_name_plural = 'Совладельцы'
        constraints = [
            models.UniqueConstraint(fields=('investor', 'investment_account'), name='co_owner_constraints')
        ]

    objects = CoOwnerManager()
    investor = models.ForeignKey(
        Investor, verbose_name='Инвестор', on_delete=models.CASCADE, related_name='co_owned_investment_accounts')
    investment_account = models.ForeignKey(
        InvestmentAccount, verbose_name='Инвестиционный счет', on_delete=models.CASCADE, related_name='co_owners')
    capital = models.DecimalField(verbose_name='Капитал', max_digits=20, decimal_places=4, default=0)
    default_share = models.DecimalField(verbose_name='Доля по умолчанию', default=0, max_digits=9, decimal_places=8)

    def __str__(self):
        return f'{self.investor}, {self.investment_account.name}'


class CurrencyAsset(models.Model):
    """ Валютный актив в портфеле """
    class Meta:
        verbose_name = 'Валютный актив'
        verbose_name_plural = 'Валютные активы'
        ordering = ('currency', )
        constraints = [
            models.UniqueConstraint(fields=('investment_account', 'currency'), name='unique_currency_asset')
        ]

    investment_account = models.ForeignKey(
        InvestmentAccount, verbose_name='Инвестиционный счет', on_delete=models.CASCADE, related_name='currency_assets')
    currency = models.ForeignKey('operations.Currency', verbose_name='Валюта', on_delete=models.PROTECT)
    value = models.DecimalField(verbose_name='Количество', max_digits=20, decimal_places=4, default=0)


@receiver(post_save, sender=InvestmentAccount)
def investment_account_post_save(**kwargs):
    if kwargs.get('created'):
        # Операции, которые будут выполнены после создания инвестиционного счета
        instance = kwargs['instance']
        # У создателя, счет станет счетом по умолчанию
        creator: Investor = instance.creator
        creator.default_investment_account = instance
        creator.save(update_fields=('default_investment_account', ))

        # Создатель счета становится одним из совладельцев счета
        co_owner = CoOwner.objects.create(
            investor=creator, investment_account=instance,
            default_share=1, capital=0
        )

        # Загружаем все операции из Тинькофф
        instance.update_portfolio()

        # Высчитывается капитал создателя счета
        # Складываются все пополнения на счет, из них вычитаются выводы со счета и комиссия сервиса
        creator_capital = (
            instance.operations
            .filter(proxy_instance_of=(PayOperation, ServiceCommissionOperation))
            .aggregate(s=Coalesce(Sum('payment'), 0))['s']
        )
        co_owner.capital = creator_capital
        co_owner.save(update_fields=['capital'])
