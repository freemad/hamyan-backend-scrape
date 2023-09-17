from django.db import models
from django.utils.translation import ugettext_lazy as _

from utils.models import BaseModel


class Contact(BaseModel):
    """
    the contact model of the device (NOT USED YET)

    FIELDS
    device: the DEVICE which the contact is belonged
    first_name: the first name stored in the contact
    last_name: the last name stored in the contact
    phone_number: the phone number stored in the contact
    """
    device = models.ForeignKey(
        "peripheral.Device", on_delete=models.CASCADE, related_name="contacts"
    )
    first_name = models.CharField(max_length=100, default="")
    last_name = models.CharField(max_length=100, default="")
    phone_number = models.CharField(max_length=50, default="")

    class Meta:
        verbose_name = _("device")
        verbose_name_plural = _("devices")
