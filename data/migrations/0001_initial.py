# -*- coding: utf-8 -*-
# Generated by Django 1.9.1 on 2016-04-25 17:47
from __future__ import unicode_literals

import django.contrib.postgres.fields.jsonb
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='BaseFileCollection',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('md5', models.CharField(blank=True, max_length=255, null=True)),
                ('filename', models.CharField(max_length=1000)),
            ],
        ),
        migrations.CreateModel(
            name='DataRepository',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
            ],
        ),
        migrations.CreateModel(
            name='FileRecord',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('tape_sequential_number', models.IntegerField(blank=True, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='PhysicalArchive',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('location', models.CharField(max_length=255)),
            ],
        ),
        migrations.CreateModel(
            name='ArchiveDataRepository',
            fields=[
                ('datarepository_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='data.DataRepository')),
                ('identifier', models.CharField(blank=True, max_length=255, null=True)),
                ('tape_contents', django.contrib.postgres.fields.jsonb.JSONField(blank=True, null=True)),
                ('physical_archive', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='data.PhysicalArchive')),
            ],
            bases=('data.datarepository',),
        ),
        migrations.CreateModel(
            name='BrainImage',
            fields=[
                ('basefilecollection_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='data.BaseFileCollection')),
            ],
            bases=('data.basefilecollection',),
        ),
        migrations.CreateModel(
            name='File',
            fields=[
                ('basefilecollection_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='data.BaseFileCollection')),
            ],
            bases=('data.basefilecollection',),
        ),
        migrations.CreateModel(
            name='LocalDataRepository',
            fields=[
                ('datarepository_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='data.DataRepository')),
                ('hostname', models.CharField(blank=True, max_length=1000, null=True)),
                ('path', models.CharField(blank=True, max_length=1000, null=True)),
            ],
            bases=('data.datarepository',),
        ),
        migrations.CreateModel(
            name='Movie',
            fields=[
                ('basefilecollection_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='data.BaseFileCollection')),
            ],
            bases=('data.basefilecollection',),
        ),
        migrations.CreateModel(
            name='NetworkDataRepository',
            fields=[
                ('datarepository_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='data.DataRepository')),
                ('fqdn', models.CharField(blank=True, max_length=1000, null=True)),
                ('share', models.CharField(blank=True, max_length=1000, null=True)),
                ('path', models.CharField(blank=True, max_length=1000, null=True)),
                ('nfs_supported', models.BooleanField()),
                ('smb_supported', models.BooleanField()),
                ('afp_supported', models.BooleanField()),
            ],
            bases=('data.datarepository',),
        ),
        migrations.CreateModel(
            name='TimeSeries',
            fields=[
                ('basefilecollection_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='data.BaseFileCollection')),
            ],
            bases=('data.basefilecollection',),
        ),
        migrations.AddField(
            model_name='filerecord',
            name='collection',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='data.BaseFileCollection'),
        ),
        migrations.AddField(
            model_name='filerecord',
            name='data_repository',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='data.DataRepository'),
        ),
    ]