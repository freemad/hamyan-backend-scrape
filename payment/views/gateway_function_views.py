import json
from django.http.response import JsonResponse
from rest_framework import permissions
from rest_framework.decorators import (
    api_view,
    permission_classes,
    renderer_classes,
    throttle_classes,
)
from rest_framework_swagger import renderers

from account_management.models import Client
from cashbox_management.decorators import has_member_role, has_owner_role
from cashbox_management.models import Membership, Cashbox
from payment.models import Gateway
from payment.models.transaction import Transaction
from utils import throttle
from utils.constants import choice
from utils.response_codes import generate_json_ok_response


@api_view(["POST"])
@throttle_classes(
    [throttle.UserMinuteRate, throttle.UserHourRate, throttle.UserDayRate]
)
@permission_classes((permissions.IsAuthenticated,))
@renderer_classes(
    [renderers.OpenAPIRenderer, renderers.SwaggerUIRenderer, renderers.JSONRenderer]
)
@has_member_role
def request_gateway_pay(request, id):
    """
    requests the payment through selected gateway
    :param request: body of the request contains the following params:
    'gateway_id': the id of the selected gateway provided for client in init_pay()
    'client_type': the type of the client that even 'android' or 'iphone'
    'total_amount': the total amount of payment (the amount plus commission)
    'destination': the destination of the payment that could be CASHBOX or WALLET
    'receiver_membership_id': the id of the receiver membership
    :param id: the cashbox id
    :return: a json response o 200 contains appropriate message and code
    """
    body = request.body.decode()
    body = body.replace("'", '"')
    data = json.loads(body)

    if "gateway_id" not in data:
        return generate_json_ok_response(1111, params="gateway_id")
    gateway = Gateway.objects.filter(id=data.get("gateway_id"), is_active=True)
    if gateway.count() == 0:
        return generate_json_ok_response(1112, params="gateway")
    gateway = gateway[0]

    payer = request.user
    if payer is None:
        return generate_json_ok_response(1112, params="payer member")

    if "client_type" not in data:
        client_type = choice.CLIENT_TYPE_ANDROID
    else:
        client_type = data.get("client_type")

    if "total_amount" not in data:
        return generate_json_ok_response(1111, params="total_amount")
    total_amount = data.get("total_amount")

    if "destination" not in data:
        return generate_json_ok_response(1111, params="destination")
    destination = data.get("destination")
    if destination not in (
        choice.TRANSACTION_DST_HAMYAN_BOX_BALANCE,
        choice.TRANSACTION_DST_HAMYAN_WALLET
    ):
        return generate_json_ok_response(1113)

    result = dict()
    transaction = None
    amount = total_amount

    cashbox = Cashbox.objects.filter(id=id).first()
    if cashbox is None:
        return generate_json_ok_response(1112, params="cashbox")
    if not cashbox.state == choice.CASHBOX_STATE_ACTIVATED:
        return generate_json_ok_response(1114)

    if destination == choice.TRANSACTION_DST_HAMYAN_WALLET:
        transaction = Transaction.objects.create(
            payer=payer,
            receiver=payer,
            ctx_id=cashbox.get_current_period().get_current_cycle().id,
            ctx_type=choice.TRANSACTION_CTX_TYPE_CYCLE,
            gateway=gateway,
            amount=amount,
            source=choice.TRANSACTION_SRC_GATEWAY,
            destination=choice.TRANSACTION_DST_HAMYAN_WALLET,
        )

    if destination == choice.TRANSACTION_DST_HAMYAN_BOX_BALANCE:
        if cashbox.is_worried_box:
            destination = choice.TRANSACTION_DST_BOX_BANKACCOUNT

        # todo: check w client devs if no receiver_membership, set it to payer or not
        if "receiver_membership_id" not in data:
            return generate_json_ok_response(1111, params="receiver_membership_id")
        receiver = (
            Membership.objects.filter(id=data.get("receiver_membership_id"))
            .first()
            .member
        )
        receiver_membership = Membership.objects.filter(
            id=data.get("receiver_membership_id")
        ).first()
        if receiver is None:
            return generate_json_ok_response(1112, params="receiver member")
        commission = receiver_membership.calculate_remaining_commission()
        transaction = Transaction.objects.create(
            payer=payer,
            receiver=receiver,
            ctx_id=cashbox.get_current_period().get_current_cycle().id,
            ctx_type=choice.TRANSACTION_CTX_TYPE_CYCLE,
            gateway=gateway,
            amount=total_amount - commission,
            commission=commission,
            source=choice.TRANSACTION_SRC_GATEWAY,
            destination=destination,
        )

    # if not transaction.is_full_provided():
    #     return JsonResponse({'message': 'the transaction is not full provided'}, status=404)
    pay_url = gateway.request_pay(transaction, client_type)
    result = dict()
    if transaction.state == choice.TRANSACTION_STATE_UNSUCCESSFUL:
        return generate_json_ok_response(1115)

    result = {
        "transaction_code": transaction.transaction_code
        if transaction is not None
        else None,
        "token": transaction.token if transaction is not None else None,
        "amount": amount,
        "commission": total_amount - amount,
        "pay_url": pay_url,
        "gateway_type": gateway.type,
    }

    return generate_json_ok_response(1110, results=result)


@api_view(["POST"])
@throttle_classes(
    [throttle.UserMinuteRate, throttle.UserHourRate, throttle.UserDayRate]
)
@permission_classes((permissions.IsAuthenticated,))
@renderer_classes(
    [renderers.OpenAPIRenderer, renderers.SwaggerUIRenderer, renderers.JSONRenderer]
)
@has_owner_role
def request_group_pay(request, id):
    cashbox = Cashbox.objects.get(id=id)

    body = request.body.decode()
    body = body.replace("'", '"')
    data = json.loads(body)

    if "client_type" not in data:
        client_type = choice.CLIENT_TYPE_ANDROID
    else:
        client_type = data.get("client_type")

    if "memberships" not in data:
        return JsonResponse({"Message", "No Membership in request"}, status=400)
    memberships = data.get("memberships")

    if 'gateway_id' not in data:
        group_gateway_unique_code = Client.objects.all()[0].preset_gateway.unique_code
        gateway = Gateway.objects.filter(
            unique_code=group_gateway_unique_code, is_active=True
        ).first()
    else:
        gateway = Gateway.objects.filter(
            id=data.get("gateway_id"), is_active=True
        ).first()
        if not gateway:
            return generate_json_ok_response(1112, params="gateway")

    membership_list = []
    commission_sum = 0
    total_sum = 0
    for m in memberships:
        membership = Membership.objects.filter(id=m["id"], period__cashbox=cashbox)
        if membership.count() == 0:
            continue
        membership = membership[0]

        membership_list.append(membership)
        commission_sum += membership.calculate_remaining_commission()
        total_sum += (
            membership.calculate_remaining_commission()
            + membership.calculate_remaining_share()
        )

    destination = choice.TRANSACTION_DST_HAMYAN_BOX_BALANCE
    if cashbox.is_worried_box:
        destination = choice.TRANSACTION_DST_BOX_BANKACCOUNT
    mother_transaction = Transaction.objects.create(
        payer=request.user,
        receiver=None,
        gateway=gateway,
        amount=total_sum - commission_sum,
        commission=commission_sum,
        ctx_id=cashbox.get_current_period().get_current_cycle().id,
        ctx_type=choice.TRANSACTION_CTX_TYPE_CYCLE,
        source=choice.TRANSACTION_SRC_GATEWAY,
        destination=destination,
        is_group_pay=True,
    )

    for m in membership_list:
        Transaction.objects.create(
            payer=request.user,
            receiver=m.member,
            gateway=gateway,
            amount=m.calculate_remaining_share(),
            commission=m.calculate_remaining_commission(),
            ctx_id=cashbox.get_current_period().get_current_cycle().id,
            ctx_type=choice.TRANSACTION_CTX_TYPE_CYCLE,
            source=choice.TRANSACTION_SRC_GATEWAY,
            destination=destination,
            mother_transaction=mother_transaction,
        )

    pay_url = gateway.request_pay(mother_transaction, client_type)
    if mother_transaction.state == choice.TRANSACTION_STATE_UNSUCCESSFUL:
        return generate_json_ok_response(1115)

    result = {
        "transaction_code": mother_transaction.transaction_code
        if mother_transaction is not None
        else None,
        "token": mother_transaction.token if mother_transaction is not None else None,
        "amount": total_sum,
        "commission": commission_sum,
        "pay_url": pay_url,
        "gateway_type": gateway.type,
    }

    return JsonResponse({"result": result}, status=200)
