from rest_framework.permissions import IsAuthenticated


# XXX: рефактор нужен, тяжело понять какие права для чего
class InvestorPermissions:
    class IsSelf(IsAuthenticated):
        """ Является ли пользователь конкретным пользователем """
        def has_object_permission(self, request, view, obj):
            return request.user == obj

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
            return obj in request.user.owned_investment_accounts.all()

    class IsInvestmentAccountCoOwner(IsAuthenticated):
        """ Является ли пользователь совладельцем конкретного ИС """
        def has_object_permission(self, request, view, obj):
            return request.user.co_owned_investment_accounts.filter(investment_account=obj).exists()

    class IsInvestorCoOwner(IsAuthenticated):
        """ Является ли инвестор конкретным совладельцем """
        def has_object_permission(self, request, view, obj):
            return request.user == obj.investor
