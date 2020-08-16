from django.core.validators import MaxValueValidator
from django.db import models

from core.utils import ProxyInheritanceManager
from operations.models_constraints import OperationTypes, OperationConstraints, OperationStatuses


class Currency(models.Model):
    """ Валюты, в которых могут проводиться операции """
    class Meta:
        verbose_name = 'Валюта'
        verbose_name_plural = 'Валюты'

    iso_code = models.CharField(verbose_name='Код', max_length=3, unique=True, primary_key=True)
    abbreviation = models.CharField(verbose_name='Символ', max_length=16)
    name = models.CharField(verbose_name='Название', max_length=100, unique=True)


class Operation(models.Model):
    """ Базовая модель операции, все виды операций наследуются от нее """
    Types = OperationTypes
    Statuses = OperationStatuses

    class Meta:
        verbose_name = 'Операция'
        verbose_name_plural = 'Операции'
        ordering = ('date', )
        constraints = OperationConstraints.ALL_CONSTRAINTS

    objects = ProxyInheritanceManager()
    proxy_constraints = OperationConstraints

    # Общие поля
    investment_account = models.ForeignKey(
        'users.InvestmentAccount', verbose_name='Инвестиционный счет', on_delete=models.CASCADE,
        related_name='operations'
    )
    type = models.CharField(verbose_name='Тип', max_length=30, choices=Types.choices)
    date = models.DateTimeField(verbose_name='Дата')
    is_margin_call = models.BooleanField(default=False)
    payment = models.DecimalField(verbose_name='Оплата', max_digits=20, decimal_places=4)
    currency = models.ForeignKey(Currency, verbose_name='Валюта', on_delete=models.PROTECT)

    # Поля, актуальные не для всех операций
    instrument = models.ForeignKey(
        'market.InstrumentType', verbose_name='Ценная бумага', on_delete=models.PROTECT, null=True,
        related_name='operations'
    )

    # Поля, актуальные для покупок и продаж
    quantity = models.PositiveIntegerField(verbose_name='Количество', default=0)
    commission = models.DecimalField(
        verbose_name='Комиссия', max_digits=16, decimal_places=4, default=0,
        validators=[MaxValueValidator(0, 'Коммиссия может быть только отрицательным число или 0')]
    )
    _id = models.CharField(verbose_name='ID', max_length=32, default='-1')
    deal = models.ForeignKey(
        'market.Deal', verbose_name='Сделка', on_delete=models.PROTECT, null=True, related_name='operations'
    )

    # Для налогов на дивиденды
    dividend_tax = models.IntegerField(
        verbose_name='Налог', default=0,
        validators=[MaxValueValidator(0, 'Налог должен быть отрицательным числом или 0')]
    )
    dividend_tax_date = models.DateTimeField('Дата налога', null=True)

    @staticmethod
    def get_operation_model_by_type(operation_type):
        # Получение модели операции по типу операции (в строковом эквиваленте)
        return {
            Operation.Types.SELL: SaleOperation,
            Operation.Types.BUY: InvestmentAccountPurchaseOperation,
            Operation.Types.BUY_CARD: CardPurchaseOperation,
            Operation.Types.DIVIDEND: DividendOperation,
            Operation.Types.PAY_IN: PayInOperation,
            Operation.Types.PAY_OUT: PayOutOperation,
            Operation.Types.SERVICE_COMMISSION: ServiceCommissionOperation,
            Operation.Types.MARGIN_COMMISSION: MarginCommissionOperation,
            Operation.Types.TAX: TaxOperation,
            Operation.Types.TAX_BACK: TaxBackOperation
        }.get(operation_type)

    def friendly_type_format(self):
        return dict(Operation.Types.choices)[self.type]

    def __str__(self):
        return f'{self.get_operation_model_by_type(self.type)}({self.pk}): {self.date}'

    def __repr__(self):
        return f'<{str(self)}>'


class PayInOperation(Operation):
    class Meta:
        verbose_name = 'Пополнение средств'
        verbose_name_plural = 'Пополнения средств'
        proxy = True


class PayOutOperation(Operation):
    class Meta:
        verbose_name = 'Вывод средств'
        verbose_name_plural = 'Выводы средств'
        proxy = True


class PayOperation(Operation):
    class Meta:
        verbose_name = 'Пополнение/Вывод средств'
        verbose_name_plural = 'Пополнения/Выводы средств'
        proxy = True


class PurchaseOperation(Operation):
    class Meta:
        verbose_name = 'Покупка'
        verbose_name_plural = 'Покупки'
        proxy = True


class CardPurchaseOperation(Operation):
    class Meta:
        verbose_name = 'Покупка с карты'
        verbose_name_plural = 'Покупки с карты'
        proxy = True


class InvestmentAccountPurchaseOperation(Operation):
    class Meta:
        verbose_name = 'Покупка с ИС'
        verbose_name_plural = 'Покупки с ИС'
        proxy = True


class SaleOperation(Operation):
    class Meta:
        verbose_name = 'Продажа'
        verbose_name_plural = 'Продажи'
        proxy = True


class Transaction(models.Model):
    """ В одной операции покупки/продажи может быть несколько транзакций,
        так бывает когда заявки реализуются по частям, а не сразу
    """
    class Meta:
        verbose_name = 'Транзакции'
        verbose_name_plural = 'Транзакции'

    id = models.CharField(verbose_name='ID', max_length=32, primary_key=True)
    operation = models.ForeignKey(Operation, verbose_name='Операция', on_delete=models.CASCADE)
    date = models.DateTimeField(verbose_name='Дата')
    quantity = models.PositiveIntegerField(verbose_name='Количество шт.')
    price = models.DecimalField(verbose_name='Цена/шт.', max_digits=20, decimal_places=4)


class DividendOperation(Operation):
    class Meta:
        verbose_name = 'Дивиденды'
        verbose_name_plural = 'Дивиденды'
        proxy = True


class ServiceCommissionOperation(Operation):
    class Meta:
        verbose_name = 'Комиссия за обслуживание'
        verbose_name_plural = 'Комиссии за обслуживание'
        proxy = True


class MarginCommissionOperation(Operation):
    class Meta:
        verbose_name = 'Комиссия за маржинальную торговлю'
        verbose_name_plural = 'Комиссии за обслуживание'
        proxy = True


class TaxOperation(Operation):
    class Meta:
        verbose_name = 'Налог'
        verbose_name_plural = 'Налоги'
        proxy = True


class TaxBackOperation(Operation):
    class Meta:
        verbose_name = 'Возврат налога'
        verbose_name_plural = 'Возвраты налога'
        proxy = True


class Share(models.Model):
    """ Отражает долю совладельца в каждой операции """
    class Meta:
        verbose_name = 'Доля в операции'
        verbose_name_plural = 'Доли в операциях'
        constraints = [
            models.UniqueConstraint(fields=('operation', 'co_owner'), name='unique_co_owner_op')
        ]
        ordering = ['pk']

    operation = models.ForeignKey(Operation, verbose_name='Операция',
                                  on_delete=models.CASCADE, related_name='shares')
    co_owner = models.ForeignKey('users.CoOwner', verbose_name='Совладелец',
                                 on_delete=models.CASCADE, related_name='shares')
    value = models.DecimalField(verbose_name='Доля', max_digits=9, decimal_places=8)

    def __str__(self):
        return f'{self.co_owner.investor.username} ({self.value})'
