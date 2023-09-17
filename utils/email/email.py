import os

from django.core.mail import EmailMessage, send_mail

from utils import log
from utils.constants import default
from utils.email import email_templates as email


def send_report_by_mail(box_name, mail_addr, report_file_name):
    try:
        mail = EmailMessage(
            email.FULL_REPORT_SUBJECT.format(box_name),
            email.FULL_REPORT_BODY.format(box_name),
            default.NO_REPLY_EMAIL_ADDRESS,
            [mail_addr],
        )
        mail.attach_file(default.REPORT_FOLDER + report_file_name)
        # print("mail: ", mail.body, mail.from_email, mail.to, mail.subject, mail.attachments)
        mail.send()
    except Exception as exp:
        log.error_logger.error(f"can't open file: {report_file_name}... e: {exp}")
        send_mail(
            f"Error in email send of {report_file_name}",
            f"Error in sending email or attaching report {report_file_name}..., exp: {exp}",
            default.NO_REPLY_EMAIL_ADDRESS,
            default.TECHNICAL_MEMBERS_EMAIL_ADDRESSES,
        )
    return report_file_name


def remove_report_file(file_name):
    try:
        os.remove(default.REPORT_FOLDER + file_name)
    except Exception as e:
        log.error_logger.error(f'error in removing moneypool report {file_name}', e)
