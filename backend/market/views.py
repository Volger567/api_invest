from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView

from users.models import InvestmentAccount


class IndexView(LoginRequiredMixin, TemplateView):
    template_name = 'index.html'


class InvestmentAccountsView(LoginRequiredMixin, TemplateView):
    template_name = 'investment_accounts.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['owned_investment_accounts_owned'] = (
            InvestmentAccount.objects
            .filter(creator=self.request.user)
            .select_related('co_owners')
        )
        context['co_owned_investment_accounts'] = (
            InvestmentAccount.objects
            .filter(co_owners=self.request.user)
            .select_related('co_owners').distinct()
        )
