import copy

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.serializers import ListSerializer

from aptbox_management.models import Aptbox
from cashbox_management.models import Cashbox
from moneypool_management.models import (
    Moneypool,
    Loan,
    Installment,
)
from moneypool_management.serializers import poolship_serializer
from moneypool_management.serializers.loan_demand_serializer import LoanDemandSerializer
from payment.models import (
    Transaction,
    MoneypoolCashin,
    MoneypoolCashout,
    Gateway,
    Order,
    Discount,
)
from payment.utils import (
    get_service_package_amount,
    calculate_order_end_date,
    calculate_order_days_count
)
from utils.constants import choice
from utils.exceptions import InvalidInstanceData


class TransactionListSerializer(ListSerializer):
    def save(self, *args, **kwargs):
        validated_data = self.validated_data
        mother_transaction = None
        if len(validated_data) > 1:
            mother_transaction_data = copy.deepcopy(validated_data)[
                0
            ]  # cp a validated_data for creating mother_transaction
            if mother_transaction_data['source'] != choice.TRANSACTION_SRC_HAMYAN_BOX_BALANCE:
                mother_transaction_data["is_group_pay"] = True
                mother_transaction_data["amount"] = 0
                mother_transaction_data["receiver"] = None
                for tr_data in validated_data:
                    mother_transaction_data["amount"] += tr_data["amount"]
                mother_transaction = Transaction.objects.create(**mother_transaction_data, **kwargs)

        transaction = None
        for tr_data in validated_data:
            transaction = Transaction.objects.create(
                **tr_data, **kwargs, mother_transaction=mother_transaction
            )
        if mother_transaction is not None:
            return mother_transaction
        elif transaction is not None:
            return transaction
        return None


class TransactionSerializer(serializers.ModelSerializer):
    state_time = serializers.CharField(source='local_state_time', read_only=True)

    class Meta:
        list_serializer_class = TransactionListSerializer
        model = Transaction
        fields = (
            "source",
            "destination",
            "payer",
            "receiver",
            "bank_account",
            "ctx_id",
            "ctx_type",
            "gateway",
            "amount",
            "commission",
            "total_commission",
            "transaction_code",
            "state",
            "state_time",
            "short_url",
            "is_group_pay",
            "mother_transaction",
            "created",
            "is_reportable",
            "pk",
            "moneypool_data",
            "aptbox_data",
            "roscabox_data",
            "cycle_data",
            "payer_name",
            "receiver_name",
        )

        read_only_fields = (
            "pk",
            "payer",
            "commission",
            "transaction_code",
            "state",
            "state_time",
            "web_key",
            "short_url",
            "is_group_pay",
            "mother_transaction",
            "created",
        )
        extra_kwargs = {"ctx_id": {"required": True}, "ctx_type": {"required": True}}


class MoneypoolCashinListSerializer(ListSerializer):
    def save(self, *args, **kwargs):
        validated_data = self.validated_data
        mother_transaction = None
        if len(validated_data) > 1:
            mother_transaction_data = copy.deepcopy(validated_data)[0].get(
                "transaction", None
            )  # cp a validated_data for creating mother_transaction
            if mother_transaction_data:
                mother_transaction_data["is_group_pay"] = True
                mother_transaction_data["amount"] = 0
                mother_transaction_data["receiver"] = None
                mother_transaction_data["payer"] = kwargs.get("registrar").member
                for cashin_data in validated_data:
                    tr_data = cashin_data.get("transaction", None)
                    if tr_data is not None:
                        mother_transaction_data["amount"] += cashin_data["amount"]
                mother_transaction = Transaction.objects.create(**mother_transaction_data)
        transaction = None
        cashin = None
        cashins = list()
        for cashin_data in validated_data:
            transaction = None
            tr_data = cashin_data.pop("transaction", None)
            if tr_data is not None:
                tr_data["amount"] = cashin_data.get("amount")
                tr_data["payer"] = kwargs.get("registrar").member
                tr_data["receiver"] = cashin_data.get("poolship").member
                transaction = Transaction.objects.create(**tr_data, mother_transaction=mother_transaction)
            cashin = MoneypoolCashin.objects.create(
                **cashin_data, **kwargs, transaction=transaction
            )
            cashins.append(cashin)
        return cashins, mother_transaction


class MoneypoolCashinSerializer(serializers.ModelSerializer):
    transaction = TransactionSerializer(required=False)
    registrar_data = poolship_serializer.PoolshipSerializer(source='registrar', read_only=True)
    poolship_data = poolship_serializer.PoolshipSerializer(source='poolship', read_only=True)

    class Meta:
        model = MoneypoolCashin
        list_serializer_class = MoneypoolCashinListSerializer
        fields = (
            "registrar",
            "poolship",
            "amount",
            "type",
            "tag",
            "transaction",
            "solved_amount",
            "time",
            "created",
            "pk",
            # ENHANCEMENT FIELDS
            "registrar_data",
            "poolship_data",
            "state",
            "deed_type",
            "is_removable",
        )
        read_only_fields = (
            "solved_amount",
            "registrar",
            "time",
            "created",
            "pk",
        )
        extra_kwargs = {
            "poolship": {"required": True},
            "amount": {"required": True}
        }

    def create(self, validated_data, *args, **kwargs):
        transaction = None
        tr_data = validated_data.pop("transaction", None)
        if tr_data is not None:
            tr_data["amount"] = validated_data.get("amount")
            tr_data["payer"] = validated_data.get("registrar").member
            tr_data["receiver"] = validated_data.get("poolship").member
            transaction = Transaction.objects.create(**tr_data)

        cashin = MoneypoolCashin.objects.create(
            **validated_data, **kwargs, transaction=transaction
        )
        return cashin


class MoneypoolCashinUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = MoneypoolCashin
        list_serializer_class = MoneypoolCashinListSerializer
        fields = (
            "poolship",
            "amount",
            "type",
            "tag",
            "transaction",
            "solved_amount",
            "registrar",
            "time",
            "created",
            "pk",
        )
        read_only_fields = ("solved_amount", "registrar", "time", "created", "pk")
        extra_kwargs = {"poolship": {"required": True}, "amount": {"required": True}}


class MoneypoolCashoutSerializer(serializers.ModelSerializer):
    transaction = TransactionSerializer(required=False)
    registrar_data = poolship_serializer.PoolshipSerializer(source='registrar', read_only=True)
    poolship_data = poolship_serializer.PoolshipSerializer(source='poolship', read_only=True)

    class Meta:
        model = MoneypoolCashout
        fields = (
            "registrar",
            "poolship",
            "amount",
            "type",
            "tag",
            "time",
            "transaction",
            "created",
            "pk",
            # Enhancement Fields
            "registrar_data",
            "poolship_data",
            "state",
            "deed_type",
            "is_removable",
        )
        read_only_fields = (
            "registrar",
            "time",
            "pk",
            "created",
        )
        extra_kwargs = {"poolship": {"required": True}, "amount": {"required": True}}

    def create(self, validated_data, *args, **kwargs):
        tr_data = validated_data.pop("transaction", None)
        transaction = None
        if tr_data is not None:
            tr_data["receiver"] = validated_data.get("poolship").member
            tr_data["payer"] = validated_data.get("registrar").member
            tr_data["amount"] = validated_data.get("amount")
            transaction = Transaction.objects.create(**tr_data)
        cashout = MoneypoolCashout.objects.create(
            **validated_data, **kwargs, transaction=transaction
        )
        return cashout


class LoanSerializer(serializers.ModelSerializer):
    cashout = MoneypoolCashoutSerializer()
    number_of_repaid_installments = serializers.IntegerField(default=0)
    loan_demand = serializers.IntegerField(source="loan_demand_id", required=False, read_only=True)
    loan_demand_data = LoanDemandSerializer(source='loan_demand', read_only=True, required=False)
    # poolship_data = poolship_serializer.PoolshipSerializer(source='poolship', read_only=True)

    class Meta:
        model = Loan
        fields = (
            "cashout",
            "number_of_repayments",
            "repayment_interval",
            "interest_rate",
            "interest_pay_mode",
            "pay_date",
            "due_date",
            "short_url",
            "created",
            "pk",
            'number_of_repaid_installments',
            # Enhanced Fields
            # "poolship",
            # "poolship_data",
            "number_of_repaid_installments",
            "number_of_delayed_installments",
            "interest_pay_mode",
            "pay_date",
            "due_date",
            "deed_type",
            "amount",
            "repaid_amount",
            "state",
            "has_delayed_installment",
            "is_fully_repaid",
            "is_removable",
            "loan_demand",
            "loan_demand_data",
        )
        read_only_fields = (
            "short_url",
            "created",
            "pk"
        )
        # extra_kwargs = {'amount': {'required': True}}

    def save(self, *args, **kwargs):
        validated_data = self.validated_data
        interest_pay_mode = validated_data.get('interest_pay_mode')
        interest_rate = validated_data.get('interest_rate')
        number_of_repaid_installments = validated_data.pop('number_of_repaid_installments')
        cashout_data = validated_data.pop("cashout")
        poolship = cashout_data["poolship"]
        cashout_data["poolship"] = poolship.pk
        tr_data = cashout_data.get('transaction', None)
        loan_amount = cashout_data.get('amount')
        if interest_pay_mode == choice.LOAN_INTEREST_PAY_MODE_PRE_REDUCED:
            cashout_data['amount'] = loan_amount - (loan_amount * interest_rate)

        if tr_data is not None:
            if cashout_data['transaction']['source'] == choice.TRANSACTION_SRC_BOX_BANKACCOUNT:
                cashout_data["transaction"]["gateway"] = cashout_data["transaction"][
                    "gateway"
                ].pk
            cashout_data["transaction"]["receiver"] = poolship.member.pk
            bank_account = tr_data.get('bank_account', None)
            if bank_account:
                cashout_data['transaction']['bank_account'] = bank_account.pk
        serializer = MoneypoolCashoutSerializer(data=cashout_data)
        if serializer.is_valid():
            cashout = serializer.save(**kwargs)
            loan = Loan.objects.create(**validated_data, cashout=cashout)
            loan.create_installments()
            installments = loan.installments.all().order_by("due_date")
            for installment, _ in zip(installments, range(number_of_repaid_installments)):
                cashin = MoneypoolCashin.objects.create(
                    amount=installment.amount,
                    registrar=kwargs.get('registrar'),
                    poolship=poolship,
                    type=choice.MONEYPOOL_CASHIN_TYPE_REPAYMENT,
                    transaction=None
                )
                if not poolship.moneypool.has_perm(choice.FEATURE_NO_DISCHARGE_BANK_BALANCE):
                    cashin.charge_bank_balance()

                installment.cashin = cashin
                installment.save()
            return loan
        raise InvalidInstanceData(serializer.errors)


class InstallmentSerializer(serializers.ModelSerializer):
    cashin = MoneypoolCashinSerializer()
    poolship_data = poolship_serializer.PoolshipSerializer(source='poolship', read_only=True)

    class Meta:
        model = Installment
        fields = (
            "loan",
            "amount",
            "index",
            "cashin",
            "due_date",
            "pk",
            "created",
            "payment_status",
            "deed_type",
            # ENHANCEMENT FIELDS
            "deed_type",
            # "poolship",
            "poolship_data",
            "pay_time",
            "is_paid",
            "is_delayed",
            "state",
            "is_removable",
        )
        read_only_fields = (
            "amount",
            "index",
            "due_date",
            "pk",
            "created"
        )


class PayReceiverSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    type = serializers.ChoiceField(
        choices=choice.BOXSHIP_TYPE + choice.MEMBER_TYPE)
    amount = serializers.IntegerField()
    cashin_type = serializers.ChoiceField(
        choices=(choice.MONEYPOOL_CASHIN_TYPE
                 + choice.CASHBOX_CASHIN_TYPE
                 + choice.MEMBER_CASHIN_TYPE
                 + choice.APTBOX_TRANSACTION_TYPE 
                 + (choice.ROSCA_TRANSACTION_TYPE_CASHIN_SHARE, "Rosca Type Cashin share")
                 )
    )
    paid_obj_id = serializers.IntegerField(required=False)


class OrderboxRelatedField(serializers.RelatedField):
    def to_representation(self, value):
        return value.id


class OrderTransactionSerializer(serializers.ModelSerializer):
    state_time = serializers.CharField(source='local_state_time', read_only=True)

    class Meta:
        list_serializer_class = TransactionListSerializer
        model = Transaction
        fields = (
            "source",
            "destination",
            "payer",
            "receiver",
            "bank_account",
            "ctx_id",
            "ctx_type",
            "gateway",
            "amount",
            "commission",
            "total_commission",
            "transaction_code",
            "state",
            "state_time",
            "short_url",
            "is_group_pay",
            "created",
            "is_reportable",
            "pk",
            "moneypool_data",
            "cycle_data",
            "payer_name",
            "receiver_name",
        )

        read_only_fields = (
            "pk",
            "payer",
            "commission",
            "transaction_code",
            "state",
            "state_time",
            "web_key",
            "short_url",
            "is_group_pay",
            "created",
        )
        extra_kwargs = {"ctx_id": {"required": False}, "ctx_type": {"required": False}}


class DiscountCodeSerializer(serializers.Serializer):
    code = serializers.CharField()

    class Meta:
        fields = ('code',)

    def validate_code(self, value):
        try:
            discount = Discount.objects.get(code=value)
        except ObjectDoesNotExist:
            raise serializers.ValidationError("discount object not found")
            return
        consumed_discount_transactions = discount.transactions.filter(
            state=choice.TRANSACTION_STATE_SUCCESSFUL)

        if discount.num_uses <= consumed_discount_transactions.count():
            raise serializers.ValidationError('discount already used')
        return value


class OrderSerializer(serializers.ModelSerializer):
    """
    {
        "transaction":{
            "source": "hwt",
        },
        "service_package": 1,
        "ctx_id": 50,
        "ctx_type": 'mnp'
    }
    """
    transaction = OrderTransactionSerializer()
    discount_code = serializers.CharField(write_only=True, required=False)
    box = OrderboxRelatedField(read_only=True)
    ctx_id = serializers.IntegerField()
    ctx_type = serializers.ChoiceField(choices=choice.BOX_TYPE)
    month_count = serializers.IntegerField(default=1, write_only=True)

    class Meta:
        model = Order
        fields = (
            'pk',
            'transaction',
            'service_package',
            'box_type',
            'box_id',
            'box',
            'end_date',
            'month_count',
            'day_count',
            'ctx_id',
            'ctx_type',
            'discount_code'
        )
        read_only_fields = (
            'pk',
        )
        extra_kwargs = {
            "box_type": {"required": False},
            "box_id": {"required": False},
            "box": {"required": False}
        }

    def save(self, *args, **kwargs):

        validated_data = self.validated_data.copy()
        transaction_data = validated_data.pop('transaction')
        discount_code = validated_data.pop('discount_code', None)

        discount = None
        if discount_code:
            try:
                discount = Discount.objects.get(code=discount_code, is_active=True)
            except ObjectDoesNotExist:
                raise serializers.ValidationError("discount object not found")
            if discount.has_target_member and kwargs['payer'] not in discount.members.all():
                raise serializers.ValidationError("you aren't in target members")

            if discount.is_expired:
                raise serializers.ValidationError("discount expired")

            consumed_discount_transactions = discount.transactions.filter(
                state=choice.TRANSACTION_STATE_SUCCESSFUL)

            if (discount.num_uses <= consumed_discount_transactions.count()
                    or consumed_discount_transactions.filter(payer=kwargs['payer']).exists()):
                raise serializers.ValidationError('discount already used')

        order_ctx_type = validated_data.pop('ctx_type')
        order_ctx_id = validated_data.pop('ctx_id')
        month_count = validated_data.pop('month_count')
        if order_ctx_type == choice.MONEYPOOL:
            box = get_object_or_404(Moneypool, id=order_ctx_id)
        elif order_ctx_type == choice.CASHBOX:
            box = get_object_or_404(Cashbox, id=order_ctx_id)
        elif order_ctx_type == choice.APTBOX:
            box = get_object_or_404(Aptbox, id=order_ctx_id)

        box_type = ContentType.objects.get_for_model(box)
        validated_data['end_date'] = calculate_order_end_date(
            month_count,
            service_package=validated_data['service_package'],
            box_type=box_type, box_id=box.id)
        validated_data['box'] = box
        validated_data['day_count'] = calculate_order_days_count(month_count)
        order = Order.objects.create(**validated_data)
        amount = get_service_package_amount(order, validated_data['service_package'], month_count)
        transaction_data['discount'] = discount
        transaction_data['destination'] = choice.TRANSACTION_DST_HAMYAN_POOL
        transaction_data['amount'] = amount
        transaction_data['ctx_type'] = choice.TRANSACTION_CTX_TYPE_ORDER
        transaction_data['ctx_id'] = order.id
        transaction_data['payer'] = kwargs['payer']
        Transaction.objects.create(**transaction_data)

        return order


class GatewaySerializer(serializers.ModelSerializer):
    class Meta:
        model = Gateway
        fields = (
            'id',
            'name',
            'unique_code',
            'type',
            'img_url',
            'is_active',
            'is_default',
            'is_in_mobile_visible',
            'terminal_type',
        )


class DiscountSerializer(serializers.ModelSerializer):
    class Meta:
        model = Discount
        fields = (
            'id',
            'code',
            'is_active',
            'name',
            'percentage',
            'valid_from',
            'valid_until',
            'valid_from_timestamp',
            'valid_until_timestamp'
        )


class GroupAllPaySerializer(serializers.Serializer):
    CHOICES = (
        choice.APTSHIP,
        choice.POOLSHIP,
        choice.MEMBERSHIP,
        choice.INSTALLMENT,
        choice.DELEYED_INSTALLMENT,
        choice.COST,
    )
    type = serializers.ChoiceField(choices=CHOICES)
    id = serializers.IntegerField()
