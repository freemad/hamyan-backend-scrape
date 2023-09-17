# Register your models here.
from __future__ import unicode_literals

from django.contrib import admin
from django.core.urlresolvers import reverse
from django.utils.safestring import mark_safe
from django.shortcuts import render

from moneypool_management import models
# from moneypool_management.models import (
#     Moneypool,
#     Poolship,
#     Share,
#     ShareValue,
#     Loan,
#     Installment,
#     Abonnement,
#     ServicePackage,
#     Invoice,
#     MoneypoolCommission,
#     MoneypoolFacility)
from payment.admin import (
    LinkedMoneypoolCashinRegisteredInline,
    LinkedMoneypoolCashinPoolshipedInline,
    LinkedMoneypoolCashoutRegisteredInline,
    LinkedMoneypoolCashoutPoolshipedInline,
    OrderInline
)
from utils.admin import BaseAdmin
from utils.constants import choice
from utils.mixins import comma_separate


class AbonnementInline(admin.TabularInline):
    extra = 0
    model = models.Abonnement


class MoneypoolCommissionInline(admin.TabularInline):
    extra = 0
    model = models.MoneypoolCommission


class MoneypoolFacilityInline(admin.TabularInline):
    extra = 0
    model = models.MoneypoolFacility


class ShareValueInline(admin.TabularInline):
    extra = 0
    model = models.ShareValue


class LinkedPoolshipInline(admin.TabularInline):
    extra = 0
    model = models.Poolship
    fields = (
        "_id",
        "_member",
        "_share",
        "role",
        "is_active",
        "_total_cashins",
        "_total_cashouts",
        "_to_be_paid_portion",
        "_paid_portion",
        "_to_be_paid_commission",
        "_paid_commission",
    )
    readonly_fields = [field for field in fields if not field == "id"]

    def _id(self, obj):
        return mark_safe(
            '<a href="{}">{}</a>'.format(
                reverse("admin:moneypool_management_poolship_change", args=(obj.pk,)),
                obj.pk.__str__(),
            )
        )

    def _member(self, obj):
        return mark_safe(
            '<a href="{}">{}</a>'.format(
                reverse(
                    "admin:account_management_member_change", args=(obj.member.pk,)
                ),
                obj.member.__str__(),
            )
        )

    def _share(self, obj):
        if obj.shares.count() > 0:
            return mark_safe(
                '<a href="{}">{}</a>'.format(
                    reverse(
                        "admin:moneypool_management_share_change",
                        args=(obj.shares.latest("start_date").pk,),
                    ),
                    obj.shares.latest("start_date").__str__(),
                )
            )
        else:
            return None

    def _total_cashins(self, obj):
        return comma_separate(obj.total_cashins_amount)

    def _total_cashouts(self, obj):
        return comma_separate(obj.total_cashouts_amount)

    def _to_be_paid_portion(self, obj):
        return comma_separate(obj.to_be_paid_portion)

    def _paid_portion(self, obj):
        return comma_separate(obj.paid_portion)

    def _to_be_paid_commission(self, obj):
        return comma_separate(obj.to_be_paid_commission)

    def _paid_commission(self, obj):
        return comma_separate(obj.paid_commission)

    _id.short_description = "id"
    _member.short_description = "member"
    _share.short_description = "share"
    _total_cashins.short_description = "Cashins"
    _total_cashouts.short_description = "Cashouts"
    _to_be_paid_portion.short_description = "TBP Portion"
    _paid_portion.short_description = "P Portion"
    _to_be_paid_commission.short_description = "TBP Com."
    _paid_commission.short_description = "P Com."


class ShareInline(admin.TabularInline):
    extra = 0
    model = models.Share


class InstallmentInline(admin.TabularInline):
    extra = 0
    model = models.Installment


class LinkedInstallmentInline(admin.TabularInline):
    extra = 0
    model = models.Installment
    fields = (
        "_id",
        "_loan",
        "_member",
        "_cashin",
        "_amount",
        "index",
        "due_date",
        "is_paid",
    )
    readonly_fields = [field for field in fields if not field == "id"]

    def _id(self, obj):
        return mark_safe(
            '<a href="{}">{}</a>'.format(
                reverse(
                    "admin:moneypool_management_installment_change", args=(obj.pk,)
                ),
                obj.pk.__str__(),
            )
        )

    def _loan(self, obj):
        if obj.loan:
            return mark_safe(
                '<a href="{}">{}</a>'.format(
                    reverse(
                        "admin:moneypool_management_loan_change", args=(obj.loan.pk,)
                    ),
                    obj.loan.__str__(),
                )
            )
        else:
            return None

    def _member(self, obj):
        return mark_safe(
            '<a href="{}">{}</a>'.format(
                reverse(
                    "admin:account_management_member_change",
                    args=(obj.loan.cashout.poolship.member.pk,),
                ),
                obj.loan.cashout.poolship.member.__str__(),
            )
        )

    def _cashin(self, obj):
        if obj.cashin:
            return mark_safe(
                '<a href="{}">{}</a>'.format(
                    reverse(
                        "admin:payment_moneypoolcashin_change", args=(obj.cashin.pk,)
                    ),
                    obj.cashin.__str__(),
                )
            )
        else:
            return None

    def _amount(self, obj):
        return comma_separate(obj.amount)

    def _is_paid(self, obj):
        return obj.is_paid

    _is_paid.boolean = True


class LinkedLoanDemandInline(admin.TabularInline):
    extra = 0
    model = models.LoanDemand
    fields = (
        "_id",
        "loan",
        "poolship",
        "_amount",
        "num_repayments",
        "demand_state",
        "state_datetime",
    )
    readonly_fields = [field for field in fields if not field == "id"]

    def _id(self, obj):
        return mark_safe(
            '<a href="{}">{}</a>'.format(
                reverse(
                    "admin:moneypool_management_loandemand_change", args=(obj.pk,)
                ),
                obj.pk.__str__(),
            )
        )

    def _amount(self, obj):
        return comma_separate(obj.amount)


class InvoiceInline(admin.TabularInline):
    extra = 0
    model = models.Invoice


def get_transactions(modeladmin, request, queryset):
    from payment.models import Transaction
    moneypool = queryset.first()
    transactions = Transaction.objects.filter(
        ctx_type=choice.TRANSACTION_CTX_TYPE_MONEYPOOL,
        ctx_id=moneypool.id
    )
    context = {
        'transactions': transactions
    }
    return render(request, 'transactions.html', context)


@admin.register(models.Moneypool)
class MoneypoolAdmin(BaseAdmin):
    list_display = (
        "id",
        "name",
        "type",
        "trust_state",
        "owner_link",
        "share_value_link",
        "total_shares",
        "_hamyan_balance",
        "_bank_balance",
        "due_date",
        "created",
        "removed",
        "_is_active",
        "bank_account_link",
        "day_of_duetion",
        "interval",
        "number_of_sedimentation_days",
    )
    raw_id_fields = ("bank_account",)
    list_filter = ("created", "removed", "type", "interval", "is_archived")
    search_fields = ("slug", "name")
    actions = [get_transactions, ]
    inlines = [LinkedPoolshipInline,
               ShareValueInline,
               MoneypoolCommissionInline,
               OrderInline,
               MoneypoolFacilityInline,
               ]

    def owner_link(self, obj):
        if obj.owner_member:
            return mark_safe(
                '<a href="{}">{}</a>'.format(
                    reverse(
                        "admin:account_management_member_change",
                        args=(obj.owner_member.pk,),
                    ),
                    obj.owner_member.__str__(),
                )
            )
        else:
            return None

    def share_value_link(self, obj):
        if obj.share_values.count() > 0:
            return mark_safe(
                '<a href="{}">{}</a>'.format(
                    reverse(
                        "admin:moneypool_management_sharevalue_change",
                        args=(obj.share_values.latest("start_date").pk,),
                    ),
                    comma_separate(obj.share_values.latest("start_date").amount),
                )
            )
        else:
            return None

    def bank_account_link(self, obj):
        if obj.bank_account:
            return mark_safe(
                '<a href="{}">{}</a>'.format(
                    reverse(
                        "admin:account_management_bankaccount_change",
                        args=(obj.bank_account.pk,),
                    ),
                    obj.bank_account.__str__(),
                )
            )
        else:
            return None

    def member_count(self, obj):
        return obj.members.count()

    def share_value(self, obj):
        if obj.get_current_period() is None:
            return 0
        return comma_separate(obj.get_current_period().share_value)

    def _hamyan_balance(self, obj):
        return comma_separate(obj.hamyan_balance)

    def _bank_balance(self, obj):
        return comma_separate(obj.bank_balance)

    def _is_active(self, obj):
        return not obj.is_archived

    _is_active.boolean = True

    owner_link.short_description = "owner"
    share_value_link.short_description = "share value"
    bank_account_link.short_description = "bank account"
    member_count.short_description = "members"
    share_value.short_description = "share (Toman)"
    _hamyan_balance.short_description = "hamyan balance"
    _bank_balance.short_description = "bank balance"
    _is_active.short_description = "is active"


@admin.register(models.Poolship)
class PoolshipAdmin(BaseAdmin):
    list_display = (
        "id",
        "member_link",
        "moneypool_link",
        "share_link",
        "role",
        "is_active",
        "_total_cashins",
        "_total_cashouts",
        "_to_be_paid_portion",
        "_paid_portion",
        "created",
        "removed",
    )
    raw_id_fields = ("member", "moneypool")
    list_filter = ("removed", "is_active")
    search_fields = (
        "moneypool__name",
        "moneypool__slug",
        "member__first_name",
        "member__last_name",
    )

    inlines = [
        ShareInline,
        LinkedMoneypoolCashinRegisteredInline,
        LinkedMoneypoolCashinPoolshipedInline,
        LinkedMoneypoolCashoutRegisteredInline,
        LinkedMoneypoolCashoutPoolshipedInline,
        LinkedLoanDemandInline,
    ]

    def member_link(self, obj):
        if obj.member:
            return mark_safe(
                '<a href="{}">{}</a>'.format(
                    reverse(
                        "admin:account_management_member_change", args=(obj.member.pk,)
                    ),
                    obj.member.__str__(),
                )
            )
        else:
            return None

    def moneypool_link(self, obj):
        if obj.moneypool:
            return mark_safe(
                '<a href="{}">{}</a>'.format(
                    reverse(
                        "admin:moneypool_management_moneypool_change",
                        args=(obj.moneypool.pk,),
                    ),
                    obj.moneypool.__str__(),
                )
            )
        else:
            return None

    def share_link(self, obj):
        if obj.shares.count() > 0:
            return mark_safe(
                '<a href="{}">{}</a>'.format(
                    reverse(
                        "admin:moneypool_management_share_change",
                        args=(obj.shares.latest("start_date").pk,),
                    ),
                    obj.shares.latest("start_date").__str__(),
                )
            )
        else:
            return None

    def _total_cashins(self, obj):
        return comma_separate(obj.total_cashins_amount)

    def _total_cashouts(self, obj):
        return comma_separate(obj.total_cashouts_amount)

    def _to_be_paid_portion(self, obj):
        return comma_separate(obj.to_be_paid_portion)

    def _paid_portion(self, obj):
        return comma_separate(obj.paid_portion)

    moneypool_link.short_description = "moneypool"
    member_link.short_description = "member"
    share_link.short_description = "share"


@admin.register(models.Share)
class ShareAdmin(BaseAdmin):
    list_display = ("id", "poolship_link", "number", "start_date", "created", "removed")
    raw_id_fields = ("poolship",)
    list_filter = ("created", "removed")
    search_fields = ("poolship__member__first_name", "poolship__member__last_name")

    def poolship_link(self, obj):
        if obj.poolship:
            return mark_safe(
                '<a href="{}">{}</a>'.format(
                    reverse(
                        "admin:moneypool_management_poolship_change",
                        args=(obj.poolship.pk,),
                    ),
                    obj.poolship.__str__(),
                )
            )
        else:
            return None

    poolship_link.short_description = "poolship"


@admin.register(models.ShareValue)
class ShareValueAdmin(BaseAdmin):
    list_display = (
        "id",
        "moneypool_link",
        "amount",
        "start_date",
        "created",
        "removed",
    )
    raw_id_fields = ("moneypool",)
    list_filter = ("created", "removed")
    search_fields = ("moneypool__name",)

    def moneypool_link(self, obj):
        if obj.moneypool:
            return mark_safe(
                '<a href="{}">{}</a>'.format(
                    reverse(
                        "admin:moneypool_management_moneypool_change",
                        args=(obj.moneypool.pk,),
                    ),
                    obj.moneypool.__str__(),
                )
            )
        else:
            return None

    moneypool_link.short_description = "moneypool"


@admin.register(models.Loan)
class LoanAdmin(BaseAdmin):
    list_display = (
        "id",
        "cashout_link",
        "poolship_link",
        "moneypool_link",
        "member_link",
        "number_of_repayments",
        "repaid_amount",
        "repayment_interval",
        "interest_rate",
        "pay_date",
        "created",
        "removed",
    )
    raw_id_fields = ("cashout",)
    list_filter = ("created", "removed")
    search_fields = (
        "cashout__poolship__moneypool__name",
        "cashout__poolship__moneypool__slug",
        "cashout__registrar__member__first_name",
        "cashout__poolship__member__first_name",
        "cashout__registrar__member__last_name",
        "cashout__poolship__member__last_name",
    )

    inlines = [LinkedInstallmentInline]

    def cashout_link(self, obj):
        if obj.cashout:
            return mark_safe(
                '<a href="{}">{}</a>'.format(
                    reverse(
                        "admin:payment_moneypoolcashout_change", args=(obj.cashout.pk,)
                    ),
                    obj.cashout.__str__(),
                )
            )
        else:
            return None

    def poolship_link(self, obj):
        if obj.cashout and obj.cashout.poolship:
            return mark_safe(
                '<a href="{}">{}</a>'.format(
                    reverse(
                        "admin:moneypool_management_poolship_change",
                        args=(obj.cashout.poolship.pk,),
                    ),
                    obj.cashout.poolship.__str__(),
                )
            )
        else:
            return None

    def moneypool_link(self, obj):
        if obj.cashout and obj.cashout.poolship and obj.cashout.poolship.moneypool:
            return mark_safe(
                '<a href="{}">{}</a>'.format(
                    reverse(
                        "admin:moneypool_management_moneypool_change",
                        args=(obj.cashout.poolship.moneypool.pk,),
                    ),
                    obj.cashout.poolship.moneypool.__str__(),
                )
            )
        else:
            return None

    def member_link(self, obj):
        if obj.cashout and obj.cashout.poolship and obj.cashout.poolship.member:
            return mark_safe(
                '<a href="{}">{}</a>'.format(
                    reverse(
                        "admin:account_management_member_change",
                        args=(obj.cashout.poolship.member.pk,),
                    ),
                    obj.cashout.poolship.member.__str__(),
                )
            )
        else:
            return None

    def _repaid_amount(self, obj):
        return obj.repaid_amount

    cashout_link.short_description = "cashout"
    poolship_link.short_description = "poolship"
    moneypool_link.short_description = "moneypool"
    member_link.short_description = "member"
    _repaid_amount.short_description = "Repaid Amount"


@admin.register(models.Installment)
class InstallmentAdmin(BaseAdmin):
    list_display = (
        "id",
        "loan_link",
        "member_link",
        "cashin_link",
        "amount",
        "index",
        "due_date",
        "is_paid",
        "created",
        "removed",
    )
    raw_id_fields = ("loan", "cashin")
    list_filter = ("created", "removed")
    search_fields = (
        "loan__cashout__registrar__member__first_name",
        "loan__cashout__poolship__member__first_name",  # noqa
        "loan__cashout__registrar__member__last_name",
        "loan__cashout__poolship__member__last_name",  # noqa
        "loan__cashout__registrar__member__phone_number",
        "loan__cashout__poolship__member__phone_number",  # noqa
        "loan__cashout__poolship__moneypool__name",
        "loan__cashout__poolship__moneypool__slug",
    )

    def loan_link(self, obj):
        if obj.loan:
            return mark_safe(
                '<a href="{}">{}</a>'.format(
                    reverse(
                        "admin:moneypool_management_loan_change", args=(obj.loan.pk,)
                    ),
                    obj.loan.__str__(),
                )
            )
        else:
            return None

    def member_link(self, obj):
        if (
                obj.loan
                and obj.loan.cashout
                and obj.loan.cashout.poolship
                and obj.loan.cashout.poolship.member
        ):
            return mark_safe(
                '<a href="{}">{}</a>'.format(
                    reverse(
                        "admin:account_management_member_change",
                        args=(obj.loan.cashout.poolship.member.pk,),
                    ),
                    obj.loan.cashout.poolship.member.__str__(),
                )
            )
        else:
            return None

    def cashin_link(self, obj):
        if obj.cashin:
            return mark_safe(
                '<a href="{}">{}</a>'.format(
                    reverse(
                        "admin:payment_moneypoolcashin_change", args=(obj.cashin.pk,)
                    ),
                    obj.cashin.__str__(),
                )
            )
        else:
            return None

    def is_paid(self, obj):
        return obj.is_paid

    is_paid.boolean = True

    loan_link.short_description = "loan"
    member_link.short_description = "member"
    cashin_link.short_description = "cashin"


@admin.register(models.Abonnement)
class AbonnementAdmin(BaseAdmin):
    list_display = (
        "id",
        "moneypool_link",
        "number_of_trial_intervals",
        "custom_coef",
        "is_manually_set",
        "created",
        "removed",
    )
    raw_id_fields = ("moneypool",)
    list_filter = ("created", "removed", "is_manually_set")
    search_fields = ("moneypool__name", "number_of_trial_intervals", "custom_coef")

    def moneypool_link(self, obj):
        if obj.moneypool:
            return mark_safe(
                '<a href="{}">{}</a>'.format(
                    reverse(
                        "admin:moneypool_management_moneypool_change",
                        args=(obj.moneypool.pk,),
                    ),
                    obj.moneypool.__str__(),
                )
            )
        else:
            return None

    moneypool_link.short_description = "moneypool"


@admin.register(models.MoneypoolFacility)
class MoneypoolFacilityAdmin(BaseAdmin):
    list_display = (
        "id",
        "moneypool_link",
        "interval_full_report_count",
        "purchased_full_report_count",
        "is_manually_set",
        "created",
        "removed",
    )
    raw_id_fields = ("moneypool",)
    list_filter = ("created", "removed", "is_manually_set")
    search_fields = ("moneypool__name", "moneypool__slug", )

    def moneypool_link(self, obj):
        if obj.moneypool:
            return mark_safe(
                '<a href="{}">{}</a>'.format(
                    reverse(
                        "admin:moneypool_management_moneypool_change",
                        args=(obj.moneypool.pk,),
                    ),
                    obj.moneypool.__str__(),
                )
            )
        else:
            return None

    moneypool_link.short_description = "moneypool"


@admin.register(models.LoanDemand)
class LoanDemandAdmin(BaseAdmin):
    list_display = (
        "id",
        "poolship_link",
        "loan_link",
        "amount",
        "num_repayments",
        "demand_state",
        "state_datetime",
        "created",
        "removed",
    )
    raw_id_fields = ("poolship", "loan", )
    list_filter = ("created", "removed",)
    search_fields = (
        "poolship__moneypool__name",
        "poolship__moneypool__slug",
        "poolship__member__phone_number",
    )

    def poolship_link(self, obj):
        if obj.poolship:
            return mark_safe(
                '<a href="{}">{}</a>'.format(
                    reverse(
                        "admin:moneypool_management_poolship_change",
                        args=(obj.poolship.pk,),
                    ),
                    obj.poolship.__str__(),
                )
            )
        else:
            return None

    def loan_link(self, obj):
        if obj.loan:
            return mark_safe(
                '<a href="{}">{}</a>'.format(
                    reverse(
                        "admin:moneypool_management_loan_change",
                        args=(obj.loan.pk,),
                    ),
                    obj.loan.__str__(),
                )
            )
        else:
            return None

    poolship_link.short_description = "poolship"
    loan_link.short_description = "loan"


@admin.register(models.ServicePackage)
class ServicePackageAdmin(BaseAdmin):
    list_display = (
        "id",
        "name",
        "type",
        "interval",
        "discount",
        "is_public",
        "created",
        "removed",
    )
    list_filter = ("created", "removed", "type", "interval", "is_public")
    search_fields = ("name", "discount")


@admin.register(models.Invoice)
class InvoiceAdmin(BaseAdmin):
    list_display = (
        "id",
        "moneypool_link",
        "transaction_link",
        "invoice_state",
        "start_date",
        "expire_date",
        "package_link",
        "is_manually_set",
        "created",
        "removed",
    )
    raw_id_fields = ("moneypool", "transaction")
    list_filter = ("created", "removed", "is_manually_set")
    search_fields = ("moneypool__name", "number_of_trial_intervals", "user_count_coef")
    readonly_fields = ("invoice_state", "expire_date")

    def moneypool_link(self, obj):
        if obj.moneypool:
            return mark_safe(
                '<a href="{}">{}</a>'.format(
                    reverse(
                        "admin:moneypool_management_moneypool_change",
                        args=(obj.moneypool.pk,),
                    ),
                    obj.moneypool.__str__(),
                )
            )
        else:
            return None

    def package_link(self, obj):
        if obj.package:
            return mark_safe(
                '<a href="{}">{}</a>'.format(
                    reverse(
                        "admin:moneypool_management_servicepackage_change",
                        args=(obj.package.pk,),
                    ),
                    obj.package.__str__(),
                )
            )
        else:
            return None

    def transaction_link(self, obj):
        if obj.transaction:
            return mark_safe(
                '<a href="{}">{}</a>'.format(
                    reverse(
                        "admin:payment_transaction_change", args=(obj.transaction.pk,)
                    ),
                    obj.transaction.__str__(),
                )
            )
        else:
            return None

    def invoice_state(self, obj):
        return dict(choice.TRANSACTION_STATE).get(obj.state)

    def expire_date(self, obj):
        return obj.expire_date

    moneypool_link.short_description = "moneypool"
    package_link.short_description = "package"
    transaction_link.short_description = "transaction"
    invoice_state.short_description = "state"
    expire_date.short_description = "expire date"


# @admin.register(models.MoneypoolCommission)
