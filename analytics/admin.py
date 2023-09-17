from django.contrib import admin

from utils.admin import BaseAdmin
from .models import EventLogAnalytics, EventLogTransaction, Category


class EventLogAnalyticsAdmin(BaseAdmin):
    actions = None
    search_fields = ("event_advisor",)
    list_display = ("event_advisor", "event", "count", "category", "created", "removed")
    list_display_links = None
    list_filter = ("event", "event_advisor")


class EventLogTransactionAdmin(BaseAdmin):
    actions = None
    search_fields = ("advisor", "app_name", "package_name", )
    list_display = ("member", "advisor", "app_name", "package_name", "version", "event", "os", "country", "category", "op", "build_number", "created", "removed")
    list_display_links = None
    list_filter = ("advisor", "app_name", "package_name", "version", "event", "os", "country", "category", "op", "build_number", "created", "removed")


class CategoryAdmin(BaseAdmin):
    actions = None
    search_fields = ("name", "created", "removed")
    list_display = ("name", "created", "removed")
    list_display_links = None


admin.site.register(EventLogAnalytics, EventLogAnalyticsAdmin)
admin.site.register(EventLogTransaction, EventLogTransactionAdmin)
admin.site.register(Category, CategoryAdmin)
