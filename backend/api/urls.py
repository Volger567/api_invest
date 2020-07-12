from django.urls import path
from api.views import InvestmentAccountView, DefaultInvestmentAccountView, SearchForCoOwnersView, CoOwnersView, \
    EditCoOwnersView

urlpatterns = [
    path('create-investment-account/', InvestmentAccountView.as_view(), name='create_investment_account'),
    path('default-investment-account/', DefaultInvestmentAccountView.as_view(), name='default_investment_account'),
    path('search-investors/', SearchForCoOwnersView.as_view(), name='search_investors'),
    path('co-owners/', CoOwnersView.as_view(), name='co_owners'),
    path('edit-co-owners/', EditCoOwnersView.as_view(), name='edit_co_owners')
]
