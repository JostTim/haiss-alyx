# Generated by Django 4.1.3 on 2023-06-13 18:23

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('data', '0014_data_model_change'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='datasettype',
            constraint=models.UniqueConstraint(fields=('object', 'attribute'), name='unique_dataset_type'),
        ),
    ]