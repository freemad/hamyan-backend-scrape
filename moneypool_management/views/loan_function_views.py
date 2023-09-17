from django.utils import timezone
from rest_framework import permissions
from rest_framework.decorators import (
    api_view,
    permission_classes,
    renderer_classes,
    throttle_classes,
)
from rest_framework_swagger import renderers

from moneypool_management.decorators import (
    is_moneypool_owner_or_manager,
    is_moneypool_member,
)
from moneypool_management.models import Poolship, Loan
from moneypool_management.utils import announcement_utils as announce
from moneypool_management.utils.installment_utils import payoff_multiple_installments
from moneypool_management.utils.loan_utils import (
    create_moneypool_loan,
    get_moneypool_loans_data,
    remove_moneypool_loan,
)
from payment.api.serializers import LoanSerializer
from utils import throttle
from utils.constants import choice, default
from utils.mixins import get_datetime_from_jalali_str, get_date_from_jalali_str
from utils.response_codes import generate_json_ok_response


@api_view(["POST"])
@throttle_classes(
    [throttle.UserMinuteRate, throttle.UserHourRate, throttle.UserDayRate]
)
@permission_classes((permissions.IsAuthenticated,))
@renderer_classes(
    [renderers.OpenAPIRenderer, renderers.SwaggerUIRenderer, renderers.JSONRenderer]
)
@is_moneypool_owner_or_manager
def create_loan(request, id, *args, **kwargs):
    """
    """
    moneypool = kwargs["moneypool"]
    caller_poolship = kwargs["poolship"]
    data = request.data

    if not moneypool.is_registrable and "number_of_repaid_installments" not in data:
        return generate_json_ok_response(2101, params=moneypool.type)

    if "amount" not in data or not isinstance(data["amount"], int):
        return generate_json_ok_response(2052, params="amount")
    amount = data.get("amount")
    if "number_of_repayments" not in data or not isinstance(
        data["number_of_repayments"], int
    ):
        return generate_json_ok_response(2052, params="number_of_repayments")
    number_of_repayments = data.get("number_of_repayments")
    if (
        "number_of_repaid_installments" not in data
        or not isinstance(data.get("number_of_repaid_installments"), int)
        or int(data.get("number_of_repaid_installments")) < 0
    ):
        number_of_repaid_installments = 0
    else:
        number_of_repaid_installments = int(data.get("number_of_repaid_installments"))

    if "repayment_interval" not in data:
        return generate_json_ok_response(2052, params="repayment_interval")
    repayment_interval = data.get("repayment_interval")
    if repayment_interval not in dict(choice.MONEYPOOL_INTERVAL):
        return generate_json_ok_response(2051, params="repayment_interval")

    if "payment_time" not in data or data["payment_time"] == "":
        payment_time = timezone.now()
    else:
        payment_time = get_datetime_from_jalali_str(data.get("payment_time"))
    pay_date = payment_time.date()
    due_date = None
    if "due_date" in data and data["due_date"] != "":
        due_date = get_date_from_jalali_str(data.get("due_date"))
    if due_date and due_date <= pay_date:
        return generate_json_ok_response(2052, params="due_date <= pay_date")

    if "cashout_tag" not in data or data["cashout_tag"] == "":
        cashout_tag = default.LOAN
    else:
        cashout_tag = data.get("cashout_tag")
    if "interest_rate" not in data:
        interest_rate = 0.0
    else:
        interest_rate = data.get("interest_rate")
    if "interest_pay_mode" not in data:
        interest_pay_mode = choice.LOAN_INTEREST_PAY_MODE_MID_APPENDED
    else:
        interest_pay_mode = data.get("interest_pay_mode")
    # if not pay_date:
    #     return generate_json_ok_response(2051, params='pay_date')
    # if not payment_time:
    #     return generate_json_ok_response(2051, params='payment_time')

    if "receiver_id" not in data:
        return generate_json_ok_response(2052, params="receiver_id")
    receiver_poolships = Poolship.objects.filter(
        id=data["receiver_id"], moneypool=moneypool
    )
    if receiver_poolships.count() == 0:
        return generate_json_ok_response(2054, params="receiver_id")
    receiver_poolship = receiver_poolships[0]
    loan_demand_id = data.get('loan_demand_id', None)

    result, loan = create_moneypool_loan(
        caller_poolship=caller_poolship,
        receiver_poolship=receiver_poolship,
        amount=amount,
        cashout_tag=cashout_tag,
        deed_type=choice.MONEYPOOL_DEED_TYPE_RECORD,
        number_of_repayments=number_of_repayments,
        repayment_interval=repayment_interval,
        due_date=due_date,
        interest_rate=interest_rate,
        interest_pay_mode=interest_pay_mode,
        pay_date=pay_date,
        cashout_time=payment_time,
        loan_demand_id=loan_demand_id
    )
    payoff_multiple_installments(
        caller_poolship=caller_poolship,
        loan=loan,
        number_of_repaid_installments=number_of_repaid_installments,
    )

    announce.send_define_loan_message(loan)
    announce.send_define_loan_notification(loan)
    announce.send_define_loan_self_sms(loan)
    announce.send_define_loan_smses(loan)

    return generate_json_ok_response(2110, results=result)


@api_view(["POST"])
@throttle_classes(
    [throttle.UserMinuteRate, throttle.UserHourRate, throttle.UserDayRate]
)
@permission_classes((permissions.IsAuthenticated,))
@renderer_classes(
    [renderers.OpenAPIRenderer, renderers.SwaggerUIRenderer, renderers.JSONRenderer]
)
@is_moneypool_owner_or_manager
def remove_loan(request, id, loan_id, *args, **kwargs):
    """
    """
    moneypool = kwargs["moneypool"]
    caller_poolship = kwargs["poolship"]

    if not moneypool.is_registrable:
        return generate_json_ok_response(2101, params=moneypool.type)

    loan = Loan.objects.filter(
        cashout__poolship__moneypool=moneypool, id=loan_id
    ).first()
    if not loan:
        return generate_json_ok_response(2054, params="loan_id")
    if not loan.is_removable:
        return generate_json_ok_response(2053, params="is_removable")
    if loan.cashout.registrar != caller_poolship:
        return generate_json_ok_response(2053, params="registrar")
    if not remove_moneypool_loan(loan):
        return generate_json_ok_response(2053)

    return generate_json_ok_response(2050)


@api_view(["GET"])
@throttle_classes(
    [throttle.UserMinuteRate, throttle.UserHourRate, throttle.UserDayRate]
)
@permission_classes((permissions.IsAuthenticated,))
@renderer_classes(
    [renderers.OpenAPIRenderer, renderers.SwaggerUIRenderer, renderers.JSONRenderer]
)
@is_moneypool_member
def list_loans(request, id, *args, **kwargs):
    """
    list all loans of the specific moneypool
    """
    moneypool = kwargs["moneypool"]

    result = dict()
    result["loans"] = get_moneypool_loans_data(moneypool)

    return generate_json_ok_response(response=2050, results=result)


@api_view(["POST"])
@throttle_classes(
    [throttle.UserMinuteRate, throttle.UserHourRate, throttle.UserDayRate]
)
@permission_classes((permissions.IsAuthenticated,))
@renderer_classes(
    [renderers.OpenAPIRenderer, renderers.SwaggerUIRenderer, renderers.JSONRenderer]
)
@is_moneypool_owner_or_manager
def grace_installments(request, id, loan_id, *args, **kwargs):
    """
    """
    data = request.data

    if "grace_intervals_count" not in data or not isinstance(
            data["grace_intervals_count"], int
    ):
        return generate_json_ok_response(2052, params="grace_intervals_count")

    grace_intervals_count = data.get("grace_intervals_count", 0)
    loan = Loan.objects.filter(id=loan_id).first()
    if not loan:
        return generate_json_ok_response(2054, params="loan_id")
    if loan.is_fully_repaid:
        return generate_json_ok_response(2051, params="loan_fully_repaid")

    loan.grace_installments(grace_intervals_count=grace_intervals_count)
    return generate_json_ok_response(response=2050, results=LoanSerializer(loan).data)
