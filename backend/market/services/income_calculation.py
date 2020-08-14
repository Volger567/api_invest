""" Расчет доходов каждого инвестора за определенную сделку
"""

from decimal import Decimal
from typing import Union, Dict, NoReturn

# Как правило, это либо username, либо id, либо CoOwner
from core.utils import is_proxy_instance
from operations.models import DividendOperation, SaleOperation, PurchaseOperation

T_INVESTOR = Union[str, int, 'users.CoOwner']
T_OPERATIONS = Union[PurchaseOperation, SaleOperation, DividendOperation]
T_OPERATIONS_QUERYSET = Union['django.db.models.QuerySet']


class SmartInvestorSet:
    """ Набор совладельцев одной сделки """
    def __init__(self):
        self.investors: Dict[T_INVESTOR, 'SmartInvestor'] = {}

    def __getitem__(self, item: T_INVESTOR) -> 'SmartInvestor':
        try:
            return self.investors[item]
        except KeyError:
            self.investors[item] = SmartInvestor(self, item)
            return self.investors[item]

    def add_operation(self, operation: T_OPERATIONS) -> None:
        """ Добавляет одну операцию """
        # FIXME: считать дивиденды, надо относительно момента, когда была див. отсечка
        if is_proxy_instance(operation, DividendOperation):
            for investor in self.investors.values():
                # Капитал инвестора увеличивается на
                # (доход с дивидендов + налог на дивиденды) * долю акций инвестора среди других инвесторов
                investor.capital += (operation.payment + operation.dividend_tax) * investor.share_of_stock_quantity
                investor.last_dividend_share = investor.share_of_stock_quantity
        elif is_proxy_instance(operation, (PurchaseOperation, SaleOperation)):
            for share in operation.shares.all():
                investor = self[share.co_owner]
                if is_proxy_instance(operation, PurchaseOperation):
                    # Количество акций у инвестора увеличивается на
                    # количество купленных за операцию акций * долю инвестора в операции
                    investor.stock_quantity += operation.quantity*share.value
                    # Количество денег уменьшается на
                    # (Стоимость операции + комиссия за операцию) * долю в операции
                    # P.S: стоимость операции - отрицательное число для покупок, а для продаж положительное,
                    # поэтому формулы одинаковые для покупки и продажи
                    investor.capital += (operation.payment + operation.commission) * share.value
                else:
                    # Количество акций у инвестора уменьшается на
                    # количество проданых за операцию акций * долю инвестора в операции
                    investor.stock_quantity -= operation.quantity*share.value/100
                    # Количество денег у инвестора увеличивается на
                    # (Стоимость операции + комиссия за операцию) * долю в операции
                    investor.capital += (operation.payment + operation.commission) * share.value

    def add_operations(self, operations: T_OPERATIONS_QUERYSET) -> None:
        """ Добавляет список операций"""
        for operation in operations.order_by('date'):
            self.add_operation(operation)

    def total_stock_quantity(self):
        """ Общее количество акций на руках инвесторов """
        return sum(self, lambda x: x.stock_quantity)

    def __iter__(self):
        return iter(self.investors.values())


class SmartInvestor:
    """ Класс для расчета дохода инвестора за сделку """

    def __init__(self, smart_investor_set: SmartInvestorSet, investor: T_INVESTOR) -> NoReturn:
        """ Устанавливает по количество ценных бумаг и количество денег инвестора
        :param smart_investor_set: Множество инвесторов, в котором находится инвестор
        :param investor: "имя" инвестора
        """
        self.smart_investor_set = smart_investor_set
        # Инвестор может быть любого строкой или числом (как правило username или id)
        self.investor: T_INVESTOR = investor
        # Количество ценных бумаг у инвестора
        self.stock_quantity: Decimal = Decimal(0)
        # Количество денег у инвестора
        self.capital = Decimal(0)
        # Доля с последних дивидендов
        # Нужна чтобы расчитать, какую часть налога на дивиденды, инвестор должен отдать
        self.last_dividend_share = 0

    @property
    def share_of_stock_quantity(self) -> Decimal:
        """ Доля акций среди всех совладельцев """
        total_stock_quantity = self.smart_investor_set.total_stock_quantity()
        if total_stock_quantity == 0:
            return total_stock_quantity
        else:
            return self.stock_quantity/total_stock_quantity

    def __str__(self):
        return str(self.investor)
