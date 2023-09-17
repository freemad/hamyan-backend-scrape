from django.db.models import Q
from django.http.response import JsonResponse
from django.utils import timezone
from django.shortcuts import render, get_object_or_404

from rest_framework import permissions, status
from rest_framework.decorators import (
    api_view,
    permission_classes,
    renderer_classes,
    throttle_classes,
)
from rest_framework.response import Response
from rest_framework_swagger import renderers

from account_management.models import Bankaccount
from account_management.models.client import Client
from account_management.models.member import Member
from account_management.serializers.bankaccount_serializer import BankaccountSerializer
from account_management.serializers.client_serializer import ClientSerializer
from account_management.utils import create_or_check_bankaccount
from payment.models.gateway import Gateway
from payment.serializers.bank_serializer import BankSerializer
from payment.models.bank import Bank
from peripheral.models import Device
from peripheral.serializers.device_serializer import (
    DeviceSerializer,
    DeviceClientSerializer,
)
from utils import throttle
from utils.constants import client, choice
from utils.response_codes import generate_json_ok_response


@api_view(["POST"])
@throttle_classes(
    [throttle.UserMinuteRate, throttle.UserHourRate, throttle.UserDayRate]
)
@permission_classes((permissions.IsAuthenticated,))
@renderer_classes(
    [renderers.OpenAPIRenderer, renderers.SwaggerUIRenderer, renderers.JSONRenderer]
)
def sync_device(request):
    data = request.data
    member = request.user

    result = dict()
    result["wallet_balance"] = member.wallet_balance
    result["bank_accounts"] = []
    result["gateway_images"] = []

    bankaccounts = Bankaccount.objects.filter(
        Q(member=request.user)
        & Q(is_member_verified=True)
        # & Q(ownership_type=choice.BANK_ACCOUNT_OWNERSHIP_TYPE_MEMBER_OWNED)
        & (Q(state=choice.BANK_ACCOUNT_STATE_ACTIVE)
           | Q(state=choice.BANK_ACCOUNT_STATE_BLOCKED_DEPOSITABLE))
    )
    for bankaccount in bankaccounts:
        result["bank_accounts"].append(BankaccountSerializer(bankaccount).data)

    gateways = Gateway.objects.filter(is_active=True)
    for gateway in gateways:
        gateway_dict = dict()
        gateway_dict["img_url"] = gateway.img_url
        result["gateway_images"].append(gateway_dict)

    result['introduce_name'] = member.introducer.get_full_name() if member.introducer else ''

    if 'device' in data:
        device_data = data.get('device')
        device_data = dict(device_data)
        device_data["member"] = member.id
        device_data["last_login_time"] = timezone.now()
        serialized_device = DeviceSerializer(data=device_data)

        if not serialized_device.is_valid():
            return JsonResponse({"message": "device data is NOT Valid"}, status=400)

        device = Device.objects.filter(
            Q(
                uuid=serialized_device.validated_data.get("uuid"),
                uuid__isnull=False,
                member=member,
            )
            | Q(
                imei=serialized_device.validated_data.get("imei"),
                imei__isnull=False,
                member=member,
            )
            | Q(
                fcm_id=serialized_device.validated_data.get("fcm_id"),
                fcm_id__isnull=False,
                member=member,
            )
        ).first()

        if device:
            serialized_device.update(device, serialized_device.validated_data)
        else:
            device = serialized_device.save()
        client_serialized_device = DeviceClientSerializer(device)
        if not device.is_active:
            return Response(data={"message": "the device is banned."},
                            status=status.HTTP_403_FORBIDDEN)

        result['device'] = client_serialized_device.data

    client_settings = Client.objects.all().first()
    if client_settings:
        result['client'] = ClientSerializer(client_settings).data
        if 'device' in data:
            device_type = device.os_type or request.client_type
            if (device_type in (choice.CLIENT_TYPE_ANDROID, None)
                    and device.app_version in client.CRITICAL_BUGGY_ANDROID_APP_VERSIONS):
                result['client']['android_force_version'] = client.ANDROID_CUSTOM_FORCE_VERSION
                result['client']['android_last_version'] = client.ANDROID_CUSTOM_FORCE_VERSION
                result['client']['android_download_link'] = client.ANDROID_CUSTOM_DOWNLOAD_LINK
    result['banks'] = BankSerializer(Bank.objects.all(), many=True).data
    # set last activity
    member.set_activity()
    return JsonResponse(result, status=200)


@api_view(["POST"])
@throttle_classes(
    [throttle.UserMinuteRate, throttle.UserHourRate, throttle.UserDayRate]
)
@permission_classes((permissions.IsAuthenticated,))
@renderer_classes(
    [renderers.OpenAPIRenderer, renderers.SwaggerUIRenderer, renderers.JSONRenderer]
)
def save_update_iban(request):
    data = request.data
    if "iban" not in data:
        return generate_json_ok_response(1052, "iban")
    iban = data.get("iban")

    if "bankaccount_id" in data:
        bankaccounts = Bankaccount.objects.filter(
            id=data.get("bankaccount_id"), member=request.user
        )
        if bankaccounts.count() == 0:
            return generate_json_ok_response(1051, "bankaccount_id")
        bankaccount = bankaccounts[0]
        bankaccount.iban = iban
        bankaccount.is_member_verified = True
        bankaccount.save()
    else:
        bankaccounts = Bankaccount.objects.filter(
            iban=iban,
            member=request.user
        )
        if bankaccounts.count() > 0:
            bankaccount = bankaccounts[0]
        else:
            bankaccount = Bankaccount.objects.create(
                iban=iban,
                member=request.user,
                is_member_verified=True,
                ownership_type=choice.BANK_ACCOUNT_OWNERSHIP_TYPE_MEMBER_OWNED,
            )

    result = dict()
    result["bankaccount_id"] = bankaccount.id
    result["iban"] = bankaccount.iban
    return generate_json_ok_response(1050, results=result)


@api_view(["POST"])
@throttle_classes(
    [throttle.UserMinuteRate, throttle.UserHourRate, throttle.UserDayRate]
)
@permission_classes((permissions.IsAuthenticated,))
@renderer_classes(
    [renderers.OpenAPIRenderer, renderers.SwaggerUIRenderer, renderers.JSONRenderer]
)
def check_iban(request):
    data = request.data
    if "iban" not in data:
        return generate_json_ok_response(1052, "iban")
    iban = data.get("iban")
    bankaccount = create_or_check_bankaccount(iban=iban, member=request.user)

    result = dict()
    if bankaccount is not None and bankaccount.is_depositable:
        result = BankaccountSerializer(bankaccount).data
        return generate_json_ok_response(1050, results=result)

    return generate_json_ok_response(1049, results=result)


@api_view(["POST"])
@throttle_classes(
    [throttle.UserMinuteRate, throttle.UserHourRate, throttle.UserDayRate]
)
@permission_classes((permissions.IsAuthenticated,))
@renderer_classes(
    [renderers.OpenAPIRenderer, renderers.SwaggerUIRenderer, renderers.JSONRenderer]
)
def verify_iban(request, bankaccount_id):
    bankaccounts = Bankaccount.objects.filter(id=bankaccount_id, member=request.user)
    if bankaccounts.count() == 0:
        return generate_json_ok_response(1051, "bankaccount_id")
    bankaccount = bankaccounts[0]

    bankaccount.is_member_verified = True
    bankaccount.save()

    result = dict()
    result["id"] = bankaccount.id
    result["iban"] = bankaccount.iban
    result["owner_name"] = bankaccount.owner_name
    result["bank_name"] = bankaccount.bank.name if bankaccount.bank else ""
    result["account_state"] = bankaccount.state
    result["account_state_description"] = bankaccount.state_description
    result["is_member_verified"] = bankaccount.is_member_verified
    return generate_json_ok_response(1050, results=result)


@api_view(["GET"])
@throttle_classes(
    [throttle.UserMinuteRate, throttle.UserHourRate, throttle.UserDayRate]
)
@permission_classes((permissions.IsAuthenticated,))
@renderer_classes(
    [renderers.OpenAPIRenderer, renderers.SwaggerUIRenderer, renderers.JSONRenderer]
)
def list_bankaccounts(request):
    bankaccounts = Bankaccount.objects.filter(
        Q(member=request.user)
        & Q(is_member_verified=True)
        & Q(ownership_type=choice.BANK_ACCOUNT_OWNERSHIP_TYPE_MEMBER_OWNED)
        & (
                Q(state=choice.BANK_ACCOUNT_STATE_ACTIVE)
                | Q(state=choice.BANK_ACCOUNT_STATE_BLOCKED_DEPOSITABLE)
        )
    )

    result = dict()
    result["bankaccounts"] = []
    for bankaccount in bankaccounts:
        result["bankaccounts"].append(BankaccountSerializer(bankaccount).data)

    return generate_json_ok_response(1050, results=result)


@api_view(["POST"])
@throttle_classes(
    [throttle.UserMinuteRate, throttle.UserHourRate, throttle.UserDayRate]
)
@permission_classes((permissions.IsAuthenticated,))
@renderer_classes(
    [renderers.OpenAPIRenderer, renderers.SwaggerUIRenderer, renderers.JSONRenderer]
)
def logout(request, device_id):
    devices = Device.objects.filter(member=request.user, id=device_id)

    if devices.count() == 0:
        return JsonResponse({"message": "device not found"}, status=404)

    device = devices[0]
    device.delete()

    return JsonResponse({}, status=200)


@api_view(["POST"])
@throttle_classes(
    [throttle.UserMinuteRate, throttle.UserHourRate, throttle.UserDayRate]
)
@permission_classes((permissions.IsAuthenticated,))
@renderer_classes(
    [renderers.OpenAPIRenderer, renderers.SwaggerUIRenderer, renderers.JSONRenderer]
)
def check_invite_code(request):
    data = dict(request.data)

    if request.user.introducer is None and "invite_code" in data:
        invite_code = data["invite_code"]
        introducer = Member.objects.filter(
            Q(member_key__exact=invite_code) | Q(phone_number__exact=invite_code)
        ).first()
        if introducer and not introducer.id == request.user.id:
            request.user.introducer = introducer
            request.user.save()
            return generate_json_ok_response(
                results={"introducer": introducer.name}, response=1240
            )

    return generate_json_ok_response(response=1241)


def verify_email(request, email, code):
    member = get_object_or_404(Member, email=email)
    if member.check_email_verification_code(code=code):
        member.verification_state = choice.VERIFICATION_STATE_VERIFIED
        member.save()
        return render(
            request,
            'verify_email.html',
            context={'email': email, 'app_link': client.ANDROID_DEEP_LINK}
        )
    else:
        return JsonResponse(data={})
