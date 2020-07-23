from rest_framework.permissions import BasePermission


class HasDefaultInvestmentAccount(BasePermission):
    """ Установлен ли у пользователя аккаунт по умолчанию """
    def has_permission(self, request, view):
        return request.user.default_investment_account is not None


class IsDefaultInvestmentAccountCreator(BasePermission):
    """ Является ли пользователь владельцем аккаунта,
        который установлен у него по умолчанию
    """
    def has_permission(self, request, view):
        # noinspection PyUnresolvedReferences
        investment_account: 'InvestmentAccount' = request.user.default_investment_account
        return investment_account and request.user == investment_account.creator
