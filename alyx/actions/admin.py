import base64
import json
import structlog

from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Case, When, Q, Value, Func, F, CharField
from django.db.models.functions import Concat
from django.urls import reverse
from django.utils.html import format_html, mark_safe
from django_admin_listfilter_dropdown.filters import (
    RelatedDropdownFilter,
    SimpleDropdownFilter,
)
from django.shortcuts import get_object_or_404
from django.contrib.admin import site, SimpleListFilter, TabularInline
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.db.models.functions import Collate
from rangefilter.filter import DateRangeFilter
from django.utils import timezone
from functools import partial

from alyx.base import BaseAdmin, DefaultListFilter, BaseInlineAdmin, get_admin_url
from .models import (
    OtherAction,
    ProcedureType,
    Session,
    EphysSession,
    Surgery,
    VirusInjection,
    WaterAdministration,
    WaterRestriction,
    Weighing,
    WaterType,
    Notification,
    NotificationRule,
    Cull,
    CullReason,
    CullMethod,
    ImagingSession,
)
from data.models import Dataset, FileRecord, DatasetType
from misc.admin import NoteInline
from misc.models import LabMember
from subjects.models import Subject, Project
from .water_control import WaterControl
from experiments.models import ProbeInsertion

# https://github.com/nnseva/django-jsoneditor
from jsoneditor.forms import JSONEditor
from django.db.models.fields.json import JSONField
from django.db.models.fields.__init__ import TextField
from markdownx.admin import MarkdownxModelAdmin

# from mdeditor.widgets import MDeditorWidget

# natsort = partial(Collate, collation="natsort_collation")

logger = structlog.get_logger("actions.admin")


# Filters
# ------------------------------------------------------------------------------------------------


class ResponsibleUserListFilter(DefaultListFilter):
    title = "responsible user"
    parameter_name = "responsible_user"

    def lookups(self, request, model_admin):
        return (
            (None, "All"),
            ("me", "Me"),
        )

    def queryset(self, request, queryset):
        value = self.value()
        if value is None:
            return queryset.all()
        elif value == "me":
            return queryset.filter(subject__responsible_user=request.user)


class SubjectAliveListFilter(DefaultListFilter):
    title = "alive"
    parameter_name = "alive"

    def lookups(self, request, model_admin):
        return (
            (None, "Yes"),
            ("n", "No"),
            ("all", "All"),
        )

    def queryset(self, request, queryset):
        if self.value() is None:
            return queryset.filter(subject__cull__isnull=True)
        if self.value() == "n":
            return queryset.exclude(subject__cull__isnull=True)
        elif self.value == "all":
            return queryset.all()


class ActiveFilter(DefaultListFilter):
    title = "active"
    parameter_name = "active"

    def lookups(self, request, model_admin):
        return (
            (None, "All"),
            ("active", "Active"),
        )

    def queryset(self, request, queryset):
        if self.value() == "active":
            return queryset.filter(
                start_time__isnull=False,
                end_time__isnull=True,
            )
        elif self.value is None:
            return queryset.all()


class CreatedByListFilter(DefaultListFilter):
    title = "users"
    parameter_name = "users"

    def lookups(self, request, model_admin):
        return (
            (None, "Me"),
            ("all", "All"),
        )

    def queryset(self, request, queryset):
        if self.value() is None:
            return queryset.filter(users=request.user)
        elif self.value == "all":
            return queryset.all()


def _bring_to_front(ids: list, id: int):
    if id in ids:
        ids.remove(id)
    ids.insert(0, id)
    return ids


# Admin
# ------------------------------------------------------------------------------------------------
class BaseActionForm(forms.ModelForm):
    def __init__(self, *args, last_subject_id=None, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if "users" in self.fields:
            self.fields["users"].queryset = get_user_model().objects.all().order_by("username")
            if user is not None:
                self.fields["users"].initial = [user]
        if "user" in self.fields:
            self.fields["user"].queryset = get_user_model().objects.all().order_by("username")
            if user is not None:
                self.fields["user"].initial = user
        if "procedures" in self.fields:
            self.fields["procedures"].queryset = ProcedureType.objects.order_by("name")
        if "projects" in self.fields:
            self.fields["projects"] = forms.ModelMultipleChoiceField(
                Project.objects,
                widget=FilteredSelectMultiple("projects", is_stacked=False),
            )
            self.fields["projects"].queryset = Project.objects.exclude(name="DefaultParameterProject").order_by("name")
        if "lab" in self.fields:
            if user is not None:
                labs_pk = user.lab_id()
                if len(labs_pk) == 1:
                    self.fields["lab"].initial = labs_pk[0]

        # restricts the subject choices only to managed subjects
        if "subject" in self.fields:  # and not (user.is_stock_manager or user.is_superuser):

            # prepare for a complex query with multiple or cases
            query = Q(cull__isnull=True)

            priority_order = []
            # Check if the instance already has a subject selected
            selected_subject = getattr(self.instance, "subject", None)
            if selected_subject:
                query |= Q(id=selected_subject.id)
                priority_order.append(selected_subject.id)

            # Check if there is a last subject for which we should make quick select available
            elif last_subject_id is not None:
                query |= Q(id=last_subject_id)
                priority_order.append(last_subject_id)

            preserved_order = [When(id=id, then=pos) for pos, id in enumerate(priority_order)]

            # default : makes all annotation one more than the priority orders max value.
            queryset = Subject.objects.filter(query).annotate(
                priority_order=Case(*preserved_order, default=len(priority_order))
            )

            # we order first on priority_order, wich is all 0 if no priority is set, then on nickname
            self.fields["subject"].queryset = queryset.order_by("priority_order", "nickname")

    procedures = forms.ModelMultipleChoiceField(
        ProcedureType.objects,
        widget=FilteredSelectMultiple("procedures", is_stacked=False),
    )

    users = forms.ModelMultipleChoiceField(
        LabMember.objects,
        widget=FilteredSelectMultiple("users", is_stacked=False),
    )

    # projects = forms.ModelMultipleChoiceField(
    #     Project.objects,
    #     widget=FilteredSelectMultiple("projects", is_stacked=False),
    # )

    json = forms.JSONField(widget=JSONEditor, required=False)

    def is_valid(self):
        valid = super().is_valid()
        if not valid:
            logger.warning(f"Form errors: {self.errors.as_json()}")
        else:
            logger.warning("No form errors found")
        return valid

    def save(self, commit=True):
        logger.warning("Saving admin form")
        logger.warning(f"Cleaned data : {self.cleaned_data}")
        instance = super().save(commit=commit)
        return instance


class BaseActionAdmin(BaseAdmin):

    mandatory_fields = ["subject", "start_time"]

    end_time_fields = ["end_time"]

    fields = (
        mandatory_fields
        + end_time_fields
        + [
            "users",
            "procedures",
            "location",
            "lab",
            "narrative",
        ]
    )
    readonly_fields = ["subject_l"]

    form = BaseActionForm

    def subject_l(self, obj):
        url = get_admin_url(obj.subject)
        return format_html('<a href="{url}">{subject}</a>', subject=obj.subject or "-", url=url)

    subject_l.short_description = "subject"
    subject_l.admin_order_field = "subject__nickname"

    def projects(self, obj):
        return ", ".join(p.name for p in obj.subject.projects.all())

    def _get_last_subject(self, request):
        return getattr(request, "session", {}).get("last_subject_id", None)

    def get_form(self, request, obj=None, **kwargs):
        Form = super().get_form(request, obj, **kwargs)
        # form.current_user = request.user
        # form.last_subject_id = self._get_last_subject(request)

        class RequestBaseActionForm(Form):
            def __new__(cls, *args, **kwargs):
                if self.form == BaseActionForm:
                    logger.warning("BaseActionForm requested")
                    kwargs["user"] = request.user
                    kwargs["last_subject_id"] = self._get_last_subject(request)
                else:
                    logger.warning("Specific Action Form requested")
                return Form(*args, **kwargs)

        return RequestBaseActionForm

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        # Logged-in user by default.
        if db_field.name == "user":
            kwargs["initial"] = request.user
        if db_field.name == "subject":
            subject_id = self._get_last_subject(request)
            if subject_id:
                subject = Subject.objects.filter(id=subject_id).first()
                if subject:
                    kwargs["initial"] = subject
        return super(BaseActionAdmin, self).formfield_for_foreignkey(db_field, request, **kwargs)

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        # Logged-in user by default.
        if db_field.name == "users":
            kwargs["initial"] = [request.user]
        return super(BaseActionAdmin, self).formfield_for_manytomany(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        logger.warning(f"Saving data model {obj}")
        subject = getattr(obj, "subject", None)
        if subject:
            getattr(request, "session", {})["last_subject_id"] = subject.id.hex
        super(BaseActionAdmin, self).save_model(request, obj, form, change)


class ProcedureTypeAdmin(BaseAdmin):
    fields = ["name", "description"]
    ordering = ["name"]


class WaterAdministrationForm(forms.ModelForm):
    class Meta:
        model = WaterAdministration
        fields = "__all__"

    def __init__(self, *args, water_administered=None, subject=None, **kwargs):
        super(WaterAdministrationForm, self).__init__(*args, **kwargs)

        # Only show subjects that are on water restriction.
        # ids = [
        #     wr.subject.pk
        #     for wr in WaterRestriction.objects.filter(
        #         start_time__isnull=False, end_time__isnull=True
        #     )
        # ]

        subjects = Subject.objects.filter(
            actions_waterrestrictions__start_time__isnull=False,
            actions_waterrestrictions__end_time__isnull=True,
        ).order_by("nickname")

        if getattr(self, "last_subject_id", None):
            last_subject_id = self.last_subject_id
        else:
            last_subject_id = False

        self.fields["subject"].queryset = subjects

        # These ids first in the list of subjects, if any ids
        if not self.fields:
            return

        # elif ids:
        #     # preserved = Case(*[When(pk=pk, then=pos) for pos, pk in enumerate(ids)])
        #     self.fields["subject"].queryset = Subject.objects.order_by(
        #         Collate("nickname", "en-u-kn-true-x-icu")
        #     )
        # else:
        #     self.fields["subject"].queryset = Subject.objects.order_by("nickname")
        self.fields["user"].queryset = get_user_model().objects.all().order_by("username")

        if subject:
            subject = get_object_or_404(Subject, nickname=subject)
            self.fields["subject"].initial = subject
        elif last_subject_id:
            subject = get_object_or_404(Subject, pk=last_subject_id)
            self.fields["subject"].initial = subject

        if water_administered:
            self.fields["water_administered"].initial = water_administered

        self.fields["water_administered"].widget.attrs.update({"autofocus": "autofocus"})


class WaterAdministrationAdmin(BaseActionAdmin):
    form = WaterAdministrationForm

    def get_form(self, request, obj=None, **kwargs):
        Form = super().get_form(request, obj, **kwargs)
        return partial(
            Form,
            water_administered=request.GET.get("water_administered", None),
            subject=request.GET.get("subject", None),
        )

    fields = [
        "subject",
        "date_time",
        "water_administered",
        "water_type",
        "adlib",
        "user",
        "session_l",
    ]
    list_display = [
        "subject_l",
        "water_administered",
        "user",
        "date_time",
        "water_type",
        "adlib",
        "session_l",
        "projects",
    ]
    list_display_links = ("water_administered",)
    list_select_related = ("subject", "user")
    ordering = ["-date_time", "subject__nickname"]
    search_fields = ["subject__nickname", "subject__projects__name"]
    list_filter = [ResponsibleUserListFilter, ("subject", RelatedDropdownFilter)]
    readonly_fields = [
        "session_l",
    ]

    def session_l(self, obj):
        url = get_admin_url(obj.session)
        return format_html('<a href="{url}">{session}</a>', session=obj.session or "-", url=url)

    session_l.short_description = "Session"
    session_l.allow_tags = True


class WaterRestrictionForm(forms.ModelForm):
    implant_weight = forms.FloatField()

    def save(self, commit=True):
        implant_weight = self.cleaned_data.get("implant_weight")
        subject = self.cleaned_data.get("subject", None)
        if implant_weight:
            subject.implant_weight = implant_weight
            subject.save()
        return super(WaterRestrictionForm, self).save(commit=commit)

    class Meta:
        model = WaterRestriction
        fields = "__all__"


class WaterRestrictionAdmin(BaseActionAdmin):

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "subject":
            kwargs["queryset"] = Subject.objects.filter(cull__isnull=True).order_by("nickname")
            subject_id = self._get_last_subject(request)
            if subject_id:
                subject = Subject.objects.get(id=subject_id)
                kwargs["initial"] = subject
        return super(BaseActionAdmin, self).formfield_for_foreignkey(db_field, request, **kwargs)

    def get_form(self, request, obj=None, **kwargs):
        form = super(WaterRestrictionAdmin, self).get_form(request, obj, **kwargs)
        subject = getattr(obj, "subject", None)
        iw = getattr(subject, "implant_weight", None)
        rw = subject.water_control.weight() if subject else None
        form.base_fields["implant_weight"].initial = iw
        if self.has_change_permission(request, obj):
            form.base_fields["reference_weight"].initial = rw or 0
        return form

    form = WaterRestrictionForm

    fields = [
        "subject",
        "implant_weight",
        "reference_weight",
        "start_time",
        "end_time",
        "water_type",
        "users",
        "narrative",
    ]

    list_display = (
        (
            "subject_w",
            "start_time_l",
            "end_time_l",
            "water_type",
            "weight",
            "weight_ref",
        )
        + WaterControl._columns[4:]
        + ("projects",)
    )
    list_select_related = ("subject",)
    list_display_links = ("start_time_l", "end_time_l")
    readonly_fields = ("weight",)  # WaterControl._columns[1:]
    ordering = ["-start_time", "subject__nickname"]
    search_fields = ["subject__nickname", "subject__projects__name"]
    list_filter = [
        ResponsibleUserListFilter,
        ("subject", RelatedDropdownFilter),
        ActiveFilter,
    ]

    def subject_w(self, obj):
        url = reverse("water-history", kwargs={"subject_id": obj.subject.id})
        return format_html('<a href="{url}">{name}</a>', url=url, name=obj.subject.nickname)

    subject_w.short_description = "subject"
    subject_w.admin_order_field = "subject"

    def start_time_l(self, obj):
        return obj.start_time.date()

    start_time_l.short_description = "start date"
    start_time_l.admin_order_field = "start_time"

    def end_time_l(self, obj):
        if obj.end_time:
            return obj.end_time.date()
        else:
            return obj.end_time

    end_time_l.short_description = "end date"
    end_time_l.admin_order_field = "end_time"

    def weight(self, obj):
        if not obj.subject:
            return
        wc = obj.subject.water_control
        date = wc.restriction_end_date(obj)
        return "%.1f" % wc.weight(date=date)

    weight.short_description = "current weight"

    def weight_ref(self, obj):
        if not obj.subject:
            return
        wc = obj.subject.water_control
        date = wc.restriction_end_date(obj)
        return "%.1f" % wc.reference_weight(date=date)

    weight_ref.short_description = "reference weight"

    def expected_weight(self, obj):
        if not obj.subject:
            return
        wc = obj.subject.water_control
        date = wc.restriction_end_date(obj)
        return "%.1f" % wc.expected_weight(date=date)

    expected_weight.short_description = "expected weight"

    def percentage_weight(self, obj):
        wc = obj.subject.water_control
        date = wc.restriction_end_date(obj)
        return wc.percentage_weight_html(date=date)

        # if not obj.subject:
        #     return
        # return "%.1f" % obj.subject.water_control.percentage_weight()

    percentage_weight.short_description = "weight %"

    def min_weight(self, obj):
        if not obj.subject:
            return

        wc = obj.subject.water_control
        date = wc.restriction_end_date(obj)
        return "%.1f" % wc.min_weight(date=date)

    min_weight.short_description = "min limit weight"

    def given_water_reward(self, obj):
        if not obj.subject:
            return

        wc = obj.subject.water_control
        date = wc.restriction_end_date(obj)
        return "%.2f" % wc.given_water_reward(date=date)

    given_water_reward.short_description = "daily water reward"

    def given_water_supplement(self, obj):
        if not obj.subject:
            return
        wc = obj.subject.water_control
        date = wc.restriction_end_date(obj)
        return "%.2f" % wc.given_water_supplement(date=date)

    given_water_supplement.short_description = "daily water supplied"

    def given_water_total(self, obj):
        if not obj.subject:
            return
        wc = obj.subject.water_control
        date = wc.restriction_end_date(obj)
        return "%.2f" % wc.given_water_total(date=date)

    given_water_total.short_description = "daily total water recieved"

    def has_change_permission(self, request, obj=None):
        # setting to override edition of water restrictions in the settings.lab file
        override = getattr(settings, "WATER_RESTRICTIONS_EDITABLE", False)
        if override:
            return True
        else:
            return super(WaterRestrictionAdmin, self).has_change_permission(request, obj=obj)

    def expected_water(self, obj):
        if not obj.subject:
            return
        wc = obj.subject.water_control
        date = wc.restriction_end_date(obj)
        return "%.2f" % wc.expected_water(date=date)

    expected_water.short_description = "daily total water expected"

    # method name is misleading, to change it, would require to change WaterControl._columns
    # posponing. # TODO
    def excess_water(self, obj):
        if not obj.subject:
            return
        wc = obj.subject.water_control
        date = wc.restriction_end_date(obj)
        return wc.remaining_water_html(date=date)

    excess_water.short_description = "daily missing water"

    def is_water_restricted(self, obj):
        return obj.is_active()

    is_water_restricted.short_description = "restriction active"
    is_water_restricted.boolean = True


class WeighingForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super(WeighingForm, self).__init__(*args, **kwargs)
        if self.fields.keys():
            self.fields["weight"].widget.attrs.update({"autofocus": "autofocus"})

    class Meta:
        model = Weighing
        fields = ["user", "subject", "date_time", "weight", "json"]


class WeighingAdmin(BaseActionAdmin):
    list_display = ["subject_l", "weight", "percentage_weight", "date_time", "projects"]
    list_select_related = ("subject",)
    fields = ["subject", "date_time", "weight", "user"]
    ordering = ("-date_time",)
    list_display_links = ("weight",)
    search_fields = ["subject__nickname", "subject__projects__name"]
    list_filter = [ResponsibleUserListFilter, ("subject", RelatedDropdownFilter)]

    form = WeighingForm

    def percentage_weight(self, obj):
        wc = obj.subject.water_control
        return wc.percentage_weight_html(date=obj.date_time)

    percentage_weight.short_description = "Weight %"


class WaterTypeAdmin(BaseActionAdmin):
    list_display = ["name", "json"]
    fields = ["name", "json"]
    ordering = ("name",)
    list_display_links = ("name",)


class SurgeryAdmin(BaseActionAdmin):
    list_display = [
        "subject_l",
        "date",
        "users_l",
        "procedures_l",
        "narrative",
        "projects",
    ]
    list_select_related = ("subject",)

    fields = list(BaseActionAdmin.fields) + ["outcome_type"]
    list_display_links = ["date"]
    search_fields = ("subject__nickname", "subject__projects__name")
    list_filter = [
        SubjectAliveListFilter,
        ResponsibleUserListFilter,
        ("subject__line", RelatedDropdownFilter),
    ]
    ordering = ["-start_time"]
    inlines = [NoteInline]

    def date(self, obj):
        return obj.start_time.date()

    date.admin_order_field = "start_time"

    def users_l(self, obj):
        return ", ".join(map(str, obj.users.all()))

    users_l.short_description = "users"

    def procedures_l(self, obj):
        return ", ".join(map(str, obj.procedures.all()))

    procedures_l.short_description = "procedures"

    def get_queryset(self, request):
        return super(SurgeryAdmin, self).get_queryset(request).prefetch_related("users", "procedures")


class DatasetInline(BaseInlineAdmin):
    show_change_link = True
    model = Dataset
    extra = 0
    fields = (
        "name",
        "dataset_type",
        "data_format",
        "collection",
        "_online",
        "created_by",
        "created_datetime",
    )
    readonly_fields = ("name", "_online", "created_by", "created_datetime")
    ordering = ("name",)

    def _online(self, obj):
        return obj.is_online

    _online.short_description = "On server"
    _online.boolean = True

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "dataset_type":
            kwargs["queryset"] = DatasetType.objects.all()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class WaterAdminInline(BaseInlineAdmin):
    model = WaterAdministration
    extra = 0
    fields = ("name", "water_administered", "water_type")
    readonly_fields = ("name", "water_administered", "water_type")


def _pass_narrative_templates(context):
    context["narrative_templates"] = base64.b64encode(json.dumps(settings.NARRATIVE_TEMPLATES).encode("utf-8")).decode(
        "utf-8"
    )
    return context


class QCFilter(SimpleDropdownFilter):
    title = "quality check"
    parameter_name = "qc"

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(qc__exact=self.value())

    def lookups(self, request, model_admin):
        return model_admin.model.QC_CHOICES


class SessionSubjectFilter(SimpleDropdownFilter):
    title = "subject"
    parameter_name = "subject"

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(subject__id=self.value())

    def lookups(self, request, model_admin):
        return Subject.objects.all().order_by("nickname").values_list("id", "nickname")


class SortedRelatedDropdownFilter(RelatedDropdownFilter):
    def field_choices(self, field, request, model_admin):
        related_model = field.related_model
        human_readable_name = related_model.human_field_string()

        related_ids = model_admin.model.objects.values_list(f"{field.name}__id", flat=True).distinct()
        choices = (
            related_model.objects.filter(id__in=related_ids)
            .order_by(human_readable_name)
            .values_list("id", human_readable_name)
        )
        return list(choices)


class DatasetTypeDropdownFilter(RelatedDropdownFilter):
    def field_choices(self, field, request, model_admin):
        related_ids = model_admin.model.objects.values_list(
            "data_dataset_session_related__dataset_type__id", flat=True
        ).distinct()
        choices = DatasetType.objects.filter(id__in=related_ids).order_by("name").values_list("id", "name")
        return list(choices)


class FormatDate(Func):
    function = "TO_CHAR"
    template = "%(function)s(%(expressions)s, 'YYYY-MM-DD')"


class ZFill(Func):
    function = "LPAD"
    template = "%(function)s(CAST(%(expressions)s AS TEXT), 3, '0')"


class SessionAdmin(BaseActionAdmin, MarkdownxModelAdmin):
    change_form_template = r"admin/session_change_form.html"

    list_display = [
        "alias_with_tooltip",
        "subject_l",
        "start_time",
        "number",
        "dataset_count",  # removed 'lab' as we are in a single lab environment
        "procedures_",
        "qc",
        "user_list",
        "project_",
    ]  # removed 'task_protocol' as we do not currentely use it too much
    # task_protocol also needs rework to attached to a defined protocol,
    # and not be just a user defined string that doesn't mean much to anyone else.

    list_display_links = ["alias_with_tooltip"]
    fields = None
    fieldsets = (
        ("Mandatory", {"fields": list(BaseActionAdmin.fields[:2]) + ["number"]}),
        (
            "Main session infos",
            {
                "fields": list(BaseActionAdmin.fields[2:-1])
                + ["projects"]
                + [BaseActionAdmin.fields[-1]]  # removed 'repo_url' as we are not web based but samba based
            },
        ),
        (
            "Post-acquisition session infos",
            {
                "fields": [
                    "default_data_repository",
                    "qc",
                    "extended_qc",
                    "n_correct_trials",
                    "n_trials",
                    "weighing",
                    "auto_datetime",
                    "json",
                ]
            },
        ),
    )
    list_filter = [
        ("users", SortedRelatedDropdownFilter),
        ("subject", SortedRelatedDropdownFilter),
        ("start_time", DateRangeFilter),
        ("projects", RelatedDropdownFilter),
        ("procedures", RelatedDropdownFilter),
        ("data_dataset_session_related__dataset_type", DatasetTypeDropdownFilter),
        QCFilter,
    ]

    search_fields = ("subject__nickname",)

    # search_fields = (
    #     "subject__nickname",
    #     "lab__name",
    #     "projects__name",
    #     "users__username",
    #     "task_protocol",
    #     "pk",
    # )
    ordering = ("-start_time", "task_protocol", "lab")
    inlines = [WaterAdminInline, DatasetInline, NoteInline]
    readonly_fields = ["repo_url", "task_protocol", "weighing", "auto_datetime"]
    formfield_overrides = {
        JSONField: {"widget": JSONEditor},
    }

    def get_search_results(self, request, queryset, search_term):

        ## Just convert back slashes to forward slashes to make sure we search for the session.alias in the right way
        # (unix style)
        search_term = search_term.replace("\\", "/")

        queryset = queryset.annotate(
            formatted_datetime=FormatDate(F("start_time")),
            formatted_number=ZFill(F("number")),
            search_alias=Concat(
                "subject__nickname",
                Value("/"),
                F("formatted_datetime"),
                Value("/"),
                F("formatted_number"),
                output_field=CharField(),
            ),
            search_u_alias=Concat(
                "subject__nickname",
                Value("_"),
                F("formatted_datetime"),
                Value("_"),
                F("formatted_number"),
                output_field=CharField(),
            ),
        )
        # queryset, use_distinct = super().get_search_results(request, queryset, search_term)

        # Adding custom filtering for the alias
        if search_term:
            custom_filter = (
                Q(search_alias__iexact=search_term)
                | Q(search_u_alias__iexact=search_term)
                | Q(formatted_number__iexact=search_term)
                | Q(formatted_datetime__iexact=search_term)
                | Q(subject__nickname__iexact=search_term)
                | Q(users__username__iexact=search_term)
                | Q(pk__iexact=search_term)
                | Q(projects__name__iexact=search_term)
            )
            queryset = queryset.filter(custom_filter)

        return queryset, True  # use_distinct

    def alias_with_tooltip(self, obj):
        return format_html(
            '<span title="Narrative :\n{tooltip}">{alias}</span>',
            tooltip=obj.narrative,
            alias=obj.alias,
        )

    alias_with_tooltip.short_description = "Session Name"

    # def get_form(self, request, obj=None, **kwargs):
    #     from subjects.admin import Project
    #     from django.db.models import Q

    #     form = super().get_form(request, obj, **kwargs)
    #     # if form.base_fields:
    #     #     if not request.user.is_superuser:
    #     #         # the projects edit box is limited to projects with no user or containing current user
    #     #         current_proj = obj.projects.all() if obj else None
    #     #         form.base_fields["projects"].queryset = Project.objects.filter(
    #     #             Q(users=request.user.pk) | Q(users=None) | Q(pk__in=current_proj)
    #     #         ).distinct()
    #     #     form.base_fields["subject"].queryset = Subject.objects.filter(death_date__isnull=True).
    # order_by("nickname")
    #     return form

    def change_view(self, request, object_id, extra_context=None, **kwargs):
        context = extra_context or {}
        context["show_button"] = object_id is not None  # True if the object already exists, else False
        if context["show_button"]:
            context["tasks_url"] = reverse("session-tasks", kwargs={"session_pk": object_id})
            context["results_url"] = f"http://haiss-alyx.local:5000/images/{object_id}"  # url for result-manager
            context["uuid"] = object_id
        context = _pass_narrative_templates(context)
        return super(SessionAdmin, self).change_view(request, object_id, extra_context=context, **kwargs)

    def add_view(self, request, extra_context=None):
        context = extra_context or {}
        context = _pass_narrative_templates(context)
        context["show_button"] = False
        context["uuid"] = None
        return super(SessionAdmin, self).add_view(request, extra_context=context)  # type: ignore

    def procedures_(self, obj):
        return [getattr(p, "name", None) for p in obj.procedures.all()]

    procedures_.short_description = "Procedures"

    def project_(self, obj):
        return [getattr(p, "name", None) for p in obj.projects.all()]

    def repo_url(self, obj):
        url = settings.SESSION_REPO_URL.format(
            lab=obj.subject.lab.name,
            subject=obj.subject.nickname,
            date=obj.start_time.date(),
            number=obj.number or 0,
        )
        return format_html('<a href="{url}">{url}</a>'.format(url=url))

    def user_list(self, obj):
        return ", ".join(map(str, obj.users.all()))

    user_list.short_description = "users"

    def dataset_count(self, ses):
        cs = (
            FileRecord.objects.filter(dataset__in=ses.data_dataset_session_related.all(), exists=True)
            .values_list("relative_path")
            .distinct()
            .count()
        )
        cr = (
            FileRecord.objects.filter(
                dataset__in=ses.data_dataset_session_related.all(),
            )
            .values_list("relative_path")
            .distinct()
            .count()
        )
        if cr == 0:
            return "-"
        col = "008000" if cr == cs else "808080"  # green if all files uploaded on server
        return format_html('<b><a style="color: #{};">{}</a></b>', col, "{:2.0f}".format(cr))

    dataset_count.short_description = "attached files"
    dataset_count.admin_order_field = "_dataset_count"

    def weighing(self, obj):
        wei = Weighing.objects.filter(date_time=obj.start_time)
        if not wei:
            return ""
        url = reverse(
            "admin:%s_%s_change" % (wei[0]._meta.app_label, wei[0]._meta.model_name),
            args=[wei[0].id],
        )
        return format_html('<b><a href="{url}" ">{} g </a></b>', wei[0].weight, url=url)

    weighing.short_description = "weight before session"


class ProbeInsertionInline(TabularInline):
    fk_name = "session"
    show_change_link = True
    model = ProbeInsertion
    fields = ("name", "model")
    extra = 0


class EphysSessionAdmin(SessionAdmin):
    inlines = [
        ProbeInsertionInline,
        WaterAdminInline,
        DatasetInline,
        NoteInline,
    ]

    def get_queryset(self, request):
        qs = super(EphysSessionAdmin, self).get_queryset(request)
        return qs.filter(procedures__name__icontains="ephys").distinct()


class NotificationUserFilter(DefaultListFilter):
    title = "notification users"
    parameter_name = "users"

    def lookups(self, request, model_admin):
        return (
            (None, "Me"),
            ("all", "All"),
        )

    def queryset(self, request, queryset):
        if self.value() is None:
            return queryset.filter(users__in=[request.user])
        elif self.value == "all":
            return queryset.all()


class NotificationAdmin(BaseAdmin):
    list_display = (
        "title",
        "subject",
        "users_l",
        "send_at",
        "sent_at",
        "status",
        "notification_type",
    )
    search_fields = ("notification_type", "subject__nickname", "title")
    list_filter = (NotificationUserFilter, "notification_type")
    fields = (
        "title",
        "notification_type",
        "subject",
        "message",
        "users",
        "status",
        "send_at",
        "sent_at",
    )
    ordering = ("-send_at",)

    def users_l(self, obj):
        return sorted(map(str, obj.users.all()))


class NotificationRuleAdmin(BaseAdmin):
    list_display = ("notification_type", "user", "subjects_scope")
    search_fields = ("notification_type", "user__username", "subject_scope")
    fields = ("notification_type", "user", "subjects_scope")

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "user":
            kwargs["initial"] = request.user.id
        return super(NotificationRuleAdmin, self).formfield_for_foreignkey(db_field, request, **kwargs)


class CullAdmin(BaseAdmin):
    list_display = (
        "date",
        "subject_l",
        "user",
        "cull_reason",
        "cull_method",
        "projects",
    )
    search_fields = ("user__username", "subject__nickname", "subject__projects__name")
    fields = ("date", "subject", "user", "cull_reason", "cull_method", "description")
    ordering = ("-date",)

    def subject_l(self, obj):
        url = get_admin_url(obj.subject)
        return format_html('<a href="{url}">{subject}</a>', subject=obj.subject or "-", url=url)

    subject_l.short_description = "subject"

    def projects(self, obj):
        return ", ".join(p.name for p in obj.subject.projects.all())


site.register(ProcedureType, ProcedureTypeAdmin)
site.register(Weighing, WeighingAdmin)
site.register(WaterAdministration, WaterAdministrationAdmin)
site.register(WaterRestriction, WaterRestrictionAdmin)

site.register(Session, SessionAdmin)
site.register(EphysSession, EphysSessionAdmin)
site.register(OtherAction, BaseActionAdmin)
site.register(VirusInjection, BaseActionAdmin)

site.register(Surgery, SurgeryAdmin)
site.register(WaterType, WaterTypeAdmin)

site.register(Notification, NotificationAdmin)
site.register(NotificationRule, NotificationRuleAdmin)

site.register(Cull, CullAdmin)
site.register(CullReason, BaseAdmin)
site.register(CullMethod, BaseAdmin)
