# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from khayyam import JalaliDatetime

from payment.models import Transaction
from utils.constants import choice
from utils.mixins import convert_to_local_time
from utils.models import BaseModel


class MoneypoolCashout(BaseModel):
    """
    the cashout to the moneypool which can be transactional or registral

    FIELDS
    registrar: the registrar of the cashout (could be owner/managers if is registral)
    poolship: the poolship that the cashout is registered for
    amount: the amount of the cashout in Tomans
    solved_amount: the solved amount of the cashout for cashouts
    type: the choice represents the type of the cashout values: loan, custom
    tag: the tag of the cashout (that should be filled by the users)
    time: the time of the cashout occurrance
    transaction: the TRANSACTION assigned to the cashout if it's transactional
    """
    registrar = models.ForeignKey(
        "moneypool_management.Poolship",
        on_delete=models.SET_NULL,
        related_name="registered_cashouts",
        null=True,
    )
    poolship = models.ForeignKey(
        "moneypool_management.Poolship",
        on_delete=models.SET_NULL,
        related_name="cashouts",
        null=True,
    )
    amount = models.IntegerField(_("Amount"), default=0)
    type = models.CharField(
        _("Type"),
        max_length=10,
        choices=choice.MONEYPOOL_CASHOUT_TYPE,
        default=choice.MONEYPOOL_CASHOUT_TYPE_CUSTOM,
    )
    tag = models.CharField(_("Tag"), max_length=300, default="", blank=True)
    time = models.DateTimeField(_("Time"), default=timezone.now)
    transaction = models.OneToOneField(
        "payment.Transaction",
        on_delete=models.SET_NULL,
        related_name="cashout",
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = _("Cashout")
        verbose_name_plural = _("Cashouts")

    def __str__(self):
        return "(%s)>>%s" % (str(self.amount), self.poolship.__str__())

    @property
    def moneypool(self):
        return self.poolship.moneypool

    @property
    def registrar_name(self):
        return self.registrar.name

    @property
    def registrar_phone_number(self):
        return self.registrar.phone_number

    @property
    def poolship_name(self):
        return self.poolship.name

    @property
    def poolship_phone_number(self):
        return self.poolship.phone_number

    @property
    def state(self):
        if not self.transaction:
            return choice.TRANSACTION_STATE_SUCCESSFUL
            # if self.moneypool.is_registrable:
            #     return choice.TRANSACTION_STATE_SUCCESSFUL
            # else:
            #     return choice.TRANSACTION_STATE_UNSUCCESSFUL
        else:
            return self.transaction.state

    @property
    def deed_type(self):
        if self.transaction:
            return choice.MONEYPOOL_DEED_TYPE_TRANSACTIONAL

        return choice.MONEYPOOL_DEED_TYPE_RECORD

    @property
    def cashout_loan(self):
        return self.loan if hasattr(self, "loan") else None

    @property
    def is_reportable(self):
        return self.transaction.is_reportable if self.transaction else True

    @property
    def is_removable(self):
        return self.deed_type == choice.MONEYPOOL_DEED_TYPE_RECORD

    @property
    def jalali_time(self):
        return JalaliDatetime(convert_to_local_time(self.time)).__str__()

    # Accessors & Mutators

    def withdraw_bank_balance(self):
        if self.deed_type == choice.MONEYPOOL_DEED_TYPE_RECORD:
            self.moneypool.withdraw_from_bank_balance(self.amount)
        else:
            raise ValueError("THe cashout deed type is not RECORD...")

    def rollback_bank_balance(self):
        if self.deed_type == choice.MONEYPOOL_DEED_TYPE_RECORD:
            self.moneypool.charge_bank_balance(self.amount)

    def set_transaction(self, destination=None, bank_account=None):
        if not self.transaction:
            self.transaction = Transaction.objects.create(
                receiver=self.poolship.member,
                amount=self.amount,
                source=choice.TRANSACTION_DST_HAMYAN_BOX_BALANCE,
                destination=destination
                if destination
                else choice.TRANSACTION_DST_HAMYAN_WALLET,
                bank_account=bank_account,
                ctx_id=self.poolship.moneypool.id,
                ctx_type=choice.TRANSACTION_CTX_TYPE_MONEYPOOL,
            )
            self.save()
        return self.transaction

    def remove(self):
        if not self.is_removable:
            raise ValueError("cashout is not removable")
        self.moneypool.charge_bank_balance(self.amount)
        self.delete()
