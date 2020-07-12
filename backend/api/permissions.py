from rest_framework.permissions import BasePermission


class HasDefaultInvestmentAccount(BasePermission):
    def has_permission(self, request, view):
        return request.user.default_investment_account is not None
