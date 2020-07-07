from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q
from rest_framework import status
from rest_framework.generics import ListCreateAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ViewSet

from api.serializers import InvestmentAccountSerializer, InvestorSerializer
from users.models import InvestmentAccount, Investor


class InvestmentAccountView(ListCreateAPIView):
    permission_classes = (IsAuthenticated, )
    serializer_class = InvestmentAccountSerializer

    def get_queryset(self):
        return InvestmentAccount.objects.filter(creator=self.request.user)


class DefaultInvestmentAccountView(APIView):
    permission_classes = (IsAuthenticated, )

    def get(self, request, *args, **kwargs):
        return Response({'value': request.user.defaul_investment_account.pk}, status=200)

    def post(self, request, *args, **kwargs):
        try:
            investment_account = (
                InvestmentAccount.objects
                .filter(Q(creator=request.user) | Q(co_owners=request.user)).distinct()
                .get(pk=request.POST.get('value'))
            )
            request.user.default_investment_account = investment_account
            request.user.save(update_fields=('default_investment_account', ))
        except ObjectDoesNotExist:
            return Response(status=status.HTTP_403_FORBIDDEN)
        else:
            return Response(status=status.HTTP_202_ACCEPTED)


class SearchInvestorsView(ViewSet):
    permission_classes = (IsAuthenticated, )

    def retrieve(self, request):
        username = request.GET.get('username')
        queryset = (
            Investor.objects
            .filter(username__istartswith=username)
            .exclude(username=self.request.user.username)
            .exclude(username__in=self.request.user.default_investment_account.co_owners.all().values('username'))
        )
        return Response(InvestorSerializer(queryset, many=True).data, status=status.HTTP_200_OK)


class CoOwnersView(APIView):
    permission_classes = (IsAuthenticated, )

    def post(self, request, *args, **kwargs):
        username = request.POST.get('username')
        if username != self.request.user:
            self.request.user.default_investment_account.co_owners.add(Investor.objects.get(username=username))
        return Response(status=status.HTTP_200_OK)

    def get(self, request, *args, **kwargs):
        response = {
            'owner': InvestorSerializer(self.request.user).data,
            'co_owners': InvestorSerializer(self.request.user.default_investment_account.co_owners, many=True).data
        }
        return Response(response, status=status.HTTP_200_OK)
