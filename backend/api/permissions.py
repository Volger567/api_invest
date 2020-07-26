from rest_framework.permissions import BasePermission, IsAuthenticated


class HasDefaultInvestmentAccount(IsAuthenticated):
    """ Установлен ли у пользователя ИС по умолчанию """
    def has_permission(self, request, view):
        return request.user.default_investment_account is not None


class IsDefaultInvestmentAccountCreator(IsAuthenticated):
    """ Является ли пользователь владельцем ИС,
        который установлен у него по умолчанию
    """
    def has_permission(self, request, view):
        # noinspection PyUnresolvedReferences
        investment_account: 'InvestmentAccount' = request.user.default_investment_account
        return investment_account and request.user == investment_account.creator


class IsInvestmentAccountCreator(IsAuthenticated):
    """ Является ли пользователь владельцем конкретного ИС """
    def has_object_permission(self, request, view, obj):
        return obj in request.user.owned_investor_accounts.all()


class CanRetrieveInvestmentAccount(BasePermission):
    """ Может ли пользователь получить конкретный ИС """
    def has_object_permission(self, request, view, obj):
        """ Пользователь может получить только тот ИС,
            совладельцем или владельцем которого он является
        """
        return (
            obj in request.user.owned_investment_accounts.all() or
            request.user.co_owned_investor_accounts.filter(investment_account=obj).exists()
        )
