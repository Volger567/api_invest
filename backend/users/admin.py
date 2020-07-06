from django.contrib import admin
from django.contrib.admin import AdminSite
from django.contrib.auth.admin import UserAdmin, GroupAdmin

from users.models import Investor, InvestorGroup, InvestmentAccount


class InvestorSite(AdminSite):
    site_title = 'Tinkoff Invest'
    site_header = 'TF-INV'


admin_site = InvestorSite()
admin.site = admin_site


class InvestorAdmin(UserAdmin):
    list_display = ('username', 'email', 'is_active')


class InvestmentAccountAdmin(admin.ModelAdmin):
    list_display = ('name', 'creator', 'broker_account_id', 'operations_sync_at', 'capital_sharing_principle')


admin_site.register(Investor, InvestorAdmin)
admin_site.register(InvestorGroup, GroupAdmin)
admin_site.register(InvestmentAccount, InvestmentAccountAdmin)
