from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ObjectDoesNotExist
from django.views.generic import TemplateView, ListView

from market.models import Operation, Stock
from users.models import InvestmentAccount


class OperationsView(LoginRequiredMixin, ListView):
    template_name = 'operations.html'
    context_object_name = 'operations'
    model = Operation

    def get_queryset(self):
        figi = self.request.GET.get('figi')
        try:
            figi_object = Stock.objects.get(figi=figi)
        except ObjectDoesNotExist:
            queryset = Operation.objects.filter(
                investment_account=self.request.user.default_investment_account,
                status=Operation.Statuses.DONE
            )
        else:
            queryset = Operation.objects.filter(
                investment_account=self.request.user.default_investment_account,
                status=Operation.Statuses.DONE, figi=figi_object
            )
        return queryset.select_related('currency', 'figi').distinct().order_by('-date')


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
