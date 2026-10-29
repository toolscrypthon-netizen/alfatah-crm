from django.contrib import admin

from .models import Activity, Area, City, FollowUp, Lead


class AreaInline(admin.TabularInline):
    model = Area
    extra = 3


@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [AreaInline]


@admin.register(Area)
class AreaAdmin(admin.ModelAdmin):
    list_display = ("name", "city")
    list_filter = ("city",)
    search_fields = ("name",)


class ActivityInline(admin.TabularInline):
    model = Activity
    extra = 0
    readonly_fields = ("created_at",)


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ("title", "intent", "city", "area", "price", "status", "source", "assigned_to", "created_at")
    list_filter = ("status", "intent", "source", "city", "property_type", "assigned_to")
    search_fields = ("title", "description", "phone", "contact_name", "external_id")
    raw_id_fields = ("area",)
    inlines = [ActivityInline]


@admin.register(FollowUp)
class FollowUpAdmin(admin.ModelAdmin):
    list_display = ("lead", "assigned_to", "due_at", "completed_at")
    list_filter = ("assigned_to",)
