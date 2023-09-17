from django.utils import timezone

from payment.models import MoneypoolCashin, Transaction
from payment.serializers.moneypool_cashin_serializer import (
    OpenMoneypoolCashinSerializer,
    RestrictedMoneypoolCashinSerializer,
)
from payment.utils import get_default_gateway
from utils.constants import choice
from utils.log import error_logger


def create_moneypool_cashin(
    caller_poolship,
    receiver_poolship,
    amount,
    cashin_type,
    cashin_tag,
    source=choice.TRANSACTION_SRC_GATEWAY,
    deed_type=choice.MONEYPOOL_DEED_TYPE_RECORD,
    cashin_time=None,
    client_type=choice.CLIENT_TYPE_ANDROID,
    gateway=None,
    mother_transaction=None,
    commission=0,
):
    # print('create_moneypool_cashin()')
    # print('amount:', amount)
    # print('cashin_type:', cashin_type)
    # print('bank_balance:', caller_poolship.moneypool.bank_balance)
    # print('hamyan_balance:', caller_poolship.moneypool.hamyan_balance)
    destination = choice.TRANSACTION_DST_HAMYAN_BOX_BALANCE
    if caller_poolship.moneypool.is_worried_box:
        destination = choice.TRANSACTION_DST_BOX_BANKACCOUNT

    result = dict()
    if deed_type == choice.MONEYPOOL_DEED_TYPE_TRANSACTIONAL:
        if source == choice.TRANSACTION_SRC_GATEWAY:
            transaction = Transaction.objects.create(
                payer=caller_poolship.member,
                receiver=receiver_poolship.member,
                amount=amount,
                source=source,
                destination=destination,
                gateway=gateway if gateway else get_default_gateway(),
                ctx_id=caller_poolship.moneypool.id,
                ctx_type=choice.TRANSACTION_CTX_TYPE_MONEYPOOL,
                mother_transaction=mother_transaction,
                commission=commission,
            )
            cashin = MoneypoolCashin.objects.create(
                registrar=caller_poolship,
                poolship=receiver_poolship,
                amount=amount,
                time=timezone.now() if not cashin_time else cashin_time,
                type=cashin_type,
                tag=cashin_tag,
                transaction=transaction
            )
            result["cashin"] = OpenMoneypoolCashinSerializer(cashin).data
            if not mother_transaction:
                pay_url = gateway.request_pay(transaction, client_type)
                result["payment"] = {
                    "transaction_code": transaction.transaction_code
                    if transaction
                    else "",
                    "token": transaction.token if transaction else "",
                    "amount": amount,
                    "commission": commission,
                    "pay_url": pay_url,
                    "gateway_type": gateway.type,
                }
        elif source == choice.TRANSACTION_SRC_HAMYAN_WALLET:
            transaction = Transaction.objects.create(
                payer=caller_poolship.member,
                receiver=receiver_poolship.member,
                amount=amount,
                source=source,
                destination=destination,
                gateway=gateway if gateway else get_default_gateway(),
                ctx_id=caller_poolship.moneypool.id,
                ctx_type=choice.TRANSACTION_CTX_TYPE_MONEYPOOL,
                mother_transaction=mother_transaction,
                commission=commission,
            )
            cashin = MoneypoolCashin.objects.create(
                registrar=caller_poolship,
                poolship=receiver_poolship,
                amount=amount,
                time=timezone.now() if not cashin_time else cashin_time,
                type=cashin_type,
                tag=cashin_tag,
                transaction=transaction
            )
            result["cashin"] = OpenMoneypoolCashinSerializer(cashin).data
            if not mother_transaction:
                result["payment"] = {
                    "transaction_code": transaction.transaction_code
                    if transaction
                    else "",
                    "amount": amount,
                    "commission": commission,
                }

    elif deed_type == choice.MONEYPOOL_DEED_TYPE_RECORD:
        # todo: inspect and fix usage of RECORD & HAMYAN WALLET and remove this part
        if source == choice.TRANSACTION_SRC_HAMYAN_WALLET:
            transaction = Transaction.objects.create(
                payer=caller_poolship.member,
                receiver=receiver_poolship.member,
                amount=amount,
                source=source,
                destination=destination,
                gateway=gateway if gateway else get_default_gateway(),
                ctx_id=caller_poolship.moneypool.id,
                ctx_type=choice.TRANSACTION_CTX_TYPE_MONEYPOOL,
                mother_transaction=mother_transaction,
                commission=commission,
            )
            cashin = MoneypoolCashin.objects.create(
                registrar=caller_poolship,
                poolship=receiver_poolship,
                amount=amount,
                time=timezone.now() if not cashin_time else cashin_time,
                type=cashin_type,
                tag=cashin_tag,
                transaction=transaction
            )
        else:
            cashin = MoneypoolCashin.objects.create(
                registrar=caller_poolship,
                poolship=receiver_poolship,
                amount=amount,
                time=timezone.now() if not cashin_time else cashin_time,
                type=cashin_type,
                tag=cashin_tag,
            )
        # in record mode just charge the bank account
        cashin.charge_bank_balance()
    return result, cashin


def remove_moneypool_cashin(cashin):
    if not cashin.is_removable:
        error_logger.error("the cashin: {} is NOT REMOVABLE".format(cashin.__str__()))
    elif cashin.deed_type == choice.MONEYPOOL_DEED_TYPE_RECORD:
        cashin.poolship.moneypool.withdraw_from_bank_balance(amount=cashin.amount)
        cashin.delete()
    return None


def get_moneypool_cashins(moneypool, is_open=False):
    cashins = MoneypoolCashin.objects.filter(poolship__moneypool=moneypool)
    cashins_data = list()
    for cashin in cashins:
        if is_open:
            cashins_data.append(OpenMoneypoolCashinSerializer(cashin).data)
        else:
            cashins_data.append(RestrictedMoneypoolCashinSerializer(cashin).data)
    return cashins_data
