from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView as SuperLoginView, LogoutView as SuperLogoutView
from django.db.models import Sum, F, Q
from django.urls import reverse
from django.views.generic import FormView, TemplateView, ListView

from market.views import UpdateInvestmentAccountMixin
from users.forms import SignupForm, LoginForm
from users.models import InvestmentAccount, CoOwner


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


class InvestmentAccountsView(LoginRequiredMixin, UpdateInvestmentAccountMixin, TemplateView):
    template_name = 'investment_accounts.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['owned_investment_accounts'] = (
            InvestmentAccount.objects
            .filter(creator=self.request.user)
            .order_by('pk')
        )
        context['co_owned_investment_accounts'] = (
            InvestmentAccount.objects
            .filter(co_owners__investor=self.request.user)
            .exclude(creator=self.request.user)
        )
        return context


class InvestmentAccountSettings(LoginRequiredMixin, UpdateInvestmentAccountMixin, ListView):
    template_name = 'investment_account_settings.html'
    model = CoOwner
    context_object_name = 'co_owners'

    def filter_queryset(self):
        """ Получение списка совладельцев """
        if self.investment_account:
            return (
                self.investment_account.co_owners
                .with_is_creator_annotations()
                .annotate(
                    limit=F('capital') +
                    Sum('deal_income_set__value', filter=Q(investment_account=self.investment_account)))
                .order_by('-is_creator', 'investor__username')
            )
        return CoOwner.objects.none()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # FIXME: сделать для всех валют
        if self.investment_account:
            context['total_capital'] = self.request.user.default_investment_account.prop_total_capital
            # context['total_income'] = (
            #     context['currency_assets'].get(currency__iso_code='RUB').value - context['total_capital']
            # )
        return context
