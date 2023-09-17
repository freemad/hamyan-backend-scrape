from django.http.response import JsonResponse
from rest_framework import permissions
from rest_framework.decorators import (
    api_view,
    renderer_classes,
    permission_classes,
    throttle_classes,
)
from rest_framework.response import Response
from rest_framework_jwt.settings import api_settings
from rest_framework_swagger import renderers

from account_management.models.bankaccount import Bankaccount
from account_management.serializers.bankaccount_serializer import BankaccountSerializer
from cashbox_management.serializers.cashbox_serializer import CashboxSerializer
from cashbox_management.serializers.cycle_serializer import CycleSerializer
from cashbox_management.serializers.membership_serializer import (
    OwnerMembershipSerializer,
    MemberMembershipSerializer,
)
from cashbox_management.serializers.period_serializer import PeriodSerializer
from cashbox_management.serializers.share_group_serializer import ShareGroupSerializer
from payment.models.transaction import Transaction
from payment.serializers.transaction_serializer import TransactionSerializer
from utils import throttle
from utils.constants import choice
from web.decorators import member_of_membership_by_key

jwt_payload_handler = api_settings.JWT_PAYLOAD_HANDLER
jwt_encode_handler = api_settings.JWT_ENCODE_HANDLER
jwt_decode_handler = api_settings.JWT_DECODE_HANDLER


@api_view(["GET"])
@permission_classes(())
@throttle_classes([throttle.WebMinuteRate, throttle.WebHourRate, throttle.WebDayRate])
@member_of_membership_by_key
def cashbox_detail(request, member_key, *args, **kwargs):
    membership = kwargs["membership"]
    cashbox = kwargs["cashbox"]

    if cashbox.is_test or cashbox.is_archived:
        return JsonResponse({'message': 'active cashbox not found'}, status=404)

    if membership.period != cashbox.get_current_period():
        return JsonResponse({"message": "the membership not found"}, status=404)
    period = cashbox.get_current_period()

    if membership.role == choice.CASHBOX_ROLE_OWNER:
        membership_serializer = OwnerMembershipSerializer(
            period.get_valid_memberships(), many=True
        )
    else:
        membership_serializer = MemberMembershipSerializer(
            period.get_valid_memberships(), many=True
        )

    response_data = {
        "cashbox": CashboxSerializer(cashbox, many=False).data,
        "period": PeriodSerializer(period, many=False).data,
        "cycle": CycleSerializer(period.get_current_cycle(), many=False).data,
        "membership": OwnerMembershipSerializer(membership, many=False).data,
        "share_groups": ShareGroupSerializer(period.share_groups.all(), many=True).data,
        "memberships": membership_serializer.data,
    }

    return Response(data=response_data, status=200)


@api_view(["GET"])
@permission_classes((permissions.IsAuthenticated,))
@throttle_classes(
    [throttle.UserMinuteRate, throttle.UserHourRate, throttle.UserDayRate]
)
@renderer_classes(
    [renderers.OpenAPIRenderer, renderers.SwaggerUIRenderer, renderers.JSONRenderer]
)
def cashout_detail(request, cashout_key):
    transaction = Transaction.objects.filter(
        web_key=cashout_key, source=choice.TRANSACTION_SRC_HAMYAN_BOX_BALANCE
    ).first()
    if not transaction:
        return JsonResponse({}, status=404)
    if transaction.receiver != request.user:
        return JsonResponse({}, status=403)

    result = dict()
    result["result"] = TransactionSerializer(transaction).data
    result["result"]["cashbox_name"] = transaction.cycle.cashbox.name
    result["result"]["cycle_index"] = transaction.cycle.index
    result["result"]["member_name"] = request.user.name

    bankaccounts = Bankaccount.objects.filter(
        member=request.user, is_member_verified=True
    )
    result["result"]["bankaccounts"] = []
    for bankaccount in bankaccounts:
        result["result"]["bankaccounts"].append(BankaccountSerializer(bankaccount).data)

    return JsonResponse(result, status=200)
