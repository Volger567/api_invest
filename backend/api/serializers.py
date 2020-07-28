import logging

from django.db.models import Sum
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from market.models import Share
from tinkoff_api import TinkoffProfile
from tinkoff_api.exceptions import InvalidTokenError
from users.models import InvestmentAccount, Investor, CoOwner

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
    """ Упощенный сериализатор для инвестора.
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


class CoOwnerSerializer(serializers.ModelSerializer):
    """ Сериализатор для совладельцев """
    class Meta:
        model = CoOwner
        fields = ('id', 'investor', 'investment_account', 'capital', 'default_share', 'is_creator')

    default_share = serializers.DecimalField(max_digits=9, decimal_places=6, max_value=100, min_value=0)
    is_creator = serializers.BooleanField(read_only=True)

    def validate_default_share(self, value):
        if self.context.get('total_default_share') is not None:
            return value/self.context['total_default_share']
        elif 1 < value < 100:
            return value / 100
        return value


class ShareSerializer(serializers.ModelSerializer):
    """ Сериализатор для долей в операции """
    class Meta:
        model = Share
        fields = '__all__'

    def validate_value(self, value):
        if self.instance is not None:
            total_share = self.instance.operation.shares.aggregate(s=Sum('value'))['s']
            if total_share - self.instance.value + value > 1:
                raise ValidationError('Доля не может быть такой большой')
        return value
