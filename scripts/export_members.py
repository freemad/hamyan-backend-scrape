# -*- coding: utf-8 -*-
from django.core.mail import EmailMessage, send_mail
from django.utils import timezone
from khayyam import JalaliDatetime

from account_management.models import Member
from utils.constants import default
from utils.log import error_logger


def export_members():
    file_stamp = timezone.now().__str__().replace(" ", "-")
    file_name = "reports/members_at_%s.csv" % file_stamp
    members_as_csv = open(file_name, "w+", encoding="utf-8")

    print("beginning to export...")
    for member in Member.objects.all().order_by("-last_name"):
        member_record = ",".join([member.phone_number, member.get_full_name()]).encode(
            "utf-8"
        )
        members_as_csv.write(member_record.decode("utf-8"))
        members_as_csv.write("\n")

    members_as_csv.close()
    print("timestamp: " + file_stamp)

    try:
        mail = EmailMessage(
            "Member Export %s" % (JalaliDatetime(timezone.now()).__str__()),
            "Member Export",
            default.NO_REPLY_EMAIL_ADDRESS,
            default.TECHNICAL_EMAIL_ADDRESS + [default.HAMYAN_BULK_EMAIL_ADDRESS],
        )
        mail.attach_file(file_name)
        mail.send(fail_silently=False)
    except:
        try:
            send_mail(
                "Daily Cashbox Report",
                "Attachment Error",
                default.NO_REPLY_EMAIL_ADDRESS,
                [default.TECHNICAL_EMAIL_ADDRESS],
            )
        except:
            error_logger(
                "send mail error on %s" % (JalaliDatetime(timezone.now()).__str__())
            )
