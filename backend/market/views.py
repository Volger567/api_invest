from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Max, Sum, Min
from django.utils import timezone
from django.views.generic import TemplateView, ListView

from market.models import Operation, Stock, Deal
from tinkoff_api import TinkoffProfile
from users.models import InvestmentAccount


class UpdateInvestmentAccount:
    def get(self, *args, **kwargs):
        self.investment_account = self.request.user.default_investment_account
        if self.investment_account:
            self.investment_account.update_all(timezone.now())
        return super().get(*args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.investment_account:
            context['currency_assets'] = \
                self.investment_account.currency_assets.all().select_related('currency').distinct()
        return context


class OperationsView(LoginRequiredMixin, UpdateInvestmentAccount, ListView):
    template_name = 'operations.html'
    context_object_name = 'operations'
    model = Operation

    def get_queryset(self):
        figi = self.request.GET.get('figi')
        try:
            figi_object = Stock.objects.get(figi=figi)
        except ObjectDoesNotExist:
            queryset = Operation.objects.filter(
                investment_account=self.investment_account,
                status=Operation.Statuses.DONE
            )
        else:
            queryset = Operation.objects.filter(
                investment_account=self.investment_account,
                status=Operation.Statuses.DONE, figi=figi_object
            )
        return queryset.select_related('currency', 'figi').distinct().order_by('-date')


class DealsView(LoginRequiredMixin, UpdateInvestmentAccount, TemplateView):
    template_name = 'deals.html'

    def get_context_data(self, **kwargs):
        figi = self.request.GET.get('figi')
        try:
            figi_object = Stock.objects.get(figi=figi)
        except ObjectDoesNotExist:
            queryset = Deal.objects.filter(investment_account=self.investment_account)
        else:
            queryset = Deal.objects.filter(investment_account=self.investment_account, figi=figi_object)

        context = super().get_context_data(**kwargs)
        context['opened_deals'] = (
            queryset.opened().annotate(earliest_operation_date=Min('operation__date'))
            .order_by('-earliest_operation_date')
        ).select_related('figi').distinct()

        context['closed_deals'] = (
            queryset.closed()
            .annotate(latest_operation_date=Max('operation__date'), earliest_operation_date=Min('operation__date'))
            .annotate(profit=Sum('operation__payment')+Sum('operation__commission'))
            .order_by('-latest_operation_date')
        ).select_related('figi').distinct()
        # FIXME: оптимизировать
        if self.investment_account:
            with TinkoffProfile(self.investment_account.token) as tp:
                context['portfolio'] = tp.portfolio()['payload']['positions']
        return context


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
