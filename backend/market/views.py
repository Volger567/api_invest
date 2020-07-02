from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView

from market.models import Operation
from users.models import InvestmentAccount


class IndexView(LoginRequiredMixin, TemplateView):
    template_name = 'index.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['operations'] = Operation.objects.filter(
            investment_account=self.request.user.default_investment_account,
            status=Operation.Statuses.DONE
        ).select_related('currency', 'figi').distinct().order_by('-date')
        context['operation_types'] = dict(Operation.Types.choices)
        return context


class InvestmentAccountsView(LoginRequiredMixin, TemplateView):
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
