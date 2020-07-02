from django.urls import path
from api.views import InvestmentAccountView, DefaultInvestmentAccount

urlpatterns = [
    path('create-investment-account/', InvestmentAccountView.as_view(), name='create_investment_account'),
    path('default-investment-account/', DefaultInvestmentAccount.as_view(), name='default_investment_account'),
]
