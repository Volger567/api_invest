import logging
import os

from rest_framework.filters import SearchFilter
from rest_framework.viewsets import ModelViewSet

from core.utils import PermissionsByActionMixin
from operations.models import Share
from users.models import InvestmentAccount, Investor, Capital
from .permissions import RequestUserPermissions
from .serializers import InvestmentAccountSerializer, CoOwnerSerializer, \
    ShareSerializer, SimplifiedInvestorSerializer, ExtendedInvestorSerializer, CapitalSerializer

logger = logging.getLogger(__name__)


class InvestorView(PermissionsByActionMixin, ModelViewSet):
    """ Инвестор """
    queryset = Investor.objects.filter(is_active=True)
    permissions_by_action = {
        'update': RequestUserPermissions.CanEditInvestor,
        'partial_update': RequestUserPermissions.CanEditInvestor,
        'destroy': RequestUserPermissions.CanEditInvestor
    }
    filter_backends = [SearchFilter]
    search_fields = ['^username']

    def filter_queryset(self, queryset):
        """ При получении списка пользователей c GET параметром username, пользователь, который
            сделал запрос и суперпользователь будут отсутствовать в выдаче
        """
        queryset = super().filter_queryset(queryset)
        exclude_usernames = [os.getenv('PROJECT_SUPERUSER_USERNAME')]
        if self.action == 'list' and self.request.GET.get('search') is not None:
            exclude_usernames.append(self.request.user.username)
        return queryset.exclude(
            username__in=exclude_usernames
        )

    def get_serializer(self, *args, **kwargs):
        """ Расширенный сериализатор возвращается в том случае,
            если изменяемый аккаунт, принадлежит пользователю
            который отправил запрос. Другие пользователи могут
            получить упрощенную информацию об аккаунте/аккаунтах
        """
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return ExtendedInvestorSerializer(*args, **kwargs)
        elif self.action == 'retrieve':
            has_permission = (
                RequestUserPermissions.CanEditInvestor()
                .has_object_permission(self.request, self, self.get_object())
            )
            if has_permission:
                return ExtendedInvestorSerializer(*args, **kwargs)
        return SimplifiedInvestorSerializer(*args, **kwargs)


class InvestmentAccountView(PermissionsByActionMixin, ModelViewSet):
    """ ИС """
    serializer_class = InvestmentAccountSerializer
    permissions_by_action = {
        'retrieve': RequestUserPermissions.CanRetrieveInvestmentAccount,
        'update': RequestUserPermissions.CanEditInvestmentAccount,
        'partial_update': RequestUserPermissions.CanEditInvestmentAccount,
        'destroy': RequestUserPermissions.CanEditInvestmentAccount
    }
    queryset = InvestmentAccount.objects.all()

    def filter_queryset(self, queryset):
        """ Список ИС, владельцем которых является пользователь """
        queryset = super().filter_queryset(queryset)
        return queryset.filter(creator=self.request.user)


class CoOwnerView(PermissionsByActionMixin, ModelViewSet):
    """ Совладелец """
    serializer_class = CoOwnerSerializer
    permissions_by_action = {
        'retrieve': RequestUserPermissions.CanRetrieveCoOwner,
        'list': RequestUserPermissions.HasDefaultInvestmentAccount,
        'update': RequestUserPermissions.CanEditCoOwner,
        'partial_update': RequestUserPermissions.CanEditCoOwner,
        'destroy': RequestUserPermissions.CanEditCoOwner
    }

    def filter_queryset(self, queryset):
        queryset = super().filter_queryset(queryset)
        return queryset.filter(investment_account=self.request.user.default_investment_account)


class CapitalView(PermissionsByActionMixin, ModelViewSet):
    """ Капитал """
    serializer_class = CapitalSerializer
    permissions_by_action = {
        'retrieve': RequestUserPermissions.CanRetrieveCapital,
        'list': RequestUserPermissions.HasDefaultInvestmentAccount,
        'update': RequestUserPermissions.CanEditCapital,
        'partial_update': RequestUserPermissions.CanEditCapital,
        'destroy': RequestUserPermissions.CanEditCapital
    }
    queryset = Capital.objects.all()


class ShareView(PermissionsByActionMixin, ModelViewSet):
    """ Доли в операциях """
    permissions_by_action = {
        'retrieve': RequestUserPermissions.CanRetrieveShare,
        'list': RequestUserPermissions.HasDefaultInvestmentAccount,
        'update': RequestUserPermissions.CanEditShare,
        'partial_update': RequestUserPermissions.CanEditShare,
        'destroy': RequestUserPermissions.CanEditShare
    }
    serializer_class = ShareSerializer
    queryset = Share.objects.all()

    def perform_update(self, serializer):
        """ После изменения доли в операции, перерасчитывается доход от сделки """
        instance = serializer.save()
        instance.operation.deal.recalculation_income()
