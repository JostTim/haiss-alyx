from django.db.models import Q, Count, Max
from rest_framework import generics
from django_filters.rest_framework import CharFilter
from django.views.generic.list import ListView
from django.views.generic.detail import DetailView
from django.shortcuts import get_object_or_404
from django.urls import reverse
import numpy as np

from alyx.base import BaseFilterSet, rest_permission_classes
import django_filters

from misc.models import Lab
from jobs.models import Task
from jobs.serializers import TaskListSerializer, TaskDetailsSeriaizer
from actions.models import Session


class TasksStatusView(ListView):
    template_name = "tasks.html"
    paginate_by = 50

    def get_context_data(self, **kwargs):
        graph = self.kwargs.get("graph", None)
        context = super(TasksStatusView, self).get_context_data(**kwargs)
        context["tableFilter"] = self.f
        context["graphs"] = list(Task.objects.all().values_list("graph", flat=True).distinct())
        # annotate the labs for template display
        cw = Count("session__tasks", filter=Q(session__tasks__status=20))
        ls = Max("session__start_time", filter=Q(session__tasks__isnull=False))
        lj = Max("session__tasks__datetime")
        context["labs"] = Lab.objects.annotate(count_waiting=cw, last_session=ls, last_job=lj).order_by("name")
        space = np.array(context["labs"].values_list("json__raid_available", flat=True), dtype=np.float)
        context["space_left"] = np.round(space / 1000, decimals=1)
        context["ibllib_version"] = list(context["labs"].values_list("json__ibllib_version", flat=True))
        if graph:
            # here the empty order_by is to fix a low level SQL bug with distinct when called
            # on value lists and unique together constraints. bof.
            # https://code.djangoproject.com/ticket/16058
            context["task_names"] = list(
                Task.objects.filter(graph=graph)
                .exclude(session__qc=50)
                .order_by("-priority")
                .order_by("level")
                .order_by()
                .values_list("name", flat=True)
                .distinct()
            )
        else:
            context["task_names"] = []
        context["title"] = "Tasks Recap"
        context["site_header"] = "Alyx"
        return context

    def get_queryset(self):
        graph = self.kwargs.get("graph", None)
        lab = self.kwargs.get("lab", None)
        qs = Session.objects.exclude(qc=50)
        if lab is None and graph is None:
            qs = Session.objects.none()
        else:
            if lab:
                qs = qs.filter(lab__name=lab)
            if graph:
                qs = qs.filter(tasks__graph=self.kwargs["graph"])

        self.f = ProjectFilter(self.request.GET, queryset=qs)

        return self.f.qs.distinct().order_by("-start_time")


class ProjectFilter(django_filters.FilterSet):
    """
    Filter used in combobox of task admin page
    """

    class Meta:
        model = Session
        fields = ["projects"]
        exclude = ["json"]

    def __init__(self, *args, **kwargs):
        super(ProjectFilter, self).__init__(*args, **kwargs)


class TaskFilter(BaseFilterSet):
    lab = CharFilter("session__lab__name")
    status = CharFilter(method="enum_field_filter")

    class Meta:
        model = Task
        exclude = ["json"]


class TaskListView(generics.ListCreateAPIView):
    """
    get: **FILTERS**
    -   **task**: task name `/jobs?task=EphysSyncPulses`
    -   **session**: uuid `/jobs?session=aad23144-0e52-4eac-80c5-c4ee2decb198`
    -   **lab**: lab name from session table `/jobs?lab=churchlandlab`
    -   **pipeline**: pipeline field from task `/jobs?pipeline=ephys`

    [===> task model reference](/admin/doc/models/jobs.task)
    """

    queryset = Task.objects.all()
    # queryset = TaskListSerializer.setup_eager_loading(queryset)
    permission_classes = rest_permission_classes()
    filter_class = TaskFilter

    def get_serializer_class(self):
        if not self.request:
            return TaskListSerializer
        if self.request.method == "GET":
            return TaskListSerializer
        if self.request.method == "POST":
            return TaskDetailsSeriaizer


class TaskDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Task.objects.all()
    # queryset = TaskDetailsSeriaizer.setup_eager_loading(queryset)
    serializer_class = TaskDetailsSeriaizer
    permission_classes = rest_permission_classes()


class TaskLogs(DetailView):
    template_name = "task_logs.html"
    # model = Task

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        task_id = self.kwargs.get("task_id", None)
        ansi_logging_content = open("/mnt/one/cajal2/Adaptation/test.log", "r").read()
        context["task_id"] = task_id
        context["task_change_url"] = reverse("admin:jobs_task_change", args=[task_id])
        context["ansi_logging_content"] = ansi_logging_content
        return context

    def get_object(self):
        return get_object_or_404(Task, pk=self.kwargs["task_id"])
