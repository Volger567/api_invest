import logging
import os

from django.db.models import Sum
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.serializers import raise_errors_on_nested_writes
from rest_framework.utils import model_meta

from core.utils import ExcludeFieldsMixin
from operations.models import Share
from tinkoff_api import TinkoffProfile
from tinkoff_api.exceptions import InvalidTokenError
from users.models import InvestmentAccount, Investor, CoOwner, Capital

logger = logging.getLogger(__name__)


class ExtendedInvestorSerializer(serializers.ModelSerializer):
    """ Расширенный сериализатор для инвестора """
    class Meta:
        model = Investor
        fields = ('id', 'username', 'default_investment_account')

    def validate_default_investment_account(self, investment_account):
        """ Валидация ИС по умолчанию.
            Пользователь может установить ИС по умолчанию
            только если является его владельцем или находится
            в совладельцах этого ИС
        """
        if self.partial:
            is_creator = investment_account in self.instance.owned_investment_accounts.all()
            is_co_owner = self.instance.co_owned_investment_accounts.filter(
                investment_account=investment_account).exists()
            if is_creator or is_co_owner:
                return investment_account
            raise ValidationError('Вы не являетесь (со)владельцем счета')
        else:
            raise ValidationError('Изменить default_investment_account можно только PATCH запросом')


class SimplifiedInvestorSerializer(serializers.ModelSerializer):
    """ Упрощенный сериализатор для инвестора.
        При получении информации другими инвесторами,
        используется он
    """
    class Meta:
        model = Investor
        fields = ('id', 'username')


class InvestmentAccountSerializer(serializers.ModelSerializer):
    """ Сериализатор для ИС """
    class Meta:
        model = InvestmentAccount
        fields = ['id', 'name', 'creator', 'token', 'broker_account_id']

    creator = serializers.PrimaryKeyRelatedField(read_only=True)
    broker_account_id = serializers.ReadOnlyField()

    def get_field_names(self, *args, **kwargs):
        """ Пользователь не должен получать поле token """
        fields = super().get_field_names(*args, **kwargs)
        if self.instance is not None and not hasattr(self, 'initial_data'):
            fields.remove('token')
        return fields

    def validate_token(self, value: str) -> str:
        """ Валидация токена. Токен должен быть валидным +
            давать доступ к реальному портфелю пользователя (а не к песочнице)
        """
        try:
            with TinkoffProfile(value) as tp:
                if tp.is_production_token_valid:
                    self.context['broker_account_id']: str = tp.broker_account_id
                    return value
                raise ValidationError('Вместо токена от торговой площадки указан токен от песочницы')
        except InvalidTokenError:
            raise ValidationError('Неверный токен')

    def create(self, validated_data):
        validated_data['creator']: 'Investor' = self.context['request'].user
        validated_data['broker_account_id']: str = self.context['broker_account_id']
        return super().create(validated_data)


class CapitalSerializer(ExcludeFieldsMixin, serializers.ModelSerializer):
    """ Сериализатор капитала совладельца """
    class Meta:
        model = Capital
        fields = ('id', 'co_owner', 'currency', 'value', 'default_share')

    default_share = serializers.DecimalField(max_digits=7, decimal_places=6, min_value=0, max_value=1)

    def __init__(self, *args, **kwargs):
        self.is_bulk_update = kwargs.pop('bulk_update', False)
        super().__init__(*args, **kwargs)

    def validate(self, attrs):
        if self.is_bulk_update:
            info = model_meta.get_field_info(self.instance)
            for attr, _ in attrs.items():
                if attr in info.relations and info.relations[attr].to_many:
                    raise ValidationError({attr: 'Нельзя изменять поля m2m через bulk_update'})
        return super().validate(attrs)

    def update(self, instance, validated_data):
        if self.is_bulk_update:
            raise_errors_on_nested_writes('update', self, validated_data)
            info = model_meta.get_field_info(instance)
            for attr, value in validated_data.items():
                if attr in info.relations and info.relations[attr].to_many:
                    raise ValidationError('Нельзя изменять поля m2m через bulk_update')
                else:
                    setattr(instance, attr, value)
            return instance
        else:
            return super().update(instance, validated_data)


class CoOwnerSerializer(serializers.ModelSerializer):
    """ Сериализатор для совладельцев """
    class Meta:
        model = CoOwner
        fields = ('id', 'investor', 'investment_account', 'capital', 'is_creator')

    capital = serializers.SerializerMethodField(read_only=True)
    investor = serializers.PrimaryKeyRelatedField(
        queryset=Investor.objects.exclude(username=os.getenv('PROJECT_SUPERUSER_USERNAME')),
    )
    is_creator = serializers.BooleanField(read_only=True)

    def get_capital(self, obj):
        return CapitalSerializer(instance=obj.capital, many=True, exclude_fields=('co_owner', )).data

    def validate_investor(self, investor):
        """ Совладельцем можно назначить любого инвестора, кроме себя"""
        if self.context['request'].user == investor:
            raise ValidationError('Вы не можете назначить себя совладельцем, вы уже им являетесь')
        return investor

    def validate_investment_account(self, investment_account):
        """ Добавление совладельцов возможно только для тех ИС,
            для которых request.user является владельцем
        """
        if self.context['request'].user == investment_account.creator:
            return investment_account
        else:
            raise ValidationError('Вы не можете добавить совладельца к ИС, владельцем которого не являетесь')


class ShareSerializer(serializers.ModelSerializer):
    """ Сериализатор для долей в операции """
    class Meta:
        model = Share
        fields = '__all__'

    def validate_value(self, value):
        """ Сумма всех долей операции должна быть не больше 1 """
        if self.instance is not None:
            total_share = self.instance.operation.shares.aggregate(s=Sum('value'))['s']
            if total_share - self.instance.value + value > 1:
                raise ValidationError('Доля не может быть такой большой')
        return value
