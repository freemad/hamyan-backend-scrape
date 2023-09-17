from django.db import models
from django.utils.translation import ugettext_lazy as _

from utils.models import BaseModel


class Client(BaseModel):
    """
    the model which is accessible by client devices to set the base data

    FIELDS:
    android_force_version: the version of the Android client which
        if is lower the force update page should be shown
    android_last_version: the last version of the Android client which
        if is lower the updated page should be shown
    android_download_link: the default download link of the Android client which can be download through
    ios_force_version: the version of the iOS client which
        if is lower the force update page should be shown
    ios_last_version: the last version of the iOS client which if is lower the updated page should be shown
    ios_download_link: the default download link of the iOS client which can be download through
    welcome_view_id: the id of the Welcome Web View which is displayed in the clients
    welcome_view_url: the URL of the Welcome Web View
    welcome_view_multiple_display: the indicator says whether the Web View should be
        shown several times or not
    group_pay_gateway: the GATEWAY object which the group payment is done through it (Deprecated)
    cashbox_count: the count of total CASHBOX objects are created in the backend (for showing in the Web Site)
    moneypool_count: the count of total MONEYPOOL objects
        are created in the backend (for showing in the Web Site)
    member_count: the count of total MEMBER objects are created in the backend (for showing in the Web Site)
    """
    android_force_version = models.CharField(max_length=20)
    android_last_version = models.CharField(max_length=20)
    android_download_link = models.CharField(max_length=200, null=True)

    ios_force_version = models.CharField(max_length=20)
    ios_last_version = models.CharField(max_length=20)
    ios_download_link = models.CharField(max_length=200, null=True)

    welcome_view_id = models.IntegerField(default=0, blank=True)
    welcome_view_url = models.CharField(max_length=250, blank=True)
    welcome_view_multiple_display = models.BooleanField(default=False, blank=True)

    preset_gateway = models.ForeignKey('payment.Gateway', on_delete=models.SET_NULL, null=True, blank=True)

    cashbox_count = models.IntegerField(default=0, blank=True)
    moneypool_count = models.IntegerField(default=0, blank=True)
    member_count = models.IntegerField(default=0, blank=True)

    class Meta:
        verbose_name = _("Client")
        verbose_name_plural = _("Clients")

    @property
    def group_pay_gateway(self):
        return self.preset_gateway
