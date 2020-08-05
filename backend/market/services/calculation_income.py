from decimal import Decimal
from typing import Union, Dict, NoReturn

# Как правило, это либо username, либо id, либо CoOwner
from operations.models import Operation

T_INVESTOR = Union[str, int, 'users.CoOwner']


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

    def add_operation(self, operation: 'Operation') -> NoReturn:
        """ Добавляет одну операцию """
        for share in operation.shares.all():
            investor = self[share.co_owner]
            if operation.type in (Operation.Types.BUY, Operation.Types.BUY_CARD):
                # Количество акций у инвестора увеличивается на
                # количество купленных за операцию акций * долю инвестора в операции
                investor.stock_quantity += operation.quantity*share.value
                # Количество денег уменьшается на
                # (Стоимость операции + комиссия за операцию) * долю в операции
                # P.S: стоимость операции - отрицательное число для покупок, а для продаж положительное,
                # поэтому формулы одинаковые для покупки и продажи
                investor.capital += (operation.payment + operation.commission) * share.value
            elif operation.type == Operation.Types.SELL:
                # Количество акций у инвестора уменьшается на
                # количество проданых за операцию акций * долю инвестора в операции
                investor.stock_quantity -= operation.quantity*share.value/100
                # Количество денег у инвестора увеличивается на
                # (Стоимость операции + комиссия за операцию) * долю в операции
                investor.capital += (operation.payment + operation.commission) * share.value
            # FIXME: считать дивиденды, надо относительно момента, когда была див. отсечка
            elif operation.type == Operation.Types.DIVIDEND:
                # Капитал инвестора увеличивается на
                # доход с дивидендов * долю акций инвестора среди других инвесторов
                investor.capital += operation.payment * investor.stock_quantity_share
                investor.last_dividend_share = investor.stock_quantity_share
            elif operation.type == Operation.Types.TAX_DIVIDEND:
                # Капитал инвестора уменьшается на долю от налога
                investor.capital += operation.payment * investor.last_dividend_share
                investor.last_dividend_share = 0

    # noinspection PyUnresolvedReferences
    def add_operations(self, operations: 'django.db.models.query.QuerySet[market.Operation]') -> NoReturn:
        """ Добавляет список операций"""
        for operation in operations:
            print(operation)
            self.add_operation(operation)

    def total_stock_quantity(self):
        """ Количество акций на руках инвесторов """
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
    def stock_quantity_share(self) -> Decimal:
        """ Доля акций среди всех совладельцев """
        total_stock_quantity = self.smart_investor_set.total_stock_quantity()
        if total_stock_quantity == 0:
            return total_stock_quantity
        else:
            return self.stock_quantity/total_stock_quantity

    def __str__(self):
        return str(self.investor)
