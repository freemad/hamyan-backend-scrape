from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AdminPasswordChangeForm, UsernameField
from django.contrib.auth.forms import UserChangeForm as BaseUserChangeForm
from django.utils.translation import ugettext_lazy as _
from reversion.admin import VersionAdmin

User = get_user_model()


class BaseAdmin(VersionAdmin):
    def get_queryset(self, request):
        """
        Returns a QuerySet of all model instances that can be edited by the
        admin site. This is used by changelist_view.
        """
        qs = self.model.all_objects.get_queryset()
        # TODO: this should be handled by some parameter to the ChangeList.
        ordering = self.get_ordering(request)
        if ordering:
            qs = qs.order_by(*ordering)
        return qs


class BaseUserCreationForm(forms.ModelForm):
    """
    A form that creates a user, with no privileges, from the given username
    """

    class Meta:
        field_classes = {"username": UsernameField}

    def __init__(self, *args, **kwargs):
        super(BaseUserCreationForm, self).__init__(*args, **kwargs)
        self.fields[self._meta.model.USERNAME_FIELD].widget.attrs.update(
            {"autofocus": ""}
        )

    def save(self, commit=True):
        user = super(BaseUserCreationForm, self).save(commit=False)
        user.set_unusable_password()
        user.set_otp(joined=True)
        if commit:
            user.save()
        return user


class UserCreationForm(BaseUserCreationForm):
    class Meta(BaseUserCreationForm.Meta):
        model = User
        fields = ("phone_number",)


class UserChangeForm(BaseUserChangeForm):
    class Meta(BaseUserChangeForm.Meta):
        model = User


class BaseUserAdmin(BaseAdmin):
    fieldsets = (
        (None, {"fields": ("phone_number", "password")}),
        (_("Base info"), {"fields": ("email",)}),
        (
            _("Permissions"),
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        (_("Important dates"), {"fields": ("last_login", "date_joined")}),
    )
    readonly_fields = ("date_joined", "last_login")
    add_fieldsets = ((None, {"classes": ("wide",), "fields": ("phone_number",)}),)
    change_password_form = AdminPasswordChangeForm
    change_user_password_template = "admin/auth/user/change_password.html"
    filter_horizontal = ("groups", "user_permissions")
    form = UserChangeForm
    add_form = UserCreationForm
