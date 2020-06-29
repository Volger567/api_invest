from django.db import models


class Operation(models.Model):
    class Meta:
        verbose_name = 'Операция'
        verbose_name_plural = 'Операции'
