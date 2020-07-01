from django.urls import path
from api.views import InvestmentAccountView

urlpatterns = [
    path('create-investment-account/', InvestmentAccountView.as_view(), name='create_investment-account'),
]
