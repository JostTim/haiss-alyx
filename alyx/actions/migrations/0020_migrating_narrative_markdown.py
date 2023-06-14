# Generated by Django 4.1.3 on 2023-06-12 16:20

from django.db import migrations
import markdownx.models


class Migration(migrations.Migration):

    dependencies = [
        ('actions', '0019_migrating_dataset_type_model'),
    ]

    operations = [
        migrations.AlterField(
            model_name='chronicrecording',
            name='narrative',
            field=markdownx.models.MarkdownxField(help_text='All other details of the experiment you want to include, in a text format. (markdown capable)'),
        ),
        migrations.AlterField(
            model_name='otheraction',
            name='narrative',
            field=markdownx.models.MarkdownxField(help_text='All other details of the experiment you want to include, in a text format. (markdown capable)'),
        ),
        migrations.AlterField(
            model_name='session',
            name='narrative',
            field=markdownx.models.MarkdownxField(help_text='All other details of the experiment you want to include, in a text format. (markdown capable)'),
        ),
        migrations.AlterField(
            model_name='surgery',
            name='narrative',
            field=markdownx.models.MarkdownxField(help_text='All other details of the experiment you want to include, in a text format. (markdown capable)'),
        ),
        migrations.AlterField(
            model_name='virusinjection',
            name='narrative',
            field=markdownx.models.MarkdownxField(help_text='All other details of the experiment you want to include, in a text format. (markdown capable)'),
        ),
        migrations.AlterField(
            model_name='waterrestriction',
            name='narrative',
            field=markdownx.models.MarkdownxField(help_text='All other details of the experiment you want to include, in a text format. (markdown capable)'),
        ),
    ]
