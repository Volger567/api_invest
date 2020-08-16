from rest_framework.permissions import IsAuthenticated


class RequestUserPermissions:
    """ Разрешения для пользователя, который выполняет запрос """
    # noinspection PyUnresolvedReferences
    class IsSpecificInvestor(IsAuthenticated):
        """ Является ли пользователь конкретным инвестором """
        def has_object_permission(self, request, view, obj: 'Investor'):
            return request.user == obj

    class HasDefaultInvestmentAccount(IsAuthenticated):
        """ Установлен ли у пользователя ИС по умолчанию """
        def has_permission(self, request, view):
            return super().has_permission(request, view) and request.user.default_investment_account is not None

    # noinspection PyUnresolvedReferences
    class IsCreatorOfDefaultInvestmentAccount(IsAuthenticated):
        """ Является ли пользователь владельцем ИС,
            который установлен у него по умолчанию
        """
        def has_permission(self, request, view):
            if super().has_permission(request, view):
                investment_account: 'InvestmentAccount' = request.user.default_investment_account
                return investment_account and request.user == investment_account.creator

    # noinspection PyUnresolvedReferences
    class IsCreatorOfSpecificInvestmentAccount(IsAuthenticated):
        """ Является ли пользователь владельцем конкретного ИС """
        def has_object_permission(self, request, view, obj: 'InvestmentAccount'):
            return request.user == obj.creator

    # noinspection PyUnresolvedReferences
    class IsCoOwnerOfSpecificInvestmentAccount(IsAuthenticated):
        """ Является ли пользователь совладельцем конкретного ИС """
        def has_object_permission(self, request, view, obj: 'InvestmentAccount'):
            return request.user.co_owned_investment_accounts.filter(investment_account=obj).exists()

    # noinspection PyUnresolvedReferences
    class IsSpecificCoOwner(IsAuthenticated):
        """ Является ли пользователь конкретным совладельцем """
        def has_object_permission(self, request, view, obj: 'CoOwner'):
            return request.user == obj.investor

    # noinspection PyUnresolvedReferences
    class IsInvestmentAccountCreatorOfCoOwner(IsAuthenticated):
        """ Является ли пользователь создателем ИС конкретного совладельца """
        def has_object_permission(self, request, view, obj: 'CoOwner'):
            return request.user == obj.investment_account.creator
