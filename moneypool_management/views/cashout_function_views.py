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
from moneypool_management.models import Poolship
from moneypool_management.utils import announcement_utils as announce
from moneypool_management.utils.cashout_utils import (
    create_moneypool_cashout,
    get_moneypool_cashouts,
)
from payment.models import MoneypoolCashout
from utils import throttle
from utils.constants import choice, default
from utils.mixins import get_datetime_from_jalali_str
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
def set_cashout(request, id, *args, **kwargs):
    """
    """
    moneypool = kwargs["moneypool"]
    caller_poolship = kwargs["poolship"]
    data = request.data

    if not moneypool.is_registrable:
        return generate_json_ok_response(2101, params=moneypool.type)

    if "amount" not in data:
        return generate_json_ok_response(2052, params="amount")
    amount = data.get("amount")
    if "cashout_type" not in data:
        return generate_json_ok_response(2052, params="cashout_type")
    cashout_type = data.get("cashout_type")
    if cashout_type != choice.MONEYPOOL_CASHOUT_TYPE_CUSTOM:
        return generate_json_ok_response(2051, params="cashout_type")

    if "cashout_tag" not in data or data["cashout_tag"] == "":
        cashout_tag = default.CASHOUT
    else:
        cashout_tag = data.get("cashout_tag")
    if "cashout_time" not in data:
        cashout_time = timezone.now()
    else:
        cashout_time = get_datetime_from_jalali_str(data.get("cashout_time"))
    if not cashout_time:
        return generate_json_ok_response(2051, params="cashout_time")

    if "receiver_id" not in data:
        return generate_json_ok_response(2052, params="receiver_id")
    receiver_poolships = Poolship.objects.filter(
        id=data["receiver_id"], moneypool=moneypool
    )
    if receiver_poolships.count() == 0:
        return generate_json_ok_response(2054, params="receiver_id")
    receiver_poolship = receiver_poolships[0]

    result, cashout = create_moneypool_cashout(
        caller_poolship=caller_poolship,
        receiver_poolship=receiver_poolship,
        amount=amount,
        cashout_type=cashout_type,
        cashout_tag=cashout_tag,
        cashout_time=cashout_time,
        deed_type=choice.MONEYPOOL_DEED_TYPE_RECORD,
    )
    if not cashout:
        return result, None

    announce.send_custom_cashout_bill_message(cashout)
    announce.send_custom_cashout_bill_notification(cashout)
    announce.send_custom_cashout_bill_smses(cashout)

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
def remove_cashout(request, id, cashout_id, *args, **kwargs):
    """
    """
    moneypool = kwargs["moneypool"]
    caller_poolship = kwargs["poolship"]

    if not moneypool.is_registrable:
        return generate_json_ok_response(2101, params=moneypool.type)

    cashout = MoneypoolCashout.objects.filter(
        poolship__moneypool=moneypool, id=cashout_id
    ).first()
    if not cashout:
        return generate_json_ok_response(2054, params="cashout_id")
    if not cashout.is_removable:
        return generate_json_ok_response(2053, params="is_removable")
    if cashout.registrar != caller_poolship:
        return generate_json_ok_response(2053, params="registrar")

    cashout.delete()

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
def list_cashouts(request, id, *args, **kwargs):
    """
    list all cashouts of the specific moneypool
    """
    moneypool = kwargs["moneypool"]
    caller_poolship = kwargs["poolship"]

    result = dict()
    result["cashouts"] = get_moneypool_cashouts(moneypool, caller_poolship.is_manager)

    return generate_json_ok_response(response=2050, results=result)
