from django.contrib import admin
from django.contrib.admin import AdminSite
from django.contrib.auth.admin import UserAdmin, GroupAdmin

from users.models import Investor, InvestorGroup


class InvestorSite(AdminSite):
    site_title = 'Tinkoff Invest'
    site_header = 'TF-INV'


admin_site = InvestorSite()
admin.site = admin_site


class InvestorAdmin(UserAdmin):
    list_display = ('username', 'email', 'is_active')


admin_site.register(Investor, InvestorAdmin)
admin_site.register(InvestorGroup, GroupAdmin)
