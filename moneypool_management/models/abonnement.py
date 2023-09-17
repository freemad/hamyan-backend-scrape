# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models
from django.utils.translation import ugettext_lazy as _

from utils.constants import default, choice
from utils.models import BaseModel


class Abonnement(BaseModel):
    """
    the ABONNEMENT model for payment of abonnement of MONEYPOOL

    FIELDS
    moneypool: the MONEYPOOL model which the abonnement is belonged
    number_of_trial_intervals: the number of trial of intervals (which the moneypool is free)
    custom_coef: the custom coefficient which multiply in each and every commissioned payments of the moneypool
    is_manually_set: the indicator which says the settings is manually set or not
    """
    moneypool = models.OneToOneField(
        "moneypool_management.Moneypool", related_name="abonnement"
    )
    number_of_trial_intervals = models.IntegerField(
        _("Number of Trial Intervals"), default=default.DEFAULT_TRIAL_INTERVALS
    )
    custom_coef = models.FloatField(_("Custom Coef"), default=1.0)
    is_manually_set = models.BooleanField(_("Is Manually Set"), default=False)

    class Meta:
        verbose_name = _("abonnement")
        verbose_name_plural = _("abonnements")

    def __str__(self):
        return "%s+%s" % (self.moneypool.__str__(), str(self.number_of_trial_intervals))

    def calculate_invoice_base_amount(self):
        poolships_count = self.moneypool.poolships.all().count()
        coef = self.custom_coef
        if self.moneypool.type == choice.MONEYPOOL_TYPE_PAYABLE:
            coef *= default.ABONNEMENT_MONEYPOOL_TYPE_COEF_PAYABLE
        elif self.moneypool.type == choice.MONEYPOOL_TYPE_REGISTRABLE:
            coef *= default.ABONNEMENT_MONEYPOOL_TYPE_COEF_REGISTRABLE
        elif self.moneypool.type == choice.MONEYPOOL_TYPE_HYBRID:
            coef *= default.ABONNEMENT_MONEYPOOL_TYPE_COEF_HYBRID
        if (
            default.INTERVAL_S_SIZED_MEMBER_COUNT_LOW_CONSTRAINT
            <= poolships_count
            <= default.INTERVAL_S_SIZED_MEMBER_COUNT_HIGH_CONSTRAINT
        ):
            invoice_base_amount = (
                coef * default.DEFAULT_S_SIZED_MONEYPOOL_INVOICE_AMOUNT
            )
        elif (
            default.INTERVAL_M_SIZED_MEMBER_COUNT_LOW_CONSTRAINT
            <= poolships_count
            <= default.INTERVAL_M_SIZED_MEMBER_COUNT_HIGH_CONSTRAINT
        ):
            invoice_base_amount = (
                coef * default.DEFAULT_M_SIZED_MONEYPOOL_INVOICE_AMOUNT
            )
        elif (
            default.INTERVAL_L_SIZED_MEMBER_COUNT_LOW_CONSTRAINT
            <= poolships_count
            <= default.INTERVAL_L_SIZED_MEMBER_COUNT_HIGH_CONSTRAINT
        ):
            invoice_base_amount = (
                coef * default.DEFAULT_L_SIZED_MONEYPOOL_INVOICE_AMOUNT
            )
        elif (
            default.INTERVAL_XL_SIZED_MEMBER_COUNT_LOW_CONSTRAINT
            <= poolships_count
            <= default.INTERVAL_XL_SIZED_MEMBER_COUNT_HIGH_CONSTRAINT
        ):
            invoice_base_amount = (
                coef * default.DEFAULT_XL_SIZED_MONEYPOOL_INVOICE_AMOUNT
            )
        else:
            invoice_base_amount = (
                coef * default.DEFAULT_XL_SIZED_MONEYPOOL_INVOICE_AMOUNT
            )
        return invoice_base_amount
