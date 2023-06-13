from django.db.models import Count, Value
from django.db.models.functions import Concat
from django.db.models.fields.json import JSONField
from django.contrib import admin
from django.utils.html import format_html
from django_admin_listfilter_dropdown.filters import RelatedDropdownFilter
from django.contrib.admin.filters import SimpleListFilter, FieldListFilter
from rangefilter.filter import DateRangeFilter

from .models import (DataRepositoryType, DataRepository, DataFormat, DatasetType,
                     Dataset, FileRecord, Download, Revision, Tag)
from alyx.base import BaseAdmin, BaseInlineAdmin, DefaultListFilter, get_admin_url

#https://github.com/nnseva/django-jsoneditor
from jsoneditor.forms import JSONEditor

class CreatedByListFilter(DefaultListFilter):
    title = 'created by'
    parameter_name = 'created_by'

    def lookups(self, request, model_admin):
        return (
            (None, 'Me'),
            ('all', 'All'),
        )

    def queryset(self, request, queryset):
        if self.value() is None:
            return queryset.filter(created_by=request.user)
        elif self.value == 'all':
            return queryset.all()


class DataRepositoryTypeAdmin(BaseAdmin):
    fields = ('name', 'json')
    list_display = ('name',)
    ordering = ('name',)

class DataRepositoryAdmin(BaseAdmin):
    fields = ('name', 'repository_type', 'hostname', 'globus_path', 'data_path', 'data_url')
    readonly_fields=('data_path',)
    list_display = fields
    ordering = ('name',)

class DataFormatAdmin(BaseAdmin):
    fields = ['name', 'description', 'file_extension',
              'matlab_loader_function', 'python_loader_function']
    list_display = fields[:-1]
    ordering = ('name',)

class UniqueObjectFilter(FieldListFilter):
    title = 'Object' # or use _('country') for translated title
    parameter_name = 'Object'

    def lookups(self, request, model_admin):
        objects = set([c.object for c in model_admin.model.objects.all()])
        return [(c.id, c.name) for c in objects]

    def queryset(self, request, queryset):
        return queryset.filter(object__icontains=self.value())
    
    def expected_parameters(self):
        return [self.lookup_kwarg]

class DatasetTypeAdmin(BaseAdmin):
    fields = ('composed_name','object','attribute','name', 'description', 'filename_pattern', 'created_by', 'file_location_template')
    readonly_fields=('composed_name',)
    list_display = ('composed_name', 'name', 'fcount', 'description', 'filename_pattern', 'created_by')
    ordering = ('name',)
    search_fields = ('name','object','attribute', 'description', 'filename_pattern', 'created_by__username')
    list_filter = [('created_by', RelatedDropdownFilter) , ('object', UniqueObjectFilter)]
    
    formfield_overrides = {
        JSONField: {'widget': JSONEditor},
    }

    def get_queryset(self, request):
        qs = super(DatasetTypeAdmin, self).get_queryset(request)
        qs = qs.select_related('created_by')
        #qs = qs.annotate(
        #    composed_name=Concat("object", Value("."), "attribute")
        #)
        return qs

    def save_model(self, request, obj, form, change):
        if not obj.created_by and 'created_by' not in form.changed_data:
            obj.created_by = request.user
        super(DatasetTypeAdmin, self).save_model(request, obj, form, change)

    def fcount(self, dt):
        return Dataset.objects.filter(dataset_type=dt).count()


class BaseExperimentalDataAdmin(BaseAdmin):
    def __init__(self, *args, **kwargs):
        for field in ('created_by', 'created_datetime'):
            if self.fields and field not in self.fields:
                self.fields += (field,)
        super(BaseAdmin, self).__init__(*args, **kwargs)


class FileRecordInline(BaseInlineAdmin):
    model = FileRecord
    extra = 1
    fields = ('data_repository', 'relative_path', 'exists')


class IsOnlineListFilter(SimpleListFilter):
    title = 'Is Empty'
    parameter_name = '_is_empty'

    def lookups(self, request, model_admin):
        return (
            ('Yes', 'Yes'),
            ('No', 'No'),
        )

    def queryset(self, request, queryset):
        value = self.value()
        if value == 'Yes':
            return queryset.exclude(file_records__gt=0)
        elif value == 'No':
            return queryset.filter(file_records__gt=0)
        return queryset

class DatasetAdmin(BaseExperimentalDataAdmin):
    fields = ['name', '_online', 'version', 'dataset_type', 'file_size', 'hash',
              'session_ro', 'collection', 'auto_datetime', 'revision_', 'default_dataset',
              '_protected', '_public', 'tags']
    readonly_fields = ['name_', 'session_ro', '_online', 'auto_datetime', 'revision_',
                       '_protected', '_public', 'tags']
    list_display = ['name_', '_online', 'version', 'collection', 'dataset_type_', 'file_size',
                    'session_ro', 'created_by', 'created_datetime']
    inlines = [FileRecordInline]
    list_filter = [('created_by', RelatedDropdownFilter),
                   ('created_datetime', DateRangeFilter),
                   ('dataset_type', RelatedDropdownFilter),
                   IsOnlineListFilter
                   ]
    search_fields = ('session__id', 'name', 'collection', 'dataset_type__name',
                     'dataset_type__filename_pattern', 'version')
    ordering = ('-created_datetime',)

    def get_queryset(self, request):
        queryset = super(DatasetAdmin, self).get_queryset(request)
        queryset = queryset.select_related('session', 'session__subject', 'created_by')
        return queryset

    def dataset_type_(self, obj):
        return obj.dataset_type.name

    def name_(self, obj):
        return obj.name or '<unnamed>'

    def revision_(self, obj):
        return obj.revision.name

    def session_ro(self, obj):
        url = get_admin_url(obj.session)
        return format_html('<a href="{url}">{name}</a>', url=url, name=obj.session)
    session_ro.short_description = 'session'

    def subject(self, obj):
        return obj.session.subject.nickname

    def _online(self, obj):
        return obj.is_online
    _online.short_description = 'On server'
    _online.boolean = True

    def _protected(self, obj):
        return obj.is_protected
    _protected.short_description = 'Protected'
    _protected.boolean = True

    def _public(self, obj):
        return obj.is_public
    _public.short_description = 'Public'
    _public.boolean = True


class FileRecordAdmin(BaseAdmin):
    fields = ('relative_path', 'data_repository', 'dataset', 'exists')
    list_display = ('relative_path', 'repository', 'dataset_name',
                    'user', 'datetime', 'exists')
    readonly_fields = ('dataset', 'dataset_name', 'repository', 'user', 'datetime')
    list_filter = ('exists', 'data_repository__name')
    search_fields = ('dataset__created_by__username', 'dataset__name',
                     'relative_path', 'data_repository__name')
    ordering = ('-dataset__created_datetime',)

    def get_queryset(self, request):
        qs = super(FileRecordAdmin, self).get_queryset(request)
        qs = qs.select_related('data_repository', 'dataset', 'dataset__created_by')
        return qs

    def repository(self, obj):
        return getattr(obj.data_repository, 'name', None)

    def dataset_name(self, obj):
        return getattr(obj.dataset, 'name', None)

    def user(self, obj):
        return getattr(obj.dataset, 'created_by', None)

    def datetime(self, obj):
        return getattr(obj.dataset, 'created_datetime', None)


class DownloadAdmin(BaseAdmin):
    fields = ('user', 'dataset', 'first_download', 'last_download', 'count', 'projects')
    autocomplete_fields = ('dataset',)
    readonly_fields = ('first_download', 'last_download')
    list_display = ('dataset_type', 'dataset_name', 'subject', 'created_by',
                    'user', 'first_download', 'last_download', 'count')
    list_display_links = ('first_download',)
    search_filter = ('user__username', 'dataset__name')

    def dataset_name(self, obj):
        return obj.dataset.name

    def subject(self, obj):
        return obj.dataset.session.subject.nickname

    def dataset_type(self, obj):
        return obj.dataset.dataset_type.name

    def created_by(self, obj):
        return obj.dataset.created_by.username


class RevisionAdmin(BaseAdmin):
    fields = ['name', 'description', 'created_datetime']
    readonly_fields = ['created_datetime']
    list_display = ['name', 'description']
    search_fields = ('name',)
    ordering = ('-created_datetime',)


class TagAdmin(BaseAdmin):
    fields = ['name', 'description', 'protected', 'public', 'dataset_count', 'session_count']
    list_display = ['name', 'description', 'dataset_count', 'session_count', 'protected', 'public']
    readonly_fields = ['dataset_count', 'session_count']
    search_fields = ('name',)
    ordering = ('name',)

    def dataset_count(self, tag):
        return tag.dataset_count

    def session_count(self, tag):
        return tag.session_count

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        queryset = queryset.annotate(dataset_count=Count("datasets"))
        queryset = queryset.annotate(session_count=Count("datasets__session", distinct=True))
        return queryset


admin.site.register(DataRepositoryType, DataRepositoryTypeAdmin)
admin.site.register(DataRepository, DataRepositoryAdmin)
admin.site.register(DataFormat, DataFormatAdmin)
admin.site.register(DatasetType, DatasetTypeAdmin)
admin.site.register(Dataset, DatasetAdmin)
admin.site.register(FileRecord, FileRecordAdmin)
admin.site.register(Download, DownloadAdmin)
admin.site.register(Revision, RevisionAdmin)
admin.site.register(Tag, TagAdmin)
