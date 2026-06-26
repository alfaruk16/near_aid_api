from django.contrib import admin

from .models import Category, Listing, ListingImage


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("key", "name_en", "name_bn", "icon", "is_active", "sort_order")
    list_editable = ("is_active", "sort_order")
    search_fields = ("key", "name_en", "name_bn")


class ListingImageInline(admin.TabularInline):
    model = ListingImage
    extra = 0


@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    list_display = ("title", "type", "status", "category", "author", "urgency",
                    "area_label", "is_hidden", "expires_at", "created_at")
    list_filter = ("type", "status", "category", "urgency", "is_hidden")
    search_fields = ("title", "description", "area_label", "author__phone")
    raw_id_fields = ("author", "category")
    readonly_fields = ("id", "lat_fuzzed", "lng_fuzzed", "created_at", "updated_at")
    inlines = [ListingImageInline]
