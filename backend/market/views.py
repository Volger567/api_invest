from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Max, Sum, Min, F, Subquery, OuterRef
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
        opened_deals = list(
            queryset.opened()
            .annotate(
                earliest_operation_date=Min('operation__date'),
                figi_name=F('figi__name'),
                figi_figi=F('figi__figi'),
                abbreviation=Subquery(
                    Operation.objects.filter(deal=OuterRef('pk')).values('currency__abbreviation')[:1]
                )
            )
            .order_by('-earliest_operation_date')
            .values()
        )
        if self.investment_account:
            with TinkoffProfile(self.investment_account.token) as tp:
                portfolio = tp.portfolio()['payload']['positions']
                portfolio = {i['figi']: i for i in portfolio}
            for deal in opened_deals:
                figi_figi = deal['figi_figi']
                asset = portfolio[figi_figi]
                price = asset['averagePositionPrice']['value'] * asset['balance']
                expected_price = price + asset['expectedYield']['value']
                if price < expected_price:
                    deal['expected_percent_profit'] = ((expected_price / price)-1)*100
                else:
                    deal['expected_percent_profit'] = -(1-(expected_price/price))*100
                deal['expected_profit'] = asset['expectedYield']['value']
                deal['lots_left'] = asset['lots']
        context['opened_deals'] = opened_deals
        context['closed_deals'] = (
            queryset.closed()
            .annotate(latest_operation_date=Max('operation__date'), earliest_operation_date=Min('operation__date'))
            .annotate(profit=Sum('operation__payment')+Sum('operation__commission'))
            .order_by('-latest_operation_date')
        ).select_related('figi').distinct()
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
