from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView as SuperLoginView, LogoutView as SuperLogoutView
from django.db.models import Q, Value, When, Case, BooleanField
from django.urls import reverse
from django.views.generic import FormView, TemplateView

from market.views import UpdateInvestmentAccount
from users.forms import SignupForm, LoginForm
from users.models import InvestmentAccount, Investor


class SignupView(FormView):
    template_name = 'signup.html'
    form_class = SignupForm

    def get_success_url(self):
        return reverse('index')

    def form_valid(self, form):
        user = form.save(commit=False)
        # user.generate_email_token(commit=False)
        user.save()
        return super().form_valid(form)


class LoginView(SuperLoginView):
    template_name = 'login.html'
    authentication_form = LoginForm


class LogoutView(SuperLogoutView):
    next_page = 'login'


class InvestmentAccountsView(LoginRequiredMixin, UpdateInvestmentAccount, TemplateView):
    template_name = 'investment_accounts.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['owned_investment_accounts'] = (
            InvestmentAccount.objects
            .filter(creator=self.request.user)
            .prefetch_related('co_owners').distinct()
        )
        context['co_owned_investment_accounts'] = (
            InvestmentAccount.objects
            .filter(co_owners=self.request.user)
            .exclude(creator=self.request.user)
            .prefetch_related('co_owners').distinct()
        )
        return context


class InvestmentAccountSettings(TemplateView):
    template_name = 'investment_account_settings.html'
