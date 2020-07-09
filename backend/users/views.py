from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView as SuperLoginView, LogoutView as SuperLogoutView
from django.db.models import Sum, F
from django.db.models.functions import Coalesce
from django.urls import reverse
from django.views.generic import FormView, TemplateView

from market.models import Operation
from market.views import UpdateInvestmentAccount
from users.forms import SignupForm, LoginForm
from users.models import InvestmentAccount


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
        context['owned_investment_accounts'] = InvestmentAccount.objects.filter(creator=self.request.user)
        context['co_owned_investment_accounts'] = \
            InvestmentAccount.objects.filter(co_owners__investor=self.request.user)
        return context


class InvestmentAccountSettings(UpdateInvestmentAccount, TemplateView):
    template_name = 'investment_account_settings.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # FIXME: сделать для всех валют
        context['total_pay_in'] = (
            self.request.user.default_investment_account.operation_set
            .filter(type__in=(Operation.Types.PAY_IN, Operation.Types.PAY_OUT, Operation.Types.SERVICE_COMMISSION))
            .aggregate(s=Sum('payment'))['s']
        )
        context['creator_capital'] = \
            context['total_pay_in'] - self.request.user.default_investment_account.co_owners.aggregate(
                s=Coalesce(Sum('capital'), 0))['s']

        context['total_income'] = (
            (context['currency_assets'].get(currency__iso_code='RUB').value - context['total_pay_in'])
        )
        return context
