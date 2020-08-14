import decimal
import logging
import os
from collections.abc import Iterable
from typing import Dict

from django.db import models
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter
from rest_framework.generics import RetrieveUpdateDestroyAPIView
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet

from operations.models import Share, PurchaseOperation, SaleOperation
from users.models import InvestmentAccount, Investor, CoOwner
from .exceptions import TotalCapitalGrowThanMaxCapital, TotalDefaultShareGrowThan100
from .permissions import RequestUserPermissions
from .serializers import InvestmentAccountSerializer, CoOwnerSerializer, \
    ShareSerializer, SimplifiedInvestorSerializer, ExtendedInvestorSerializer

logger = logging.getLogger(__name__)


class PermissionsByActionMixin:
    """ Получение permissions в зависимости от action """
    # noinspection PyUnresolvedReferences
    permissions_by_action: Dict[str, 'BasePermission'] = {}

    def get_permissions(self):
        # noinspection PyUnresolvedReferences
        permissions = self.permissions_by_action.get(self.action, self.permission_classes)
        if not isinstance(permissions, Iterable):
            permissions = [permissions]
        return [permission() for permission in permissions]


class InvestorView(PermissionsByActionMixin, ModelViewSet):
    """ Инвестор """
    queryset = Investor.objects.filter(is_active=True)
    permissions_by_action = {
        'update': RequestUserPermissions.IsSpecificInvestor,
        'partial_update': RequestUserPermissions.IsSpecificInvestor,
        'destroy': RequestUserPermissions.IsSpecificInvestor
    }
    filter_backends = [SearchFilter]
    search_fields = ['^username']

    def filter_queryset(self, queryset):
        """ При получении списка пользователей, пользователь, который
            сделал запрос и суперпользователь будут отсутствовать в выдаче
        """
        queryset = super().filter_queryset(queryset)
        return queryset.exclude(
            username__in=(os.getenv('PROJECT_SUPERUSER_USERNAME'), self.request.user.username)
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
                RequestUserPermissions.IsSpecificInvestor()
                .has_object_permission(self.request, self, self.get_object())
            )
            if has_permission:
                return ExtendedInvestorSerializer(*args, **kwargs)
        return SimplifiedInvestorSerializer(*args, **kwargs)


class InvestmentAccountView(PermissionsByActionMixin, ModelViewSet):
    """ ИС """
    serializer_class = InvestmentAccountSerializer
    permissions_by_action = {
        'retrieve': (
            RequestUserPermissions.IsCreatorOfSpecificInvestmentAccount |
            RequestUserPermissions.IsCoOwnerOfSpecificInvestmentAccount
        ),
        'update': RequestUserPermissions.IsCreatorOfSpecificInvestmentAccount,
        'partial_update': RequestUserPermissions.IsCreatorOfSpecificInvestmentAccount,
        'destroy': RequestUserPermissions.IsCreatorOfSpecificInvestmentAccount
    }

    def filter_queryset(self, queryset):
        """ Список ИС, владельцем которых является пользователь """
        queryset = super().filter_queryset(queryset)
        return queryset.filter(creator=self.request.user)


class CoOwnerView(PermissionsByActionMixin, ModelViewSet):
    """ Совладелец """
    serializer_class = CoOwnerSerializer
    permissions_by_action = {
        'retrieve': (
            RequestUserPermissions.IsInvestmentAccountCreatorOfCoOwner |
            RequestUserPermissions.IsSpecificCoOwner
        ),
        'list': RequestUserPermissions.HasDefaultInvestmentAccount,
        'update': RequestUserPermissions.IsInvestmentAccountCreatorOfCoOwner,
        'partial_update': RequestUserPermissions.IsInvestmentAccountCreatorOfCoOwner,
        'destroy': (
            RequestUserPermissions.IsInvestmentAccountCreatorOfCoOwner |
            RequestUserPermissions.IsSpecificCoOwner
        )
    }

    def filter_queryset(self, queryset):
        queryset = super().filter_queryset(queryset)
        return queryset.filter(investment_account=self.request.user.default_investment_account)

    @action(detail=False, methods=['patch'])
    def multiple_update(self, request):
        pass


# FIXME: сделать все сериализаторы и вьюхи по человечески
class CoOwnersView(APIView):
    """ Совладельцы ИС """
    permission_classes = (RequestUserPermissions.HasDefaultInvestmentAccount, )

    def post(self, request, *args, **kwargs):
        """ Добавление совладельца """
        username = request.POST.get('username')
        logger.info(f'{request.user} пытается добавить совладельца '
                    f'{username} в {request.user.default_investment_account}')
        try:
            if username != os.getenv('PROJECT_SUPERUSER_USERNAME'):
                CoOwner.objects.get_or_create(
                    investor=Investor.objects.get(username=username),
                    investment_account=self.request.user.default_investment_account
                )
            else:
                raise models.ObjectDoesNotExist
        except models.ObjectDoesNotExist:
            return Response(status=status.HTTP_400_BAD_REQUEST)
        logger.info('Совладелец успешно добавлен')
        return Response(status=status.HTTP_200_OK)

    def get(self, request, *args, **kwargs):
        """ Получение совладельцев """
        co_owners = self.request.user.default_investment_account.co_owners
        response = CoOwnerSerializer(
            co_owners.with_is_creator_annotations().order_by('-is_creator'),
            many=True
        ).data
        return Response(response, status=status.HTTP_200_OK)


class CoOwnersUpdateView(APIView):
    permission_classes = (RequestUserPermissions.IsCreatorOfDefaultInvestmentAccount, )

    def post(self, request, *args, **kwargs):
        """ Изменение капитала и доли по умолчанию совладельцев """
        # FIXME: сделать красиво
        updated_investment_account = InvestmentAccount.objects.get(pk=request.data.get('investment_account'))

        # Сумма капиталов всех совладельцев
        total_capital = 0
        # Совладельцы, которые будут изменены
        bulk_updates = []

        total_default_share = sum(map(lambda x: decimal.Decimal(x['default_share']), request.data.get('co_owners')))
        if total_default_share > 100:
            raise TotalDefaultShareGrowThan100
        for co_owner_data in request.data.get('co_owners'):
            co_owner = CoOwner.objects.get(pk=co_owner_data['pk'], investment_account=updated_investment_account)
            co_owner_serialized = CoOwnerSerializer(
                instance=co_owner, data=co_owner_data, partial=True,
                context={'total_default_share': total_default_share}
            )
            if co_owner_serialized.is_valid():
                capital = co_owner_serialized.validated_data['capital']
                default_share = co_owner_serialized.validated_data['default_share']
                co_owner.capital = capital
                co_owner.default_share = default_share
                total_capital += capital
                bulk_updates.append(co_owner)
            else:
                logger.warning(co_owner_serialized.errors)
        max_capital = updated_investment_account.prop_total_capital
        if total_capital > max_capital:
            raise TotalCapitalGrowThanMaxCapital
        else:
            CoOwner.objects.bulk_update(bulk_updates, ['capital', 'default_share'])

        # Если передан флаг change_prev_operations, то предыдущие доли операций
        # инвестиционного счета меняются в соответствие с переданными данными
        if request.data.get('change_prev_operations'):
            # FIXME: оптимизировать
            Share.objects.filter(operation__investment_account=updated_investment_account).delete()
            co_owners = updated_investment_account.co_owners.values_list('pk', 'default_share', named=True)
            bulk_creates = []
            operations = (
                updated_investment_account.operations
                .filter(proxy_instance_of=(PurchaseOperation, SaleOperation))
            )
            for operation in operations:
                for co_owner in co_owners:
                    bulk_creates.append(Share(
                        co_owner_id=co_owner.pk,
                        operation=operation,
                        value=co_owner.default_share
                    ))
            Share.objects.bulk_create(bulk_creates)
            for deal in updated_investment_account.deals.all():
                deal.recalculation_income()
        return Response(status=status.HTTP_202_ACCEPTED)


class ShareView(RetrieveUpdateDestroyAPIView):
    """ Доли совладельцев в операциях """
    permission_classes = (RequestUserPermissions.IsCreatorOfDefaultInvestmentAccount, )
    serializer_class = ShareSerializer
    queryset = Share.objects.all()

    def check_object_permissions(self, request, obj):
        return request.user.default_investment_account == obj.co_owner.investment_account

    def perform_update(self, serializer):
        instance = serializer.save()
        instance.operation.deal.recalculation_income()
