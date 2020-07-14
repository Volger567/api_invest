from rest_framework.permissions import BasePermission


class HasDefaultInvestmentAccount(BasePermission):
    def has_permission(self, request, view):
        return request.user.default_investment_account is not None


class IsDefaultInvestmentAccountCreator(BasePermission):
    def has_permission(self, request, view):
        investment_account = request.user.default_investment_account
        return investment_account and request.user == investment_account.creator
