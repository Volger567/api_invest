import datetime
import logging
import os
from typing import List, Dict, Any

import dateutil.parser
import pytz
from django.contrib.auth.models import AbstractUser, Group
from django.db import models
from django.db.models import Sum, Min, Case, When, Q, F, ExpressionWrapper, Avg
from django.db.models.functions import Coalesce
from django.db.models.signals import post_save
from django.dispatch import receiver

from core import settings
from market.models import Operation, Currency, Stock, Deal, Share, DealIncome
from tinkoff_api import TinkoffProfile
from tinkoff_api.exceptions import InvalidTokenError
from users.services import update_operations_service

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
        default=datetime.datetime(1900, 1, 1, tzinfo=pytz.timezone(settings.TIME_ZONE))
    )

    @property
    def prop_total_income(self):
        """ Расчет дохода инвестиционного счета """
        closed_deals_total_income = (
            self.deals.closed()
            .annotate(_income=Sum('operations__payment')+Sum('operations__commission'))
            .aggregate(Sum('_income'))['_income__sum']
        )

        f_price = ExpressionWrapper(
            (F('operations__payment')+F('operations__commission'))/F('operations__quantity'),
            output_field=models.DecimalField()
        )
        only_buy = Q(operations__type__in=(Operation.Types.BUY, Operation.Types.BUY_CARD))
        only_sell = Q(operations__type=Operation.Types.SELL)
        avg_sum = Avg(f_price, filter=only_buy) + Avg(f_price, filter=only_sell)
        pieces_sold = Sum('operations__quantity', filter=only_sell)
        opened_deals_total_income = (
            Deal.objects.opened()
            .annotate(_income=Coalesce(ExpressionWrapper(avg_sum*pieces_sold, output_field=models.DecimalField()), 0))
        ).aggregate(Sum('_income'))['_income__sum']
        return closed_deals_total_income + opened_deals_total_income

    @property
    def prop_total_capital(self):
        # FIXME: сделать для всех валют
        return (
            self.operations
            .filter(type__in=(Operation.Types.PAY_IN, Operation.Types.PAY_OUT, Operation.Types.SERVICE_COMMISSION))
            .aggregate(Sum('payment'))['payment__sum']
        )

    def update_operations(self):
        """ Обновление списка операций и сделок """
        # Получаем список операций в диапазоне
        # от даты последнего получения операций минус 12 часов до текущего момента
        logger.info('Обновление операций')
        project_timezone = pytz.timezone(settings.TIME_ZONE)
        from_datetime = self.sync_at - datetime.timedelta(hours=12)
        to_datetime = datetime.datetime.now(tz=pytz.timezone(settings.TIME_ZONE))
        operations = update_operations_service.get_operations_from_tinkoff_api(
            self.token, project_timezone, from_datetime, to_datetime
        )
        logger.info('Операции получены')

        # Тут будет храниться список всех операций
        pre_bulk_create_operations: List[Dict[str, Any]] = []
        # Словарь комиссий. Ключ - дата комиссии
        commissions: Dict[datetime.datetime, Dict[str, Any]] = {}
        # Список валют
        currencies = Currency.objects.all()

        for operation in operations:
            logger.info(f'Обрабатываем операцию: {operation}')
            operation_date = project_timezone.localize(
                dateutil.parser.isoparse(operation['date']).replace(tzinfo=None)
            )
            # Будем брать только успешные операции
            if operation['status'] != Operation.Statuses.DONE:
                logger.info('Статус операции не равен DONE')
                continue
            # Если операция - комиссия брокера, добавляем в словарь комиссий
            if operation['operationType'] == Operation.Types.BROKER_COMMISSION:
                logger.info('Комиссия брокера, добавляем в словарь комиссий')
                commissions[operation_date] = operation
            # Во всех других случаях, добавляем в список операций
            else:
                # XXX:
                if operation['operationType'] == Operation.Types.MARGIN_COMMISSION:
                    logger.info('Комиссия за маржу')
                    continue
                pre_bulk_create_operations.append({
                    # Инвестиционный счет, которому принадлежит операция
                    'investment_account': self,
                    # Тип операции, например продажа/покупка/налог
                    'type': operation['operationType'],
                    # Дата, когда произошла операция
                    'date': operation_date,
                    # Маржин колл
                    'is_margin_call': operation['isMarginCall'],
                    # Стоимость операции. Число отрицательное для убыточных операций
                    'payment': operation['payment'],
                    # В какой валюте была произведена операция
                    'currency': currencies.get(iso_code__iexact=operation['currency']),
                    # Статус операции, например Done/Decline
                    'status': operation['status'],
                    # ID операции. Уникален, если не равен -1
                    'secondary_id': operation['id'],
                    # Тип инструмента, например Stock
                    'instrument_type': operation.get('instrumentType', ''),
                    # Количество проданных, купленных ценных бумаг
                    'quantity': operation.get('quantity', 0),
                })
                # Уникальный идентификатор ценной бумаги
                try:
                    figi = None if operation.get('figi') is None else Stock.objects.get(figi=operation['figi'])
                except models.ObjectDoesNotExist:
                    figi = None
                pre_bulk_create_operations[-1]['figi'] = figi
        # Список для bulk_create операции
        bulk_create_operations = []
        # Заносим в операции комиссию
        for operation in pre_bulk_create_operations:
            commission = commissions.get(operation['date'], 0)
            if commission:
                commission = commission['payment']
            bulk_create_operations.append(
                Operation(**operation, commission=commission)
            )

        # Создаем операции, ignore_conflict + constraints модели Operation
        # позволяет избегать дублирования операций
        Operation.objects.bulk_create(bulk_create_operations, ignore_conflicts=True)

        # Создание сделок
        operations = Operation.objects.filter(
            investment_account=self,
            date__range=(from_datetime, to_datetime),
            deal__isnull=True,
            type__in=(
                Operation.Types.BUY, Operation.Types.BUY_CARD, Operation.Types.TAX_DIVIDEND,
                Operation.Types.DIVIDEND, Operation.Types.SELL,
            ),
            figi__isnull=False
        ).order_by('date')
        bulk_create_shares = []
        co_owners = self.co_owners.all().values_list('pk', 'default_share', named=True)
        deals_for_recalculation_income = []
        for operation in operations:
            if operation.type in (Operation.Types.BUY, Operation.Types.BUY_CARD):
                for co_owner in co_owners:
                    bulk_create_shares.append(Share(
                        operation=operation, co_owner_id=co_owner.pk, value=co_owner.default_share
                    ))
                deal, _ = Deal.objects.opened().get_or_create(
                    investment_account=self,
                    figi=operation.figi
                )
                deal.operations.add(operation)
            elif operation.type == Operation.Types.SELL:
                deal, _ = Deal.objects.opened().get_or_create(investment_account=self, figi=operation.figi)
                deal.operations.add(operation)
            else:
                deal = (
                    Deal.objects
                    .filter(investment_account=self, figi=operation.figi)
                    .annotate(opened_at=Min('operations__date'))
                    .order_by('-opened_at')[0]
                )
                deal.operations.add(operation)
            deals_for_recalculation_income.append(deal)
        Share.objects.bulk_create(bulk_create_shares, ignore_conflicts=True)
        for d in deals_for_recalculation_income:
            d.recalculation_income()

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
        logger.info(f'Обновление портфеля "{self}"')
        update_frequency = datetime.timedelta(minutes=float(os.getenv('PROJECT_OPERATIONS_UPDATE_FREQUENCY', 1)))
        try:
            if now - self.sync_at > update_frequency:
                self.update_currency_assets()
                self.update_operations()
                self.sync_at = now
                self.save()
                logger.info('Обновление завершено')
            else:
                logger.info('Раннее обновление')
        except InvalidTokenError:
            logger.info('Обновление не удалось, токен невалидный')

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
    currency = models.ForeignKey(Currency, verbose_name='Валюта', on_delete=models.PROTECT)
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
        instance.update_operations()

        # Высчитывается капитал создателя счета
        # Складываются все пополнения на счет, из них вычитаются выводы со счета и комиссия сервиса
        creator_capital = (
            instance.operations
            .filter(type__in=(
                Operation.Types.PAY_IN, Operation.Types.PAY_OUT, Operation.Types.SERVICE_COMMISSION))
            .aggregate(s=Coalesce(Sum('payment'), 0))['s']
        )
        co_owner.capital = creator_capital
        co_owner.save(update_fields=['capital'])
