# -*- coding: utf-8 -*-
# Generated by Django 1.9.1 on 2016-05-06 16:30
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('behavior', '0001_initial'),
    ]

    operations = [
        migrations.RenameField(
            model_name='pupiltracking',
            old_name='injection_type',
            new_name='eye',
        ),
    ]
