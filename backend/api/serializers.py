from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from tinkoff_api import TinkoffProfile
from tinkoff_api.exceptions import InvalidTokenError
from users.models import InvestmentAccount, Investor, CoOwner


class InvestmentAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvestmentAccount
        fields = ('id', 'name', 'creator', 'token', 'broker_account_id')

    creator = serializers.PrimaryKeyRelatedField(read_only=True)
    broker_account_id = serializers.ReadOnlyField()

    def validate_token(self, value):
        try:
            with TinkoffProfile(value) as tp:
                if tp.is_production_token_valid:
                    self.context['broker_account_id'] = tp.broker_account_id
                    return value
                raise ValidationError('Вместо токена от торговой площадки указан токен от песочницы')
        except InvalidTokenError:
            raise ValidationError('Неверный токен')

    def create(self, validated_data):
        validated_data['creator'] = self.context['request'].user
        validated_data['broker_account_id'] = self.context['broker_account_id']
        return super().create(validated_data)


class InvestorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Investor
        fields = ('id', 'username')


class CoOwnerSerializer(serializers.ModelSerializer):
    class Meta:
        model = CoOwner
        fields = ('id', 'investor', 'investment_account', 'capital', 'default_share', 'is_creator')

