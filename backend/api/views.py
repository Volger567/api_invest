from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q
from rest_framework import status
from rest_framework.generics import ListCreateAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ViewSet

from api.serializers import InvestmentAccountSerializer, InvestorSerializer, CoOwnerSerializer
from users.models import InvestmentAccount, Investor, CoOwner


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


class SearchInvestorsView(ViewSet):
    permission_classes = (IsAuthenticated, )

    def retrieve(self, request):
        """ Получение инвесторов по username для добавления в совладельцы """
        username = request.GET.get('username')
        queryset = (
            Investor.objects
            .filter(username__istartswith=username)
            .exclude(username=self.request.user.username)
            .exclude(username__in=self.request.user.default_investment_account.co_owners
                     .all().values('investor__username'))
        )
        return Response(InvestorSerializer(queryset, many=True).data, status=status.HTTP_200_OK)


class CoOwnersView(APIView):
    permission_classes = (IsAuthenticated, )

    def post(self, request, *args, **kwargs):
        """ Добавление совладельца """
        username = request.POST.get('username')
        if username != self.request.user and not CoOwner.objects.filter(investor__username=username).exists():
            CoOwner.objects.create(
                investor=Investor.objects.get(username=username),
                investment_account=self.request.user.default_investment_account
            )
        return Response(status=status.HTTP_200_OK)

    def get(self, request, *args, **kwargs):
        """ Получение совладельцев """
        response = CoOwnerSerializer(
            self.request.user.default_investment_account.co_owners.with_is_creator_annotations().order_by('-is_creator')
        ).data
        return Response(response, status=status.HTTP_200_OK)
