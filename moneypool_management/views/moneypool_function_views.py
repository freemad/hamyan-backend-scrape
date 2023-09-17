import json

from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.db.models import Q
from django.http.response import JsonResponse
from django.utils import timezone
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
from cashbox_management.views.cashbox_function_views import cashbox_list
from moneypool_management.decorators import (
    is_moneypool_member,
    is_moneypool_owner,
    is_moneypool_owner_or_manager)
from moneypool_management.models import Moneypool, Loan, Poolship
from moneypool_management.serializers.loan_serializer import LoanSerializer
from moneypool_management.serializers.moneypool_serializer import MoneypoolSerializer
from moneypool_management.utils import announcement_utils as announce
from moneypool_management.utils.moneypool_utils import get_moneypool_data
from payment.models import MoneypoolCashin, MoneypoolCashout
from payment.serializers.moneypool_cashin_serializer import (
    OpenMoneypoolCashinSerializer,
    RestrictedMoneypoolCashinSerializer,
)
from payment.serializers.moneypool_cashout_serializer import (
    OpenMoneypoolCashoutSerializer,
    RestrictedMoneypoolCashoutSerializer,
)
from payment.utils import transfer_hamyan_balance_to_bank
from utils import throttle
from utils.constants import default, choice
from utils.response_codes import generate_json_ok_response


@api_view(["POST"])
@throttle_classes(
    [throttle.UserMinuteRate, throttle.UserHourRate, throttle.UserDayRate]
)
@permission_classes((permissions.IsAuthenticated,))
@renderer_classes(
    [renderers.OpenAPIRenderer, renderers.SwaggerUIRenderer, renderers.JSONRenderer]
)
def create_moneypool(request):
    """
    create a moneypool
    the sample data:
    {
        "share_value": 10000, // * the share value of the moneypool
        "name": "moneypool name", // * moneypool name
        "interval": "mnt", // * see MONEYPOOL_INTERVAL
        "day_of_duetion": 4, // * 1-30 or 1-7 due to thr "interval"
        "type": choice.MONEYPOOL_TYPE_PAYABLE, // see MONEYPOOL_TYPE
        "number_of_shares": 2, // number or shares of owner
        "image_id": 5, // the id of the image avatar
        "bank_account": 2, // the id of the bank_account obj
        "bank_balance": 200000, // the initial bank balance (for registrable or hybrid moneypool)
    }
    :param request: the request object contains data above
    :return: announces the creation to the owner and returns an OK response with 2100 custom code
             containing moneypool, bank_account and owner's poolship data
             and 2052, 2051 custom code if there is an error
    """
    owned_moneypools = request.user.get_owned_moneypools()
    owned_cashboxes = request.user.get_owned_cashboxes()
    state = choice.MONEYPOOL_STATE_ACTIVATED
    moneypool_type = choice.MONEYPOOL_TYPE_HYBRID_SINGLE_PAY
    notification_announce = choice.ANNOUNCEMENT_MODE_JUST_OWNER
    sms_announce = choice.ANNOUNCEMENT_MODE_JUST_OWNER
    if request.user.plan == choice.MEMBER_PLAN_HAMYAN:
        moneypool_type = choice.MONEYPOOL_TYPE_PAYABLE
        notification_announce = choice.ANNOUNCEMENT_MODE_ANNOUNCE_ALL
        sms_announce = choice.ANNOUNCEMENT_MODE_ANNOUNCE_ALL

    # already have a box check boxes
    # if there is any permission about unlimited box creation
    # state set to activated
    if len(owned_cashboxes) + len(owned_moneypools) > 0:
        for cbx in owned_cashboxes:
            if (
                    not cbx.has_perm(choice.FEATURE_UNLIMITED_CREATE_BOX)
                    and cbx.state != choice.CASHBOX_STATE_UNPAID
                    and not cbx.is_test
                    and not cbx.is_archived
            ):
                state = choice.CASHBOX_STATE_UNPAID
        for mp in owned_moneypools:
            if (
                    not mp.has_perm(choice.FEATURE_UNLIMITED_CREATE_BOX)
                    and mp.state != choice.CASHBOX_STATE_UNPAID
                    and not mp.is_archived
            ):
                state = choice.CASHBOX_STATE_UNPAID

    elif len(owned_cashboxes) + len(owned_moneypools) == 0:
        state = choice.MONEYPOOL_STATE_ACTIVATED
    data = request.data
    if not data:
        return generate_json_ok_response(response=2052, params="data")
    if "share_value" not in data:
        return generate_json_ok_response(response=2052, params="share_value")

    share_value = data.pop("share_value")
    if "number_of_shares" in data:
        number_of_shares = data.pop("number_of_shares")
    else:
        number_of_shares = 1
    moneypool_data = data
    moneypool_serializer = MoneypoolSerializer(data=moneypool_data)
    if not moneypool_serializer.is_valid():
        return generate_json_ok_response(response=2051)

    moneypool = moneypool_serializer.save(
        state=state,
        type=moneypool_type,
        notification_announce=notification_announce,
        sms_announce=sms_announce
    )
    moneypool.set_or_update_share_value(share_value)
    moneypool.initiate_next_interval()
    moneypool.create_owner_poolship(
        owner=request.user, number_of_shares=number_of_shares
    )
    moneypool.create_moneypool_commission()
    announce.send_create_moneypool_message(moneypool)
    announce.send_create_moneypool_notification(moneypool)
    return generate_json_ok_response(
        response=2100, results=get_moneypool_data(moneypool, request.user)
    )


@api_view(["GET"])
@throttle_classes(
    [throttle.UserMinuteRate, throttle.UserHourRate, throttle.UserDayRate]
)
@permission_classes((permissions.IsAuthenticated,))
@renderer_classes(
    [renderers.OpenAPIRenderer, renderers.SwaggerUIRenderer, renderers.JSONRenderer]
)
@is_moneypool_member
def get_moneypool(request, id, *args, **kwargs):
    return JsonResponse(
        get_moneypool_data(kwargs["moneypool"], request.user), status=200
    )


@api_view(["GET"])
@throttle_classes(
    [throttle.UserMinuteRate, throttle.UserHourRate, throttle.UserDayRate]
)
@permission_classes((permissions.IsAuthenticated,))
@renderer_classes(
    [renderers.OpenAPIRenderer, renderers.SwaggerUIRenderer, renderers.JSONRenderer]
)
def moneypool_list(request):
    moneypools = (
        Moneypool.objects.filter(
            Q(is_archived=False)
            & Q(poolships__member=request.user)
        ).distinct().order_by("-created")
    )
    results = dict()
    moneypools.check_and_update_due_dates()
    results["moneypools"] = []
    for moneypool in moneypools:
        moneypool_data = get_moneypool_data(
            moneypool=moneypool,
            member=request.user,
            should_fail=True
        )
        if moneypool_data == -1:
            continue
        results["moneypools"].append(moneypool_data)
    return generate_json_ok_response(response=2050, results=results)


@api_view(["GET"])
@throttle_classes(
    [throttle.UserMinuteRate, throttle.UserHourRate, throttle.UserDayRate]
)
@permission_classes((permissions.IsAuthenticated,))
@renderer_classes(
    [renderers.OpenAPIRenderer, renderers.SwaggerUIRenderer, renderers.JSONRenderer]
)
def moneypool_and_cashbox_list(request):
    moneypool_list_response = json.loads(
        moneypool_list(request).content.decode("UTF-8")
    )
    cashbox_list_response = json.loads(
        cashbox_list(request).content.decode("UTF-8")
    )
    results = dict()
    results["moneypools"] = moneypool_list_response.get("results").get("moneypools")
    results["cashboxes"] = cashbox_list_response.get("results")
    return generate_json_ok_response(response=2050, results=results)


@api_view(["POST"])
@throttle_classes(
    [throttle.UserMinuteRate, throttle.UserHourRate, throttle.UserDayRate]
)
@permission_classes((permissions.IsAuthenticated,))
@renderer_classes(
    [renderers.OpenAPIRenderer, renderers.SwaggerUIRenderer, renderers.JSONRenderer]
)
@is_moneypool_owner_or_manager
def update_moneypool(request, id, *args, **kwargs):
    moneypool = kwargs["moneypool"]
    caller_poolship = kwargs["poolship"]
    assert isinstance(moneypool, Moneypool)
    assert isinstance(caller_poolship, Poolship)
    data = request.data
    if not data:
        return generate_json_ok_response(response=2052, params="data")
    if "bank_account" in data and data.get("bank_account"):
        bank_accounts = Bankaccount.objects.filter(
            id=data.get("bank_account"), member=caller_poolship.member
        )
        if bank_accounts.count() == 0:
            return generate_json_ok_response(response=2051, params="bank_account")

    share_value = None
    if "share_value" in data and isinstance(data.get("share_value"), int):
        share_value = data.pop("share_value")
    if "number_of_shares" in data:
        number_of_shares = int(data.pop("number_of_shares"))
        caller_poolship.set_or_update_number_of_shares(number_of_shares)
    update_moneypool_serializer = MoneypoolSerializer(instance=moneypool, data=data)
    if not update_moneypool_serializer.is_valid():
        return generate_json_ok_response(response=2051, params="moneypool data")

    is_changed_trust_state = False
    trust_state = update_moneypool_serializer.validated_data.get("trust_state", None)
    if trust_state is not None and trust_state != moneypool.trust_state:
        if trust_state == choice.TRUST_STATE_WORRIED_IN_PROGRESS:
            is_changed_trust_state = True
    update_moneypool_serializer.update(
        instance=moneypool, validated_data=update_moneypool_serializer.validated_data
    )
    if is_changed_trust_state:
        transfer_hamyan_balance_to_bank(box=moneypool)
    if share_value is not None:
        moneypool.set_or_update_share_value(share_value)
    if (not moneypool.due_date
            or moneypool.get_next_due_date(timezone.now().date()) != moneypool.due_date):
        moneypool.due_date = moneypool.get_next_due_date(timezone.now().date())
        moneypool.save()
        if moneypool.is_interval_terminated():
            moneypool.initiate_next_interval()
    announce.send_moneypool_update_messages(moneypool)
    announce.send_moneypool_update_notifications(moneypool)
    return generate_json_ok_response(
        response=2050, results=get_moneypool_data(moneypool, request.user)
    )


@api_view(["POST"])
@throttle_classes(
    [throttle.UserMinuteRate, throttle.UserHourRate, throttle.UserDayRate]
)
@permission_classes((permissions.IsAuthenticated,))
@renderer_classes(
    [renderers.OpenAPIRenderer, renderers.SwaggerUIRenderer, renderers.JSONRenderer]
)
@is_moneypool_owner
def archive_moneypool(request, id, *args, **kwargs):
    moneypool = kwargs["moneypool"]
    assert isinstance(moneypool, Moneypool)
    if moneypool.is_removable:
        moneypool.archive()
        announce.send_moneypool_archive_messages(moneypool)
        announce.send_moneypool_archive_notification(moneypool)
        return generate_json_ok_response(2050)

    data = {'detail': 'Moneypool object is not removable'}
    return Response(data=data, status=status.HTTP_406_NOT_ACCEPTABLE)


@api_view(["GET"])
@throttle_classes(
    [throttle.UserMinuteRate, throttle.UserHourRate, throttle.UserDayRate]
)
@permission_classes((permissions.IsAuthenticated,))
@renderer_classes(
    [renderers.OpenAPIRenderer, renderers.SwaggerUIRenderer, renderers.JSONRenderer]
)
@is_moneypool_member
def list_moneypool_cashins_and_cashouts(request, id, *args, **kwargs):
    """
    list all cashins and cashouts of the specific moneypool
    """
    moneypool = kwargs["moneypool"]
    caller_poolship = kwargs["poolship"]
    assert isinstance(moneypool, Moneypool)
    assert isinstance(caller_poolship, Poolship)
    result_list = list()
    cashins = MoneypoolCashin.objects.filter(
        Q(poolship__moneypool=moneypool)
        & (Q(transaction__isnull=True)
           | Q(transaction__state__in=(
                    choice.TRANSACTION_STATE_SUCCESSFUL,
                    choice.TRANSACTION_STATE_IN_PROGRESS,
                    choice.TRANSACTION_STATE_TO_BANK
                )))
    )
    cashouts = MoneypoolCashout.objects.filter(
        Q(poolship__moneypool=moneypool)
        & (Q(transaction__isnull=True)
           | Q(transaction__state__in=(
                    choice.TRANSACTION_STATE_SUCCESSFUL,
                    choice.TRANSACTION_STATE_IN_PROGRESS,
                    choice.TRANSACTION_STATE_TO_BANK
                )))
    )
    if "q" in request.GET:
        query = request.GET.get("q")
        cashins = cashins.filter(
            Q(poolship__member__first_name__contains=query)
            | Q(poolship__member__last_name__contains=query)
        )
        cashouts = cashouts.filter(
            Q(poolship__member__first_name__contains=query)
            | Q(poolship__member__last_name__contains=query)
        )
    if caller_poolship.is_manager:
        result_list = OpenMoneypoolCashinSerializer(cashins, many=True).data
        result_list += OpenMoneypoolCashoutSerializer(cashouts, many=True).data
    else:
        result_list = RestrictedMoneypoolCashinSerializer(cashins, many=True).data
        result_list += RestrictedMoneypoolCashoutSerializer(cashouts, many=True).data
    # for cashin in cashins:
    #     if not cashin.is_reportable:
    #         continue
    #
    #     if caller_poolship.is_manager:
    #         result_list.append(OpenMoneypoolCashinSerializer(cashin).data)
    #     else:
    #         result_list.append(RestrictedMoneypoolCashinSerializer(cashin).data)
    # for cashout in cashouts:
    #     if not cashout.is_reportable:
    #         continue
    #
    #     if caller_poolship.is_manager:
    #         result_list.append(OpenMoneypoolCashoutSerializer(cashout).data)
    #     else:
    #         result_list.append(RestrictedMoneypoolCashoutSerializer(cashout).data)

    result_list.sort(key=lambda cio: cio["time"], reverse=True)
    result = dict()
    if "page" in request.GET:
        paginator = Paginator(result_list, default.PAGINATION)
        num_page = request.GET.get("page")
        try:
            result_list = paginator.page(num_page)
        except PageNotAnInteger:
            result_list = paginator.page(1)
        except EmptyPage:
            result_list = paginator.page(paginator.num_pages)
        result["pagination"] = dict()
        result["pagination"]["has_next"] = result_list.has_next()
        result["pagination"]["has_previous"] = result_list.has_previous()

    result["result"] = list(result_list)
    return generate_json_ok_response(response=2050, results=result)


@api_view(["GET"])
@throttle_classes(
    [throttle.UserMinuteRate, throttle.UserHourRate, throttle.UserDayRate]
)
@permission_classes((permissions.IsAuthenticated,))
@renderer_classes(
    [renderers.OpenAPIRenderer, renderers.SwaggerUIRenderer, renderers.JSONRenderer]
)
@is_moneypool_member
def list_moneypool_loans_and_installments(request, id, *args, **kwargs):
    """
    list all loans and installments of the specific moneypool
    """
    moneypool = kwargs["moneypool"]
    poolship = kwargs["poolship"]
    assert isinstance(moneypool, Moneypool)
    assert isinstance(poolship, Poolship)

    def sort_list_loans(loan, poolship=poolship):
        # global poolship
        if poolship.role == choice.MONEYPOOL_ROLE_NORMAL:
            if loan['poolship'] == poolship.id:
                return 1
            return 2
        # poolship is in owner or manager role
        if loan['poolship'] == poolship.id:
            return 1
        elif loan['has_deleyed_installment']:
            return 2
        return 3

    result = dict()
    result["loans"] = list()
    loans = Loan.objects.filter(
        Q(cashout__poolship__moneypool=moneypool)
        & (
                Q(
                    cashout__transaction__state__in=(
                        choice.TRANSACTION_STATE_IN_PROGRESS,
                        choice.TRANSACTION_STATE_SUCCESSFUL,
                        choice.TRANSACTION_STATE_TO_BANK,
                    )
                )
                | Q(cashout__transaction__state__isnull=True)
        )
    )
    if "q" in request.GET:
        query = request.GET.get("q")
        loans = loans.filter(
            Q(cashout__poolship__member__first_name__contains=query)
            | Q(cashout__poolship__member__last_name__contains=query)
            | Q(cashout__poolship__member__phone_number__contains=query)
        )
    if "page" in request.GET:
        paginator = Paginator(loans, 2)
        num_page = request.GET.get("page")
        try:
            loans = paginator.page(num_page)
        except PageNotAnInteger:
            loans = paginator.page(1)
        except EmptyPage:
            loans = paginator.page(paginator.num_pages)
        result["pagination"] = dict()
        result["pagination"]["has_next"] = loans.has_next()
        result["pagination"]["has_previous"] = loans.has_previous()
    for loan in loans:
        result["loans"].append(LoanSerializer(loan).data)
    result["loans"].sort(key=lambda ln: ln["pay_date"], reverse=True)
    result["loans"].sort(key=sort_list_loans)
    return generate_json_ok_response(response=2050, results=result)
