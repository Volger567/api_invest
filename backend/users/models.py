from django.contrib.auth.models import AbstractUser, Group
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver


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


@receiver(post_save, sender=InvestmentAccount)
def investment_account_post_save(sender, instance, created, *args, **kwargs):
    if created:
        creator: Investor = instance.creator
        creator.default_investment_account = instance
        creator.save(update_fields=('default_investment_account', ))
