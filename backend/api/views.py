import collections
import decimal
import logging
import os
from typing import List, Dict, Any, Set, Optional

from django.db.models import F, Sum
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.filters import SearchFilter
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from core.utils import PermissionsByActionMixin, CheckObjectPermissionMixin
from operations.models import Share
from users.models import InvestmentAccount, Investor, Capital, CoOwner
from .annotations import T_CAPITAL_ID, T_CAPITAL_FIELD_NAME, T_CAPITAL_ID_INT, T_CURRENCY_ISO_CODE, \
    TValidatedDataByCurrency
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
        'destroy': RequestUserPermissions.CanEditInvestmentAccount,
        'update_shares_by_default_share': RequestUserPermissions.CanEditDefaultInvestmentAccount
    }
    queryset = InvestmentAccount.objects.all()

    def filter_queryset(self, queryset):
        """ Список ИС, владельцем которых является пользователь """
        queryset = super().filter_queryset(queryset)
        return queryset.filter(creator=self.request.user)

    @action(detail=False, methods=['post'])
    def update_shares_by_default_share(self, request):
        """ Обновление долей в операциях ИС установленного по умолчанию
            в соответствии со значением default_share капиталов
        """
        request.user.default_investment_account.update_shares_by_default_share()
        return Response(status=status.HTTP_200_OK)


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
        """ Получение совладельцев только того ИС, который установлен по умолчанию
        """
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
        """ Обновление сразу нескольких capital одного ИС с помощью bulk_update.
            Данные приходят в формате:
            {
                '1': {'default_share': 0.5, 'value': 1000},
                '2': {'default_share': 0.1, 'value': 2000}
            }
            где ключ - id capital (капиталы могут быть разных валют,
            но обязательного должны принадлежать одному ИС),
            значение - изменяемые поля.
        """

        logger.info('Capital множественное обновление')
        # id всех изменяемых capital, нужные для дальнейшей валидации и возвращения
        # в случае успешного обновления
        instances_ids: List[T_CAPITAL_ID] = list(request.data.keys())
        instances = (
            self.get_queryset()
            .filter(pk__in=instances_ids)
            .annotate(investment_account_id=F('co_owner__investment_account_id'))
        )
        # Если просто вызывать raise ValidationError,
        # то в ошибке не будет содержаться информация об id,
        # поэтому все capital сначала проходят валидацию, а в случае ошибки,
        # добавляются в этот словарь, в котором ключ - id
        errors: Dict[T_CAPITAL_ID, Dict[T_CAPITAL_FIELD_NAME, Any]] = {}
        # Сериализаторы, которые хранят в себе экземпляры для дальнейшего bulk_update
        save_serializers: List['serializers.ModelSerializer'] = []
        # Множество полей, которые будут обновляться (для передачи в bulk_update -> fields)
        update_fields: Set[T_CAPITAL_FIELD_NAME] = set()
        # id ИС, капиталы которого будут обновляться, ИС каждого капитала будет сравниваться с этим
        # значением, если id ИС капитала отличается, будет возбужден ValidationError
        investment_account_id: Optional[T_CAPITAL_ID_INT] = None
        # Словарь, содержащий в себе информацию о сумме всех прошедших валидацию default_share и value,
        # сгруппированных по currency
        # Нужен чтобы проверить не превышает ли
        # сумма всех default_share капитолов ИС единицу (для каждой валюты сумма default_share <= 1)
        # и не превышает ли total_capital_value максимальный допустимый капитал (для каждрй валюты)
        validated_data: collections.defaultdict[T_CURRENCY_ISO_CODE, TValidatedDataByCurrency] = \
            collections.defaultdict(TValidatedDataByCurrency)

        for instance in instances:
            self.check_object_permission(request, instance, RequestUserPermissions.CanEditCapital)
            if instance.investment_account_id != investment_account_id and investment_account_id is not None:
                raise ValidationError('Все capital должны принадлежать одному ИС')
            if investment_account_id is None:
                investment_account_id = instance.investment_account_id
            instance_data = request.data[str(instance.pk)]
            # Добавляем в множество полей для bulk_update все изменяемые поля текущего instance
            update_fields |= set(instance_data.keys())
            # Аргумент bulk_update позволит после вызова метода .save()
            # не вызывать .save() у instance сериализатора, а только изменить поля и вернуть instance
            # !нельзя изменять m2m поля
            serializer = self.get_serializer(instance=instance, data=instance_data, bulk_update=True, partial=True)
            if serializer.is_valid():
                if instance.currency_id not in validated_data:
                    validated_data[instance.currency_id] = TValidatedDataByCurrency(decimal.Decimal)
                save_serializers.append(serializer)
                # Если поле не изменялось, то его не будет в validated_data сериализатора.
                # Поэтому берем значение, которое у instance установлено
                validated_data[instance.currency_id]['total_default_share'] += \
                    serializer.validated_data.get('default_share', instance.default_share)
                validated_data[instance.currency_id]['total_value'] += \
                    serializer.validated_data.get('value', instance.value)
            else:
                errors[instance.pk] = serializer.errors
        if errors:
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)
        else:
            # TODO: перенести в сериализатор/бизнес-логику
            capital_info = InvestmentAccount.objects.get(pk=investment_account_id).capital_info()
            # Суммы всех default_share и value остальных капиталов ИС
            remaining_capital = (
                Capital.objects
                .filter(co_owner__investment_account_id=investment_account_id, currency_id__in=validated_data.keys())
                .exclude(pk__in=instances_ids)
                .values('currency')
                .order_by()
                .annotate(total_default_share=Sum('default_share'), total_value=Sum('value'))
            )
            # Пользователь вводить default_share в виде числа с плавающей запятой.
            # Ему для ввода доступно максимум 2 знака после запятой.
            # Если, например, владельцев 3, то на каждого будет приходится по 0.33
            # Таким образом пропадает 0.01, в этом словаре будет хранится КФ, на который
            # надо домножить default_share каждого совладельца, чтобы получилась единица
            update_default_share: Dict[T_CURRENCY_ISO_CODE, decimal.Decimal] = {}
            if not remaining_capital.exists():
                remaining_capital = []
                for currency in validated_data:
                    remaining_capital.append({
                        'currency': currency,
                        'total_default_share': decimal.Decimal('0'),
                        'total_value': decimal.Decimal('0')
                    })
            logger.info(f'Общая валидация: {validated_data}')
            for remaining_capital_item in remaining_capital:
                currency = remaining_capital_item['currency']
                logger.info(f'Валюта: {currency}')
                info_total_capital = capital_info[currency]['total_capital']
                logger.info(f'Доступный капитал: {info_total_capital}')
                remaining_total_default_share = remaining_capital_item['total_default_share']
                logger.info(f'Сумма остальных долей: {remaining_total_default_share}')
                remaining_total_capital = remaining_capital_item['total_value']
                logger.info(f'Сумма остальных капиталов: {remaining_total_capital}')
                validated_total_default_share = validated_data[currency]['total_default_share']
                logger.info(f'Сумма долей, прошедших валидацию: {validated_total_default_share}')
                validated_total_capital = validated_data[currency]['total_value']
                logger.info(f'Сумма капиталов, прошедших валидацию: {validated_total_capital}')
                total_default_share = remaining_total_default_share + validated_total_default_share
                logger.info(f'Сумма всех долей валюты: {total_default_share}')
                total_capital = remaining_total_capital + validated_total_capital
                logger.info(f'Сумма всех капиталов валюты: {total_capital}')

                if not (0 < total_default_share <= 1):
                    raise ValidationError(f'Сумма всех долей валюты {currency} должна быть больше 0 и не больше 1')
                elif total_default_share < 1:
                    update_default_share[currency] = 1 / total_default_share
                if total_capital > capital_info[currency]['total_capital']:
                    raise ValidationError(f'Сумма всех капиталов валюты {currency} > {info_total_capital}')

            bulk_update_objs = [serializer.save() for serializer in save_serializers]
            Capital.objects.bulk_update(bulk_update_objs, fields=update_fields)
            logger.info(update_default_share)
            for key, value in update_default_share.items():
                (
                    Capital.objects
                    .filter(co_owner__investment_account_id=investment_account_id, currency_id=key)
                    .update(default_share=F('default_share')*value)
                )
            return Response({'ids': instances_ids}, status=200)


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
