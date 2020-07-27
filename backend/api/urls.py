from django.urls import path
from rest_framework.routers import DefaultRouter

from api.views import InvestmentAccountView, InvestorView, SearchForCoOwnersView, CoOwnersView, \
    CoOwnersUpdateView, ShareView

router = DefaultRouter()
router.register('investment-accounts', InvestmentAccountView, basename='investment_account')

urlpatterns = [
    path('investors/<int:pk>/', InvestorView.as_view(), name='investor'),
    path('search-investors/', SearchForCoOwnersView.as_view(), name='search_investors'),
    path('co-owners/', CoOwnersView.as_view(), name='co_owners'),
    path('edit-co-owners/', CoOwnersUpdateView.as_view(), name='edit_co_owners'),
    path('share/<int:pk>/', ShareView.as_view(), name='share')
]

urlpatterns.extend(router.urls)
