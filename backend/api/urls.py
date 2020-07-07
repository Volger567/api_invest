from django.urls import path
from api.views import InvestmentAccountView, DefaultInvestmentAccountView, SearchInvestorsView, CoOwnersView

urlpatterns = [
    path('create-investment-account/', InvestmentAccountView.as_view(), name='create_investment_account'),
    path('default-investment-account/', DefaultInvestmentAccountView.as_view(), name='default_investment_account'),
    path('search-investors/', SearchInvestorsView.as_view({'get': 'retrieve'}), name='search_investors'),
    path('co-owners/', CoOwnersView.as_view(), name='co_owners')
]
