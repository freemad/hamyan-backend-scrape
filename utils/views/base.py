from rest_framework import viewsets, status
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from reversion.views import RevisionMixin


class OldBaseViews(RevisionMixin, viewsets.ModelViewSet):
    partial = True
    lookup_fields = {}
    lookup_fields_queryset = None
    permission_classes = {}

    def get_target_user(self):
        return None

    def get_permissions(self):
        # todo I don't even know what is metadata!
        if not self.action or self.action == "metadata":
            return [AllowAny()]
        if type(self.permission_classes) == dict:
            return [permission() for permission in self.permission_classes[self.action]]
        return super(OldBaseViews, self).get_permissions()

    def get_object(self):
        if self.lookup_fields:
            query_filters = {}
            queryset = (
                self.lookup_fields_queryset
                if self.lookup_fields_queryset
                else self.get_queryset()
            )
            fields = (
                self.lookup_fields[self.action]
                if type(self.lookup_fields) == dict
                else self.lookup_fields
            )
            for field in fields:
                query_filters[field] = self.kwargs[field]
            obj = get_object_or_404(queryset, **query_filters)
            return obj
        return super(OldBaseViews, self).get_object()

    def initial(self, request, *args, **kwargs):
        self.kwargs["partial"] = kwargs["partial"] = self.partial
        return super(OldBaseViews, self).initial(request, *args, **kwargs)

    def create(self, request, request_data=None, *args, **kwargs):
        data = request_data if request_data else request.data
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(
            serializer.data, status=status.HTTP_201_CREATED, headers=headers
        )


class BaseView(viewsets.ModelViewSet):
    serializers = {"default": None}
    action_permissions = {"default": None}

    def get_serializer_class(self):
        return self.serializers.get(self.action, self.serializers["default"])

    def get_permissions(self):
        permissions = self.action_permissions.get("default")
        if not hasattr(permissions, '__iter__'):
            # for support multiple permission for same action
            permissions = [permissions]

        return [permission() for permission in permissions]

    def check_object_permissions(self, request, obj):
        permissions = self.action_permissions.get(
            self.action, self.action_permissions["default"]
        )
        if not hasattr(permissions, '__iter__'):
            permissions = [permissions]

        for permission in permissions:
            permission = permission()
            if not permission.has_object_permission(request, self, obj):
                self.permission_denied(
                    request, message=getattr(permission, "message", None)
                )

    def check_permissions(self, request):
        for permission in self.get_permissions():
            if not permission.has_permission(request, self):
                self.permission_denied(
                    request, message=getattr(permission, "message", None)
                )
