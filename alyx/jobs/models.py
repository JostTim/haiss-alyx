import uuid
from django.db import models

from actions.models import Session


class Task(models.Model):
    """
    Provides a model for a Task, with priorities and resources
    """

    STATUS_DATA_SOURCES = [
        (20, "Created"),
        (25, "Waiting"),
        (30, "Started"),
        (35, "No_Info"),
        (40, "Warnings"),
        (45, "Errors"),
        (50, "Critical"),
        (55, "Failed"),
        (60, "Uncatched_Fail"),
        (100, "Complete"),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # some information for parallel runs
    name = models.CharField(max_length=64, blank=True, null=True)
    priority = models.SmallIntegerField(blank=True, null=True)
    io_charge = models.SmallIntegerField(blank=True, null=True)
    level = models.SmallIntegerField(blank=True, null=True)
    gpu = models.SmallIntegerField(blank=True, null=True)
    cpu = models.SmallIntegerField(blank=True, null=True)
    ram = models.SmallIntegerField(blank=True, null=True)
    time_out_secs = models.SmallIntegerField(blank=True, null=True)
    time_elapsed_secs = models.FloatField(blank=True, null=True)
    executable = models.CharField(
        max_length=128, blank=True, null=True, help_text="Usually the Python class name on the workers"
    )
    graph = models.CharField(
        max_length=64,
        blank=True,
        null=True,
        help_text="The name of the graph containing a set of related and possibly dependent tasks",
    )
    _shelp = " / ".join([str(s[0]) + ": " + s[1] for s in STATUS_DATA_SOURCES])
    status = models.IntegerField(default=20, choices=STATUS_DATA_SOURCES, help_text=_shelp)
    log = models.TextField(blank=True, null=True)
    session = models.ForeignKey(Session, blank=True, null=True, on_delete=models.CASCADE, related_name="tasks")
    version = models.CharField(
        blank=True, null=True, max_length=64, help_text="version of the algorithm generating the file"
    )
    # dependency pattern for the task graph
    parents = models.ManyToManyField("self", blank=True, related_name="children", symmetrical=False)
    datetime = models.DateTimeField(auto_now=True)
    arguments = models.JSONField(blank=True, null=True, help_text="dictionary of input arguments")
    data_repository = models.ForeignKey(
        "data.DataRepository", null=True, blank=True, related_name="tasks", on_delete=models.CASCADE
    )

    @property
    def session_path(self):
        return self.session.path

    def __str__(self):
        return f"{self.name}  {self.session}  {self.get_status_display()}"

    # class Meta:
    #     constraints = [
    #         models.UniqueConstraint(fields=["name", "session", "arguments"], name="unique_name_arguments_per_session")
    #     ]
