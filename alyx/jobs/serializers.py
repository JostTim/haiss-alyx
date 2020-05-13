from rest_framework import serializers
from actions.models import Session
from jobs.models import Job, Task


class JobStatusField(serializers.Field):

    def to_representation(self, int_status):
        choices = Job._meta.get_field('status').choices
        status = [ch for ch in choices if ch[0] == int_status]
        return status[0][1]

    def to_internal_value(self, str_status):
        choices = Job._meta.get_field('status').choices
        status = [ch for ch in choices if ch[1] == str_status]
        if len(status) == 0:
            raise serializers.ValidationError("Invalid status, choices are: " +
                                              ', '.join([ch[1] for ch in choices]))
        return status[0][0]


class JobSerializer(serializers.ModelSerializer):
    task = serializers.SlugRelatedField(
        read_only=False, required=False, slug_field='name', many=False,
        queryset=Task.objects.all(),
    )
    data_repository = serializers.SlugRelatedField(
        read_only=True, required=False, slug_field='name', many=False,
    )
    session = serializers.SlugRelatedField(
        read_only=False, required=False, slug_field='id', many=False,
        queryset=Session.objects.all()
    )
    status = JobStatusField(required=False)
    parents = serializers.ReadOnlyField()
    pipeline = serializers.ReadOnlyField()

    class Meta:
        model = Job
        fields = '__all__'


class TaskSerializer(serializers.ModelSerializer):

    parents = serializers.SlugRelatedField(
        read_only=False, required=False, slug_field='name', many=True,
        queryset=Task.objects.all(),
    )

    class Meta:
        model = Task
        fields = '__all__'
