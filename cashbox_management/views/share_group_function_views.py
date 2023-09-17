from django.db.models import Q
from django.http.response import JsonResponse
from rest_framework import permissions
from rest_framework.decorators import (
    api_view,
    permission_classes,
    renderer_classes,
    throttle_classes,
)
from rest_framework_swagger import renderers

from account_management.models.member import Member
from cashbox_management.decorators import (
    has_owner_role,
    has_member_role,
    has_owner_or_manager_role,
)
from cashbox_management.models import ShareGroup
from cashbox_management.models.cashbox import Cashbox
from cashbox_management.models.membership import Membership
from cashbox_management.serializers.membership_serializer import (
    OwnerMembershipSerializer,
)
from cashbox_management.serializers.share_group_serializer import ShareGroupSerializer
from cashbox_management.utils import is_phone_number_valid
from payment.models import Transaction
from utils import throttle
from utils.constants import choice
from utils.log import info_logger


@api_view(["POST"])
@throttle_classes(
    [throttle.UserMinuteRate, throttle.UserHourRate, throttle.UserDayRate]
)
@permission_classes((permissions.IsAuthenticated,))
@renderer_classes(
    [renderers.OpenAPIRenderer, renderers.SwaggerUIRenderer, renderers.JSONRenderer]
)
@has_owner_role
def create_share_group(request, id):
    data = request.data
    if "group_members" not in data:
        return JsonResponse({"message": "no group_members in data"}, status=400)
    group_members_data = data.pop("group_members")

    cashbox = Cashbox.objects.get(id=id)
    period = cashbox.get_current_period()

    if period.is_terminated:
        return JsonResponse(
            {"message": "current period is terminated, start new one and invite"},
            status=403,
        )
    total_share_residue = 0
    for group_member_data in group_members_data:
        if "phone_number" not in group_member_data:
            return JsonResponse(
                {"message": "member data doesn't have phone_number"}, status=400
            )
        members = Member.objects.filter(phone_number=group_member_data["phone_number"])
        if members.count() > 0:
            memberships = Membership.objects.filter(member=members[0], period=period)
            if memberships.count() > 0 and memberships[0].share_group:
                return JsonResponse(
                    {"message": "membership already in a share_group"}, status=403
                )
        total_share_residue += group_member_data["share_residue"]
    if total_share_residue != period.share_value:
        return JsonResponse(
            {"message": "the total amount of share residues not equal to share value"},
            status=400,
        )

    for group_member_data in group_members_data:
        phone_number = group_member_data.get("phone_number")
        # print('phone_number: ', phone_number)
        phone_number, phone_number_is_valid = is_phone_number_valid(phone_number)
        if not phone_number_is_valid:
            return JsonResponse(
                {
                    "message": "format of Phone number must be : +999999999. Up to 14 digits allowed."
                },
                status=401,
            )
    if "share_group" not in data:
        return JsonResponse({"message": "share_group not in data"}, status=400)
    share_group_data = data["share_group"]
    if "id" not in share_group_data or share_group_data["id"] == 0:
        group_name = share_group_data["name"] if "name" in share_group_data else ""
        share_group = ShareGroup.objects.create(period=period, name=group_name)
    else:
        share_groups = ShareGroup.objects.filter(
            id=data["share_group"]["id"], period=period
        )
        if share_groups.count() == 0:
            return JsonResponse({"message": "not a valid share_group id"}, status=400)
        share_group = share_groups[0]

    result = dict()
    result["memberships"] = []
    for group_member_data in group_members_data:
        phone_number = group_member_data.get("phone_number")
        member, is_created = Member.objects.get_or_create(phone_number=phone_number)
        if is_created:
            info_logger.info(
                "The member with phone number: {} is created".format(
                    member.phone_number
                )
            )

        memberships = Membership.objects.filter(member=member, period=period)
        if memberships.count() > 0:
            membership = memberships[0]
        else:
            membership = Membership.objects.create(
                member=member, period=period, number_of_shares=0
            )

        membership.set_share_group(
            share_group=share_group,
            share_residue=group_member_data.get("share_residue"),
        )

        result["memberships"].append(OwnerMembershipSerializer(membership).data)

    share_group.send_invitation_messages()
    share_group.send_invitation_notifications(is_created)
    share_group.send_invitation_smses(is_created)

    result["share_group"] = ShareGroupSerializer(share_group).data
    return JsonResponse(result, status=200)


@api_view(["POST"])
@throttle_classes(
    [throttle.UserMinuteRate, throttle.UserHourRate, throttle.UserDayRate]
)
@permission_classes((permissions.IsAuthenticated,))
@renderer_classes(
    [renderers.OpenAPIRenderer, renderers.SwaggerUIRenderer, renderers.JSONRenderer]
)
@has_owner_or_manager_role
def kick_out_share_group(request, id, share_group_id):
    """
    Kicks out the memberships of a share group
    :param request: the request of the view
    :param id: the Cashbox's ID which the current Period defined in it
    :param share_group_id: the ID of the share group which to be kicked out
    :return: the OK response (200) if delete is successful
    or Bad Request Error (400) or Not Found Error (404)
    """
    cashbox = Cashbox.objects.get(id=id)
    period = cashbox.get_current_period()
    cycles = period.cycles.all()

    if cashbox.state == choice.CASHBOX_STATE_ACTIVATED and period.cycle_index > 1:
        return JsonResponse(
            {
                "message": "cashbox is Active and has cycle(s), can't kick out share group!"
            },
            status=400,
        )

    if period.is_terminated:
        return JsonResponse(
            {"message": "current period is terminated, can't kick now"}, status=403
        )

    to_be_kicked_share_groups = ShareGroup.objects.filter(
        id=share_group_id, period=period
    )
    if to_be_kicked_share_groups.count() == 0:
        return JsonResponse({"message": "No share group found"}, status=404)

    for membership in to_be_kicked_share_groups[0].memberships.all():
        to_be_kicked_member = membership.member
        to_be_kicked_member_transactions = Transaction.objects.filter(
            (Q(payer=to_be_kicked_member) | Q(receiver=to_be_kicked_member))
            & Q(ctx_id__in=[cycle.id for cycle in cycles])
            & Q(ctx_type=choice.TRANSACTION_CTX_TYPE_CYCLE)
            & Q(state=choice.TRANSACTION_STATE_SUCCESSFUL)
        )
        if to_be_kicked_member_transactions.count() > 0:
            return JsonResponse(
                {"message": "member has successful transaction(s)... can't be kicked!"},
                status=400,
            )
        membership.reset_share_group()
        if membership.number_of_shares == 0:
            membership.delete()
    if to_be_kicked_share_groups[0].memberships.count() > 0:
        return JsonResponse(
            {
                "message": "There is still a member in the share group, the share group deletion has undone"
            },
            status=400,
        )

    to_be_kicked_share_groups[0].delete()
    return JsonResponse({}, status=200)


@api_view(["GET"])
@throttle_classes(
    [throttle.UserMinuteRate, throttle.UserHourRate, throttle.UserDayRate]
)
@permission_classes((permissions.IsAuthenticated,))
@renderer_classes(
    [renderers.OpenAPIRenderer, renderers.SwaggerUIRenderer, renderers.JSONRenderer]
)
@has_member_role
def list_share_groups(request, id):
    cashbox = Cashbox.objects.filter(id=id).first()
    share_groups = cashbox.get_current_period().share_groups.all()
    result = dict()
    result["results"] = []
    for share_group in share_groups:
        result["results"].append(ShareGroupSerializer(share_group).data)
    return JsonResponse(result, status=200)


@api_view(["POST"])
@throttle_classes(
    [throttle.UserMinuteRate, throttle.UserHourRate, throttle.UserDayRate]
)
@permission_classes((permissions.IsAuthenticated,))
@renderer_classes(
    [renderers.OpenAPIRenderer, renderers.SwaggerUIRenderer, renderers.JSONRenderer]
)
@has_member_role
def update_share_group(request, id, share_group_id):
    data = request.data
    # data integrity check
    if "group_members" not in data:
        return JsonResponse({"message": "no group_members in data"}, status=400)
    group_members_data = data.pop("group_members")
    for group_member_data in group_members_data:
        if "phone_number" not in group_member_data:
            return JsonResponse(
                {"message": "member data doesn't have phone_number"}, status=400
            )
        phone_number = group_member_data.get("phone_number")
        phone_number, phone_number_is_valid = is_phone_number_valid(phone_number)
        if not phone_number_is_valid:
            return JsonResponse(
                {
                    "message": "format of Phone number must be : +999999999. Up to 14 digits allowed."
                },
                status=401,
            )

    cashbox = Cashbox.objects.get(id=id)
    period = cashbox.get_current_period()

    if period.is_terminated:
        return JsonResponse(
            {"message": "current period is terminated, start new one!"}, status=403
        )
    if not period.cycle_index <= 1:
        return JsonResponse({"message": "The cycle index is more than 1."}, status=403)

    share_group = ShareGroup.objects.filter(id=share_group_id, period=period).first()
    if not share_group:
        return JsonResponse({"message": "share group not found"}, status=404)

    total_share_residue = 0
    for group_member_data in group_members_data:
        total_share_residue += group_member_data["share_residue"]
    if total_share_residue != period.share_value:
        return JsonResponse(
            {"message": "the total amount of share residues not equal to share value"},
            status=400,
        )

    if "share_group" in data:
        share_group_data = data["share_group"]
        if "name" in share_group_data:
            share_group.name = share_group_data["name"]
            share_group.save()

    for membership in share_group.memberships.all():
        membership.reset_share_group()
        if membership.number_of_shares == 0:
            membership.delete()

    result = dict()
    result["memberships"] = list()
    for group_member_data in group_members_data:
        phone_number = group_member_data.get("phone_number")
        member, is_created = Member.objects.get_or_create(phone_number=phone_number)
        if is_created:
            info_logger.info(
                "The member with phone number: {} is created".format(
                    member.phone_number
                )
            )

        membership = Membership.objects.filter(member=member, period=period).first()
        if not membership:
            membership = Membership.objects.create(
                member=member, period=period, number_of_shares=0
            )

        membership.set_share_group(
            share_group=share_group,
            share_residue=group_member_data.get("share_residue"),
        )

        result["memberships"].append(OwnerMembershipSerializer(membership).data)

    result["share_group"] = ShareGroupSerializer(share_group).data
    return JsonResponse(result, status=200)
