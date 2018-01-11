# -*- coding: utf-8 -*-
# Generated by Django 1.11 on 2017-06-19 08:09
from __future__ import unicode_literals

from django.conf import settings
import django.contrib.postgres.fields.jsonb
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('misc', '0001_initial'),
        ('actions', '0001_initial'),
        ('data', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('equipment', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ROI',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('json', django.contrib.postgres.fields.jsonb.JSONField(blank=True, help_text='Structured data, formatted in a user-defined way', null=True)),
                ('created_date', models.DateTimeField(blank=True, default=django.utils.timezone.now, help_text='The creation date.', null=True)),
                ('roi_type', models.CharField(blank=True, help_text='soma, dendrite, neuropil, …> TODO: normalize?', max_length=255)),
                ('optogenetic_response', models.CharField(blank=True, help_text="e.g. 'Short latency' (only if applicable)", max_length=255)),
                ('putative_cell_type', models.CharField(blank=True, help_text="e.g. 'Sst interneuron', 'PT cell'", max_length=255)),
                ('estimated_layer', models.CharField(blank=True, help_text="e.g. 'Layer 5b'", max_length=255)),
                ('created_by', models.ForeignKey(blank=True, help_text='The creator of the data.', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='imaging_roi_created_by_related', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='ROIDetection',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('json', django.contrib.postgres.fields.jsonb.JSONField(blank=True, help_text='Structured data, formatted in a user-defined way', null=True)),
                ('created_date', models.DateTimeField(blank=True, default=django.utils.timezone.now, help_text='The creation date.', null=True)),
                ('preprocessing', models.CharField(blank=True, help_text="computed (F-F0) / F0, estimating F0 as running min'", max_length=255)),
                ('created_by', models.ForeignKey(blank=True, help_text='The creator of the data.', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='imaging_roidetection_created_by_related', to=settings.AUTH_USER_MODEL)),
                ('f', models.ForeignKey(blank=True, help_text='array of size nT by nROIs giving raw fluorescence', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='roi_detection_f', to='data.TimeSeries')),
                ('f0', models.ForeignKey(blank=True, help_text='array of size nT by nROIs giving resting fluorescence', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='roi_detection_f0', to='data.TimeSeries')),
                ('masks', models.ForeignKey(blank=True, help_text='array of size nROIs by nY by nX', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='roi_detection_masks', to='data.Dataset')),
                ('plane', models.ForeignKey(blank=True, help_text='array saying which plane each roi is found in. TODO: is this an ArrayField? JSON?', null=True, on_delete=django.db.models.deletion.CASCADE, to='data.Dataset')),
                ('session', models.ForeignKey(blank=True, help_text='The Session to which this data belongs', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='imaging_roidetection_session_related', to='actions.Session')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='SVDCompressedMovie',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('json', django.contrib.postgres.fields.jsonb.JSONField(blank=True, help_text='Structured data, formatted in a user-defined way', null=True)),
                ('created_date', models.DateTimeField(blank=True, default=django.utils.timezone.now, help_text='The creation date.', null=True)),
                ('compressed_data_U', models.ForeignKey(blank=True, help_text='nSVs*nY*nX binary array giving normalized eigenframesSVD-compression eigenframes', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='svd_movie_u', to='data.Dataset')),
                ('compressed_data_V', models.ForeignKey(blank=True, help_text='nSamples*nSVs binary array SVD-compression timecourses', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='svd_movie_v', to='data.TimeSeries')),
                ('created_by', models.ForeignKey(blank=True, help_text='The creator of the data.', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='imaging_svdcompressedmovie_created_by_related', to=settings.AUTH_USER_MODEL)),
                ('session', models.ForeignKey(blank=True, help_text='The Session to which this data belongs', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='imaging_svdcompressedmovie_session_related', to='actions.Session')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='TwoPhotonImaging',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('json', django.contrib.postgres.fields.jsonb.JSONField(blank=True, help_text='Structured data, formatted in a user-defined way', null=True)),
                ('created_date', models.DateTimeField(blank=True, default=django.utils.timezone.now, help_text='The creation date.', null=True)),
                ('description', models.CharField(blank=True, help_text="e.g. 'V1 layers 2-4'", max_length=255)),
                ('excitation_wavelength', models.FloatField(blank=True, help_text='in nm', null=True)),
                ('recording_wavelength', models.FloatField(blank=True, help_text='in nm. Can be array for multispectral imaging. TODO: deal with arrays?', null=True)),
                ('compressed_data', models.ForeignKey(blank=True, help_text='to Compressed_movie, if compression was run', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='two_photon_compressed', to='imaging.SVDCompressedMovie')),
                ('created_by', models.ForeignKey(blank=True, help_text='The creator of the data.', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='imaging_twophotonimaging_created_by_related', to=settings.AUTH_USER_MODEL)),
                ('image_position', models.ForeignKey(blank=True, help_text='Note if different planes have different alignment (e.g. flyback plane), this can’t be done in a single 3x3 transformation matrix, instead you would have an array of 3x2 matrices. TODO: how do we deal with this?', null=True, on_delete=django.db.models.deletion.CASCADE, to='misc.CoordinateTransformation')),
                ('raw_data', models.ForeignKey(blank=True, help_text='array of size nT by nX by nY by nZ by nC', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='two_photon_raw', to='data.TimeSeries')),
                ('reference_stack', models.ForeignKey(blank=True, help_text='TODO: reference stack / BrainImage', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='two_photon_reference', to='data.Dataset')),
                ('session', models.ForeignKey(blank=True, help_text='The Session to which this data belongs', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='imaging_twophotonimaging_session_related', to='actions.Session')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='WidefieldImaging',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('json', django.contrib.postgres.fields.jsonb.JSONField(blank=True, help_text='Structured data, formatted in a user-defined way', null=True)),
                ('created_date', models.DateTimeField(blank=True, default=django.utils.timezone.now, help_text='The creation date.', null=True)),
                ('nominal_start_time', models.DateTimeField(blank=True, help_text='in seconds relative to session start. TODO: not DateTimeField? / TimeDifference', null=True)),
                ('nominal_end_time', models.DateTimeField(blank=True, help_text='Equals start time if single application. TODO: should this be an offset? Or DateTimeField? Or TimeDifference?', null=True)),
                ('imaging_indicator', models.CharField(blank=True, help_text='<GCaMP6f, GCaMP6m, GCaMP6s, VSFPb1.2, intrinsic, …>. TODO: normalize!', max_length=255)),
                ('preprocessing', models.CharField(blank=True, help_text="e.g. 'computed (F-F0) / F0, estimating F0 as running min'", max_length=255)),
                ('description', models.CharField(blank=True, help_text="e.g. 'field of view includes V1, S1, retrosplenial'", max_length=255)),
                ('excitation_nominal_wavelength', models.FloatField(blank=True, help_text='in nm. Can be array for multispectral', null=True)),
                ('recording_nominal_wavelength', models.FloatField(blank=True, help_text='in nm. Can be array for multispectral', null=True)),
                ('recording_device', models.CharField(blank=True, help_text='e.g. camera manufacturer, plus filter description etc. TODO: Appliance subclass - what name?', max_length=255)),
                ('compressed_data', models.ForeignKey(blank=True, help_text='Link to SVD compressed movie, if compression was run', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='widefield_compressed', to='imaging.SVDCompressedMovie')),
                ('created_by', models.ForeignKey(blank=True, help_text='The creator of the data.', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='imaging_widefieldimaging_created_by_related', to=settings.AUTH_USER_MODEL)),
                ('excitation_device', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='equipment.LightSource')),
                ('image_position', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='misc.CoordinateTransformation')),
                ('raw_data', models.ForeignKey(blank=True, help_text='pointer to nT by nX by nY by nC (colors) binary file', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='widefield_raw', to='data.TimeSeries')),
                ('session', models.ForeignKey(blank=True, help_text='The Session to which this data belongs', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='imaging_widefieldimaging_session_related', to='actions.Session')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.AddField(
            model_name='roidetection',
            name='two_photon_imaging_id',
            field=models.ForeignKey(blank=True, help_text='2P imaging stack.', null=True, on_delete=django.db.models.deletion.CASCADE, to='imaging.TwoPhotonImaging'),
        ),
        migrations.AddField(
            model_name='roi',
            name='roi_detection_id',
            field=models.ForeignKey(blank=True, help_text='link to detection entry', null=True, on_delete=django.db.models.deletion.CASCADE, to='imaging.ROIDetection'),
        ),
        migrations.AddField(
            model_name='roi',
            name='session',
            field=models.ForeignKey(blank=True, help_text='The Session to which this data belongs', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='imaging_roi_session_related', to='actions.Session'),
        ),
    ]