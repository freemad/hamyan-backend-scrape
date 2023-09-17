from django.shortcuts import get_object_or_404
from django.db.models import Q
from rest_framework import permissions, status
from rest_framework.response import Response
from utils.views.base import BaseView
from utils.constants import choice
from .models import Roscabox, Rosship, RoscaCycle, RoscaTransaction, RoscaTemplate
from . import serializers as serializer_classes


class RoscaboxView(BaseView):
    serializers = {
        'default': serializer_classes.RoscaboxSerializer
    }
    action_permissions = {
        'default': permissions.IsAuthenticated
    }
    lookup_field = 'pk'

    def get_queryset(self):
        return Roscabox.objects.filter(
            rosships__member=self.request.user,
        )


class RosshipView(BaseView):
    serializers = {
        'default': serializer_classes.RosshipSerializer
    }
    action_permissions = {
        'default': permissions.IsAuthenticated
    }
    lookup_field = 'pk'

    def get_queryset(self):
        return Rosship.objects.filter(
            box_id=self.kwargs['box_id'],
            box__rosships__member=self.request.user
        )


class RoscaCycleView(BaseView):
    serializers = {
        'default': serializer_classes.RoscaCycleSerializer
    }
    action_permissions = {
        'default': permissions.IsAuthenticated
    }

    def get_queryset(self):
        return RoscaCycle.objects.filter(
            box_id=self.kwargs['box_id'],
            box__rosships__member=self.request.user
        )


class RoscaTransactionView(BaseView):
    serializers = {
        'default': serializer_classes.RoscaTransactionSerializer,
        'create': serializer_classes.CreateRoscaTransactionSerializer
    }
    action_permissions = {
        'default': permissions.IsAuthenticated
    }

    def get_queryset(self):
        return RoscaTransaction.objects.filter(
            Q(rosship__box_id=self.kwargs['box_id']) &
            Q(rosship__box__rosships__member=self.request.user) &
            (
                Q(transaction__isnull=True) |
                Q(transaction__state__in=(
                    choice.TRANSACTION_STATE_IN_PROGRESS,
                    choice.TRANSACTION_STATE_SUCCESSFUL,
                    choice.TRANSACTION_STATE_TO_BANK,
                ))
            )
        )

    def create(self, request, *args, **kwargs):
        caller_rosship = get_object_or_404(
            Rosship, member=request.user, box_id=kwargs["box_id"]
        )
        rosca_cycle = caller_rosship.box.current_cycle
        serializer = self.get_serializer(
            data=request.data, many=True, allow_empty=False
        )
        serializer.is_valid(raise_exception=True)
        rosca_transactions, mother_transaction = serializer.save(
            registrar=caller_rosship, rosca_cycle=rosca_cycle
        )

        data = {}
        if mother_transaction is not None:
            # its an  group pay transaction
            data["rosca_transactions"] = serializer_classes.RoscaTransactionSerializer(
                rosca_transactions, many=True
            ).data
            pay_url = mother_transaction.pay(client_type=request.client_type)
            data["mother_transaction"] = serializer_classes.TransactionSerializer(mother_transaction).data
            data["mother_transaction"]["pay_url"] = pay_url
        else:
            rosca_transaction = rosca_transactions[0]
            pay_url = rosca_transaction.transaction.pay(
                    client_type=request.client_type
            )

            data["rosca_transactions"] = serializer_classes.RoscaTransactionSerializer(
                rosca_transactions, many=True,
            ).data
            data["rosca_transactions"][0]["transaction"]["pay_url"] = pay_url

        return Response(data=data, status=status.HTTP_201_CREATED)



class RoscaTemplateView(BaseView):
    serializers = {
        'default': serializer_classes.RoscaTemplateSerializer,
        'list': serializer_classes.RoscaTemplateListSerializer
    }

    action_permissions = {
        'default': permissions.AllowAny
    }

    lookup_field = 'pk'
    pagination_class = None

    def get_queryset(self):
        return RoscaTemplate.objects.all()

