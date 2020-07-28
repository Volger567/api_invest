from rest_framework.permissions import IsAuthenticated


class CoOwnerPermissions:
    class IsInvestmentAccountCreator(IsAuthenticated):
        """ Является ли совладелец создателем указанного у него ИС """
        def has_object_permission(self, request, view, obj):
            return request.user == obj.investment_account.creator
