# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.db.models.signals import post_save
from django.dispatch.dispatcher import receiver
from django.utils.translation import ugettext_lazy as _

from cashbox_management.models.commission import Commission
from payment.models import Transaction
from utils.constants import choice
from utils.constants.default import WEB_APP_BASE_URL, WEB_DOWNLOAD_LINK
from utils.constants.notification_constant import (
    NOTIFICATION_ACTION_FIELD_CASHBOX_DETAIL,
)
from utils.firebase.notification import (
    send_notification_to_member,
    create_page_notification_data,
)
from utils.firebase.notification_templates import (
    MEMBERSHIP_INVITATION_BODY,
    MEMBERSHIP_INVITATION_TITLE,
    MEMBERSHIP_REQUEST_BODY,
    MEMBERSHIP_REQUEST_TITLE,
    MEMBERSHIP_REQUEST_ACCEPTANCE_BODY,
    MEMBERSHIP_REQUEST_ACCEPTANCE_TITLE,
    MEMBERSHIP_INVITATION_ACCEPTANCE_BODY,
    MEMBERSHIP_INVITATION_ACCEPTANCE_TITLE,
)
from utils.message.message import send_message_to_member
from utils.message.message_templates import (
    MEMBERSHIP_INVITE_MSG,
    MEMBERSHIP_REQUEST_MSG,
    MEMBERSHIP_REQUEST_ACCEPTANCE_MSG,
    MEMBERSHIP_INVITATION_ACCEPTANCE_MSG,
)
from utils.mixins import spacey, date_to_datetime
from utils.models import BaseModel
from utils.randomization import generate_alphanumeric_uid
from utils.shorten_url import shorten_url
from utils.tasks import send_high_priority_templated_sms
from utils.sms import sms_templates

MEMBERSHIP_BASE_URL = WEB_APP_BASE_URL + "account/cashbox/private/"


class Membership(BaseModel):
    """
    represents the membership of a service MEMBER to a specific PERIOD of a CASHBOX

    FIELDS
    member: the MEMBER object of the membership who becomes the member of the cashbox (its period)
    period: the PERIOD object which the member is assigned to
    role: the choice represented the role of the member in this period owner/normal
    percentage_balance: the percentage of the total balance of period
        which is covered by the membership payment
    number_of_shares: the number of the shares the member has in the period
    share_residue: the amount of the member has in a share group (if enrolled in any) in Tomans
    share_group: the share group object the membership is enrolled (if any)
    rosca_commission: the value of the ROSCA commission (if the CASHBOX is onw of them)
    local_score: the score is defined and calculated in the cashbox scope
    won_shares: the number or won shares
    web_key: the UUID key which is used and accessed in web application
    short_url: the shorted url which cab be accessed from web browser
    is_owner_accept: the indicator which say whether
        the owner accepts the enrollment or not (DEPRECATED always TRUE)
    is_member_accept: the indicator which say whether
        the member accepts the enrollment or not (DEPRECATED always TRUE)
    PROPERTIES
    non_won_shares: number of shares in the period which is NOT yet won in draw procedure
    """

    member = models.ForeignKey(
        "account_management.Member",
        on_delete=models.SET_NULL,
        related_name="period_memberships",
        null=True,
    )
    period = models.ForeignKey(
        "cashbox_management.Period",
        on_delete=models.CASCADE,
        related_name="membership_through",
    )
    role = models.CharField(
        max_length=10, choices=choice.CASHBOX_ROLE, default=choice.CASHBOX_ROLE_NORMAL
    )
    percentage_balance = models.FloatField(default=0)
    number_of_shares = models.IntegerField(default=1)
    share_residue = models.IntegerField(default=0, null=True, blank=True)
    share_group = models.ForeignKey(
        "cashbox_management.ShareGroup",
        on_delete=models.SET_NULL,
        related_name="memberships",
        null=True,
        blank=True,
    )
    rosca_commission = models.IntegerField(
        _("ROSCA Commission"),
        default=0)  # in Tomans
    local_score = models.FloatField(default=0.0, null=True)

    won_shares = models.IntegerField(default=0)
    web_key = models.CharField(max_length=20, default="", null=True, blank=True)
    short_url = models.CharField(max_length=50, default="", null=True, blank=True)

    # At least one of these fields should be True
    is_owner_accept = models.BooleanField(default=True)  # True -> member is invited
    is_member_accept = models.BooleanField(
        default=True
    )  # True -> member is requested to join

    class Meta:
        verbose_name = _("membership")
        verbose_name_plural = _("memberships")
        unique_together = ("member", "period", "id")
        ordering = ["-id"]

    def __str__(self):
        return "%s-%s" % (self.member.__str__(), self.period.__str__())

    @property
    def cashbox(self):
        return self.period.cashbox

    @property
    def name(self):
        return self.member.name

    @property
    def phone_number(self):
        return self.member.phone_number

    @property
    def have_cashout(self):
        if self.get_cashout() is not None:
            return True
        return False

    @property
    def cashout_state(self):
        cashouts = self.get_cashouts()
        if cashouts is not None:
            if cashouts.count() > 1:
                init_cashouts = [
                    init_cashout
                    for init_cashout in cashouts
                    if init_cashout.state == choice.TRANSACTION_STATE_INIT
                ]
                if len(init_cashouts) > 0:
                    return choice.TRANSACTION_STATE_INIT
                elif cashouts[0].state != choice.TRANSACTION_STATE_TO_BANK:
                    return choice.TRANSACTION_STATE_IN_PROGRESS
                else:
                    return cashouts[0].state
            elif cashouts.count() > 0:
                if cashouts[0].state != choice.TRANSACTION_STATE_TO_BANK:
                    return cashouts[0].state
                return choice.TRANSACTION_STATE_IN_PROGRESS

        return ""

    @property
    def cashout_amount(self):
        cashouts = self.get_cashouts()
        if cashouts is not None:
            if cashouts.count() > 1:
                init_cashouts = [
                    init_cashout
                    for init_cashout in cashouts
                    if init_cashout.state == choice.TRANSACTION_STATE_INIT
                ]
                if len(init_cashouts) > 0:
                    return init_cashouts[0].amount
                else:
                    return cashouts[0].amount
            elif cashouts.count() > 0:
                return cashouts[0].amount

        return 0

    @property
    def share_amount(self):
        """
        amount of money to be paid due to the shares (partial & net) of the membership
        :return:
        """
        return self.number_of_shares * self.period.share_value + self.share_residue

    @property
    def share_weight(self):
        """
        the membership's weight of total share (net + partial)
        :return:
        """
        return self.share_amount / self.period.share_value

    @property
    def commission(self):
        """
        the amount of commission to be paid by the MEMBERSHIP in each CYCLE  # noqa
        if the CASHBOX's commission type is regular the COMMISSION is calculated through the COMMISSION model of the CASHBOX  # noqa
        else if cashbox's commission type is ROSCA, the COMMISSION is fetched from the rosca_commission field directly  # noqa
        :return: the amount of the commission for the MEMBERSHIP  # noqa
        """
        if self.cashbox.commission_type == choice.CASHBOX_COMMISSION_TYPE_REGULAR:
            if self.cashbox.commission.is_manually_set:
                return self.cashbox.get_cycle_commission()
            elif self.cashbox.is_in_trial_time():
                return 0
            return Commission.calculate_cycle_commission(self.share_amount)
        elif self.cashbox.commission_type == choice.CASHBOX_COMMISSION_TYPE_ROSCA:
            return self.rosca_commission

    @property
    def remaining_share_amount(self):
        return self.calculate_remaining_share()

    @property
    def remaining_commission(self):
        return self.calculate_remaining_commission()

    @property
    def is_financially_satisfied(self):
        return self.balance == self.share_amount

    @property
    def non_won_shares(self):
        if self.is_valid() and (self.number_of_shares >= self.won_shares):
            return self.number_of_shares - self.won_shares
        else:
            return 0

    @property
    def have_partial_share(self):
        return self.share_group is not None

    @property
    def groupmates(self):
        return (
            Membership.objects.filter(share_group=self.share_group).exclude(pk=self.pk)
            if self.share_group is not None
            else None
        )

    # TODO
    @property
    def balance(self):
        return int(round(self.percentage_balance * self.period.balance))

    @property
    def global_credit(self):
        return self.member.global_credit

    def is_valid(self):
        if self.is_owner_accept and self.is_member_accept:
            return True
        return False

    # Setters

    def set_number_of_shares(self, number_of_shares):
        self.number_of_shares = number_of_shares
        self.save()

    # Share Group methods

    def get_groupmates(self):
        return (
            Membership.objects.filter(share_group=self.share_group).exclude(pk=self.pk)
            if self.share_group is not None
            else None
        )

    def reset_share_group(self):
        self.set_share_group(share_group=None, share_residue=0)

    def set_share_group(self, share_group, share_residue):
        self.share_group = share_group
        self.share_residue = share_residue
        self.save()

    # Score & Credit methods

    def calculate_local_score(self, origin_date, attenuator, alpha, days_factor):
        cycles = self.period.cycles.all()
        all_successful_transactions = Transaction.objects.filter(
            state=choice.TRANSACTION_STATE_SUCCESSFUL,
            receiver=self.member,
            ctx_id__in=[cycle.id for cycle in cycles],
            ctx_type=choice.TRANSACTION_CTX_TYPE_CYCLE,
            state_time__lte=date_to_datetime(origin_date),
        )
        membership_score = 0
        for tr in all_successful_transactions:
            delta_date = (
                origin_date - date_to_datetime(tr.state_time).replace(tzinfo=None)
            ).days
            if tr.source in (choice.TRANSACTION_SRC_GATEWAY, choice.TRANSACTION_SRC_HAMYAN_WALLET):
                membership_score += (
                    tr.amount / attenuator * (1 + alpha) ** (delta_date / days_factor)
                )
            elif tr.destination == choice.TRANSACTION_DST_MEMBER_BANKACCOUNT:
                membership_score -= (
                    tr.amount / attenuator * (1 + alpha) ** (delta_date / days_factor)
                )
        return membership_score

    # Balance methods

    def get_cashouts(self):
        for cycle in self.period.cycles.all():
            cashouts = Transaction.objects.filter(
                Q(source=choice.TRANSACTION_SRC_HAMYAN_BOX_BALANCE)
                & (
                    Q(state=choice.TRANSACTION_STATE_INIT)
                    | Q(state=choice.TRANSACTION_STATE_IN_PROGRESS)
                    | Q(state=choice.TRANSACTION_STATE_TO_BANK)
                )
                & Q(destination=choice.TRANSACTION_DST_MEMBER_BANKACCOUNT)
                & Q(ctx_id=cycle.id)
                & Q(ctx_type=choice.TRANSACTION_CTX_TYPE_CYCLE)
                & Q(receiver=self.member)
            )
            if cashouts.count() > 0:
                return cashouts.order_by("state")
        return None

    def get_cashout(self):
        cashouts = self.get_cashouts()
        if cashouts is not None:
            init_cashouts = [
                init_cashout
                for init_cashout in cashouts
                if init_cashout.state == choice.TRANSACTION_STATE_INIT
            ]
            if len(init_cashouts) > 0:
                return init_cashouts[0]
            return cashouts[0]
        return None

    def reset_balance(self, destination=choice.TRANSACTION_DST_HAMYAN_BOX_BALANCE):
        current_balance = self.balance
        self.percentage_balance = 0
        self.save()
        if destination == choice.TRANSACTION_DST_BOX_BANKACCOUNT:
            period = self.period.cashbox.get_current_period()
            period.bank_balance = period.bank_balance - current_balance
            period.save()
        return current_balance

    def reset(self, destination=choice.TRANSACTION_DST_HAMYAN_BOX_BALANCE):
        current_balance = self.balance
        self.percentage_balance = 0
        self.won_shares = 0
        self.save()
        if destination == choice.TRANSACTION_DST_BOX_BANKACCOUNT:
            period = self.period.cashbox.get_current_period()
            period.bank_balance = period.bank_balance - current_balance
            period.save()

    def make_winner(self):
        if self.won_shares == self.number_of_shares:
            return -1
        self.won_shares += 1
        self.save()
        return self.won_shares

    def unmake_winner(self):
        if self.won_shares > 0:
            self.won_shares -= 1
            self.save()

    def calculate_remaining_share(self):
        return self.share_amount - self.balance

    def calculate_remaining_commission(self):
        return (self.calculate_remaining_share() / self.share_amount) * self.commission

    def calculate_remaining_commission_per_amount(self, amount):
        cashbox = self.period.cashbox
        if (cashbox.has_perm(choice.FEATURE_ZERO_COMMISSION_PAYMENT)
                or not cashbox.has_perm(choice.FEATURE_PAYMENT)):
            return 0
        percentage = amount / self.share_amount
        return percentage * self.commission

    def get_web_url(self):
        return WEB_APP_BASE_URL + "private/" + str(self.web_key)

    def get_web_short_url(self):
        if self.short_url is None or self.short_url == "":
            self.short_url = shorten_url(self.get_web_url())
            self.save()

        if self.short_url == "":
            return self.get_web_url()

        return self.short_url

    def have_notification_announce(self):
        if self.cashbox.notification_announce == choice.ANNOUNCEMENT_MODE_SILENT:
            return False
        if self.cashbox.notification_announce == choice.ANNOUNCEMENT_MODE_JUST_OWNER:
            return self.role == choice.CASHBOX_ROLE_OWNER

        return True

    def have_sms_announce(self):
        if self.cashbox.sms_announce == choice.ANNOUNCEMENT_MODE_SILENT:
            return False
        if self.cashbox.sms_announce == choice.ANNOUNCEMENT_MODE_JUST_OWNER:
            return self.role == choice.CASHBOX_ROLE_OWNER

        return True

    # alert management methods
    # message methods

    def send_invitation_message(self):
        owner_name = self.period.membership_through.filter(
            role=choice.CASHBOX_ROLE_OWNER
        )[0].name
        cashbox_name = self.period.cashbox.name
        message_body = MEMBERSHIP_INVITE_MSG.format(owner_name, cashbox_name)

        send_message_to_member(
            member=self.member,
            action=choice.MESSAGE_ACTION_BOARD,
            params=self.cashbox.slug,
            body=message_body,
        )

    def send_request_message(self):
        message_body = MEMBERSHIP_REQUEST_MSG.format(self.name, self.cashbox.name)

        send_message_to_member(
            member=self.cashbox.owner,
            action=choice.MESSAGE_ACTION_BOARD,
            params=self.cashbox.id,
            body=message_body,
        )

    def send_request_acceptance_message(self):
        message_body = MEMBERSHIP_REQUEST_ACCEPTANCE_MSG.format(
            self.name, self.cashbox.name
        )

        send_message_to_member(
            member=self.member,
            action=choice.MESSAGE_ACTION_CASHBOX,
            params=self.cashbox.id,
            body=message_body,
        )

    def send_invitation_acceptance_message(self):
        message_body = MEMBERSHIP_INVITATION_ACCEPTANCE_MSG.format(
            self.name, self.cashbox.name
        )

        send_message_to_member(
            member=self.cashbox.owner,
            action=choice.MESSAGE_ACTION_CASHBOX,
            params=self.cashbox.id,
            body=message_body,
        )

    # Notification methods

    def send_request_notification(self):
        if not self.have_notification_announce():
            return

        message_body = MEMBERSHIP_REQUEST_BODY.format(self.name, self.cashbox.name)

        send_notification_to_member(
            MEMBERSHIP_REQUEST_TITLE, message_body, self.cashbox.owner
        )

    def send_invitation_notification(self, is_created):
        if not self.have_notification_announce():
            return

        message_body = MEMBERSHIP_INVITATION_BODY.format(
            self.cashbox.owner.name, self.cashbox.name
        )

        send_notification_to_member(
            MEMBERSHIP_INVITATION_TITLE,
            message_body,
            self.member,
            notif_data=create_page_notification_data(
                page=NOTIFICATION_ACTION_FIELD_CASHBOX_DETAIL,
                cashbox_id=self.cashbox.id,
            ),
        )

    def send_request_acceptance_notification(self):
        if not self.have_notification_announce():
            return

        message_body = MEMBERSHIP_REQUEST_ACCEPTANCE_BODY.format(
            self.name, self.cashbox.name
        )

        send_notification_to_member(
            MEMBERSHIP_REQUEST_ACCEPTANCE_TITLE, message_body, self.member
        )

    def send_invitation_acceptance_notification(self):
        if not self.have_notification_announce():
            return

        message_body = MEMBERSHIP_INVITATION_ACCEPTANCE_BODY.format(
            self.name, self.cashbox.name
        )

        send_notification_to_member(
            MEMBERSHIP_INVITATION_ACCEPTANCE_TITLE, message_body, self.cashbox.owner
        )

    # Sms methods

    def send_cashbox_activation_sms(self):
        # if not self.have_sms_announce():
        #     return
        # if not self.period.cashbox.has_perm(choice.FEATURE_SMS_ANNOUNCEMENT):
        #     return
        if not self.period.cashbox.has_perm(choice.FEATURE_PAYMENT):
            send_high_priority_templated_sms.delay(
                phone_number=self.phone_number,
                template=sms_templates.ACTIVATION,
                args=(
                    spacey(self.cashbox.name),
                    WEB_DOWNLOAD_LINK,
                ),
            )
        else:
            send_high_priority_templated_sms.delay(
                phone_number=self.phone_number,
                template=sms_templates.ACTIVATION_WITH_LINK,
                args=(
                    spacey(self.cashbox.name),
                    self.get_web_short_url(),
                    WEB_DOWNLOAD_LINK,
                ),
            )

    def send_invitation_sms(self, is_created):
        # if not self.have_sms_announce():
        #     return
        # if not self.period.cashbox.has_perm(choice.FEATURE_SMS_ANNOUNCEMENT):
        #     return
        if not self.period.cashbox.has_perm(choice.FEATURE_PAYMENT):
            send_high_priority_templated_sms.delay(
                phone_number=self.phone_number,
                template=sms_templates.INVITE_WITH_DOWNLOAD_APP_LINK,
                args=(spacey(self.cashbox.owner.name), spacey(self.cashbox.name), WEB_DOWNLOAD_LINK),
            )
        else:
            send_high_priority_templated_sms.delay(
                phone_number=self.phone_number,
                template=sms_templates.INVITE_WITH_LINK_AND_DOWNLOAD_LINK,
                args=(
                    spacey(self.cashbox.owner.name),
                    spacey(self.cashbox.name),
                    self.cashbox.get_or_assign_web_url(),
                    WEB_DOWNLOAD_LINK
                ),
            )

    def delete(self, using=None, force=False):
        self.is_member_accept = False
        self.is_owner_accept = False
        self.save()
        super(Membership, self).delete(using, force)


@receiver(post_save, sender=Membership)
def assign_web_key(sender, instance, **kwargs):
    if instance.web_key is None or instance.web_key == "":
        instance.web_key = generate_alphanumeric_uid(settings.MEMBERSHIP_WEB_KEY_LENGTH)
        instance.save()
