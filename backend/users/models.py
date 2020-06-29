from django.contrib.auth.models import AbstractUser, Group
from django.db import models


class Investor(AbstractUser):
    email = models.EmailField(verbose_name='Email', blank=True, unique=True)
    operations_sync_at = models.DateTimeField(verbose_name='Время последней синхронизации', null=True)
    production_token = models.CharField(verbose_name='Токен для торговли', max_length=120, blank=True)
    sandbox_token = models.CharField(verbose_name='Токен для песочницы', max_length=120, blank=True)


class InvestorGroup(Group):
    class Meta:
        proxy = True
        verbose_name = 'Группа пользователей'
        verbose_name_plural = 'Группы пользователей'
