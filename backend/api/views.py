import logging
import os

from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.db.models import Q, Subquery
from rest_framework import status
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from api.permissions import HasDefaultInvestmentAccount, IsDefaultInvestmentAccountCreator
from api.serializers import InvestmentAccountSerializer, CoOwnerSerializer, ShareSerializer
from api.exceptions import TotalCapitalGrowThanMaxCapital
from market.models import Share, Operation
from users.models import InvestmentAccount, Investor, CoOwner


logger = logging.getLogger(__name__)


# FIXME: сделать все сериализаторы и вьюхи по человечески
class InvestmentAccountView(ListCreateAPIView):
    """ Создание инвестиционных счетов и получения списка тех, которыми инвестор владеет """
    permission_classes = (IsAuthenticated, )
    serializer_class = InvestmentAccountSerializer
    queryset = InvestmentAccount.objects.all()

    def list(self, request, *args, **kwargs):
        return self.request.user.owned_investment_accounts


class DefaultInvestmentAccountView(APIView):
    """ Получение инвестиционного счета, установленного по умолчанию.
        Установка инвестиционного счета как счета по умолчанию
    """
    permission_classes = (IsAuthenticated, )

    def get(self, request, *args, **kwargs):
        return Response(
            InvestmentAccountSerializer(request.user.default_investment_account).data,
            status=status.HTTP_200_OK
        )

    def post(self, request, *args, **kwargs):
        """ Установка инвестиционного счета по умолчанию """
        try:
            investment_account = (
                InvestmentAccount.objects
                .filter(Q(creator=request.user) | Q(co_owners__investor=request.user)).distinct()
                .get(pk=request.POST.get('value'))
            )
            request.user.default_investment_account = investment_account
            request.user.save(update_fields=('default_investment_account', ))
        except ObjectDoesNotExist:
            return Response(status=status.HTTP_403_FORBIDDEN)
        else:
            return Response(status=status.HTTP_202_ACCEPTED)


class SearchForCoOwnersView(APIView):
    """ Поиск пользователя по началу username """
    permission_classes = (IsAuthenticated, HasDefaultInvestmentAccount)

    def get(self, request, *args, **kwargs):
        """ Получение инвесторов по username для добавления в совладельцы """
        username = request.GET.get('username')
        logger.info(f'{request.user} ищет пользователя "{username}"')
        names = (
            Investor.objects
            .filter(username__istartswith=username)
            .exclude(username=os.getenv('PROJECT_SUPERUSER_USERNAME'))
            .exclude(username__in=Subquery(
                self.request.user.default_investment_account.co_owners.values('investor__username')
            ))[:5].values_list('username', flat=True)
        )
        logger.info(f'{request.user} нашел {names}')
        return Response(names, status=status.HTTP_200_OK)


class CoOwnersView(APIView):
    permission_classes = (IsAuthenticated, HasDefaultInvestmentAccount)

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
    permission_classes = (IsAuthenticated, IsDefaultInvestmentAccountCreator)

    def post(self, request, *args, **kwargs):
        """ Изменение капитала и доли по умолчанию совладельцев """
        # FIXME: сделать красиво
        updated_investment_account = InvestmentAccount.objects.get(pk=request.data.get('investment_account'))

        # Сумма капиталов всех совладельцев
        total_capital = 0
        # Совладельцы, которые будут изменены
        bulk_updates = []
        for co_owner_data in request.data.get('co_owners'):
            co_owner = CoOwner.objects.get(pk=co_owner_data['pk'], investment_account=updated_investment_account)
            co_owner_serialized = CoOwnerSerializer(
                instance=co_owner, data=co_owner_data, partial=True
            )
            if co_owner_serialized.is_valid(raise_exception=True):
                capital = co_owner_serialized.validated_data['capital']
                default_share = co_owner_serialized.validated_data['default_share']
                co_owner.capital = capital
                co_owner.default_share = default_share
                total_capital += capital
                bulk_updates.append(co_owner)
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
            operations = updated_investment_account.operations.filter(type__in=(
                Operation.Types.BUY, Operation.Types.BUY_CARD, Operation.Types.TAX_DIVIDEND,
                Operation.Types.DIVIDEND
            ))
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
    permission_classes = (IsAuthenticated, IsDefaultInvestmentAccountCreator)
    serializer_class = ShareSerializer
    queryset = Share.objects.all()

    def check_object_permissions(self, request, obj):
        return request.user.default_investment_account == obj.co_owner.investment_account

    def perform_update(self, serializer):
        instance = serializer.save()
        instance.operation.deal.recalculation_income()
