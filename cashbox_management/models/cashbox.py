# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.conf import settings
from django.contrib.contenttypes.fields import GenericRelation
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from django.utils.datetime_safe import date
from django.utils.encoding import smart_text
from django.utils.translation import ugettext_lazy as _

from cashbox_management.models import Commission
from cashbox_management.models import Cycle
from cashbox_management.models.membership import Membership
from cashbox_management.models.period import Period
from cashbox_management.models.winner import Winner
from cashbox_management.utils import (
    list_winners_to_string,
    get_cashbox_service_package,
    get_last_successful_order)
from payment.models import Transaction
from utils.announce import Announce, choice as template_choice
from utils.constants import choice
from utils.constants.announcements import (
    DRAW_TYPE_MANUAL,
    DRAW_TYPE_AUTOMATIC,
    DRAW_TYPE_SEMI_AUTOMATIC,
)
from utils.constants.default import WEB_APP_BASE_URL
from utils.constants.notification_constant import (
    NOTIFICATION_ACTION_FIELD_CASHBOX_DETAIL,
    NOTIFICATION_ACTION_FIELD_MAIN,
    NOTIFICATION_ACTION_FIELD_CASHBOX_PAYMENT,
)
from utils.firebase import notification_templates as notif
from utils.firebase.notification import (
    send_notification_to_member_list,
    send_notification_to_member,
    create_page_notification_data,
)
from utils.log import info_logger, error_logger
from utils.message import message_templates as msg
from utils.message.message import send_message_to_member, send_message_to_member_list
from utils.mixins import comma_separate, spacey, BoxPermissionMixin
from utils.models import BaseModel
from utils.randomization import generate_numeric_uid, generate_alphanumeric_uid
from utils.sms import sms_templates
from utils.tasks import send_high_priority_templated_sms
from utils.announce import Announce, choice as template_choice
from utils.shorten_url import shorten_url
from cashbox_management.utils import list_winners_to_string, get_cashbox_service_package, get_last_successful_order

CASHBOX_BASE_URL = WEB_APP_BASE_URL + "account/cashbox/public/"


def default_cashbox_slug():
    return generate_numeric_uid(settings.CASHBOX_SLUG_LENGTH)


class Cashbox(BaseModel, BoxPermissionMixin):
    """
    the main and container model of the boxes which all members pay their shares in a cycle (Nowbat)
    and all of the gathered amount delivers to the winner(s) of the cycle

    FIELDS
    name: the name of the cashbox
    image_id: the id of the image (avatar) of the box
    slug: the uuid (slug) of the cashbox which with can be unified
    state: the choice represents the activity state of the cashbox values: inactive/draft/active
    period_index: the index of the period which the cashbox is run in
    bank_account: the bank_account which is assigned to transfer all money to it (in Worried states)
    commission_type: the choice represents the type of the COMMISSION
        which the CASHBOX is on to values: regular, rosca
    trust_state: the choice which represents the trust state of the cashbox values:
        trusted, worried_unverified, worried_in_progress, worried_verified, trusted
    web_key: the uuid key for accessing through web and ... (public access)
    is_test: the indicator says the cashbox is test (or archived) or not
    is_draft: the indicator says the cashbox is come alive from draft or not
    notification_announce: the choice represents the state of
        sending notification values: to all/just owner/silent
    sms_announce: the choice represents the state of sending sms values: to all/just owner/silent
    manual_cashout: the indicator which says the owner can create manual cashout or not
    editable_members: the indicator which says owner can add or modify members
        of the cashbox or not (after activation)
    """
    name = models.CharField(max_length=100, default="")
    image_id = models.IntegerField(default=1)  # 1Based
    slug = models.CharField(max_length=10, default=default_cashbox_slug)
    state = models.CharField(
        max_length=10,
        choices=choice.CASHBOX_STATE,
        default=choice.CASHBOX_STATE_UNPAID,
    )
    period_index = models.IntegerField(default=1)  # 1Base
    bank_account = models.ForeignKey(
        "account_management.Bankaccount",
        on_delete=models.SET_NULL,
        related_name="cashboxes",
        null=True,
        blank=True,
    )
    commission_type = models.CharField(
        _("Commission Type"),
        max_length=5,
        choices=choice.CASHBOX_COMMISSION_TYPE,
        default=choice.CASHBOX_COMMISSION_TYPE_REGULAR,
    )
    trust_state = models.CharField(
        _("Trust State"),
        max_length=5,
        choices=choice.TRUST_STATE,
        default=choice.TRUST_STATE_TRUSTED,
    )
    type = models.CharField(
        _("Cashbox Type"),
        choices=choice.CASHBOX_TYPES,
        default=choice.CASHBOX_TYPE_PAYABLE,
        max_length=10)
    web_key = models.CharField(
        _("Web Key"),
        max_length=20,
        default="",
        null=True,
        blank=True
    )
    is_test = models.BooleanField(
        _("Is Test"),
        default=False
    )
    is_archived = models.BooleanField(
        _("Is Archived"),
        default=False
    )
    is_draft = models.BooleanField(
        _("Is Draft"),
        default=False
    )
    notification_announce = models.CharField(
        _("Notification Announce"),
        max_length=10,
        choices=choice.ANNOUNCE_STATE,
        default=choice.ANNOUNCEMENT_MODE_JUST_OWNER,
    )
    sms_announce = models.CharField(
        _("SMS Announce"),
        max_length=10,
        choices=choice.ANNOUNCE_STATE,
        default=choice.ANNOUNCEMENT_MODE_JUST_OWNER,
    )
    manual_cashout = models.BooleanField(
        _("Manual Cashout"),
        default=False
    )
    editable_members = models.BooleanField(
        _("Editable Members"),
        default=False
    )

    orders = GenericRelation(to='payment.Order', object_id_field='box_id', content_type_field='box_type')

    short_url = models.CharField(
        _("Short URL"), max_length=70, default="", null=True, blank=True
    )

    class Meta:
        verbose_name = _("Cashbox")
        verbose_name_plural = _("Cashboxes")

    def __str__(self):
        return "%s (%s)" % (self.name, self.slug)

    @property
    def service_package(self):
        return get_cashbox_service_package(self)

    @property
    def service_package_remaining_days(self):
        order = get_last_successful_order(self)
        if order:
            return (order.end_date - timezone.now().date()).days

    @property
    def balance(self):
        return (self.get_current_period().balance
                if self.get_current_period() is not None else 0)

    @property
    def overall_balance(self):
        return self.bank_balance + self.hamyan_balance + self.inprogress_balance

    @property
    def bank_balance(self):
        return self.get_current_period().bank_balance

    @property
    def hamyan_balance(self):
        return self.get_current_period().hamyan_balance

    @property
    def inprogress_balance(self):
        return self.get_current_period().inprogress_balance

    @property
    def owner(self):
        if self.get_current_period() is not None:
            return self.get_current_period().owner()
        else:
            periods = Period.objects.filter(cashbox=self, index=self.period_index)
            if periods.count() == 0:
                return None
            else:
                periods.first().owner()

    @property
    def owner_name(self):
        return self.owner.name

    @property
    def owner_membership(self):
        return self.get_current_period().owner_membership()

    @property
    def remaining_days_to_draw(self):
        return (
            (
                    self.get_current_period().get_current_cycle().draw_date - date.today()
            ).days
            if self.state == choice.CASHBOX_STATE_ACTIVATED
            else 1000000
        )

    @property
    def is_removable(self):
        orders = self.orders.all()
        for order in orders:
            transaction = order.transaction
            if transaction.state == choice.TRANSACTION_STATE_SUCCESSFUL:
                if self.service_package_remaining_days > 0:
                    return False

        if self.state != choice.CASHBOX_STATE_ACTIVATED and self.period_index <= 1:
            # cashbox is not active and period index is <= 1, it is removable
            return True
        # cashbox is active
        period = self.get_current_period()
        if not period.is_terminated:
            cycles = period.cycles.all()
            # cashbox is in first period, check further constraints
            successful_transactions = Transaction.objects.filter(
                destination__in=(
                    choice.TRANSACTION_DST_HAMYAN_BOX_BALANCE,
                    choice.TRANSACTION_DST_BOX_BANKACCOUNT
                ),
                state=choice.TRANSACTION_STATE_SUCCESSFUL,
                ctx_id__in=[cycle.id for cycle in cycles],
                ctx_type=choice.TRANSACTION_CTX_TYPE_CYCLE,
            )
            if successful_transactions.count() == 0:
                return True
            else:
                return False
        return True

    @property
    def web_url(self):
        return self.get_or_assign_web_url()

    @property
    def is_worried_box(self):
        return self.trust_state in (choice.TRUST_STATE_WORRIED_UNVERIFIED,
                                    choice.TRUST_STATE_WORRIED_IN_PROGRESS,
                                    choice.TRUST_STATE_WORRIED_VERIFIED)

    @property
    def mux_list(self):
        the_list = list()
        if (self.bank_account is not None
                and self.bank_account.has_payping_account
                and self.bank_account.payping_user.verification_state == choice.VERIFICATION_STATE_VERIFIED):
            the_list.append(
                {'type': choice.MUX_TYPE_PAYPING}
            )
        if len(the_list) == 0 and self.trust_state in (choice.TRUST_STATE_WORRIED_IN_PROGRESS,
                                                       choice.TRUST_STATE_WORRIED_VERIFIED):
            the_list.append(
                {'type': choice.MUX_TYPE_HAMYAN}
            )
        return the_list

    def get_last_cycle_unpaid_winners(self, caller_membership):
        # last or current cycle
        result = list()
        if caller_membership is not None and caller_membership.role == choice.CASHBOX_ROLE_OWNER:
            period = self.get_current_period()
            current_cycle = period.get_current_cycle()
            if current_cycle is not None:
                cycles = Cycle.objects.filter(index__in=(int(current_cycle.index - 1), current_cycle.index),
                                              period__cashbox=self)
                for cycle in cycles:
                    if cycle is not None:
                        winners = cycle.winners.all()
                        for winner in winners:
                            if self.is_draft:
                                if winner.created > self.created:
                                    if not winner.has_cashout:
                                        result.append(winner)
                            else:
                                if not winner.has_cashout:
                                    result.append(winner)

        return result

    def get_current_period(self):
        period = Period.objects.filter(
            cashbox=self, index=self.period_index).order_by("-created").first()
        if period is not None:
            return period

        return None

    def get_owner(self):
        return self.get_current_period().owner()

    def get_cycles(self):
        return Cycle.objects.filter(
            period__cashbox=self
        )
        # cycles = list()
        # for period in self.periods.all():
        #     for cycle in period.cycles.all():
        #         cycles.append(cycle)
        # return cycles

    def draw_cycle_and_start_new(self, winner=None):
        """
        makes the draw done and starts a new cycle
        :param winner: a Member object, if the draw is manual and None if the draw is automatic
        :return: None if cashbox is Inactive or the cycle is drawn, otherwise returns winner member
        """
        if self.state == choice.CASHBOX_STATE_INACTIVATED:
            return None

        cycle = self.get_current_period().get_current_cycle()
        # handle both automatic & manual
        winner = cycle.draw(winner)

        if self.get_current_period().number_of_remained_cycles > 0:
            # there are some shares remained to win
            self.get_current_period().create_new_cycle()
        else:  # all shares have been won, terminate the period
            self.state = choice.CASHBOX_STATE_INACTIVATED

        self.save()

        return winner

    def draw(
            self, winners_count=-1, drawable_list=None, amount=-1, create_cashouts=True
    ):
        if self.state == choice.CASHBOX_STATE_INACTIVATED:
            return None

        if drawable_list is None or len(drawable_list) == 0:
            drawable_list = self.get_current_period().get_weighted_drawable_list()

        if create_cashouts:
            if winners_count * amount > self.balance:
                error_logger.error("Cannot draw with cashouts sum bigger than balance")
                error_logger.error("{} : {} ".format(self.id, smart_text(self.name)))
                return -1

        from cashbox_management.utils import choose_winners

        if winners_count in (-1, 0):
            winners_count = self.get_current_period().number_of_loans

        winners = choose_winners(
            drawable_list=drawable_list, winners_count=winners_count, amount=amount
        )

        if winners is None:
            return -2

        if create_cashouts:
            for winner in winners:
                self.create_cashout_for_winner(winner=winner)

        return winners

    def is_in_trial_time(self):
        return (
                self.period_index == 1
                and self.get_current_period().cycle_index
                <= self.commission.number_of_trial_cycles
        )

    def get_cycle_commission(self):
        if self.is_in_trial_time():
            return 0
        else:
            return self.commission.cycle_commission

    def is_financially_satisfied(self):
        return self.balance == self.get_current_period().satisfactory_amount

    def get_last_winners_list(self):
        return [
            winner
            for winner in Winner.objects.filter(
                cycle=self.get_current_period().get_current_cycle()
            )
        ]

    # Accessor & Mutator

    def set_state(self, state):
        self.state = state
        self.save()

    def archive(self):
        self.is_archived = True
        self.save()

    def set_test(self):
        self.is_test = True
        self.save()

    # Balance methods

    def checkout_balance_and_reset(self):
        returned_balance = self.balance
        for membership in self.get_current_period().get_valid_memberships():
            membership.reset_balance()
        self.save()
        return returned_balance

    # Cashout methods

    def create_cashout(
            self,
            amount=0,
            account=None,
            member=None,
            state=choice.TRANSACTION_STATE_INIT,
            send_sms=False,
    ):
        if amount > self.balance:
            error_logger.error(smart_text(self.name))
            error_logger.error("amount is bigger than cashout balance")

            return None

        if member is None:
            error_logger.error(smart_text(smart_text(self.name)))
            error_logger.error("Member is None")

            return None

        # remaining = amount

        # for m in self.get_current_period().get_valid_memberships():
        #     if remaining == 0:
        #         break
        #     if m.balance >= remaining:
        #         m.withdraw_balance(remaining)
        #         remaining = 0
        #         break

        #     remaining -= m.balance
        # m.reset_balance()

        trans = Transaction.objects.create(
            source=choice.TRANSACTION_SRC_HAMYAN_BOX_BALANCE,
            destination=choice.TRANSACTION_DST_MEMBER_BANKACCOUNT,
            ctx_id=self.get_current_period().get_current_cycle().id,
            ctx_type=choice.TRANSACTION_CTX_TYPE_CYCLE,
            payer=self.get_owner(),
            receiver=member,
            amount=amount,
            bank_account=account,
            state=state,
        )

        if send_sms:
            trans.send_cashout_process_announcement_message()
            trans.send_cashout_process_announcement_sms()

        return trans

    def create_cashout_for_winner(
            self, winner, state=choice.TRANSACTION_STATE_INIT, send_sms=False
    ):
        if winner.membership is not None and winner.share_group is None:
            # winner is a membership and have a complete share
            return self.create_cashout(
                amount=winner.loan_amount,
                state=state,
                send_sms=send_sms,
                member=winner.member,
            )
        elif winner.membership is None and winner.share_group is not None:
            # winner is a share group and loan amount should be divided
            number_of_creation = 0
            for membership in winner.share_group.memberships.all():
                amount = (
                        winner.loan_amount
                        * membership.share_residue
                        / winner.cycle.period.share_value
                )
                if self.create_cashout(
                        amount=amount,
                        member=membership.member,
                        state=state,
                        send_sms=send_sms,
                ):
                    number_of_creation += 1
            return number_of_creation == winner.share_group.number_of_portions

        # some error in assigning occurs
        return False

    def charge_bank_balance(self, amount):
        return self.get_current_period().charge_bank_balance(amount)

    def discharge_from_bank_balance(self, amount):
        return self.get_current_period().discharge_bank_balance(amount)

    def can_change_trust_state(self):
        cycle = self.get_current_period().get_current_cycle()
        if cycle is not None:
            return not Transaction.objects.filter(ctx_type=choice.TRANSACTION_CTX_TYPE_CYCLE, ctx_id=cycle.id,
                                                  state=choice.TRANSACTION_STATE_SUCCESSFUL).exists()
        return True

    # Messaging Helper methods

    def get_notification_members(self):
        if self.is_archived:
            return []
        if self.notification_announce == choice.ANNOUNCEMENT_MODE_SILENT:
            return []

        if self.notification_announce == choice.ANNOUNCEMENT_MODE_JUST_OWNER:
            return [
                membership.member
                for membership in Membership.objects.filter(
                    period=self.get_current_period(), role="own"
                )
            ]

        return [
            membership.member
            for membership in Membership.objects.filter(
                period=self.get_current_period()
            )
        ]

    def get_sms_members(self):
        if self.is_archived:
            return []
        if self.sms_announce == choice.ANNOUNCEMENT_MODE_SILENT:
            return []

        if self.sms_announce == choice.ANNOUNCEMENT_MODE_JUST_OWNER:
            return [
                membership.member
                for membership in Membership.objects.filter(
                    period=self.get_current_period(), role="own"
                )
            ]

        return [
            membership.member
            for membership in Membership.objects.filter(
                period=self.get_current_period()
            )
        ]

    def update_trust_state(self, state=None):
        if state is None:
            state = choice.TRUST_STATE_TRUSTED
        self.trust_state = state
        self.save()

    # Message methods

    def send_create_cashbox_message(self):
        if self.is_archived:
            return None

        message_body = msg.CASHBOX_CREATE_MSG.format(self.name)
        send_message_to_member(
            member=self.get_owner(),
            action=choice.MESSAGE_ACTION_CASHBOX,
            params=self.id,
            body=message_body,
        )

    def send_activation_messages(self):
        if self.is_archived:
            return None

        message_body = msg.CASHBOX_ACTIVATION_MSG.format(self.name)
        send_message_to_member_list(
            member_list=self.get_current_period().get_valid_members(),
            action=choice.MESSAGE_ACTION_CASHBOX,
            params=self.id,
            body=message_body,
        )

    def send_cashbox_update_messages(self):
        if self.is_archived:
            return None

        message_body = msg.CASHBOX_UPDATE_MSG.format(self.name)
        send_message_to_member_list(
            member_list=self.get_current_period().get_valid_members(),
            action=choice.MESSAGE_ACTION_CASHBOX,
            params=self.id,
            body=message_body,
        )

    def send_pay_reminder_messages(self):
        if self.is_archived:
            return None
        if (self.get_current_period().get_current_cycle()
                and self.get_current_period().get_current_cycle().is_drawn):
            # the current cycle is already drawn and finished
            return None

        members = self.get_current_period().get_unpaid_members()
        if len(members) == 0:
            return
        message_body = msg.PAY_REMINDER_MSG.format(
            self.remaining_days_to_draw, self.name
        )

        send_message_to_member_list(
            member_list=members,
            action=choice.MESSAGE_ACTION_PAY,
            params=self.id,
            body=message_body,
        )

    def send_cycle_winner_announcement_messages(self, winners, draw_type=choice.DRAW_MANUAL):
        """
        send the cycle winner message
        :param winners: list of winners in the cycle
        :param draw_type: type of draw that have a default of DRAW_MANUAL
        :return: none
        """
        if self.is_archived:
            return None

        if not self.get_current_period().is_terminated:
            winning_cycle_index = self.get_current_period().cycle_index - 1
        else:
            winning_cycle_index = self.get_current_period().cycle_index

        draw_text = DRAW_TYPE_MANUAL
        if draw_type == choice.DRAW_AUTOMATIC:
            draw_text = DRAW_TYPE_AUTOMATIC
        elif draw_type == choice.DRAW_SEMI_AUTOMATIC:
            draw_text = DRAW_TYPE_SEMI_AUTOMATIC

        if self.get_current_period().number_of_loans > 1:
            # create un-named winner announce msg
            message_body = msg.CYCLE_WINNER_ANNOUNCEMENT_MSG.format(
                winning_cycle_index, self.name, draw_text
            )
        else:
            # create named winner announce msg
            message_body = msg.CYCLE_WINNER_NAMED_ANNOUNCEMENT_MSG.format(
                winning_cycle_index, self.name, draw_text, winners[0].name
            )
        other_members = self.get_current_period().get_valid_members()

        for winner in winners:
            if winner.winner_type == "membership":
                if other_members.__contains__(winner.member):
                    other_members.remove(winner.member)
            elif winner.winner_type == "share_group":
                for winner_member in winner.members:
                    if other_members.__contains__(winner_member):
                        other_members.remove(winner_member)

        if len(other_members) == 0:
            return
        send_message_to_member_list(
            member_list=other_members,
            action=choice.MESSAGE_ACTION_CASHBOX,
            params=self.id,
            body=message_body,
        )

    def send_winner_self_announcement_message(self, winners, draw_type=choice.DRAW_MANUAL):
        if self.is_archived:
            return None

        if not self.get_current_period().is_terminated:
            winning_cycle_index = self.get_current_period().cycle_index - 1
        else:
            winning_cycle_index = self.get_current_period().cycle_index

        winners = self.get_last_winners_list()

        draw_text = DRAW_TYPE_MANUAL
        if draw_type == choice.DRAW_AUTOMATIC:
            draw_text = DRAW_TYPE_AUTOMATIC
        elif draw_type == choice.DRAW_SEMI_AUTOMATIC:
            draw_text = DRAW_TYPE_SEMI_AUTOMATIC

        for winner in winners:
            message_body = msg.WINNER_SELF_ANNOUNCEMENT_MSG.format(
                winner.name, winning_cycle_index, self.name, draw_text
            )
            if winner.winner_type == "membership":
                send_message_to_member(
                    member=winner.member,
                    action=choice.MESSAGE_ACTION_CASHBOX,
                    params=self.id,
                    body=message_body,
                )
            if winner.winner_type == "share_group":
                for winner_member in winner.members:
                    send_message_to_member(
                        member=winner_member,
                        action=choice.MESSAGE_ACTION_CASHBOX,
                        params=self.id,
                        body=message_body,
                    )

    def send_member_payment_announcement_messages(self, payer_member, receiver_member, amount):
        if self.is_archived:
            return None

        message_body = msg.MEMBER_PAYMENT_ANNOUNCEMENT_MSG.format(
            self.name, comma_separate(amount), receiver_member.name
        )
        if payer_member.id == receiver_member.id:
            for member in self.get_current_period().get_valid_members():
                send_message_to_member(
                    member=member,
                    action=choice.MESSAGE_ACTION_CASHBOX,
                    params=self.id,
                    body=message_body,
                )
        else:
            for member in self.get_current_period().get_valid_members():
                if receiver_member.id == member.id:
                    receiver_body = msg.MEMBER_PAYMENT_ANNOUNCEMENT_RECEIVER_MSG.format(
                        payer_member.name, self.name, comma_separate(amount)
                    )

                    send_message_to_member(
                        member=member,
                        action=choice.MESSAGE_ACTION_CASHBOX,
                        params=self.id,
                        body=receiver_body,
                    )
                else:
                    send_message_to_member(
                        member=member,
                        action=choice.MESSAGE_ACTION_CASHBOX,
                        params=self.id,
                        body=message_body,
                    )

    # Notification methods

    def send_activation_notifications(self):
        if self.is_archived:
            return None

        message_body = notif.CASHBOX_ACTIVATION_BODY.format(self.name)
        send_notification_to_member_list(
            notif.CASHBOX_ACTIVATION_TITLE,
            message_body,
            self.get_notification_members(),
            notif_data=create_page_notification_data(
                page=NOTIFICATION_ACTION_FIELD_CASHBOX_DETAIL, cashbox_id=self.id
            ),
        )

    def send_draw_notifications(self):
        if self.is_archived:
            return None

        if not self.get_current_period().is_terminated:
            winning_cycle_index = self.get_current_period().cycle_index - 1
        else:
            winning_cycle_index = self.get_current_period().cycle_index
        message_body = notif.CYCLE_DRAW_BODY.format(winning_cycle_index, self.name)
        send_notification_to_member_list(
            notif.CYCLE_DRAW_TITLE, message_body, self.get_notification_members()
        )

    def send_cashbox_update_notifications(self):
        if self.is_archived:
            return None

        message_body = notif.CASHBOX_UPDATE_BODY.format(self.name)
        send_notification_to_member_list(
            notif.CASHBOX_UPDATE_TITLE,
            message_body,
            self.get_notification_members(),
            notif_data=create_page_notification_data(
                page=NOTIFICATION_ACTION_FIELD_CASHBOX_DETAIL, cashbox_id=self.id
            ),
        )

    def send_pay_reminder_notification(self):
        if self.is_archived:
            return None
        if self.notification_announce == choice.ANNOUNCEMENT_MODE_SILENT:
            return None
        if (self.get_current_period().get_current_cycle()
                and self.get_current_period().get_current_cycle().is_drawn):
            # the current cycle is already drawn and finished
            return None

        if self.notification_announce == choice.ANNOUNCEMENT_MODE_JUST_OWNER:
            target_members = [
                membership.member
                for membership in Membership.objects.filter(
                    period=self.get_current_period(),
                    role=choice.CASHBOX_ROLE_OWNER
                )
                if membership.balance < membership.share_amount
            ]
        else:
            target_members = self.get_current_period().get_unpaid_members()

        if len(target_members) == 0:
            return

        message_body = notif.PAY_REMINDER_BODY.format(
            self.remaining_days_to_draw, self.name
        )

        send_notification_to_member_list(
            notif.PAY_REMINDER_TITLE,
            message_body,
            target_members,
            notif_data=create_page_notification_data(
                page=NOTIFICATION_ACTION_FIELD_CASHBOX_PAYMENT, cashbox_id=self.id
            ),
        )

    def send_cycle_winner_announcement_notifications(self, winners, draw_type=choice.DRAW_MANUAL):
        """
        send the cycle winner notifications
        :param winners: list of winners in the cycle
        :param draw_type: type of draw that have a default of DRAW_MANUAL
        :return: none
        """
        if self.is_archived:
            return None
        if self.notification_announce == choice.ANNOUNCEMENT_MODE_SILENT:
            return

        if not self.get_current_period().is_terminated:
            winning_cycle_index = self.get_current_period().cycle_index - 1
        else:
            winning_cycle_index = self.get_current_period().cycle_index

        draw_text = DRAW_TYPE_MANUAL
        if draw_type == choice.DRAW_AUTOMATIC:
            draw_text = DRAW_TYPE_AUTOMATIC
        elif draw_type == choice.DRAW_SEMI_AUTOMATIC:
            draw_text = DRAW_TYPE_SEMI_AUTOMATIC

        if self.get_current_period().number_of_loans > 1:
            message_body = notif.CYCLE_WINNER_ANNOUNCEMENT_BODY.format(
                winning_cycle_index, self.name, draw_text
            )
        else:
            message_body = notif.CYCLE_WINNER_NAMED_ANNOUNCEMENT_BODY.format(
                winning_cycle_index, self.name, draw_text, winners[0].name
            )

        other_members = self.get_current_period().get_valid_members()

        for winner in winners:
            if winner.winner_type == "membership":
                if other_members.__contains__(winner.member):
                    other_members.remove(winner.member)
            elif winner.winner_type == "share_group":
                for winner_member in winner.members:
                    if other_members.__contains__(winner_member):
                        other_members.remove(winner_member)

        if len(other_members) == 0:
            return

        send_notification_to_member_list(
            notif.CYCLE_WINNER_ANNOUNCEMENT_TITLE,
            message_body,
            other_members,
            notif_data=create_page_notification_data(
                page=NOTIFICATION_ACTION_FIELD_MAIN
            ),
        )

    def send_winner_self_announcement_notification(self, winners, draw_type=choice.DRAW_MANUAL):
        if self.is_archived:
            return None
        if self.notification_announce == choice.ANNOUNCEMENT_MODE_SILENT:
            return

        if not self.get_current_period().is_terminated:
            winning_cycle_index = self.get_current_period().cycle_index - 1
        else:
            winning_cycle_index = self.get_current_period().cycle_index

        draw_text = DRAW_TYPE_MANUAL
        if draw_type == choice.DRAW_AUTOMATIC:
            draw_text = DRAW_TYPE_AUTOMATIC
        elif draw_type == choice.DRAW_SEMI_AUTOMATIC:
            draw_text = DRAW_TYPE_SEMI_AUTOMATIC

        for winner in winners:
            message_body = notif.WINNER_SELF_ANNOUNCEMENT_BODY.format(
                winner.name, winning_cycle_index, self.name, draw_text
            )
            if winner.winner_type == "membership":
                membership = Membership.objects.filter(
                    member=winner.member, period=self.get_current_period()
                ).first()
                if (
                        membership.role != choice.CASHBOX_ROLE_OWNER
                        and self.notification_announce
                        == choice.ANNOUNCEMENT_MODE_JUST_OWNER
                ):
                    continue

                send_notification_to_member(
                    notif.WINNER_SELF_ANNOUNCEMENT_TITLE,
                    message_body,
                    winner.member,
                    notif_data=create_page_notification_data(
                        page=NOTIFICATION_ACTION_FIELD_CASHBOX_DETAIL,
                        cashbox_id=self.id,
                    ),
                )
            if winner.winner_type == "share_group":
                for winner_member in winner.members:
                    send_notification_to_member(
                        notif.WINNER_SELF_ANNOUNCEMENT_TITLE,
                        message_body,
                        winner_member,
                        notif_data=create_page_notification_data(
                            page=NOTIFICATION_ACTION_FIELD_CASHBOX_DETAIL,
                            cashbox_id=self.id,
                        ),
                    )

            return winners

    def send_member_payment_announcement_notifications(self, payer_member, receiver_member, amount):
        if self.is_archived:
            return None
        if self.notification_announce == choice.ANNOUNCEMENT_MODE_SILENT:
            return

        message_body = notif.MEMBER_PAYMENT_ANNOUNCEMENT_BODY.format(
            self.name, comma_separate(amount), receiver_member.name
        )

        if payer_member.id == receiver_member.id:
            for member in self.get_notification_members():
                if payer_member.id == member.id:
                    continue

                send_notification_to_member(
                    notif.MEMBER_PAYMENT_ANNOUNCEMENT_TITLE,
                    message_body,
                    member,
                    notif_data=create_page_notification_data(
                        page=NOTIFICATION_ACTION_FIELD_CASHBOX_DETAIL,
                        cashbox_id=self.id,
                    ),
                )
        else:
            for member in self.get_notification_members():
                if payer_member.id == member.id:
                    continue

                if receiver_member.id == member.id:
                    receiver_body = notif.MEMBER_PAYMENT_ANNOUNCEMENT_RECEIVER_BODY.format(
                        payer_member.name, self.name, comma_separate(amount)
                    )
                    send_notification_to_member(
                        notif.MEMBER_PAYMENT_ANNOUNCEMENT_RECEIVER_TITLE,
                        receiver_body,
                        member,
                        notif_data=create_page_notification_data(
                            page=NOTIFICATION_ACTION_FIELD_CASHBOX_DETAIL,
                            cashbox_id=self.id,
                        ),
                    )
                else:
                    send_notification_to_member(
                        notif.MEMBER_PAYMENT_ANNOUNCEMENT_TITLE,
                        message_body,
                        member,
                        notif_data=create_page_notification_data(
                            page=NOTIFICATION_ACTION_FIELD_CASHBOX_DETAIL,
                            cashbox_id=self.id,
                        ),
                    )

    # new announcement methods

    def send_cycle_winner_announcement(self, winners, draw_type=choice.DRAW_MANUAL):
        """
        send the cycle winner message
        :param winners: list of winners in the cycle
        :param draw_type: type of draw that have a default of DRAW_MANUAL
        :return: none
        """
        if self.is_archived:
            return None
        if not self.get_current_period().is_terminated:
            winning_cycle_index = self.get_current_period().cycle_index - 1
        else:
            winning_cycle_index = self.get_current_period().cycle_index

        draw_text = DRAW_TYPE_MANUAL
        if draw_type == choice.DRAW_AUTOMATIC:
            draw_text = DRAW_TYPE_AUTOMATIC
        elif draw_type == choice.DRAW_SEMI_AUTOMATIC:
            draw_text = DRAW_TYPE_SEMI_AUTOMATIC

        members = self.get_current_period().get_valid_members()

        for winner in winners:
            if winner.winner_type == 'membership':
                if members.__contains__(winner.member):
                    members.remove(winner.member)
            elif winner.winner_type == 'share_group':
                for winner_member in winner.members:
                    if members.__contains__(winner_member):
                        members.remove(winner_member)
        winners_name = winners[0].name
        if len(winners) > 1:
            winners_name = list_winners_to_string(winners)
        announce = Announce(template=template_choice.CASHBOX_INFORM_DRAW, receiver=members, many=True)
        announce.generate_msg(
            name=self.name,
            cycle_index=winning_cycle_index,
            draw_type=draw_text,
            winners_name=winners_name,
        )
        announce.send_sms()
        announce.send_message()
        announce.send_notification()

    def send_winner_self_announcement(self, winners, draw_type=choice.DRAW_MANUAL):
        if self.is_archived:
            return None

        if not self.get_current_period().is_terminated:
            winning_cycle_index = self.get_current_period().cycle_index - 1
        else:
            winning_cycle_index = self.get_current_period().cycle_index

        draw_text = DRAW_TYPE_MANUAL
        if draw_type == choice.DRAW_AUTOMATIC:
            draw_text = DRAW_TYPE_AUTOMATIC
        elif draw_type == choice.DRAW_SEMI_AUTOMATIC:
            draw_text = DRAW_TYPE_SEMI_AUTOMATIC

        if len(winners) > 1:
            for winner in winners:
                tmp_winners = winners.copy()
                tmp_winners.remove(winner)
                winners_name_str = list_winners_to_string(tmp_winners)
                announce = Announce(
                    template=template_choice.CASHBOX_DRAW_NAMED_SOME_WINNER_BILL,
                    receiver=winner.member
                )
                announce.generate_msg(
                    name=self.name,
                    cycle_index=winning_cycle_index,
                    receiver_name=winner.member.name,
                    draw_type=draw_text,
                    winners_str=winners_name_str,
                )
                announce.send_sms()
                announce.send_message()
                announce.send_notification()
        else:
            winner = winners[0]
            if winner.winner_type == "membership":
                announce = Announce(
                    template=template_choice.CASHBOX_DRAW_NAMED_WINNER_BILL,
                    receiver=winner.member
                )
                announce.generate_msg(
                    name=self.name,
                    cycle_index=winning_cycle_index,
                    receiver_name=winner.member.name,
                    draw_type=draw_text
                )
                announce.send_sms()
                announce.send_message()
                announce.send_notification()
            elif winner.winner_type == "share_group":
                for winner_member in winner.members:
                    announce = Announce(
                        template=template_choice.CASHBOX_DRAW_NAMED_WINNER_BILL,
                        receiver=winner_member
                    )
                    announce.generate_msg(
                        name=self.name,
                        cycle_index=winning_cycle_index,
                        receiver_name=winner_member.name,
                        draw_type=draw_text
                    )
                    announce.send_sms()
                    announce.send_message()
                    announce.send_notification()

    # Sms methods

    def send_activation_sms(self):
        if self.is_archived or self.is_test:
            return None

        memberships = self.get_current_period().get_valid_memberships()

        for membership in memberships:
            membership.send_cashbox_activation_sms()

    def send_pay_reminder_sms(self):
        if self.is_archived or self.is_test or not self.has_perm(choice.FEATURE_SMS_ANNOUNCEMENT):
            return None
        if (self.get_current_period().get_current_cycle()
                and self.get_current_period().get_current_cycle().is_drawn):
            # the current cycle is already drawn and finished
            return None
        if self.sms_announce == choice.ANNOUNCEMENT_MODE_SILENT:
            return

        if self.sms_announce == choice.ANNOUNCEMENT_MODE_JUST_OWNER:
            members = [
                membership
                for membership in Membership.objects.filter(
                    period=self.get_current_period(),
                    role=choice.CASHBOX_ROLE_OWNER
                )
                if membership.balance < membership.share_amount
            ]
        else:
            members = [
                membership
                for membership in Membership.objects.filter(
                    period=self.get_current_period()
                )
                if membership.balance < membership.share_amount
            ]
        if len(members) == 0:
            return

        for member in members:
            send_high_priority_templated_sms.delay(
                phone_number=member.phone_number,
                template=sms_templates.REMINDER,
                args=(
                    self.remaining_days_to_draw,
                    spacey(self.name),
                    member.get_web_short_url(),
                ),
            )

    def send_winner_self_announcement_sms(self, winners, draw_type=choice.DRAW_MANUAL):
        if self.is_archived or self.is_test or not self.has_perm(choice.FEATURE_SMS_ANNOUNCEMENT):
            return None
        if self.sms_announce == choice.ANNOUNCEMENT_MODE_SILENT:
            return

        if not self.get_current_period().is_terminated:
            winning_cycle_index = self.get_current_period().cycle_index - 1
        else:
            winning_cycle_index = self.get_current_period().cycle_index
        draw_text = DRAW_TYPE_MANUAL
        if draw_type == choice.DRAW_AUTOMATIC:
            draw_text = DRAW_TYPE_AUTOMATIC
        elif draw_type == choice.DRAW_SEMI_AUTOMATIC:
            draw_text = DRAW_TYPE_SEMI_AUTOMATIC
        cycles = self.get_current_period().cycles.filter(index=winning_cycle_index)
        for winner in winners:
            if winner.winner_type == "membership":
                if (
                        winner.membership.role != choice.CASHBOX_ROLE_OWNER
                        and self.sms_announce == choice.ANNOUNCEMENT_MODE_JUST_OWNER
                ):
                    continue

                ts = Transaction.objects.filter(
                    receiver=winner.member,
                    source=choice.TRANSACTION_SRC_HAMYAN_BOX_BALANCE,
                    ctx_id__in=[cycle.id for cycle in cycles],
                    ctx_type=choice.TRANSACTION_CTX_TYPE_CYCLE,
                )
                if ts.count() == 0:
                    send_high_priority_templated_sms.delay(
                        phone_number=winner.phone_number,
                        template=sms_templates.WINNER,
                        args=(
                            winning_cycle_index,
                            spacey(self.name),
                            spacey(draw_text),
                        ),
                    )
                else:
                    send_high_priority_templated_sms.delay(
                        phone_number=winner.phone_number,
                        template=sms_templates.WINNER_WEB,
                        args=(
                            winning_cycle_index,
                            spacey(self.name),
                            spacey(draw_text),
                            ts.first().get_web_short_url(),
                        ),
                    )
            elif winner.winner_type == "share_group":
                for winner_member in winner.members:
                    ts = Transaction.objects.filter(
                        receiver=winner_member,
                        source=choice.TRANSACTION_SRC_HAMYAN_BOX_BALANCE,
                        ctx_id__in=[cycle.id for cycle in cycles],
                        ctx_type=choice.TRANSACTION_CTX_TYPE_CYCLE,
                    )
                    if ts.count() == 0:
                        send_high_priority_templated_sms.delay(
                            phone_number=winner_member.phone_number,
                            template=sms_templates.WINNER,
                            args=(
                                winning_cycle_index,
                                spacey(self.name),
                                spacey(draw_text),
                            ),
                        )
                    else:
                        send_high_priority_templated_sms.delay(
                            phone_number=winner_member.phone_number,
                            template=sms_templates.WINNER_WEB,
                            args=(
                                winning_cycle_index,
                                spacey(self.name),
                                spacey(draw_text),
                                ts.first().get_web_short_url(),
                            ),
                        )
        return winners

    def send_draw_result_sms(self, winners, draw_type=choice.DRAW_MANUAL):
        if self.is_archived or self.is_test or not self.has_perm(choice.FEATURE_SMS_ANNOUNCEMENT):
            return None

        if not self.get_current_period().is_terminated:
            winning_cycle_index = self.get_current_period().cycle_index - 1
        else:
            winning_cycle_index = self.get_current_period().cycle_index
        draw_text = DRAW_TYPE_MANUAL
        if draw_type == choice.DRAW_AUTOMATIC:
            draw_text = DRAW_TYPE_AUTOMATIC
        elif draw_type == choice.DRAW_SEMI_AUTOMATIC:
            draw_text = DRAW_TYPE_SEMI_AUTOMATIC
        other_members = self.get_current_period().get_valid_members()
        for winner in winners:
            if winner.winner_type == "membership":
                if other_members.__contains__(winner.member):
                    other_members.remove(winner.member)
            elif winner.winner_type == "share_group":
                for winner_member in winner.members:
                    if other_members.__contains__(winner_member):
                        other_members.remove(winner_member)
        if len(other_members) == 0:
            return

        for member in other_members:
            if self.get_current_period().number_of_loans > 1:
                send_high_priority_templated_sms.delay(
                    phone_number=member.phone_number,
                    template=sms_templates.DRAW_RESULT,
                    args=(winning_cycle_index, spacey(self.name), spacey(draw_text)),
                )
            else:
                send_high_priority_templated_sms.delay(
                    phone_number=member.phone_number,
                    template=sms_templates.DRAW_NAMED_RESULT,
                    args=(
                        winning_cycle_index,
                        spacey(self.name),
                        spacey(draw_text),
                        spacey(winners[0].name),
                    ),
                )

    def get_or_assign_web_url(self):
        if self.web_key in (None, ''):
            self.web_key = generate_alphanumeric_uid(settings.CASHBOX_WEB_KEY_LENGTH)
            self.save()
        if self.short_url in (None, ''):
            web_url = CASHBOX_BASE_URL + self.web_key + "/"
            self.short_url = shorten_url(web_url)
            self.save()

        return self.short_url


@receiver(post_save, sender=Cashbox)
def assign_web_key(sender, instance, **kwargs):
    if instance.web_key is None or instance.web_key == "":
        instance.web_key = generate_alphanumeric_uid(settings.CASHBOX_WEB_KEY_LENGTH)
        instance.save()


@receiver(post_save, sender=Cashbox)
def create_commission(sender, instance, **kwargs):
    commissions = Commission.all_objects.filter(cashbox=instance).first()
    if commissions is None:
        commission = Commission.objects.create(cashbox=instance)
        commission.save()
