from django.utils import timezone
from django.db.models import Q
from datetime import timedelta

from moneypool_management.models import Moneypool, Installment, Loan, Poolship
from cashbox_management.models import Cashbox
from payment.models import Transaction
from utils.constants import choice


def main(days=90):
    start_date = (timezone.now() - timedelta(days=days)).replace(second=0, microsecond=0, hour=0, minute=0)
    cashboxes = Cashbox.objects.filter(is_test=False)
    moneypools = Moneypool.objects.filter(is_archived=False)

    # created list of active cashboxes and moneypools

    active_cashboxes = list()
    active_moneypools = list()

    for cashbox in cashboxes:
        cycles_id = list()
        for period in cashbox.periods.all():
            for cycle in period.cycles.all():
                cycles_id.append(cycle.id)
        trs = Transaction.objects.filter(
            state=choice.TRANSACTION_STATE_SUCCESSFUL,
            is_group_pay=False,
            ctx_type=choice.TRANSACTION_CTX_TYPE_CYCLE,
            ctx_id__in=cycles_id,
            created__gte=start_date
        )

        if trs.count() >= 9:
            period = cashbox.get_current_period()
            if len(period.get_valid_memberships()) >= 4:
                active_cashboxes.append(cashbox)

    for moneypool in moneypools:
        trs = Transaction.objects.filter(
            state=choice.TRANSACTION_STATE_SUCCESSFUL,
            is_group_pay=False,
            ctx_type=choice.TRANSACTION_CTX_TYPE_MONEYPOOL,
            ctx_id=moneypool.id,
            created__gte=start_date
        )

        if trs.count() >= 9:
            if moneypool.members.count() >= 4:
                active_moneypools.append(moneypool)


    cashboxes_balance = 0
    cashboxes_loans_count = 0
    cashboxes_loans_amount = 0
    cashboxes_memberships_unpaid_share = 0
    cashboxes_total_cashins = 0
    cashboxes_total_cashouts = cashboxes_loans_amount
    cashboxes_has_tr_members = 0

    moneypools_balance = 0
    moneypool_loans_count = 0
    moneypools_loans_amount = 0
    moneypools_unpaid_installments_amount = 0
    moneypools_total_cashins = 0
    moneypools_total_cashouts = 0
    moneypools_has_tr_members = 0
    moneypool_poolships_unpaid_portion_amount = 0


    for cashbox in cashboxes:
        try:
            cashboxes_balance += cashbox.balance
            cycles_id = list()
            for period in cashbox.periods.all():
                for cycle in period.cycles.all():
                    cycles_id.append(cycle.id)

            trs = Transaction.objects.filter(
                source__in=(choice.TRANSACTION_SRC_HAMYAN_BOX_BALANCE, choice.TRANSACTION_SRC_BOX_BANKACCOUNT),
                destination=choice.TRANSACTION_DST_MEMBER_BANKACCOUNT,
                state=choice.TRANSACTION_STATE_SUCCESSFUL,
                is_group_pay=False,
                ctx_type=choice.TRANSACTION_CTX_TYPE_CYCLE,
                ctx_id__in=cycles_id,
                created__gte=start_date
            )
            cashboxes_loans_count += trs.count()
            for tr in trs:
                cashboxes_loans_amount += tr.amount


            memberships = cashbox.get_current_period().get_valid_memberships()
            for msp in memberships:
                if msp.remaining_share_amount > 0:
                    cashboxes_memberships_unpaid_share += msp.remaining_share_amount
            cashin_trs = Transaction.objects.filter(
                source__in=(choice.TRANSACTION_SRC_GATEWAY, choice.TRANSACTION_SRC_HAMYAN_WALLET),
                destination__in=(choice.TRANSACTION_DST_BOX_BANKACCOUNT, choice.TRANSACTION_DST_HAMYAN_BOX_BALANCE),
                state=choice.TRANSACTION_STATE_SUCCESSFUL,
                is_group_pay=False,
                ctx_id__in=cycles_id,
                ctx_type=choice.TRANSACTION_CTX_TYPE_CYCLE,
            )
            has_tr_members = list()
            for tr in cashin_trs:
                has_tr_members.append(tr.payer)
                cashboxes_total_cashins += tr.amount
            has_tr_members = list(set(has_tr_members))
            cashboxes_has_tr_members += len(has_tr_members)
        except Exception as e:
            print('Exception cbx id %s err:%s' % (cashbox.id, e))



    for moneypool in moneypools:
        try:
            moneypools_balance += moneypool.hamyan_balance + moneypool.bank_balance + moneypool.inprogress_balance
            loans = Loan.objects.filter(
                cashout__poolship__moneypool=moneypool
            )
            moneypool_loans_count += loans.count()
            for loan in loans:
                moneypools_loans_amount += loan.amount
                for installment in loan.unpaid_installments:
                    moneypools_unpaid_installments_amount += installment.amount

            has_tr_members = list()
            cashin_trs = Transaction.objects.filter(
                source__in=(choice.TRANSACTION_SRC_GATEWAY, choice.TRANSACTION_SRC_HAMYAN_WALLET),
                destination__in=(choice.TRANSACTION_DST_BOX_BANKACCOUNT, choice.TRANSACTION_DST_HAMYAN_BOX_BALANCE),
                state=choice.TRANSACTION_STATE_SUCCESSFUL,
                is_group_pay=False,
                ctx_id=moneypool.id,
                ctx_type=choice.TRANSACTION_CTX_TYPE_MONEYPOOL,
            )

            for tr in cashin_trs:
                has_tr_members.append(tr.payer)
                moneypools_total_cashins += tr.amount

            has_tr_members = list(set(has_tr_members))
            moneypools_has_tr_members += len(has_tr_members)
            
            cashout_trs = Transaction.objects.filter(
                source__in=(choice.TRANSACTION_SRC_HAMYAN_BOX_BALANCE, choice.TRANSACTION_SRC_BOX_BANKACCOUNT),
                destination=choice.TRANSACTION_DST_MEMBER_BANKACCOUNT,
                state=choice.TRANSACTION_STATE_SUCCESSFUL,
                is_group_pay=False,
                ctx_id=moneypool.id,
                ctx_type=choice.TRANSACTION_CTX_TYPE_MONEYPOOL
            )

            for tr in cashout_trs:
                moneypools_total_cashouts += tr.amount

            poolships = Poolship.objects.filter(
                moneypool=moneypool,
                is_active=True
            )
            for psp in poolships:
                if psp.unpaid_portion > 0:
                    moneypool_poolships_unpaid_portion_amount += psp.unpaid_portion
        except Exception as e:
            print('Exception mnp id %s err: %s' % (moneypool.id, e))

    print('cashboxes_balance', cashboxes_balance)
    print('cashboxes_loans_count', cashboxes_loans_count)
    print('cashboxes_loans_amount', cashboxes_loans_amount)
    print('cashboxes_memberships_unpaid_share', cashboxes_memberships_unpaid_share)
    print('cashboxes_total_cashins', cashboxes_total_cashins)
    print('cashboxes_total_cashouts', cashboxes_total_cashouts)
    print('cashboxes_has_tr_members', cashboxes_has_tr_members)
    print('moneypools_balance', moneypools_balance)
    print('moneypool_loans_count', moneypool_loans_count)
    print('moneypools_loans_amount', moneypools_loans_amount)
    print('moneypools_unpaid_installments_amount', moneypools_unpaid_installments_amount)
    print('moneypools_total_cashins', moneypools_total_cashins)
    print('moneypools_total_cashouts', moneypools_total_cashouts)
    print('moneypools_has_tr_members', moneypools_has_tr_members)
    print('moneypool_poolships_unpaid_portion_amount', moneypool_poolships_unpaid_portion_amount)
