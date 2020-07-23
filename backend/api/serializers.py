from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from market.models import Share
from tinkoff_api import TinkoffProfile
from tinkoff_api.exceptions import InvalidTokenError
from users.models import InvestmentAccount, Investor, CoOwner


class InvestmentAccountSerializer(serializers.ModelSerializer):
    """ Сериализатор для инвестиционного счета """
    class Meta:
        model = InvestmentAccount
        fields = ['id', 'name', 'creator', 'token', 'broker_account_id']

    creator = serializers.PrimaryKeyRelatedField(read_only=True)
    broker_account_id = serializers.ReadOnlyField()

    def get_field_names(self, *args, **kwargs):
        """ Пользователь не должен получать поле token """
        fields = super().get_field_names(*args, **kwargs)
        if self.instance is not None and self.data is None:
            fields.remove('token')
        return fields

    def validate_token(self, value: str) -> str:
        """ Валидация токена. Токен должен быть валидным +
            давать доступ к реальному портфелю пользователя (а не к песочнице)
        :param value: токен
        :return: либо токен, либо raise ValidationError
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


class InvestorSerializer(serializers.ModelSerializer):
    """ Сериализатор для инвесторов """
    class Meta:
        model = Investor
        fields = ('id', 'username')


class CoOwnerSerializer(serializers.ModelSerializer):
    """ Сериализатор для совладельцев """
    class Meta:
        model = CoOwner
        fields = ('id', 'investor', 'investment_account', 'capital', 'default_share', 'is_creator')

    is_creator = serializers.BooleanField(read_only=True)


class ShareSerializer(serializers.ModelSerializer):
    """ Сериализатор для долей в операции """
    class Meta:
        model = Share
        fields = '__all__'
