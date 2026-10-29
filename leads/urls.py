from django.urls import path

from . import api, views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("leads/", views.lead_list, name="lead_list"),
    path("leads/new/", views.lead_create, name="lead_create"),
    path("leads/export.csv", views.lead_export, name="lead_export"),
    path("leads/bulk-assign/", views.lead_bulk_assign, name="lead_bulk_assign"),
    path("leads/<int:pk>/", views.lead_detail, name="lead_detail"),
    path("leads/<int:pk>/edit/", views.lead_edit, name="lead_edit"),
    path("leads/<int:pk>/activity/", views.lead_log_activity, name="lead_log_activity"),
    path("leads/<int:pk>/pipeline/", views.lead_pipeline, name="lead_pipeline"),
    path("leads/<int:pk>/claim/", views.lead_claim, name="lead_claim"),
    path("leads/<int:pk>/follow-up/", views.lead_add_follow_up, name="lead_add_follow_up"),
    path("follow-ups/", views.follow_up_list, name="follow_up_list"),
    path("follow-ups/<int:pk>/done/", views.follow_up_complete, name="follow_up_complete"),
    path("api/leads/ingest/", api.ingest, name="api_ingest"),
]
