from datetime import timedelta

from django.utils import timezone

from cashbox_management.models import Membership
from moneypool_management.models import Poolship
from aptbox_management.models import Aptship
from payment.models import Transaction
from peripheral.models import Device
from utils.constants import choice
from utils.mixins import comma_separate


def get_all_box_owner_members(end_date=None, delta_date=None):
    if not end_date:
        end_date = timezone.now()  # timezone.datetime(2018, 12, 20)
    if not delta_date:
        delta_date = 30
    owner_members = list()
    owner_members.extend(get_all_cashbox_owner_members(end_date=end_date, delta_date=delta_date))
    owner_members.extend(get_all_moneypool_owner_members(end_date=end_date, delta_date=delta_date))
    owner_members.extend(get_all_aptbox_owner_members(end_date=end_date, delta_date=delta_date))
    return list(set(owner_members))


def export_owners_phone_number(owner_member_list):
    phone_list = list()
    for owner in owner_member_list:
        phone_list.append(owner.phone_number + ', ')
    return phone_list


def get_all_cashbox_owner_members(end_date=None, delta_date=None):
    if not end_date:
        end_date = timezone.now()  # timezone.datetime(2018, 12, 20)
    if not delta_date:
        delta_date = 30
    start_date = end_date - timedelta(delta_date)

    owner_memberships = Membership.objects.filter(
        role=choice.CASHBOX_ROLE_OWNER,
        created__lt=end_date,
        created__gte=start_date
    )
    owner_member_list = list()
    for ms in owner_memberships:
        owner_member_list.append(ms.member)
    return list(set(owner_member_list))


def get_all_moneypool_owner_members(end_date=None, delta_date=None):
    if not end_date:
        end_date = timezone.now()  # timezone.datetime(2018, 12, 20)
    if not delta_date:
        delta_date = 30
    start_date = end_date - timedelta(delta_date)

    owner_poolships = Poolship.objects.filter(
        role=choice.MONEYPOOL_ROLE_OWNER,
        created__lt=end_date,
        created__gte=start_date
    )
    owner_member_list = list()
    for ps in owner_poolships:
        owner_member_list.append(ps.member)
    return list(set(owner_member_list))


def get_all_aptbox_owner_members(end_date=None, delta_date=None):
    if not end_date:
        end_date = timezone.now()  # timezone.datetime(2018, 12, 20)
    if not delta_date:
        delta_date = 30
    start_date = end_date - timedelta(delta_date)

    owner_aptships = Aptship.objects.filter(
        role=choice.APTBOX_ROLE_OWNER,
        created__lt=end_date,
        created__gte=start_date
    )
    owner_member_list = list()
    for ts in owner_aptships:
        owner_member_list.append(ts.member)
    return list(set(owner_member_list))

