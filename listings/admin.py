from django.contrib import admin

from .models import Listing, ListingPhoto


class PhotoInline(admin.TabularInline):
    model = ListingPhoto
    extra = 0


@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    list_display = ("__str__", "purpose", "property_type", "city", "area", "price", "status", "on_website", "approved_at", "created_by")
    list_filter = ("status", "purpose", "property_type", "on_website", "city")
    search_fields = ("title", "location_text", "area__name", "owner_name", "owner_phone")
    raw_id_fields = ("lead",)
    readonly_fields = ("approved_at", "approved_by")
    inlines = [PhotoInline]
