from rest_framework.generics import ListCreateAPIView
from rest_framework.permissions import IsAuthenticated

from api.serializers import InvestmentAccountSerializer
from users.models import InvestmentAccount


class InvestmentAccountView(ListCreateAPIView):
    permission_classes = (IsAuthenticated, )
    serializer_class = InvestmentAccountSerializer

    def get_queryset(self):
        return InvestmentAccount.objects.filter(owner=self.request.user)
