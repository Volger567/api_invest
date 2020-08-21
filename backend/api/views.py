import logging
import os

from django.db.models import F
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from core.utils import PermissionsByActionMixin, CheckObjectPermissionMixin
from operations.models import Share
from users.models import InvestmentAccount, Investor, Capital, CoOwner
from .permissions import RequestUserPermissions
from .serializers import InvestmentAccountSerializer, CoOwnerSerializer, \
    ShareSerializer, SimplifiedInvestorSerializer, ExtendedInvestorSerializer, CapitalSerializer

logger = logging.getLogger(__name__)


class InvestorView(PermissionsByActionMixin, ModelViewSet):
    """ Инвестор """
    permissions_by_action = {
        'update': RequestUserPermissions.CanEditInvestor,
        'partial_update': RequestUserPermissions.CanEditInvestor,
        'destroy': RequestUserPermissions.CanEditInvestor
    }
    queryset = Investor.objects.filter(is_active=True)
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
    queryset = CoOwner.objects.all()

    def filter_queryset(self, queryset):
        queryset = super().filter_queryset(queryset)
        return queryset.filter(investment_account=self.request.user.default_investment_account)


class CapitalView(PermissionsByActionMixin, CheckObjectPermissionMixin, ModelViewSet):
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

    @action(detail=False, methods=['patch'])
    def multiple_updates(self, request):
        instances = (
            self.get_queryset()
            .filter(pk__in=request.data)
            .annotate(investment_account_id=F('co_owner__investment_account_id'))
        )
        errors = {}
        save_serializers = []
        update_fields = set()
        for instance in instances:
            self.check_object_permission(request, instance, RequestUserPermissions.CanEditCapital)
            instance_data = request.data[str(instance.pk)]
            update_fields |= set(instance_data)
            serializer = self.get_serializer(instance=instance, data=instance_data, bulk_update=True, partial=True)
            if serializer.is_valid():
                save_serializers.append(serializer)
            else:
                errors[instance.pk] = serializer.errors
        if errors:
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)
        else:
            bulk_update_objs = [serializer.save() for serializer in save_serializers]
            Capital.objects.bulk_update(bulk_update_objs, fields=update_fields)
            return Response({'ids': list(request.data)}, status=200)


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
