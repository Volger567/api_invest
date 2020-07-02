from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q
from rest_framework import status
from rest_framework.generics import ListCreateAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from api.serializers import InvestmentAccountSerializer
from users.models import InvestmentAccount


class InvestmentAccountView(ListCreateAPIView):
    permission_classes = (IsAuthenticated, )
    serializer_class = InvestmentAccountSerializer

    def get_queryset(self):
        return InvestmentAccount.objects.filter(creator=self.request.user)


class DefaultInvestmentAccount(APIView):
    permission_classes = (IsAuthenticated, )

    def get(self, request, *args, **kwargs):
        return Response({'value': request.user.defaul_investment_account.pk}, status=200)

    def post(self, request, *args, **kwargs):
        try:
            investment_account = InvestmentAccount.objects.get(
                Q(pk=request.data['value']) & (Q(creator=request.user) | Q(co_owners=request.user))
            )
            request.user.default_investment_account = investment_account
            request.user.save(update_fields=('default_investment_account', ))
        except ObjectDoesNotExist:
            return Response(status=status.HTTP_403_FORBIDDEN)
        else:
            return Response(status=status.HTTP_202_ACCEPTED)

