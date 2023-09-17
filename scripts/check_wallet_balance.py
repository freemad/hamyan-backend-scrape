from account_management.models import Member
from payment.models import Transaction
from utils.constants import choice


# for member in Member.objects.all():
id = 103814
member = Member.objects.get(id=id)

cashins_trs = Transaction.objects.filter(
    destination=choice.TRANSACTION_DST_HAMYAN_WALLET,
    state=choice.TRANSACTION_STATE_SUCCESSFUL,
    receiver=member,
    is_group_pay=False
)

cashouts_trs = Transaction.objects.filter(
    source=choice.TRANSACTION_SRC_HAMYAN_WALLET,
    payer=member,
    state=choice.TRANSACTION_STATE_SUCCESSFUL,
    is_group_pay=False
) 
cashins_amount = sum(list(cashins_trs.values_list('amount', flat=True)))
cashouts_amount = sum(list(cashouts_trs.values_list('amount', flat=True)))
if cashouts_amount > cashins_amount:
    print('cashins', cashins_amount)
    print('cashout', cashouts_amount)
    print('member_name', member.name)
    print('member_id', member.id)
    print('\n')
    print('-'*30)
    print('\n')
    # print('balance', cashins_amount - cashouts_amount)







for member in Member.objects.all():
    # member = Member.objects.get(id=id)

    cashins_trs = Transaction.objects.filter(
        destination=choice.TRANSACTION_DST_HAMYAN_WALLET,
        state=choice.TRANSACTION_STATE_SUCCESSFUL,
        receiver=member,
        is_group_pay=False
    )

    cashouts_trs = Transaction.objects.filter(
        source=choice.TRANSACTION_SRC_HAMYAN_WALLET,
        payer=member,
        state=choice.TRANSACTION_STATE_SUCCESSFUL,
        is_group_pay=False
    ) 
    cashins_amount = sum(list(cashins_trs.values_list('amount', flat=True)))
    cashouts_amount = sum(list(cashouts_trs.values_list('amount', flat=True)))
    if cashouts_amount > cashins_amount:
        print('cashins', cashins_amount)
        print('cashout', cashouts_amount)
        print('member_name', member.name)
        print('member_id', member.id)
        print('\n')
        print('-'*30)
        print('\n')
    # print('balance', cashins_amount - cashouts_amount)




