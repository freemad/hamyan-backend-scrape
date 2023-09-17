import random

from django.db import models
from django.utils.datetime_safe import date
from django.utils.translation import ugettext_lazy as _
from khayyam import JalaliDate

from cashbox_management.models.membership import Membership
from cashbox_management.models.winner import Winner
from payment.models.transaction import Transaction
from utils.constants import choice
from utils.constants.notification_constant import (
    NOTIFICATION_ACTION_FIELD_CASHBOX_DETAIL,
)
from utils.firebase.notification import (
    send_notification_to_member_list,
    create_page_notification_data,
)
from utils.firebase.notification_templates import (
    DRAW_DATE_CHANGE_BODY,
    DRAW_DATE_CHANGE_TITLE,
)
from utils.message.message import send_message_to_member_list
from utils.message.message_templates import DRAW_DATE_CHANGE_MSG
from utils.mixins import timestamp
from utils.models import BaseModel


class Cycle(BaseModel):
    """
    the CYCLE model represents "Nowbat" (in persian)
    which models each cycle of the drawing and winnings loans of the PERIOD

    FIELDS
    index: the index of the CYCLE in PERIOD
    start_date: the start date
    draw_date: the date which draw will occur in it
    drawing_date: the actual drawing date
    is_manually_drawn: an indicator says whether it is drawn manually or not
    period: the PERIOD object which contains this cycle
    winner: the winner MEMBER object of the cycle if it's drawn (DEPRECATED)
    """
    index = models.IntegerField(default=1)  # 1base
    start_date = models.DateField(null=True, blank=True)
    # the date which is supposed to draw
    draw_date = models.DateField(null=True, blank=True)
    # the drawing date which the draw actually happened
    drawing_date = models.DateField(null=True, blank=True)
    is_manually_drawn = models.BooleanField(default=False, blank=True)
    period = models.ForeignKey(
        "cashbox_management.Period", on_delete=models.CASCADE, related_name="cycles"
    )
    winner = models.ForeignKey(
        "account_management.Member",
        on_delete=models.SET_NULL,
        related_name="won_cycles",
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = _("cycle")
        verbose_name_plural = _("cycles")

    def __str__(self):
        return "%s -C %s" % (self.period.__str__(), str(self.index))

    @property
    def cashbox(self):
        return self.period.cashbox

    @property
    def start_date_stamp(self):
        return timestamp(self.start_date)

    @property
    def draw_date_jalali(self):
        return JalaliDate(self.draw_date).__str__()

    @property
    def drawing_date_jalali(self):
        if self.drawing_date is None:
            return ""
        return JalaliDate(self.drawing_date).__str__()

    @property
    def winner_name(self):
        if self.winner is None:
            return ""
        return self.winner.name

    @property
    def days_to_draw(self):
        return (self.draw_date - date.today()).days

    @property
    def is_drawn(self):
        return self.winners.exists()

    def is_in_period(self, period):
        return self in period.cycles

    def draw(self, winner=None):
        if self.winner is not None:
            # the winner already chosen
            return None
        if not self.cashbox.is_financially_satisfied():
            # the cashbox is not financially satisfied
            return None
        if len(self.period.get_unpaid_memberships()) > 0:
            # some members may not pay their shares completely
            return None

        memberships = self.period.get_valid_memberships()
        if winner is None:
            # draw is automatic
            if self.index == 1 and self.period.is_manager_first_winner:
                # 1st winner should be cashbox's owner
                winner = self.cashbox.get_owner()
                self.is_manually_drawn = True
            else:
                total_member_chances = []
                for membership in memberships:
                    for i in range(0, membership.non_won_shares):
                        total_member_chances.append(membership.member)
                winner = random.choice(seq=total_member_chances)
                self.is_manually_drawn = False
        else:
            # draw is manual
            self.is_manually_drawn = True

        self.set_winner_and_setup_transaction(winner)

        Winner.objects.create(
            cycle=self,
            loan_amount=self.period.satisfactory_amount,
            membership=Membership.objects.get(period=self.period, member=winner),
        )

        return self.winner

    def rollback_winner(self):
        if self.winner is not None:
            rolledback_membership = Membership.objects.filter(
                member=self.winner, period=self.period
            )[0]
            rolledback_membership.unmake_winner()
            self.winner = None
            self.drawing_date = None
            self.save()

    def set_winner(self, winner, drawing_date=None):
        """
        set the winner of the cycle and do the model updates
        :param winner: a Member which is won
        :param drawing_date: the date of actual draw of the cycle
        :return: Nothing
        """
        self.winner = winner
        if drawing_date is None:
            self.drawing_date = date.today()
        else:
            self.drawing_date = drawing_date
        won_membership = Membership.objects.filter(member=winner, period=self.period)[0]
        won_membership.make_winner()
        Winner.objects.create(
            cycle=self,
            membership=won_membership,
            loan_amount=self.period.satisfactory_amount,
        )
        self.save()

    def set_winner_and_setup_transaction(self, winner, drawing_date=None):
        """
        set the winner of the cycle and do the model updates
        :param winner: a Member which is won
        :param drawing_date: the date of actual draw of the cycle
        :return: Nothing
        """
        self.winner = winner
        if drawing_date is None:
            self.drawing_date = date.today()
        else:
            self.drawing_date = drawing_date
        won_membership = Membership.objects.filter(member=winner, period=self.period)[0]
        won_membership.make_winner()
        Transaction.objects.create(
            source=choice.TRANSACTION_SRC_HAMYAN_BOX_BALANCE,
            destination=choice.TRANSACTION_DST_HAMYAN_WALLET,
            receiver=won_membership.member,
            amount=self.cashbox.checkout_balance_and_reset(),
            ctx_id=self.id,
            ctx_type=choice.TRANSACTION_CTX_TYPE_CYCLE,
        )
        self.save()

    # Message methods

    def send_draw_date_change_messages(self):
        message_body = DRAW_DATE_CHANGE_MSG.format(
            self.cashbox.name, JalaliDate(self.draw_date).__str__()
        )

        send_message_to_member_list(
            member_list=self.period.get_valid_members(),
            action=choice.MESSAGE_ACTION_CASHBOX,
            params=self.id,
            body=message_body,
        )

    # Notification methods

    def send_draw_date_change_notifications(self):
        message_body = DRAW_DATE_CHANGE_BODY.format(
            self.cashbox.name, JalaliDate(self.draw_date).__str__()
        )

        send_notification_to_member_list(
            DRAW_DATE_CHANGE_TITLE,
            message_body,
            self.cashbox.get_notification_members(),
            notif_data=create_page_notification_data(
                page=NOTIFICATION_ACTION_FIELD_CASHBOX_DETAIL,
                cashbox_id=self.cashbox.id,
            ),
        )
