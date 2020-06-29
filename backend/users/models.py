from django.contrib.auth.models import AbstractUser, Group
from django.db import models


class Investor(AbstractUser):
    email = models.EmailField(verbose_name='Email', blank=True, unique=True)


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
        ABSOLUTE = 'Abs', 'Абсолютный'
        RELATIVE = 'Rel', 'Относительный'

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
