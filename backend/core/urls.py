"""core URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include

from core import settings
from market.views import OperationsView, DealsView
from users.views import SignupView, LoginView, LogoutView, InvestmentAccountSettings, InvestmentAccountsView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('signup/', SignupView.as_view(), name='signup'),
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),

    path('api/', include('api.urls'), name='api'),
    path('operations/', OperationsView.as_view(), name='operations'),
    path('deals/', DealsView.as_view(), name='deals'),
    path('investment-accounts/', InvestmentAccountsView.as_view(), name='investment_accounts'),
    path('investment-account-settings/', InvestmentAccountSettings.as_view(), name='investment_account_settings'),
    path('', OperationsView.as_view(), name='index'),
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
