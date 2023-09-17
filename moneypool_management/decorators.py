from django.http.response import JsonResponse

from moneypool_management.models import Moneypool, Poolship
from utils.constants import choice


def is_moneypool_member(view_function):
    def _decorated(request, id, *args, **kwargs):
        moneypool = Moneypool.objects.filter(id=id).first()
        if not moneypool:
            return JsonResponse({"message": "no moneypool found"}, status=404)

        poolship = Poolship.objects.filter(
            moneypool=moneypool, member=request.user
        ).first()

        if not poolship:
            return JsonResponse({"message": "no poolship found"}, status=404)

        kwargs["moneypool"] = moneypool
        kwargs["poolship"] = poolship
        return view_function(request, id, *args, **kwargs)

    return _decorated


def is_moneypool_owner(view_function):
    def _decorated(request, id, *args, **kwargs):
        moneypool = Moneypool.objects.filter(id=id).first()
        if not moneypool:
            return JsonResponse({"message": "no moneypool found"}, status=404)

        poolship = Poolship.objects.filter(
            moneypool=moneypool, member=request.user
        ).first()

        if not poolship:
            return JsonResponse({"message": "no poolship found"}, status=404)

        if poolship.role != choice.MONEYPOOL_ROLE_OWNER:
            return JsonResponse(
                {"message": "only owner are authorized to do the function"}, status=403
            )

        kwargs["moneypool"] = moneypool
        kwargs["poolship"] = poolship
        return view_function(request, id, *args, **kwargs)

    return _decorated


def is_moneypool_owner_or_manager(view_function):
    def _decorated(request, id, *args, **kwargs):
        moneypool = Moneypool.objects.filter(id=id).first()
        if not moneypool:
            return JsonResponse({"message": "no moneypool found"}, status=404)

        poolship = Poolship.objects.filter(
            moneypool=moneypool, member=request.user
        ).first()

        if not poolship:
            return JsonResponse({"message": "no poolship found"}, status=404)

        if not (
            poolship.role == choice.MONEYPOOL_ROLE_OWNER
            or poolship.role == choice.MONEYPOOL_ROLE_MANAGER
        ):
            return JsonResponse(
                {"message": "only owner or manager are authorized to do the function"},
                status=403,
            )

        kwargs["moneypool"] = moneypool
        kwargs["poolship"] = poolship
        return view_function(request, id, *args, **kwargs)

    return _decorated
