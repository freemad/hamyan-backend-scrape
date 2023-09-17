from django.conf.urls import url, include  # noqa

from cashbox_management.views import (
    cashbox_function_views,
    draft_cashbox_function_views,
    commission_function_views,
    share_group_function_views,
    cycle_function_views,
    membership_function_views,
)

draft_cashbox_urlpatterns = [
    url(r"^create/$", draft_cashbox_function_views.create_draft_cashbox, name="create"),
    url(
        r"^(?P<id>\d+)/retrieve-members/$",
        draft_cashbox_function_views.retrieve_members,
        name="retrieve-members",
    ),
    url(
        r"^(?P<id>\d+)/inform-winners/$",
        draft_cashbox_function_views.inform_winners,
        name="inform-winners",
    ),
    url(
        r"^(?P<id>\d+)/wipe-cycle/$",
        draft_cashbox_function_views.wipe_cycle,
        name="wipe-cycle",
    ),
    url(
        r"^(?P<id>\d+)/list-winners/$",
        draft_cashbox_function_views.list_draft_winners,
        name="list-winners",
    ),
    url(
        r"^(?P<id>\d+)/activate/$",
        draft_cashbox_function_views.activate_draft_cashbox,
        name="activate",
    ),
    url(
        r"^(?P<id>\d+)/wipe-winner/$",
        draft_cashbox_function_views.wipe_winner,
        name="wipe-winner",
    ),
]

cashbox_urlpatterns = [
    url(r"^create/$", cashbox_function_views.create_cashbox, name="create"),
    url(
        r"^(?P<id>\d+)/$", cashbox_function_views.get_full_cashbox, name="retrieve"
    ),  # GET
    url(r"^(?P<id>\d+)/update/$", cashbox_function_views.update_cashbox, name="update"),
    url(
        r"^(?P<id>\d+)/history/$",
        cashbox_function_views.get_cashbox_history,
        name="history",
    ),
    url(
        r"^search-cashbox/(?P<slug>\d+)/$",
        cashbox_function_views.search_cashbox,
        name="search-cashbox",
    ),
    url(r"^list/$", cashbox_function_views.cashbox_list, name="list"),
    url(
        r"^invited-and-request-list/$",
        cashbox_function_views.cashbox_invited_and_request_list,
        name="^invited-and-request-list",
    ),
    url(
        r"^(?P<id>\d+)/initiate-period/$",
        cashbox_function_views.initiate_period,
        name="initiate-period",
    ),
    url(
        r"^(?P<id>\d+)/change-period-day-of-draw/$",
        cashbox_function_views.change_period_day_of_draw,
        name="change-period-day-of-draw",
    ),
    url(
        r"^(?P<id>\d+)/change-cycle-draw-date/$",
        cashbox_function_views.change_cycle_draw_date,
        name="change-cycle-draw-date",
    ),
    url(
        r"^(?P<id>\d+)/activate/$",
        cashbox_function_views.activate_cashbox,
        name="activate",
    ),
    url(
        r"^(?P<id>\d+)/deactivate/$",
        cashbox_function_views.deactivate_cashbox,
        name="deactivate",
    ),
    url(
        r"^(?P<id>\d+)/start-new-cycle/$",
        cycle_function_views.start_new_cycle,
        name="start-new-cycle",
    ),
    url(
        r"^(?P<id>\d+)/cycles-list/$",
        cashbox_function_views.list_period_cycles,
        name="cycles-list",
    ),
    url(
        r"^(?P<id>\d+)/winners-list/$",
        cashbox_function_views.list_period_winners,
        name="winners-list",
    ),
    url(
        r"^(?P<id>\d+)/draw-cycle-and-start-new/$",
        cycle_function_views.draw_cycle_and_start_new,
        name="draw-cycle-and-start-new",
    ),
    url(r"^(?P<id>\d+)/draw/$", cycle_function_views.draw, name="draw"),
    url(
        r"^(?P<id>\d+)/request-drawable-memberships/$",
        cycle_function_views.request_drawable_memberships,
        name="request-drawable-memberships",
    ),
    url(
        r"^(?P<id>\d+)/request-drawables/$",
        cycle_function_views.request_drawables,
        name="request-drawables",
    ),
    url(
        r"^(?P<id>\d+)/transaction-list/$",
        cashbox_function_views.list_transactions,
        name="transaction-list",
    ),
    url(r"^(?P<id>\d+)/remove/$", cashbox_function_views.remove_cashbox, name="remove"),
    url(
        r"^(?P<id>\d+)/manual-cashout-init/$",
        cashbox_function_views.manual_cashout_init,
        name="manual-cashout-init",
    ),
    url(
        r"^(?P<id>\d+)/list-memberships-and-share-groups/$",
        cashbox_function_views.list_memberships_and_share_groups,
        name="list-memberships-and-share-groups",
    ),
]

membership_urlpatterns = [
    url(r"invite/$", membership_function_views.create_membership, name="invite"),
    url(
        r"invite-by-list/$",
        membership_function_views.create_membership_list,
        name="invite-by-list",
    ),
    url(
        r"update/(?P<membership_id>\d+)/$",
        membership_function_views.update_membership,
        name="update-request",
    ),
    url(
        r"request/$",
        membership_function_views.create_request_membership,
        name="request",
    ),
    url(
        r"accept-invitation/$",
        membership_function_views.accept_membership_invitation,
        name="accept-invitation",
    ),
    url(
        r"deny-invitation/$",
        membership_function_views.deny_membership_invitation,
        name="deny-invitation",
    ),
    url(
        r"accept-request/(?P<membership_id>\d+)/$",
        membership_function_views.accept_membership_request,
        name="accept-request",
    ),
    url(
        r"deny-request/(?P<membership_id>\d+)/$",
        membership_function_views.deny_membership_request,
        name="deny-request",
    ),
    url(r"leave/$", membership_function_views.leave_cashbox, name="leave"),
    url(
        r"kick-out-member/(?P<membership_id>\d+)/$",
        membership_function_views.kick_out_member,
        name="kick-out-member",
    ),
    url(
        r"member-list/$",
        membership_function_views.list_cashbox_members,
        name="member-list",
    ),
    url(
        r"requested-list/$",
        membership_function_views.list_cashbox_requested_members,
        name="requested-list",
    ),
    url(
        r"init-group-pay/$",
        membership_function_views.init_group_pay,
        name="init-group-pay",
    ),
    url(
        r"^transactions/$",
        membership_function_views.get_membership_transactions,
        name='get-membership-transactions'
    ),
]

share_group_urlpatterns = [
    url(r"create/$", share_group_function_views.create_share_group, name="create"),
    url(r"list/$", share_group_function_views.list_share_groups, name="list"),
    url(
        r"update/(?P<share_group_id>\d+)/$",
        share_group_function_views.update_share_group,
        name="update",
    ),
    url(
        r"kick-out/(?P<share_group_id>\d+)/$",
        share_group_function_views.kick_out_share_group,
        name="kick-out",
    ),
]

commission_urlpatterns = [
    url(
        r"^(?P<id>\d+)/calculate-cycle-commission/$",
        commission_function_views.calculate_cycle_commission,
        name="calculate-cycle-commission",
    )
]

urlpatterns = [
    url(r"^cashbox/", include(cashbox_urlpatterns, namespace="cashbox")),
    url(r"^draft_cashbox/", include(draft_cashbox_urlpatterns, namespace="draft")),
    url(
        r"^(?P<id>\d+)/membership/",
        include(membership_urlpatterns, namespace="membership"),
    ),
    url(
        r"^(?P<id>\d+)/share_group/",
        include(share_group_urlpatterns, namespace="share-group"),
    ),
    url(r"^commission/", include(commission_urlpatterns, namespace="commission")),
]
