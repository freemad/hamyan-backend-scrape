# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.contrib import admin, messages
from django.core.urlresolvers import reverse
from django.shortcuts import render
from django.utils.safestring import mark_safe
from khayyam.jalali_date import JalaliDate

from account_management.models.bankaccount import Bankaccount
from cashbox_management.forms.cashout_form import CashoutForm
from cashbox_management.models import Cycle, Commission, ShareGroup
from cashbox_management.models.cashbox import Cashbox
from cashbox_management.models.membership import Membership
from cashbox_management.models.period import Period
from cashbox_management.models.winner import Winner
from payment.models import Transaction
from utils.admin import BaseAdmin
from utils.constants import choice
from utils.mixins import comma_separate
from payment.admin import OrderInline


class CashboxInline(admin.TabularInline):
    extra = 0
    model = Cashbox


class CommissionInline(admin.TabularInline):
    extra = 0
    model = Commission


class PeriodInline(admin.TabularInline):
    extra = 0
    model = Period


class LinkedPeriodInline(admin.TabularInline):
    extra = 0
    model = Period
    fields = (
        "_id",
        "index",
        "_share_value",
        "_memberships_count",
        "_share_groups_count",
        "cycle_index",
    )
    readonly_fields = [field for field in fields if not field == "id"]

    def _id(self, obj):
        return mark_safe(
            '<a href="{}">{}</a>'.format(
                reverse("admin:cashbox_management_period_change", args=(obj.pk,)),
                obj.pk.__str__(),
            )
        )

    def _memberships_count(self, obj):
        return obj.membership_through.count()

    def _share_groups_count(self, obj):
        return obj.share_groups.count()

    def _share_value(self, obj):
        return comma_separate(obj.share_value)


class CycleInline(admin.TabularInline):
    extra = 0
    model = Cycle


class LinkedCycleInline(admin.TabularInline):
    extra = 0
    model = Cycle
    fields = ("_id", "index", "_period", "start_date", "draw_date", "_winner")
    readonly_fields = [field for field in fields if not field == "id"]

    def _id(self, obj):
        return mark_safe(
            '<a href="{}">{}</a>'.format(
                reverse("admin:cashbox_management_cycle_change", args=(obj.pk,)),
                obj.pk.__str__(),
            )
        )

    def _period(self, obj):
        if obj.period:
            return mark_safe(
                '<a href="{}">{}</a>'.format(
                    reverse(
                        "admin:cashbox_management_period_change", args=(obj.period.pk,)
                    ),
                    obj.period.__str__(),
                )
            )
        else:
            return None

    def _winner(self, obj):
        if obj.winner:
            return mark_safe(
                '<a href="{}">{}</a>'.format(
                    reverse(
                        "admin:cashbox_management_winner_change", args=(obj.member.pk,)
                    ),
                    obj.winner.__str__(),
                )
            )
        else:
            return None


class MembershipInline(admin.TabularInline):
    extra = 0
    model = Membership


class LinkedMembershipInline(admin.TabularInline):
    extra = 0
    model = Membership
    fields = (
        "_id",
        "_member",
        "role",
        "balance",
        "number_of_shares",
        "share_residue",
        "_share_group",
        "won_shares",
    )
    readonly_fields = [field for field in fields if not field == "id"]

    def _id(self, obj):
        return mark_safe(
            '<a href="{}">{}</a>'.format(
                reverse("admin:cashbox_management_membership_change", args=(obj.pk,)),
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

    def _share_group(self, obj):
        if obj.share_group is not None:
            return mark_safe(
                '<a href="{}">{}</a>'.format(
                    reverse(
                        "admin:cashbox_management_sharegroup_change",
                        args=(obj.share_group.pk,),
                    ),
                    obj.share_group.__str__(),
                )
            )
        else:
            return None

    _id.short_description = "id"
    _share_group.short_description = "share group"
    _member.short_description = "member"


class ShareGroupInline(admin.TabularInline):
    extra = 0
    model = ShareGroup


class LinkedShareGroupInline(admin.TabularInline):
    extra = 0
    model = ShareGroup
    fields = ("_id", "_is_valid")
    readonly_fields = [field for field in fields if not field == "id"]

    def _id(self, obj):
        return mark_safe(
            '<a href="{}">{}</a>'.format(
                reverse("admin:cashbox_management_sharegroup_change", args=(obj.pk,)),
                obj.pk.__str__(),
            )
        )

    def _is_valid(self, obj):
        return obj.is_valid()

    _is_valid.boolean = True
    _id.short_description = "id"


class WinnerInline(admin.TabularInline):
    extra = 0
    model = Winner


class LinkedWinnerInline(admin.TabularInline):
    extra = 0
    model = Winner
    fields = ("_id", "_membership", "_share_group")
    readonly_fields = [field for field in fields if not field == "id"]

    def _id(self, obj):
        return mark_safe(
            '<a href="{}">{}</a>'.format(
                reverse("admin:cashbox_management_winner_change", args=(obj.pk,)),
                obj.pk.__str__(),
            )
        )

    def _membership(self, obj):
        if obj.membership:
            return mark_safe(
                '<a href="{}">{}</a>'.format(
                    reverse(
                        "admin:cashbox_management_membership_change",
                        args=(obj.membership.pk,),
                    ),
                    obj.membership.__str__(),
                )
            )
        else:
            return None

    def _share_group(self, obj):
        if obj.share_group:
            return mark_safe(
                '<a href="{}">{}</a>'.format(
                    reverse(
                        "admin:cashbox_management_sharegroup_change",
                        args=(obj.share_group.pk,),
                    ),
                    obj.share_group.__str__(),
                )
            )
        else:
            return None


def get_transactions(modeladmin, request, queryset):
    from payment.models import Transaction

    cashbox = queryset.first()
    cycles_id = list()
    for period in cashbox.periods.all():
        for cycle in period.cycles.all():
            cycles_id.append(cycle.id)
    transactions = Transaction.objects.filter(
        ctx_type=choice.TRANSACTION_CTX_TYPE_CYCLE,
        ctx_id__in=cycles_id
    )
    context = {
        'transactions': transactions
    }
    return render(request, 'transactions.html', context)


def get_successful_transactions(modeladmin, request, queryset):
    from payment.models import Transaction

    cashbox = queryset.first()
    cycles_id = list()
    for period in cashbox.periods.all():
        for cycle in period.cycles.all():
            cycles_id.append(cycle.id)
    transactions = Transaction.objects.filter(
        ctx_type=choice.TRANSACTION_CTX_TYPE_CYCLE,
        ctx_id__in=cycles_id,
        state=choice.TRANSACTION_STATE_SUCCESSFUL
    )
    context = {
        'transactions': transactions
    }
    return render(request, 'transactions.html', context)


class CashboxAdmin(BaseAdmin):
    list_display = (
        "id",
        "name",
        "trust_state",
        "owner_link",
        "state",
        "_is_test",
        "_is_archived",
        "commission_type",
        "share_value",
        "_balance",
        "member_count",
        "share_count",
        "draw_date",
        "created",
        "removed",
    )
    list_filter = ("state",
                   "commission_type",
                   "is_test",
                   "is_archived",
                   "removed",)
    search_fields = ("slug", "name")
    raw_id_fields = ("bank_account",)
    actions = ["create_cashout", get_transactions, get_successful_transactions]
    inlines = [CommissionInline, LinkedPeriodInline, OrderInline]

    def owner_link(self, obj):
        if obj.owner:
            return mark_safe(
                '<a href="{}">{}</a>'.format(
                    reverse(
                        "admin:account_management_member_change", args=(obj.owner.pk,)
                    ),
                    obj.owner.__str__(),
                )
            )
        else:
            return None

    def share_count(self, obj):
        if not obj.get_current_period():
            return 0
        return obj.get_current_period().total_shares

    def member_count(self, obj):
        if not obj.get_current_period():
            return 0
        return obj.get_current_period().members.count()

    def share_value(self, obj):
        if not obj.get_current_period():
            return 0
        return comma_separate(obj.get_current_period().share_value)

    def draw_date(self, obj):
        if not obj.get_current_period():
            return None
        if obj.get_current_period().cycle_index == 0:
            return (
                "("
                + str(obj.get_current_period().interval)
                + ")\n"
                + str(obj.get_current_period().day_of_draw)
            )
        if obj.get_current_period().get_current_cycle():
            return JalaliDate(
                obj.get_current_period().get_current_cycle().draw_date
            ).__str__()
        else:
            return None

    def _balance(self, obj):
        return comma_separate(obj.balance)

    def _is_test(self, obj):
        return obj.is_test

    def _is_archived(self, obj):
        return obj.is_archived

    def create_cashout(self, request, queryset):
        cashbox = queryset[0]
        if "do_action" in request.POST:
            form = CashoutForm(request.POST)

            if form.is_valid():
                value = form.cleaned_data["amount"]
                member = form.cleaned_data["receiver"]
                state = form.cleaned_data["state"]
                send_sms = form.cleaned_data["send_sms"]
                if form.cleaned_data["bank_account"] == "":
                    bank_account = None
                else:
                    bank_account = form.cleaned_data["bank_account"]

                if bank_account is None and send_sms:
                    messages.error(request, "Select bank account for sending sms")
                    return

                if (
                    cashbox.create_cashout(
                        amount=value,
                        member=member,
                        account=bank_account,
                        state=state,
                        send_sms=send_sms,
                    )
                    is not None
                ):
                    messages.success(request, "Cashout Created Successfully")
                else:
                    messages.error(request, "Invalid input data")
                return
        else:
            form = CashoutForm(
                initial={
                    "ctx_id": cashbox.get_current_period().get_current_cycle().id,
                    "ctx_type": choice.TRANSACTION_CTX_TYPE_CYCLE,
                    "state": choice.TRANSACTION_STATE_INIT,
                    "amount": cashbox.balance,
                }
            )

            form.fields["receiver"].queryset = cashbox.get_current_period().members
            form.fields["bank_account"].queryset = Bankaccount.objects.filter(
                member__in=cashbox.get_current_period().get_valid_members()
            )

        return render(request, "cashout_form.html", {"form": form, "cashbox": cashbox})

    create_cashout.short_description = "Create Cashout"

    _is_test.boolean = True
    _is_archived.boolean = True
    owner_link.short_description = "owner"
    member_count.short_description = "members"
    share_count.short_description = "shares"
    share_value.short_description = "share (Toman)"


class PeriodAdmin(BaseAdmin):
    list_display = (
        "id",
        "cashbox_link",
        "index",
        "_share_value",
        "_memberships_count",
        "_share_groups_count",
        "cycle_index",
        "created",
        "removed",
    )
    raw_id_fields = ("cashbox",)
    list_filter = ("removed",)
    search_fields = ("cashbox__name", "cashbox__slug", "index")
    actions = ["start_new_cycle"]

    inlines = [LinkedCycleInline, LinkedMembershipInline, LinkedShareGroupInline]

    def cashbox_link(self, obj):
        return mark_safe(
            '<a href="{}">{}</a>'.format(
                reverse(
                    "admin:cashbox_management_cashbox_change", args=(obj.cashbox.pk,)
                ),
                obj.cashbox.__str__(),
            )
        )

    def start_new_cycle(self, request, queryset):
        for cs in queryset:
            if cs.balance > 0:
                messages.error(
                    request, "Cashbox {} is not empty".format(cs.cashbox.name)
                )

                return

            cs.create_new_cycle()

        messages.success(request, "Succeed")

    def _memberships_count(self, obj):
        return obj.membership_through.count()

    def _share_groups_count(self, obj):
        return obj.share_groups.count()

    def _share_value(self, obj):
        return comma_separate(obj.share_value)

    cashbox_link.short_description = "cashbox"


class CycleAdmin(BaseAdmin):
    list_display = ("id", "period_link", "index", "start_date", "draw_date", "winner")
    raw_id_fields = (
        "period",
        "winner",
    )
    list_filter = ("draw_date", "removed")
    search_fields = (
        "period__cashbox__name",
        "period__cashbox__slug",
        "winner__first_name",
        "winner__last_name",
        "winner__phone_number",
        "index",
    )

    inlines = [LinkedWinnerInline]

    def winner_link(self, obj):
        if obj.winner is not None:
            return mark_safe(
                '<a href="{}">{}</a>'.format(
                    reverse(
                        "admin:cashbox_management_winner_change", args=(obj.winner.pk,)
                    ),
                    obj.winner.__str__(),
                )
            )
        else:
            return None

    def period_link(self, obj):
        if obj.period is not None:
            return mark_safe(
                '<a href="{}">{}</a>'.format(
                    reverse(
                        "admin:cashbox_management_period_change", args=(obj.period.pk,)
                    ),
                    obj.period.__str__(),
                )
            )
        else:
            return None

    winner_link.short_description = "winner"
    period_link.short_description = "period"


class MembershipAdmin(BaseAdmin):
    list_display = (
        "id",
        "member_link",
        "period_link",
        "role",
        "balance",
        "number_of_shares",
        "share_residue",
        "share_group_link",
        "won_shares",
        "created",
        "removed",
    )
    raw_id_fields = ("member", "period", "share_group")
    list_filter = ("role", "removed")
    search_fields = (
        "member__first_name",
        "member__last_name",
        "member__phone_number",
        "period__cashbox__name",
        "period__cashbox__slug",
    )

    actions = ["fix_balance"]

    def member_link(self, obj):
        if obj.member is not None:
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

    def period_link(self, obj):
        if obj.period is not None:
            return mark_safe(
                '<a href="{}">{}</a>'.format(
                    reverse(
                        "admin:cashbox_management_period_change", args=(obj.period.pk,)
                    ),
                    obj.period.__str__(),
                )
            )
        else:
            return None

    def share_group_link(self, obj):
        if obj.share_group is not None:
            return mark_safe(
                '<a href="{}">{}</a>'.format(
                    reverse(
                        "admin:cashbox_management_sharegroup_change",
                        args=(obj.share_group.pk,),
                    ),
                    obj.share_group.__str__(),
                )
            )
        else:
            return None

    def fix_balance(self, request, queryset):
        for q in queryset:
            if q.balance > q.share_amount:
                transactions = Transaction.objects.filter(
                    payer=q.member,
                    ctx_id=q.cycles.latest().id,
                    ctx_type=choice.TRANSACTION_CTX_TYPE_CYCLE,
                    state=choice.TRANSACTION_STATE_SUCCESSFUL,
                ).orderby("id")
                to_be_charged_amount = 0
                transactions_amounts_balance = 0
                for tr in transactions:
                    if transactions_amounts_balance <= q.share_amount:
                        transactions_amounts_balance += tr.amount
                    else:
                        tr.amount = tr.amount + tr.commission
                        tr.commission = 0
                        tr.destination = choice.TRANSACTION_DST_HAMYAN_WALLET
                        tr.save()
                        to_be_charged_amount += tr.amount
                q.member.charge_wallet_balance(to_be_charged_amount)

    period_link.short_description = "period"
    member_link.short_description = "member"
    share_group_link.short_description = "share group"


class ShareGroupAdmin(BaseAdmin):
    list_display = ("id", "_period", "name", "is_valid", "is_won", "created", "removed")
    raw_id_fields = ("period",)
    list_filter = ("period__cashbox__name", "period__cashbox__slug", "removed")
    search_fields = ("name",)

    inlines = [LinkedMembershipInline]

    def _period(self, obj):
        if obj.period is not None:
            return mark_safe(
                '<a href="{}">{}</a>'.format(
                    reverse(
                        "admin:cashbox_management_period_change", args=(obj.period.pk,)
                    ),
                    obj.period.__str__(),
                )
            )
        else:
            return None

    def is_valid(self, obj):
        return obj.is_valid()

    is_valid.boolean = True
    _period.short_description = "period"


class CommissionAdmin(BaseAdmin):
    list_display = (
        "id",
        "cashbox_link",
        "is_manually_set",
        "cycle_commission",
        "number_of_trial_cycles",
    )
    raw_id_fields = ("cashbox",)
    list_filter = ("cycle_commission", "number_of_trial_cycles")
    search_fields = ("cashbox__name", "cashbox__slug")

    def cashbox_link(self, obj):
        if obj.cashbox is not None:
            return mark_safe(
                '<a href="{}">{}</a>'.format(
                    reverse(
                        "admin:cashbox_management_cashbox_change",
                        args=(obj.cashbox.pk,),
                    ),
                    obj.cashbox.__str__(),
                )
            )
        else:
            return None

    cashbox_link.short_description = "cashbox"


class WinnerAdmin(BaseAdmin):
    list_display = (
        "id",
        "cycle_link",
        "membership_link",
        "share_group_link",
        "loan_amount",
        "created",
        "removed",
    )
    raw_id_fields = ("cycle", "membership", "share_group")
    list_filter = ("created", "removed")
    search_fields = (
        "cycle__period__cashbox__name",
        "cycle__period__cashbox__slug",
        "id",
    )

    def cycle_link(self, obj):
        if obj.cycle is not None:
            return mark_safe(
                '<a href="{}">{}</a>'.format(
                    reverse(
                        "admin:cashbox_management_cycle_change", args=(obj.cycle.pk,)
                    ),
                    obj.cycle.__str__(),
                )
            )
        else:
            return None

    def membership_link(self, obj):
        if obj.membership is not None:
            return mark_safe(
                '<a href="{}">{}</a>'.format(
                    reverse(
                        "admin:cashbox_management_membership_change",
                        args=(obj.membership.pk,),
                    ),
                    obj.membership.__str__(),
                )
            )
        else:
            return None

    def share_group_link(self, obj):
        if obj.share_group is not None:
            return mark_safe(
                '<a href="{}">{}</a>'.format(
                    reverse(
                        "admin:cashbox_management_sharegroup_change",
                        args=(obj.share_group.pk,),
                    ),
                    obj.share_group.__str__(),
                )
            )
        else:
            return None

    def get_form(self, request, obj=None, **kwargs):
        form = super(WinnerAdmin, self).get_form(request, obj, **kwargs)

        if obj is not None:
            if obj.cycle is not None:
                form.base_fields["cycle"].queryset = Cycle.objects.filter(
                    period=obj.cycle.period
                )
                form.base_fields["membership"].queryset = Membership.objects.filter(
                    period=obj.cycle.period
                )

        return form

    cycle_link.short_description = "cycle"
    membership_link.short_description = "membership"
    share_group_link.short_description = "share group"


admin.site.register(Cashbox, CashboxAdmin)
admin.site.register(Period, PeriodAdmin)
admin.site.register(Cycle, CycleAdmin)
admin.site.register(Membership, MembershipAdmin)
admin.site.register(ShareGroup, ShareGroupAdmin)
admin.site.register(Commission, CommissionAdmin)
admin.site.register(Winner, WinnerAdmin)
