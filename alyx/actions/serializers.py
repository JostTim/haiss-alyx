from rest_framework import serializers
from django.contrib.admin.models import LogEntry, ADDITION
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
import structlog

from alyx.base import BaseSerializerEnumField, get_admin_url
from .models import ProcedureType, Session, Surgery, WaterAdministration, Weighing, WaterType, WaterRestriction
from subjects.models import Subject, Project
from data.models import Dataset, DatasetType
from misc.models import LabLocation, Lab
from experiments.serializers import ProbeInsertionListSerializer, FilterDatasetSerializer
from misc.serializers import NoteSerializer
from data.serializers import DatasetSerializer
from data.models import DataRepository

from time import time

SESSION_FIELDS = (
    "id",
    "subject",
    "users",
    "location",
    "procedures",
    "lab",
    "projects",
    "type",
    "task_protocol",
    "number",
    "start_time",
    "end_time",
    "narrative",
    "parent_session",
    "n_correct_trials",
    "n_trials",
    "url",
    "extended_qc",
    "qc",
    "wateradmin_session_related",
    "data_dataset_session_related",
    "auto_datetime",
    "alias",
    "u_alias",
    "path",
)

logger = structlog.get_logger("actions.serializers")


def _log_entry(instance, user):
    if instance.pk:
        LogEntry.objects.log_action(
            user_id=user.pk,
            content_type_id=ContentType.objects.get_for_model(instance).pk,
            object_id=instance.pk,
            object_repr=str(instance),
            action_flag=ADDITION,
            change_message=[{"added": {}}],
        )
    return instance


class BaseActionSerializer(serializers.HyperlinkedModelSerializer):
    subject = serializers.SlugRelatedField(read_only=False, slug_field="nickname", queryset=Subject.objects.all())

    users = serializers.SlugRelatedField(
        read_only=False,
        many=True,
        slug_field="username",
        queryset=get_user_model().objects.all(),
        required=False,
        default=serializers.CurrentUserDefault(),
    )

    location = serializers.SlugRelatedField(
        read_only=False,
        slug_field="name",
        queryset=LabLocation.objects.all(),
        allow_null=True,
        required=False,
    )

    procedures = serializers.SlugRelatedField(
        read_only=False,
        many=True,
        slug_field="name",
        queryset=ProcedureType.objects.all(),
        allow_null=True,
        required=False,
    )

    lab = serializers.SlugRelatedField(
        read_only=False,
        slug_field="name",
        queryset=Lab.objects.all(),
        many=False,
        required=False,
    )


class LabLocationSerializer(serializers.ModelSerializer):
    lab = serializers.SlugRelatedField(
        read_only=False,
        slug_field="name",
        queryset=Lab.objects.all(),
        many=False,
        required=False,
    )

    class Meta:
        model = LabLocation
        fields = ("name", "lab", "json")


class SessionDatasetsSerializer(serializers.ModelSerializer):
    object = serializers.StringRelatedField(source="dataset_type.object")
    attribute = serializers.StringRelatedField(source="dataset_type.attribute")
    default_revision = serializers.CharField(source="default_dataset")

    class Meta:
        list_serializer_class = FilterDatasetSerializer
        model = Dataset
        fields = (
            "id",
            "name",
            "object",
            "attribute",
            "collection",
            "url",
            "file_size",
            "hash",
            "version",
            "revision",
            "default_revision",
        )


class SessionWaterAdminSerializer(serializers.ModelSerializer):
    water_type = serializers.SlugRelatedField(
        read_only=False,
        required=False,
        slug_field="name",
        queryset=WaterType.objects.all(),
    )

    class Meta:
        model = WaterAdministration
        fields = ("id", "name", "water_type", "water_administered")


class SessionListSerializer(BaseActionSerializer):
    projects = serializers.SlugRelatedField(
        read_only=False, slug_field="name", queryset=Project.objects.all(), many=True
    )

    default_data_repository = serializers.SlugRelatedField(
        read_only=False, slug_field="data_path", queryset=DataRepository.objects.all(), many=False
    )

    admin_url = serializers.SerializerMethodField()

    def get_admin_url(self, obj):
        return get_admin_url(obj)

    @staticmethod
    def setup_eager_loading(queryset):
        """Perform necessary eager loading of data to avoid horrible performance."""
        queryset = queryset.select_related("subject", "lab")
        queryset = queryset.prefetch_related("projects")
        return queryset.order_by("-start_time")

    class Meta:
        model = Session
        fields = (
            "id",
            "subject",
            "start_time",
            "number",
            "projects",
            "users",
            "url",
            "admin_url",
            "procedures",
            "default_data_repository",
        )


class SessionDetailSerializer(BaseActionSerializer):
    # data_dataset_session_related = SessionDatasetsSerializer(read_only=True, many=True)
    data_dataset_session_related = DatasetSerializer(read_only=True, many=True)
    wateradmin_session_related = SessionWaterAdminSerializer(read_only=True, many=True)
    probe_insertion = ProbeInsertionListSerializer(read_only=True, many=True)
    projects = serializers.SlugRelatedField(
        read_only=False, slug_field="name", many=True, queryset=Project.objects.all(), required=False
    )
    notes = NoteSerializer(read_only=True, many=True)
    qc = BaseSerializerEnumField(required=False)

    default_data_repository_pk = serializers.PrimaryKeyRelatedField(
        read_only=False, required=False, queryset=DataRepository.objects.all(), source="default_data_repository"
    )

    default_data_repository_path = serializers.SlugRelatedField(
        read_only=True, slug_field="data_path", source="default_data_repository"
    )

    default_data_repository_name = serializers.SlugRelatedField(
        read_only=False,
        slug_field="name",
        source="default_data_repository",
        queryset=DataRepository.objects.all(),
        required=False,
    )

    rel_path = serializers.CharField(
        source="alias", read_only=True
    )  # rel_path is the same as alias. Just for retro-compatibility sake and understandability of code
    # (weird to use an "alias" arg in pathes construction)

    admin_url = serializers.SerializerMethodField()

    def get_admin_url(self, obj):
        return get_admin_url(obj)

    @staticmethod
    def setup_eager_loading(queryset):
        queryset = queryset.prefetch_related(
            "data_dataset_session_related",
            "data_dataset_session_related__dataset_type",
            "data_dataset_session_related__file_records",
            "wateradmin_session_related",
            "probe_insertion",
        )
        return queryset.order_by("-start_time")

    def to_representation(self, instance):
        start_time = time()
        representation = super().to_representation(instance)
        end_time = time()
        logger.warning(f"Serializing {instance} took {end_time - start_time:.6f} seconds")
        return representation

    class Meta:
        model = Session
        fields = SESSION_FIELDS + (
            "id",
            "json",
            "probe_insertion",
            "notes",
            "default_data_repository_path",
            "default_data_repository_name",
            "default_data_repository_pk",
            "rel_path",
            "admin_url",
        )


class WeighingDetailSerializer(serializers.HyperlinkedModelSerializer):
    subject = serializers.SlugRelatedField(read_only=False, slug_field="nickname", queryset=Subject.objects.all())

    user = serializers.SlugRelatedField(
        read_only=False,
        slug_field="username",
        queryset=get_user_model().objects.all(),
        required=False,
        default=serializers.CurrentUserDefault(),
    )

    def create(self, validated_data):
        user = self.context["request"].user
        instance = Weighing.objects.create(**validated_data)
        _log_entry(instance, user)
        return instance

    @staticmethod
    def setup_eager_loading(queryset):
        return queryset.select_related("subject", "user")

    class Meta:
        model = Weighing
        fields = ("subject", "date_time", "weight", "user", "url")


class ProcedureTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProcedureType
        fields = "__all__"


class WaterTypeDetailSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = WaterType
        fields = "__all__"
        extra_kwargs = {"url": {"view_name": "watertype-detail", "lookup_field": "name"}}


class WaterRestrictionListSerializer(serializers.HyperlinkedModelSerializer):
    subject = serializers.SlugRelatedField(read_only=True, slug_field="nickname")
    water_type = serializers.SlugRelatedField(read_only=True, slug_field="name")

    class Meta:
        model = WaterRestriction
        fields = ("subject", "start_time", "end_time", "water_type", "reference_weight")
        extra_kwargs = {"url": {"view_name": "water-restriction-list"}}


class WaterAdministrationDetailSerializer(serializers.HyperlinkedModelSerializer):
    subject = serializers.SlugRelatedField(read_only=False, slug_field="nickname", queryset=Subject.objects.all())

    user = serializers.SlugRelatedField(
        read_only=False,
        slug_field="username",
        queryset=get_user_model().objects.all(),
        required=False,
        default=serializers.CurrentUserDefault(),
    )

    water_type = serializers.SlugRelatedField(
        read_only=False,
        slug_field="name",
        queryset=WaterType.objects.all(),
        required=False,
    )

    session = serializers.SlugRelatedField(
        read_only=False,
        required=False,
        slug_field="id",
        queryset=Session.objects.all(),
    )

    @staticmethod
    def setup_eager_loading(queryset):
        return queryset.select_related("subject", "user", "session")

    def create(self, validated_data):
        user = self.context["request"].user
        instance = WaterAdministration.objects.create(**validated_data)
        _log_entry(instance, user)
        return instance

    class Meta:
        model = WaterAdministration
        fields = ("subject", "date_time", "water_administered", "water_type", "user", "url", "session", "adlib")
        extra_kwargs = {"url": {"view_name": "water-administration-detail"}}


class SurgerySerializer(serializers.ModelSerializer):
    subject = serializers.SlugRelatedField(read_only=False, slug_field="nickname", queryset=Subject.objects.all())

    class Meta:
        model = Surgery
        fields = "__all__"
