from rest_framework.permissions import IsAuthenticated, BasePermission


class RequestUserPermissions:
    """ Разрешения для пользователя, который выполняет запрос """

    class CanEditInvestor(IsAuthenticated):
        """ Может ли пользователь редактировать информацию об инвесторе """
        message = 'Вы не можете изменять информацию об этом пользователе'

        def has_object_permission(self, request, view, obj: 'Investor'):
            return request.user == obj

    class HasDefaultInvestmentAccount(BasePermission):
        """ Установлен ли у пользователя ИС по умолчанию """
        message = 'У вас не установлен ИС по умолчанию'

        def has_permission(self, request, view):
            return (
                IsAuthenticated().has_permission(request, view) and
                request.user.default_investment_account is not None
            )

    class CanEditDefaultInvestmentAccount(BasePermission):
        """ Может ли пользователь редактировать информацию об ИС,
            который установлен у него по умолчанию
        """
        message = 'Вы не можете редактировать информацию об ИС, который установлен у вас по умолчанию'

        def has_permission(self, request, view):
            if IsAuthenticated().has_permission(request, view):
                investment_account: 'InvestmentAccount' = request.user.default_investment_account
                return investment_account and request.user == investment_account.creator
            return False

    class CanEditInvestmentAccount(IsAuthenticated):
        """ Является ли пользователь владельцем конкретного ИС """
        message = 'Вы не являетесь владельцем этого ИС'

        def has_object_permission(self, request, view, obj: 'InvestmentAccount'):
            return request.user == obj.creator

    class CanRetrieveInvestmentAccount(IsAuthenticated):
        """ Является ли пользователь совладельцем конкретного ИС """
        message = 'Вы не являетесь совладельцем этого ИС'

        def has_object_permission(self, request, view, obj: 'InvestmentAccount'):
            return request.user in obj.investors or request.user == obj.creator

    class CanRetrieveCoOwner(IsAuthenticated):
        """ Может ли пользователь получить информацию о совладельце/совладельцах """
        message = 'Вы не можете получить информацию об этом'

        def has_object_permission(self, request, view, obj: 'CoOwner'):
            return request.user in (obj.investor, obj.investment_account.creator)

    class CanEditCoOwner(IsAuthenticated):
        """ Может ли пользовать редактировать информацию о совладельце """
        message = 'Вы не можете изменять информацию об этом совладельце'

        def has_object_permission(self, request, view, obj: 'CoOwner'):
            return request.user == obj.investment_account.creator

    class CanRetrieveCapital(IsAuthenticated):
        """ Может ли пользователь получать информацию о капитале """
        message = 'Вы не можете получить информацию об этом'

        def has_object_permission(self, request, view, obj: 'Capital'):
            return request.user in obj.co_owner.investment_account.investors

    class CanEditCapital(IsAuthenticated):
        """ Может ли пользователь редактировать информацию о капитале """
        message = 'Вы не можете изменять информацию об этом капитале'

        def has_object_permission(self, request, view, obj: 'Capital'):
            return request.user == obj.co_owner.investment_account.creator

    class CanRetrieveShare(IsAuthenticated):
        """ Может ли пользователь получить информацию о доле в операции """
        message = 'Вы не можете получить информацию об этом'

        def has_object_permission(self, request, view, obj: 'Share'):
            return request.user in obj.operation.investment_account.investors

    class CanEditShare(IsAuthenticated):
        """ Может ли пользователь редактировать информацию о доле в операции """
        message = 'Вы не можете изменять информацию об этой доле'

        def has_object_permission(self, request, view, obj):
            return request.user == obj.operation.investment_account.creator
