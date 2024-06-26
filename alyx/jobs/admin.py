from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django_admin_listfilter_dropdown.filters import DropdownFilter, ChoiceDropdownFilter

from jobs.models import Task
from alyx.base import BaseAdmin, get_admin_url
from actions.models import Session


class TaskAdmin(BaseAdmin):
    exclude = ["json"]
    readonly_fields = ["get_log_link", "parents"]
    list_display = [
        "name",
        "graph",
        "status",
        "version_str",
        "level",
        "datetime",
        "session_str",
        "session_task_protocol",
        "session_projects",
    ]
    search_fields = (
        "session__id",
        "session__lab__name",
        "session__subject__nickname",
        "log",
        "version",
        "session__task_protocol",
        "session__projects__name",
    )
    ordering = ("-datetime",)
    list_editable = ("status",)
    list_filter = [
        ("name", DropdownFilter),
        ("status", ChoiceDropdownFilter),
        ("graph", DropdownFilter),
    ]

    def get_log_link(self, obj):
        url = reverse("task-logs", kwargs={"task_id": str(obj.pk)})
        return format_html('<a href="{url}">{log}</a>', log=obj.log or "-", url=url)

    get_log_link.short_description = "log"

    def has_change_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if obj:
            return obj.session.lab.name in request.user.lab

    def session_projects(self, obj):
        if obj.session is not None and obj.session.projects is not None:
            return obj.session.projects.name

    session_projects.short_description = "projects"

    def session_task_protocol(self, obj):
        if obj.session is not None:
            return obj.session.task_protocol

    session_task_protocol.short_description = "task_protocol"

    def session_str(self, obj):
        if obj.session is not None:
            url = get_admin_url(obj.session)
            return format_html('<a href="{url}">{session}</a>', session=obj.session or "-", url=url)

    session_str.short_description = "session"

    def version_str(self, obj):
        black, green, orange, red = ("000000", "008000", "FF7F50", "FF0000")
        if obj.status == 40:  # error
            col = red
        elif obj.status == 50:  # empty
            col = orange
        elif obj.status == 60:  # complete
            col = green
        else:
            col = black
        return format_html('<b><a style="color: #{};">{}</a></b>', col, "{}".format(obj.version))

    version_str.short_description = "version"

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "session":  # replace 'session' with your session field name
            kwargs["queryset"] = Session.objects.order_by("-start_time")  # replace Session and logic here.
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


admin.site.register(Task, TaskAdmin)
