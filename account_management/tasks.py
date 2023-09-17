from datetime import timedelta

import xlsxwriter
from celery import shared_task
from celery.schedules import crontab
from celery.task import periodic_task
from django.conf import settings
from django.core.mail import EmailMessage
from django.db.models import Count
from django.utils import timezone

from account_management.models import Member
from cashbox_management.models import Cashbox, Membership, Period
from moneypool_management.models import Moneypool, Poolship
from payment.models import Transaction
from peripheral.models import Device
from utils import scoring
from utils.constants import choice, default
from utils.firebase import notification_templates
from utils.firebase.notification import send_notification_to_member_list_v2, send_notification_to_member
from utils.log import error_logger
from utils.message import message_templates
from utils.message.message import send_message_to_member
from utils.message.message import send_message_to_member_list
from utils.mixins import daterange, date_to_datetime
from utils.sms.sms_templates import QUESTIONER_SMS
from utils.tasks import send_high_priority_templated_sms, send_high_priority_sms


@shared_task(queue=choice.CELERY_DEFAULT_QUEUE)
def send_bulk_notification_to_all_members(title, body, device_type=None, url=None):
    members = list()
    if device_type == 'all':
        members = Member.objects.all()
    elif device_type == choice.CLIENT_TYPE_IOS:
        for device in Device.objects.all():
            if device.is_ios:
                members.append(device.member)
    elif device_type == choice.CLIENT_TYPE_ANDROID:
        for device in Device.objects.all():
            if not device.is_ios:
                members.append(
                    device.member
                )
    members = list(set(members))
    send_notification_to_member_list_v2(
        title=title, body=body, member_list=members, url=url
    )


@shared_task(queue=choice.CELERY_DEFAULT_QUEUE)
def send_bulk_message_to_all_members(body, action, param, device_type=None, url=None):
    members = list()
    if device_type is None:
        members = Member.objects.all()
    elif device_type == choice.CLIENT_TYPE_IOS:
        for device in Device.objects.all():
            if device.is_ios:
                members.append(device.member)
    elif device_type == choice.CLIENT_TYPE_ANDROID:
        for device in Device.objects.all():
            if not device.is_ios:
                members.append(
                    device.member
                )
    members = list(set(members))
    send_message_to_member_list(
        member_list=members, action=action, params=param, body=body
    )


@shared_task(queue=choice.CELERY_DEFAULT_QUEUE)
def send_bulk_sms_to_members(body, device_type=None, members=[]):
    tmp_members = members
    members = list()
    for member_id in tmp_members:
        member = Member.objects.filter(id=member_id).first()
        if member:
            members.append(member)

    if device_type == 'all':
        members = Member.objects.all()
    elif device_type == choice.CLIENT_TYPE_IOS and not members:
        for device in Device.objects.all():
            if device.is_ios:
                members.append(device.member)
    elif device_type == choice.CLIENT_TYPE_ANDROID and not members:
        for device in Device.objects.all():
            if not device.is_ios:
                members.append(
                    device.member
                )
    members = list(set(members))
    for member in members:
        send_high_priority_sms.delay(message=body, phone_number=member.phone_number)


@shared_task(queue=choice.CELERY_DEFAULT_QUEUE)
def export_members_task(
        from_date,
        box_type,
        to_date=timezone.now(),
        client_type=choice.CLIENT_TYPE_ANDROID,
        have_transaction=False,
):
    members = Member.objects.filter(created__gte=from_date, created__lte=to_date)
    if box_type == "cashbox":
        memberships = Membership.objects.filter(member__in=members)
        members = list()
        for membership in memberships:
            members.append(membership.member)
    elif box_type == "moneypool":
        poolships = Poolship.objects.filter(member__in=members)
        members = list()
        for poolship in poolships:
            members.append(poolship.member)
    members = list(set(members))
    if have_transaction:
        tmp_members = members
        members = list()
        for member in tmp_members:
            trs = Transaction.objects.filter(
                state=choice.TRANSACTION_STATE_SUCCESSFUL,
                payer__isnull=False,
                receiver=member,
            )
            if trs.count() > 0:
                members.append(member)
    else:
        tmp_members = members
        members = list()
        for member in tmp_members:
            trs = Transaction.objects.filter(
                state=choice.TRANSACTION_STATE_SUCCESSFUL,
                payer__isnull=False,
                receiver=member,
            )
            if trs.count() == 0:
                members.append(member)

    if client_type == choice.CLIENT_TYPE_ANDROID:
        tmp_members = members
        members = list()
        for member in tmp_members:
            devices = Device.objects.filter(member=member)
            for device in devices:
                if not device.is_ios:
                    members.append(member)
    elif client_type == choice.CLIENT_TYPE_IOS:
        tmp_members = members
        members = list()
        for member in tmp_members:
            devices = Device.objects.filter(member=member)
            for device in devices:
                if device.is_ios:
                    members.append(member)

    file_name = "./reports/members" + str(timezone.now()) + ".csv"
    with open(file_name, mode="w", encoding="utf-8") as f:
        f.write("id,first_name,last_name,phone_number")
        for member in members:
            f.write(
                str(member.id)
                + ","
                + str(member.first_name)
                + ","
                + str(member.last_name)
                + ","
                + str(member.phone_number)
            )
            f.write("\n")
        f.close()
    try:
        mail = EmailMessage(
            subject="report members",
            body="Report members in %s" % timezone.now(),
            to=default.MARKETING_MEMBERS_EMAIL_ADDRESSES,
        )
        mail.attach_file(file_name)
        mail.send()
    except Exception as e:
        error_logger.error("exception in export_members_task %s" % e)


@periodic_task(
    run_every=(crontab(hour="1", minute="00", day_of_week={1, 5})),
    name="weekly_scores_update",
    ignore_results=True,
    queue=choice.CELERY_PERIODIC_QUEUE,
    options={'queue': choice.CELERY_PERIODIC_QUEUE},
)
def weekly_scores_update():
    if settings.DEBUG:
        return

    # scoring.backup_scores()
    scoring.set_memberships_local_score()
    scoring.set_poolships_local_score()
    scoring.set_members_global_score()


# @periodic_task(
#     run_every=(crontab(hour='4', minute='00', )),
#     name='daily_kpi_in_range_report',
#     ignore_results=True)
# def daily_kpi_in_range_report():
#     end_date = timezone.now().date()  # timezone.datetime(2018, 12, 20)
#     start_date = end_date - timedelta(30)
#
#     all_successful_transactions = \
#         Transaction.objects.filter(state=choice.TRANSACTION_STATE_SUCCESSFUL, is_group_pay=False)
#     tred_cashboxes = list()
#     tred_moneypools = list()
#     tred_wallet_members = list()
#     tred_cashbox_members = list()
#     tred_moneypool_members = list()
#     total_cashboxes_balance = 0
#     total_moneypools_balance = 0
#     total_wallets_balance = 0
#     total_commissions_amount = 0
#     total_turnover = 0
#     for tr in all_successful_transactions:
#         total_commissions_amount += tr.commission
#         total_turnover += tr.amount
#         if tr.cycle and tr.cycle.removed is None:  # it's a cashbox transaction
#             tred_cashboxes.append(tr.cycle.cashbox)
#         elif tr.moneypool and tr.moneypool.removed is None:  # it's a moneypool transaction
#             tred_moneypools.append(tr.moneypool)
#         elif tr.destination == choice.TRANSACTION_DST_HAMYAN_WALLET:  # it's a wallet transaction
#             tred_wallet_members.append(tr.payer)
#     tred_cashboxes = list(set(tred_cashboxes))
#     tred_moneypools = list(set(tred_moneypools))
#     tred_wallet_members = list(set(tred_wallet_members))
#     for cashbox in tred_cashboxes:
#         total_cashboxes_balance += cashbox.balance
#         for period in cashbox.periods.all():
#             for member in period.members.all():
#                 tred_cashbox_members.append(member)
#     for moneypool in tred_moneypools:
#         total_moneypools_balance += moneypool.hamyan_balance
#         for member in moneypool.members.all():
#             tred_moneypool_members.append(member)
#     for member in tred_wallet_members:
#         total_wallets_balance += member.wallet_balance
#     tred_cashbox_members = list(set(tred_cashbox_members))
#     tred_moneypool_members = list(set(tred_moneypool_members))
#
#     successful_transactions_till_end_date = \
#         all_successful_transactions.filter(created__lte=date_to_datetime(end_date))
#     tred_cashboxes_till_end_date = list()
#     tred_moneypools_till_end_date = list()
#     tred_cashbox_members_till_end_date = list()
#     tred_moneypool_members_till_end_date = list()
#     tred_wallet_members_till_end_date = list()
#     cashbox_gateway_cashins_amount_till_end_date = 0
#     cashbox_wallet_cashins_amount_till_end_date = 0
#     cashbox_cash_cashouts_amount_till_end_date = 0
#     cashbox_wallet_cashouts_amount_till_end_date = 0
#     moneypool_gateway_cashins_amount_till_end_date = 0
#     moneypool_wallet_cashins_amount_till_end_date = 0
#     moneypool_cash_cashouts_amount_till_end_date = 0
#     moneypool_wallet_cashouts_amount_till_end_date = 0
#     wallet_cashins_amount_till_end_date = 0
#     commissions_amount_till_end_date = 0
#     total_turnover_till_end_date = 0
#     for tr in successful_transactions_till_end_date:
#         if tr.cycle and tr.cycle.removed is None:  # its cashbox transaction
#             tred_cashboxes_till_end_date.append(tr.cycle.cashbox)
#             if tr.source == choice.TRANSACTION_SRC_GATEWAY:
#                 if tr.gateway is not None:
#                     cashbox_gateway_cashins_amount_till_end_date += tr.amount
#             if tr.source == choice.TRANSACTION_SRC_HAMYAN_WALLET:
#                 cashbox_wallet_cashins_amount_till_end_date += tr.amount
#             if tr.destination == choice.TRANSACTION_DST_MEMBER_BANKACCOUNT:
#                 cashbox_cash_cashouts_amount_till_end_date += tr.amount
#             if tr.destination == choice.TRANSACTION_DST_HAMYAN_WALLET:
#                 cashbox_wallet_cashouts_amount_till_end_date += tr.amount
#         elif tr.moneypool and tr.moneypool.removed is None:  # its moneypool transaction
#             tred_moneypools_till_end_date.append(tr.moneypool)
#             if tr.source == choice.TRANSACTION_SRC_GATEWAY:
#                 if tr.gateway is not None:
#                     moneypool_gateway_cashins_amount_till_end_date += tr.amount
#             if tr.source == choice.TRANSACTION_SRC_HAMYAN_WALLET:
#                 moneypool_wallet_cashins_amount_till_end_date += tr.amount
#             if tr.destination == choice.TRANSACTION_DST_MEMBER_BANKACCOUNT:
#                 moneypool_cash_cashouts_amount_till_end_date += tr.amount
#             if tr.destination == choice.TRANSACTION_DST_HAMYAN_WALLET:
#                 moneypool_wallet_cashouts_amount_till_end_date += tr.amount
#         elif tr.source == choice.TRANSACTION_SRC_GATEWAY \
#                 and tr.destination == choice.TRANSACTION_DST_HAMYAN_WALLET:
#             if tr.gateway is not None:
#                 tred_wallet_members_till_end_date.append(tr.payer)
#                 wallet_cashins_amount_till_end_date += tr.amount
#         total_turnover_till_end_date += tr.amount
#         commissions_amount_till_end_date += tr.commission
#     for cashbox in tred_cashboxes_till_end_date:
#         for period in cashbox.periods.all():
#             for member in period.members.all():
#                 tred_cashbox_members_till_end_date.append(member)
#     for moneypool in tred_moneypools_till_end_date:
#         for member in moneypool.members.all():
#             tred_moneypool_members_till_end_date.append(member)
#     tred_cashboxes_till_end_date = list(set(tred_cashboxes_till_end_date))
#     tred_moneypools_till_end_date = list(set(tred_moneypools_till_end_date))
#     tred_wallet_members_till_end_date = list(set(tred_wallet_members_till_end_date))
#     tred_cashbox_members_till_end_date = list(set(tred_cashbox_members_till_end_date))
#     tred_moneypool_members_till_end_date = list(set(tred_moneypool_members_till_end_date))
#
#     successful_transactions_in_range = \
#         all_successful_transactions.filter(
#             created__gte=date_to_datetime(start_date),
#             created__lte=date_to_datetime(end_date))
#     tred_cashboxes_in_range = list()
#     tred_moneypools_in_range = list()
#     tred_wallet_members_in_range = list()
#     tred_cashbox_members_in_range = list()
#     tred_moneypool_members_in_range = list()
#     cashbox_gateway_cashins_amount_in_range = 0
#     cashbox_wallet_cashins_amount_in_range = 0
#     cashbox_cash_cashouts_amount_in_range = 0
#     cashbox_wallet_cashouts_amount_in_range = 0
#     moneypool_gateway_cashins_amount_in_range = 0
#     moneypool_wallet_cashins_amount_in_range = 0
#     moneypool_cash_cashouts_amount_in_range = 0
#     moneypool_wallet_cashouts_amount_in_range = 0
#     wallet_cashins_amount_in_range = 0
#     commissions_amount_in_range = 0
#     turnover_in_range = 0
#     for tr in successful_transactions_in_range:
#         if tr.cycle and tr.cycle.removed is None:  # its cashbox transaction
#             tred_cashboxes_in_range.append(tr.cycle.cashbox)
#             if tr.source == choice.TRANSACTION_SRC_GATEWAY and tr.gateway is not None:
#                 cashbox_gateway_cashins_amount_in_range += tr.amount
#             if tr.source == choice.TRANSACTION_SRC_HAMYAN_WALLET:
#                 cashbox_wallet_cashins_amount_in_range += tr.amount
#             if tr.destination == choice.TRANSACTION_DST_MEMBER_BANKACCOUNT:
#                 cashbox_cash_cashouts_amount_in_range += tr.amount
#             if tr.destination == choice.TRANSACTION_DST_HAMYAN_WALLET:
#                 cashbox_wallet_cashouts_amount_in_range += tr.amount
#         elif tr.moneypool and tr.moneypool.removed is None:  # its moneypool transaction
#             tred_moneypools_in_range.append(tr.moneypool)
#             if tr.source == choice.TRANSACTION_SRC_GATEWAY and tr.gateway is not None:
#                 moneypool_gateway_cashins_amount_in_range += tr.amount
#             if tr.source == choice.TRANSACTION_SRC_HAMYAN_WALLET:
#                 moneypool_wallet_cashins_amount_in_range += tr.amount
#             if tr.destination == choice.TRANSACTION_DST_MEMBER_BANKACCOUNT:
#                 moneypool_cash_cashouts_amount_in_range += tr.amount
#             if tr.destination == choice.TRANSACTION_DST_HAMYAN_WALLET:
#                 moneypool_wallet_cashouts_amount_in_range += tr.amount
#         elif tr.source == choice.TRANSACTION_SRC_GATEWAY \
#                 and tr.destination == choice.TRANSACTION_DST_HAMYAN_WALLET \
#                 and tr.gateway is not None:  # its wallet transaction
#             tred_wallet_members_in_range.append(tr.payer)
#             wallet_cashins_amount_in_range += tr.amount
#         turnover_in_range += tr.amount
#         commissions_amount_in_range += tr.commission
#     for cashbox in tred_cashboxes_in_range:
#         for period in cashbox.periods.all():
#             for member in period.members.all():
#                 tred_cashbox_members_in_range.append(member)
#     for moneypool in tred_moneypools_in_range:
#         for member in moneypool.members.all():
#             tred_moneypool_members_in_range.append(member)
#     tred_cashboxes_in_range = list(set(tred_cashboxes_in_range))
#     tred_moneypools_in_range = list(set(tred_moneypools_in_range))
#     tred_wallet_members_in_range = list(set(tred_wallet_members_in_range))
#     tred_cashbox_members_in_range = list(set(tred_cashbox_members_in_range))
#     tred_moneypool_members_in_range = list(set(tred_moneypool_members_in_range))
#
#     content_str = ""
#     content_str += "All Successful Transactions: " + comma_separate(all_successful_transactions.count()) + "\n\r"  # noqa
#     content_str += "TRed Cashboxes: " + comma_separate(len(tred_cashboxes)) + "\n\r"  # noqa
#     content_str += "TRed Moneypools: " + comma_separate(len(tred_moneypools)) + "\n\r"  # noqa
#     content_str += "TRed Wallet Members: " + comma_separate(len(tred_wallet_members)) + "\n\r"  # noqa
#     content_str += "TRed Cashbox Members: " + comma_separate(len(tred_cashbox_members)) + "\n\r"  # noqa
#     content_str += "TRed Moneypool Members: " + comma_separate(len(tred_moneypool_members)) + "\n\r"  # noqa
#     content_str += "Total Wallets Balance: " + comma_separate(total_wallets_balance) + "\n\r"  # noqa
#     content_str += "Total Cashboxes Balance: " + comma_separate(total_cashboxes_balance) + "\n\r"  # noqa
#     content_str += "Total Moneypools Balance: " + comma_separate(total_moneypools_balance) + "\n\r"  # noqa
#     content_str += "Total Balances: " + comma_separate(total_moneypools_balance + total_cashboxes_balance + total_wallets_balance) + "\n\r"  # noqa
#     content_str += "Total Turnover: " + comma_separate(total_turnover) + "\n\r"  # noqa
#     content_str += "Total Commissions Amount: " + comma_separate(total_commissions_amount) + "\n\r"  # noqa
#     content_str += "In-Range Turnover: " + comma_separate(turnover_in_range) + "\n\r"  # noqa
#     content_str += "In-Range Commissions Amount: " + comma_separate(commissions_amount_in_range) + "\n\r"  # noqa
#     content_str += "=============================================" + "\n\r"  # noqa
#     content_str += "KPI IN RANGE: " + start_date.__str__() + " --> " + end_date.__str__() + "\n\r"  # noqa
#     content_str += "=============================================" + "\n\r"  # noqa
#     content_str += "Successful Transactions In Range: " + comma_separate(successful_transactions_in_range.count()) + "\n\r"  # noqa
#     content_str += "TRed Cashboxes In Range: " + comma_separate(len(tred_cashboxes_in_range)) + "\n\r"  # noqa
#     content_str += "TRed Moneypools In Range: " + comma_separate(len(tred_moneypools_in_range)) + "\n\r"  # noqa
#     content_str += "TRed Wallet Members In Range: " + comma_separate(len(tred_wallet_members_in_range)) + "\n\r"  # noqa
#     content_str += "TRed Cashbox Members In Range: " + comma_separate(len(tred_cashbox_members_in_range)) + "\n\r"  # noqa
#     content_str += "TRed Moneypool Members In Range: " + comma_separate(len(tred_moneypool_members_in_range)) + "\n\r"  # noqa
#     content_str += "Total Gateway Cashins Amount In Range: " + comma_separate(cashbox_gateway_cashins_amount_in_range + moneypool_gateway_cashins_amount_in_range + wallet_cashins_amount_in_range) + "\n\r"  # noqa
#     content_str += "Cashbox Gateway Cashins Amount In Range: " + comma_separate(cashbox_gateway_cashins_amount_in_range) + "\n\r"  # noqa
#     content_str += "Moneypool Gateway Cashins Amount In Range: " + comma_separate(moneypool_gateway_cashins_amount_in_range) + "\n\r"  # noqa
#     content_str += "Total Wallet Cashins Amount In Range: " + comma_separate(cashbox_wallet_cashins_amount_in_range + moneypool_wallet_cashins_amount_in_range) + "\n\r"  # noqa
#     content_str += "Cashbox Wallet Cashins Amount In Range: " + comma_separate(cashbox_wallet_cashins_amount_in_range) + "\n\r"  # noqa
#     content_str += "Moneypool Wallet Cashins Amount In Range: " + comma_separate(moneypool_wallet_cashins_amount_in_range) + "\n\r"  # noqa
#     content_str += "Total Cash Cashouts Amount In Range: " + comma_separate(cashbox_cash_cashouts_amount_in_range + moneypool_cash_cashouts_amount_in_range) + "\n\r"  # noqa
#     content_str += "Cashbox Cash Cashouts Amount In Range: " + comma_separate(cashbox_cash_cashouts_amount_in_range) + "\n\r"  # noqa
#     content_str += "Moneypool Cash Cashouts Amount In Range: " + comma_separate(moneypool_cash_cashouts_amount_in_range) + "\n\r"  # noqa
#     content_str += "Total Wallet Cashouts Amount In Range: " + comma_separate(cashbox_wallet_cashouts_amount_in_range + moneypool_wallet_cashouts_amount_in_range) + "\n\r"  # noqa
#     content_str += "Cashbox Wallet Cashouts Amount In Range: " + comma_separate(cashbox_wallet_cashouts_amount_in_range) + "\n\r"  # noqa
#     content_str += "Moneypool Wallet Cashouts Amount In Range: " + comma_separate(moneypool_wallet_cashouts_amount_in_range) + "\n\r"  # noqa
#     content_str += "Wallet Cashins Amount In Range: " + comma_separate(wallet_cashins_amount_in_range) + "\n\r"  # noqa
#     content_str += "Commissions Amount In Range: " + comma_separate(commissions_amount_in_range) + "\n\r"  # noqa
#     content_str += "Total Turnover In Range: " + comma_separate(turnover_in_range) + "\n\r"  # noqa
#     content_str += "=============================================" + "\n\r"  # noqa
#     content_str += "STATISTICS FROM THE BEGINNING --> " + end_date.__str__() + "\n\r"  # noqa
#     content_str += "=============================================" + "\n\r"  # noqa
#     content_str += "Successful Transactions Till End Date: " + comma_separate(successful_transactions_till_end_date.count()) + "\n\r"  # noqa
#     content_str += "TRed Cashboxes Till End Date: " + comma_separate(len(tred_cashboxes_till_end_date)) + "\n\r"  # noqa
#     content_str += "TRed Moneypools Till End Date: " + comma_separate(len(tred_moneypools_till_end_date)) + "\n\r"  # noqa
#     content_str += "TRed Wallet Members Till End Date: " + comma_separate(len(tred_wallet_members_till_end_date)) + "\n\r"  # noqa
#     content_str += "TRed Cashbox Members Till End Date: " + comma_separate(len(tred_cashbox_members_till_end_date)) + "\n\r"  # noqa
#     content_str += "TRed Moneypool Members Till End Date: " + comma_separate(len(tred_moneypool_members_till_end_date)) + "\n\r"  # noqa
#     content_str += "Total Gateway Cashins Amount Till End Date: " + comma_separate(cashbox_gateway_cashins_amount_till_end_date + moneypool_gateway_cashins_amount_till_end_date + wallet_cashins_amount_till_end_date) + "\n\r"  # noqa
#     content_str += "Cashbox Gateway Cashins Amount Till End Date: " + comma_separate(cashbox_gateway_cashins_amount_till_end_date) + "\n\r"  # noqa
#     content_str += "Moneypool Gateway Cashins Amount Till End Date: " + comma_separate(moneypool_gateway_cashins_amount_till_end_date) + "\n\r"  # noqa
#     content_str += "Total Wallet Cashins Amount Till End Date: " + comma_separate(cashbox_wallet_cashins_amount_till_end_date + moneypool_wallet_cashins_amount_till_end_date) + "\n\r"  # noqa
#     content_str += "Cashbox Wallet Cashins Amount Till End Date: " + comma_separate(cashbox_wallet_cashins_amount_till_end_date) + "\n\r"  # noqa
#     content_str += "Moneypool Wallet Cashins Amount Till End Date: " + comma_separate(moneypool_wallet_cashins_amount_till_end_date) + "\n\r"  # noqa
#     content_str += "Total Cash Cashouts Amount Till End Date: " + comma_separate(cashbox_cash_cashouts_amount_till_end_date + moneypool_cash_cashouts_amount_till_end_date) + "\n\r"  # noqa
#     content_str += "Cashbox Cash Cashouts Amount Till End Date: " + comma_separate(cashbox_cash_cashouts_amount_till_end_date) + "\n\r"  # noqa
#     content_str += "Moneypool Cash Cashouts Amount Till End Date: " + comma_separate(moneypool_cash_cashouts_amount_till_end_date) + "\n\r"  # noqa
#     content_str += "Total Wallet Cashouts Amount Till End Date: " + comma_separate(cashbox_wallet_cashouts_amount_till_end_date + moneypool_wallet_cashouts_amount_till_end_date) + "\n\r"  # noqa
#     content_str += "Cashbox Wallet Cashouts Amount Till End Date: " + comma_separate(cashbox_wallet_cashouts_amount_till_end_date) + "\n\r"  # noqa
#     content_str += "Moneypool Wallet Cashouts Amount Till End Date: " + comma_separate(moneypool_wallet_cashouts_amount_till_end_date) + "\n\r"  # noqa
#     content_str += "Wallet Cashins Amount Till End Date: " + comma_separate(wallet_cashins_amount_till_end_date) + "\n\r"  # noqa
#     content_str += "Commissions Amount Till End Date: " + comma_separate(commissions_amount_till_end_date) + "\n\r"  # noqa
#     content_str += "Total Turnover Till End Date: " + comma_separate(total_turnover_till_end_date) + "\n\r"  # noqa
#
#     # print(content_str)
#     try:
#         send_mail("Daily KPI Report " + JalaliDate(end_date).__str__(),
#                   content_str,
#                   default.NO_REPLY_EMAIL_ADDRESS,
#                   default.BUSINESS_MEMBERS_EMAIL_ADDRESSES +
#                   default.BACKEND_STAFFS_EMAIL_ADDRESSES +
#                   [default.HAMYAN_BULK_EMAIL_ADDRESS])
#     except Exception as e:
#         error_logger.error('exception in daily_kpi_in_range_report %s' % e)
#
#     return True


@periodic_task(
    run_every=(crontab(hour="11", minute="30", day_of_week={0, 1, 2, 3, 4, 6})),
    name="send_questioner_to_members_period_task",
    ignore_results=True,
    queue=choice.CELERY_PERIODIC_QUEUE,
    options={'queue': choice.CELERY_PERIODIC_QUEUE},
)
def send_questioner_to_members_period_task():
    return
    if settings.DEBUG:
        return

    last_two_days = (timezone.now() - timedelta(days=2)).replace(hour=0, minute=0, second=0, microsecond=0)
    next_day = last_two_days + timedelta(days=1)
    devices = Device.objects.filter(
        created__gte=last_two_days,
        created__lt=next_day
    )
    members = list()
    for device in devices:
        if Device.all_objects.filter(member=device.member).count() <= 1:
            members.append(device.member)
    members = list(set(members))
    for member in members:
        send_high_priority_templated_sms.delay(
            phone_number=member.phone_number,
            template=QUESTIONER_SMS,
            args=(
                default.PORSLINE_QUESTIONER_SHORT_URL,
            )
        )


@periodic_task(
    run_every=(crontab(hour='18', minute='00', )),
    name='verify_boxes_trust_state',
    ignore_results=True,
    queue=choice.CELERY_PERIODIC_QUEUE,
    options={'queue': choice.CELERY_PERIODIC_QUEUE},
)
def verify_boxes_trust_state():
    if settings.DEBUG:
        return

    last_two_days = (timezone.now() - timedelta(days=2)).replace(hour=0, minute=0, second=0, microsecond=0)
    next_day = last_two_days + timedelta(days=1)
    moneypools = Moneypool.objects.filter(
        trust_state=choice.TRUST_STATE_WORRIED_IN_PROGRESS,
        created__gte=last_two_days,
        created__lt=next_day
    )
    cashboxes = Cashbox.objects.filter(
        trust_state=choice.TRUST_STATE_WORRIED_IN_PROGRESS,
        created__gte=last_two_days,
        created__lt=next_day
    )
    for cashbox in cashboxes:
        owner_member = cashbox.get_owner()
        if owner_member is not None:
            if owner_member.verification_state == choice.VERIFICATION_STATE_VERIFIED:
                cashbox.trust_state = choice.TRUST_STATE_WORRIED_VERIFIED
                cashbox.save()
            else:
                owner_member.set_and_email_verification_code()
                send_notification_to_member.delay(
                    title=notification_templates.MEMBER_VERIFICATION_REMINDER_TITLE,
                    body=notification_templates.MEMBER_VERIFICATION_REMINDER_BODY,
                    member=owner_member
                )
                send_message_to_member(
                    member=owner_member,
                    action=choice.MESSAGE_ACTION_CASHBOX,
                    params=cashbox.id,
                    body=message_templates.MEMBER_VERIFICATION_REMINDER
                )

    for moneypool in moneypools:
        owner_member = moneypool.owner_member
        if owner_member is not None:
            if owner_member.verification_state == choice.VERIFICATION_STATE_VERIFIED:
                moneypool.trust_state = choice.TRUST_STATE_WORRIED_VERIFIED
                moneypool.save()
            else:
                owner_member.set_and_email_verification_code()
                send_notification_to_member.delay(
                    title=notification_templates.MEMBER_VERIFICATION_REMINDER_TITLE,
                    body=notification_templates.MEMBER_VERIFICATION_REMINDER_BODY,
                    member=owner_member
                )
                send_message_to_member(
                    member=owner_member,
                    action=choice.MESSAGE_ACTION_MONEYPOOL,
                    params=moneypool.id,
                    body=message_templates.MEMBER_VERIFICATION_REMINDER
                )


@periodic_task(
    run_every=(crontab(hour='9', minute='00', day_of_week={0})),
    name='send_inform_unverified_trust_state',
    ignore_results=True,
    queue=choice.CELERY_PERIODIC_QUEUE,
    options={'queue': choice.CELERY_PERIODIC_QUEUE},
    )
def send_inform_unverified_trust_state():
    if settings.DEBUG:
        return

    start_date = (timezone.now() - timedelta(days=7)).replace(hour=0, minute=0, second=0, microsecond=0)
    end_date = (timezone.now() - timedelta(days=2)).replace(hour=0, minute=0, second=0, microsecond=0)
    moneypools = Moneypool.objects.filter(
        trust_state=choice.TRUST_STATE_WORRIED_IN_PROGRESS,
        created__gte=start_date,
        created__lt=end_date
    )
    cashboxes = Cashbox.objects.filter(
        trust_state=choice.TRUST_STATE_WORRIED_IN_PROGRESS,
        created__gte=start_date,
        created__lt=end_date
    )
    file_name = 'reports/unverified_trust_states-%s.xlsx' % timezone.now()
    workbook = xlsxwriter.Workbook(file_name)
    worksheet = workbook.add_worksheet()
    worksheet.write('A1', 'type')
    worksheet.write('B1', 'full name')
    worksheet.write('C1', 'email')
    worksheet.write('D1', 'phone number')
    worksheet.write('E1', 'box name')
    worksheet.write('F1', 'box slug')

    i = 2
    for cashbox in cashboxes:
        owner = cashbox.get_owner()
        worksheet.write('A%s' % i, 'cashbox')
        worksheet.write('B%s' % i, owner.name)
        worksheet.write('C%s' % i, owner.email)
        worksheet.write('D%s' % i, owner.phone_number)
        worksheet.write('E%s' % i, cashbox.name)
        worksheet.write('F%s' % i, cashbox.slug)
        i += 1

    for moneypool in moneypools:
        owner = moneypool.owner_member
        worksheet.write('A%s' % i, 'moneypool')
        worksheet.write('B%s' % i, owner.name)
        worksheet.write('C%s' % i, owner.email)
        worksheet.write('D%s' % i, owner.phone_number)
        worksheet.write('E%s' % i, moneypool.name)
        worksheet.write('F%s' % i, moneypool.slug)
        i += 1
    workbook.close()

    try:
        mail = EmailMessage(
            subject="unverified trust states",
            body="Report time in %s" % timezone.now(),
            to=default.CRM_MEMBERS_EMAIL_ADDRESSES,
        )
        mail.attach_file(file_name)
        mail.send()
    except Exception as e:
        error_logger.error("exception in send_inform_unverified_trust_state %s" % e)


@periodic_task(
    run_every=(crontab(hour='5', minute='00', )),
    name='send_new_revenue_7_day_stats',
    ignore_results=True,
    queue=choice.CELERY_PERIODIC_QUEUE,
    options={'queue': choice.CELERY_PERIODIC_QUEUE},
    )
def send_new_revenue_7_day_stats():
    end_date = timezone.now().date()
    delta_date = 7
    start_date = end_date - timedelta(delta_date)

    dates = list()
    members_count_list = list()
    cashbox_owners_count_list = list()
    moneypool_owners_count_list = list()
    cashboxes_count_list = list()
    moneypools_count_list = list()
    plus_5_member_cashboxes_count_list = list()
    plus_5_member_moneypools_count_list = list()
    for date in daterange(start_date, end_date):
        dates.append(date)
        members_count = Member.objects.filter(
            created__lte=date_to_datetime(date),
            created__gt=date_to_datetime(date - timedelta(1)),
        ).exclude(
            first_name="",
            last_name=""
        ).count()
        members_count_list.append(members_count)

        memberships_count = Membership.objects.filter(
            member__created__lte=date_to_datetime(date),
            member__created__gt=date_to_datetime(date - timedelta(1)),
            member__plan=choice.MEMBER_PLAN_FREEMIUM,
            role=choice.CASHBOX_ROLE_OWNER
        ).count()
        poolships_count = Poolship.objects.filter(
            member__created__lte=date_to_datetime(date),
            member__created__gt=date_to_datetime(date - timedelta(1)),
            member__plan=choice.MEMBER_PLAN_FREEMIUM,
            role=choice.CASHBOX_ROLE_OWNER
        ).count()
        cashbox_owners_count_list.append(memberships_count)
        moneypool_owners_count_list.append(poolships_count)

        cashboxes_count = Membership.objects.filter(
            created__lte=date_to_datetime(date),
            created__gt=date_to_datetime(date - timedelta(1)),
            member__plan=choice.MEMBER_PLAN_FREEMIUM,
            role=choice.CASHBOX_ROLE_OWNER
        ).count()
        moneypools_count = Poolship.objects.filter(
            created__lte=date_to_datetime(date),
            created__gt=date_to_datetime(date - timedelta(1)),
            member__plan=choice.MEMBER_PLAN_FREEMIUM,
            role=choice.CASHBOX_ROLE_OWNER
        ).count()
        cashboxes_count_list.append(cashboxes_count)
        moneypools_count_list.append(moneypools_count)

        plus_5_member_cashboxes_count = Period.objects.annotate(
            member_count=Count('members')
        ).filter(
            created__lte=date_to_datetime(date),
            created__gt=date_to_datetime(date - timedelta(1)),
            member_count__gte=5
        ).count()
        plus_5_member_moneypools_count = Moneypool.objects.annotate(
            member_count=Count('members')
        ).filter(
            created__lte=date_to_datetime(date),
            created__gt=date_to_datetime(date - timedelta(1)),
            member_count__gte=5
        ).count()
        plus_5_member_cashboxes_count_list.append(plus_5_member_cashboxes_count)
        plus_5_member_moneypools_count_list.append(plus_5_member_moneypools_count)

    file_name = 'reports/new_revenue_7_day_stats-%s.xlsx' % end_date
    workbook = xlsxwriter.Workbook(file_name)
    worksheet = workbook.add_worksheet()
    worksheet.write('A1', 'DATE')
    worksheet.write('B1', 'CASHBOX MEMBERS')
    worksheet.write('C1', 'MONEYPOOL MEMBERS')
    worksheet.write('D1', 'CASHBOXES')
    worksheet.write('E1', 'MONEYPOOLS')
    worksheet.write('F1', '5-MEMBER CASHBOXES')
    worksheet.write('G1', '+5-MEMBER MONEYPOOLS')
    worksheet.write('H1', 'SIGNED-IN MEMBERS')

    def stat_list_2_worksheet(the_worksheet, stat_list, sheet_column='A', start_row=2):
        index = start_row
        for item in stat_list:
            the_worksheet.write(sheet_column + str(index), str(item))
            index += 1
        return the_worksheet

    stat_list_2_worksheet(
        the_worksheet=worksheet,
        stat_list=dates,
        sheet_column='A',
    )
    stat_list_2_worksheet(
        the_worksheet=worksheet,
        stat_list=cashbox_owners_count_list,
        sheet_column='B',
    )
    stat_list_2_worksheet(
        the_worksheet=worksheet,
        stat_list=moneypool_owners_count_list,
        sheet_column='C',
    )
    stat_list_2_worksheet(
        the_worksheet=worksheet,
        stat_list=cashboxes_count_list,
        sheet_column='D',
    )
    stat_list_2_worksheet(
        the_worksheet=worksheet,
        stat_list=moneypools_count_list,
        sheet_column='E',
    )
    stat_list_2_worksheet(
        the_worksheet=worksheet,
        stat_list=plus_5_member_cashboxes_count_list,
        sheet_column='F',
    )
    stat_list_2_worksheet(
        the_worksheet=worksheet,
        stat_list=plus_5_member_moneypools_count_list,
        sheet_column='G',
    )
    stat_list_2_worksheet(
        the_worksheet=worksheet,
        stat_list=members_count_list,
        sheet_column='H',
    )

    workbook.close()

    try:
        mail = EmailMessage(
            subject="new revenue 7-day stats",
            body="Report time in %s" % timezone.now(),
            to=(default.MARKETING_MEMBERS_EMAIL_ADDRESSES
                + default.PRODUCT_OWNER_EMAIL_ADDRESSES),
        )
        mail.attach_file(file_name)
        mail.send()
    except Exception as e:
        error_logger.error("exception in send_new_revenue_7_day_stats %s" % e)
