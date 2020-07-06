from datetime import timedelta

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Max, Sum, Min
from django.utils import timezone
from django.views.generic import TemplateView, ListView

from market.models import Operation, Stock, Deal
from users.models import InvestmentAccount


# TODO: Обновление данных об операциях
class OperationsView(LoginRequiredMixin, ListView):
    template_name = 'operations.html'
    context_object_name = 'operations'
    model = Operation

    def get_queryset(self):
        investment_account = self.request.user.default_investment_account
        if investment_account and timezone.now() - investment_account.operations_sync_at > timedelta(seconds=30):
            self.request.user.default_investment_account.update_operations()
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


class DealsView(LoginRequiredMixin, TemplateView):
    template_name = 'deals.html'

    def get_context_data(self, **kwargs):
        investment_account = self.request.user.default_investment_account
        if investment_account and timezone.now() - investment_account.operations_sync_at > timedelta(seconds=30):
            self.request.user.default_investment_account.update_operations()
        context = super().get_context_data(**kwargs)
        context['opened_deals'] = (
            Deal.objects
                .filter(investment_account=self.request.user.default_investment_account, is_closed=False)
                .annotate(earliest_operation_date=Min('operation__date'))
                .order_by('-earliest_operation_date')
        ).select_related('figi').distinct()

        context['closed_deals'] = (
            Deal.objects
                .filter(investment_account=self.request.user.default_investment_account, is_closed=True)
                .annotate(latest_operation_date=Max('operation__date'), earliest_operation_date=Min('operation__date'))
                .annotate(profit=Sum('operation__payment')+Sum('operation__commission'))
                .order_by('-latest_operation_date', 'earliest_operation_date')
        ).select_related('figi').distinct()
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
