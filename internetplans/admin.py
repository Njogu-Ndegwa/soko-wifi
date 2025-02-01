from django.contrib import admin
from .models import InternetPlan

@admin.register(InternetPlan)
class InternetPlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'duration_hours', 'price', 'is_active')  # Columns to display in the list view
    list_filter = ('is_active', 'duration_hours')  # Filters in the admin sidebar
    search_fields = ('name',)  # Search bar for filtering by name
    ordering = ('-is_active', 'name')  # Default ordering (active plans first, then by name)
    list_editable = ('is_active',)  # Allows toggling `is_active` status directly from the list view
