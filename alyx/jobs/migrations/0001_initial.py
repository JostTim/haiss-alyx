# Generated by Django 2.2.6 on 2020-06-23 17:06

from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('actions', '0011_auto_20200317_1055'),
    ]

    operations = [
        migrations.CreateModel(
            name='Task',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(blank=True, max_length=64, null=True)),
                ('priority', models.SmallIntegerField(blank=True, null=True)),
                ('io_charge', models.SmallIntegerField(blank=True, null=True)),
                ('level', models.SmallIntegerField(blank=True, null=True)),
                ('gpu', models.SmallIntegerField(blank=True, null=True)),
                ('cpu', models.SmallIntegerField(blank=True, null=True)),
                ('ram', models.SmallIntegerField(blank=True, null=True)),
                ('time_out_secs', models.SmallIntegerField(blank=True, null=True)),
                ('time_elapsed_secs', models.FloatField(blank=True, null=True)),
                ('executable', models.CharField(blank=True, help_text='Usually the Python class name on the workers', max_length=128, null=True)),
                ('graph', models.CharField(blank=True, help_text='The name of the graph containing a set of related and possibly dependent tasks', max_length=64, null=True)),
                ('status', models.IntegerField(choices=[(20, 'Waiting'), (30, 'Started'), (40, 'Errored'), (50, 'Empty'), (60, 'Complete')], default=10)),
                ('log', models.TextField(blank=True, null=True)),
                ('version', models.CharField(blank=True, help_text='version of the algorithm generating the file', max_length=64, null=True)),
                ('datetime', models.DateTimeField(auto_now=True)),
                ('parents', models.ManyToManyField(blank=True, related_name='children', to='jobs.Task')),
                ('session', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='jobs', to='actions.Session')),
            ],
        ),
        migrations.AddConstraint(
            model_name='task',
            constraint=models.UniqueConstraint(fields=('name', 'session'), name='unique_task_name_per_session'),
        ),
    ]
