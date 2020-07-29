from django.urls import path
from rest_framework.routers import DefaultRouter

from api.views import InvestmentAccountView, InvestorView, CoOwnersView, \
    CoOwnersUpdateView, ShareView, CoOwnerView

router = DefaultRouter()
router.register('investment-accounts', InvestmentAccountView, basename='investment_accounts')
router.register('investors', InvestorView, basename='investors')
router.register('co-owners2', CoOwnerView, basename='co_owners2')

urlpatterns = [
    path('co-owners/', CoOwnersView.as_view(), name='co_owners'),
    path('edit-co-owners/', CoOwnersUpdateView.as_view(), name='edit_co_owners'),
    path('share/<int:pk>/', ShareView.as_view(), name='share')
]

urlpatterns.extend(router.urls)
