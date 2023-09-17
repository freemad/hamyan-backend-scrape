import csv
from datetime import timedelta

from celery import shared_task
from celery.schedules import crontab
from celery.task import periodic_task
from django.conf import settings
from django.core.mail import EmailMessage, send_mail
from django.shortcuts import get_object_or_404
from django.utils import timezone
from khayyam import JalaliDate

from moneypool_management.models import Moneypool
from moneypool_management.utils import announcement_utils as announce
from moneypool_management.utils.moneypool_utils import (
    get_moneypool_as_string,
    get_moneypool_as_dict,
)
from moneypool_management.utils import report_utils
from utils.announce import Announce, choice as template_choice
from utils.constants import choice
from utils.constants import default
from utils.email import email
from utils.log import info_logger, error_logger
from utils.mixins import persian
from .utils.service_package import get_last_successful_order


@periodic_task(
    run_every=(crontab(hour="9", minute="00")),
    name="moneypool_send_pay_portion_reminder_announcements",
    ignore_results=True,
    queue=choice.CELERY_PERIODIC_QUEUE,
    options={'queue': choice.CELERY_PERIODIC_QUEUE},
)
def moneypool_send_pay_portion_reminder_announcements():
    if settings.DEBUG:
        return
    info_logger.info("Task moneypool_send_pay_portion_reminder_announcements")
    all_active_moneypools = Moneypool.objects.filter(is_archived=False)
    for moneypool in all_active_moneypools:
        try:
            announce.send_pay_portion_reminder_message(moneypool)
            announce.send_pay_portion_reminder_notification(moneypool)
            announce.send_pay_portion_reminder_smses(moneypool)
        except Exception as e:
            error_logger.error("MP pay portion reminder... id: %s, e: %s"
                               % (str(moneypool.id), str(e)))


@periodic_task(
    run_every=(crontab(hour="9", minute="10")),
    name="moneypool_send_delayed_pay_portion_reminder_announcements",
    ignore_results=True,
    queue=choice.CELERY_PERIODIC_QUEUE,
    options={'queue': choice.CELERY_PERIODIC_QUEUE},
)
def moneypool_send_delayed_pay_portion_reminder_announcements():
    if settings.DEBUG:
        return
    info_logger.info("Task moneypool_send_delayed_pay_portion_reminder_announcements")
    all_active_moneypools = Moneypool.objects.filter(is_archived=False)
    for moneypool in all_active_moneypools:
        try:
            announce.send_pay_delayed_portion_reminder_message(moneypool)
            announce.send_pay_delayed_portion_reminder_notification(moneypool)

            announce.send_inform_pay_delayed_portion_reminder_message(moneypool)
            announce.send_inform_pay_delayed_portion_reminder_notification(moneypool)
        except Exception as e:
            error_logger.error("MP delayed pay portion reminder... id: %s, e: %s"
                               % (str(moneypool.id), str(e)))


@periodic_task(
    run_every=(crontab(hour="9", minute="20")),
    name="moneypool_send_pay_installment_reminder_announcements",
    ignore_results=True,
    queue=choice.CELERY_PERIODIC_QUEUE,
    options={'queue': choice.CELERY_PERIODIC_QUEUE},
)
def moneypool_send_pay_installment_reminder_announcements():
    if settings.DEBUG:
        return
    info_logger.info("Task moneypool_send_pay_installment_reminder_announcements")
    all_active_moneypools = Moneypool.objects.filter(is_archived=False)
    for moneypool in all_active_moneypools:
        try:
            announce.send_pay_installment_reminder_message(moneypool)
            announce.send_pay_installment_reminder_notification(moneypool)
            announce.send_pay_installment_reminder_smses(moneypool)
        except Exception as e:
            error_logger.error("MP pay installment reminder... id: %s, e: %s"
                               % (str(moneypool.id), str(e)))


@periodic_task(
    run_every=(crontab(hour="9", minute="30")),
    name="moneypool_send_delayed_pay_installment_reminder_announcements",
    ignore_results=True,
    queue=choice.CELERY_PERIODIC_QUEUE,
    options={'queue': choice.CELERY_PERIODIC_QUEUE},
)
def moneypool_send_delayed_pay_installment_reminder_announcements():
    if settings.DEBUG:
        return
    info_logger.info(
        "Task moneypool_send_delayed_pay_installment_reminder_announcements"
    )
    all_active_moneypools = Moneypool.objects.filter(is_archived=False)
    for moneypool in all_active_moneypools:
        try:
            announce.send_pay_delayed_installment_reminder_message(moneypool)
            announce.send_pay_delayed_installment_reminder_notification(moneypool)

            announce.send_inform_pay_delayed_installment_reminder_message(moneypool)
            announce.send_inform_pay_delayed_installment_reminder_notification(moneypool)
        except Exception as e:
            error_logger.error("MP delayed pay installment reminder... id: %s, e: %s"
                               % (str(moneypool.id), str(e)))


# @periodic_task(
#     run_every=(crontab(hour='10', minute='00', )),
#     name='moneypool_send_pay_invoice_reminder_announcements',
#     ignore_results=True)
# def moneypool_send_pay_invoice_reminder_announcements():
#     info_logger.info("Task moneypool_send_pay_invoice_reminder_announcements")
#     all_active_moneypools = Moneypool.objects.filter(is_archived=False)
#     for moneypool in all_active_moneypools:
#         announce.send_pay_invoice_reminder_message(moneypool)
#         announce.send_pay_invoice_reminder_notification(moneypool)
#         announce.send_pay_invoice_reminder_smses(moneypool)


@periodic_task(
    run_every=(crontab(hour="10", minute="10")),
    name="daily_moneypools_report",
    ignore_results=True,
    queue=choice.CELERY_PERIODIC_QUEUE,
    options={'queue': choice.CELERY_PERIODIC_QUEUE},
)
def daily_moneypools_report(report_datetime=None):
    if settings.DEBUG:
        return
    """
    create and mail the dail moneypool report based on report_datetime
    :param report_datetime: the datetime of report, if None gets the timezone now()
    :return: None, but emails the report to the business and crm members address & also hamyan bulk address
    """
    if not report_datetime:
        report_datetime = timezone.now()
    start_date = report_datetime - timedelta(days=1)
    end_date = start_date + timedelta(days=1)

    ignore_list_numbers = default.DEVELOPERS_TESTERS_PHONE_NUMBERS

    file_name = "reports/moneypools_" + JalaliDate(start_date).__str__() + ".txt"
    file = open(file_name, "w", encoding="utf-8")

    moneypools = Moneypool.objects.filter(
        created__gt=start_date.date(), created__lt=end_date.date()
    )
    moneypools = sorted(list(moneypools), key=lambda k: k.members_count, reverse=True)
    for moneypool in moneypools:
        if moneypool.owner.phone_number in ignore_list_numbers:
            continue
        file.write(get_moneypool_as_string(moneypool))
    file.flush()

    try:
        mail = EmailMessage(
            "Daily Moneypools Report " + JalaliDate(start_date).__str__(),
            "Daily Moneypools Report",
            default.NO_REPLY_EMAIL_ADDRESS,
            default.BUSINESS_MEMBERS_EMAIL_ADDRESSES
            + default.CRM_MEMBERS_EMAIL_ADDRESSES
            + [default.HAMYAN_BULK_EMAIL_ADDRESS],
        )
        mail.attach_file(file_name)
        mail.send(fail_silently=False)
    except Exception as e:
        error_logger("MP daily report send mail attachment error on %s, e: %s"
                     % (JalaliDate(start_date).__str__(), str(e)))
        try:
            send_mail(
                "Daily Moneypools Report",
                "Attachment Error",
                default.NO_REPLY_EMAIL_ADDRESS,
                [default.TECHNICAL_EMAIL_ADDRESS],
                fail_silently=False,
            )
        except Exception as e:
            error_logger("MP daily send mail error on %s, e: %s"
                         % (JalaliDate(start_date).__str__(), str(e)))


@periodic_task(
    run_every=(crontab(hour="10", minute="10")),
    name="daily_moneypools_report_csv",
    ignore_results=True,
    queue=choice.CELERY_PERIODIC_QUEUE,
    options={'queue': choice.CELERY_PERIODIC_QUEUE},
)
def daily_moneypools_report_csv(report_datetime=None):
    if settings.DEBUG:
        return
    """
    create and mail the dail moneypool in csv format report based on report_datetime
    :param report_datetime: the datetime of report, if None gets the timezone now()
    :return: None, but emails the report to the business and crm members address & also hamyan bulk address
    """

    _report_datetime = (
        report_datetime if report_datetime is not None else timezone.now()
    )
    start_date = _report_datetime - timedelta(days=1)
    end_date = start_date + timedelta(days=1)

    ignore_list_numbers = default.DEVELOPERS_TESTERS_PHONE_NUMBERS

    file_name = "reports/moneypools_%s.csv" % (JalaliDate(start_date).__str__())

    moneypools = Moneypool.objects.filter(
        created__gt=start_date.date(), created__lt=end_date.date()
    )
    moneypools = sorted(list(moneypools), key=lambda k: k.members_count, reverse=True)

    fieldnames = [
        "moneypool_name",
        "moneypool_slug",
        "moneypool_type",
        "hamyan_balance",
        "bank_balance",
        "owner_name",
        "owner_number",
        "interval",
        "is_archived",
        "share_value",
        "members",
        "shares",
        "created",
        "due_date",
        "short_URL",
    ]
    with open(file_name, "w", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for moneypool in moneypools:
            if moneypool.owner.phone_number in ignore_list_numbers:
                continue
            writer.writerow(get_moneypool_as_dict(moneypool))

    try:
        mail = EmailMessage(
            "Daily Moneypools CSV Report %s" % (JalaliDate(start_date).__str__()),
            "Daily Moneypools CSV Report",
            default.NO_REPLY_EMAIL_ADDRESS,
            default.BUSINESS_MEMBERS_EMAIL_ADDRESSES
            + default.CRM_MEMBERS_EMAIL_ADDRESSES
            + [default.HAMYAN_BULK_EMAIL_ADDRESS],
        )
        mail.attach_file(file_name)
        mail.send(fail_silently=False)
    except Exception as e:
        error_logger("MP daily CSV report send mail attachment error on %s, e: %s"
                     % (JalaliDate(start_date).__str__(), str(e)))
        try:
            send_mail(
                "Daily Moneypools CSV Report",
                "Attachment Error",
                default.NO_REPLY_EMAIL_ADDRESS,
                [default.TECHNICAL_EMAIL_ADDRESS],
                fail_silently=False,
            )
        except Exception as e:
            error_logger("MP daily CSV send mail error on %s, e: %s"
                         % (JalaliDate(start_date).__str__(), str(e)))


@periodic_task(
    run_every=(crontab(hour="18", minute="00")),
    name="send_service_package_order_reminder",
    ignore_results=True,
    queue=choice.CELERY_PERIODIC_QUEUE,
    options={'queue': choice.CELERY_PERIODIC_QUEUE},
)
def send_service_package_order_reminder():
    moneypools = Moneypool.objects.filter(orders__isnull=False)
    moneypools = list(set(moneypools))
    for moneypool in moneypools:
        remaining_days = moneypool.service_package_remaining_days
        if remaining_days not in (default.DEFAULT_1ST_DELTA_SERVICE_PACKAGE_PAYMENT_REMINDER,
                                  default.DEFAULT_2ND_DELTA_SERVICE_PACKAGE_PAYMENT_REMINDER):
            continue

        order = get_last_successful_order(moneypool)
        if order.is_yearly:
            interval_text = default.YEARLY
        else:
            interval_text = default.MONTHLY
        if order is not None:
            try:
                announce_obj = Announce(
                    template=template_choice.PAY_SERVICE_PACKAGE_ORDER_REMINDER,
                    receiver=moneypool.owner,
                    many=False
                )
                announce_obj.generate_msg(
                    name=moneypool.name,
                    interval=interval_text,
                    days=persian(moneypool.service_package_remaining_days)
                )
                announce_obj.send_sms()
                announce_obj.send_notification()
                announce_obj.send_message()
            except Exception as e:
                error_logger.error("MP order reminder... id: %s, e: %s"
                                   % (str(moneypool.id), str(e)))


@shared_task(queue=choice.CELERY_DEFAULT_QUEUE)
def create_and_mail_moneypool_report(moneypool_id, mail_addr, remove_after=True):
    moneypool = get_object_or_404(Moneypool, id=moneypool_id)
    file_name = report_utils.generate_moneypool_full_report(moneypool=moneypool)
    if file_name:
        file_name = email.send_report_by_mail(
            box_name=moneypool.name,
            mail_addr=mail_addr,
            report_file_name=file_name
        )
        if file_name and remove_after:
            email.remove_report_file(file_name)
