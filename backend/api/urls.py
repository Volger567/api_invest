from rest_framework.routers import DefaultRouter

from api.views import InvestmentAccountView, InvestorView, ShareView, CoOwnerView, CapitalView

router = DefaultRouter()
router.register('investors', InvestorView, basename='investors')
router.register('investment-accounts', InvestmentAccountView, basename='investment_accounts')
router.register('co-owners', CoOwnerView, basename='co_owners')
router.register('capital', CapitalView, basename='capital')
router.register('shares', ShareView, basename='shares')

urlpatterns = router.urls
