from django.urls import path

from . import views

urlpatterns = [
    path("listings/", views.listing_list, name="listing_list"),
    path("listings/new/", views.listing_create, name="listing_create"),
    path("listings/<int:pk>/", views.listing_detail, name="listing_detail"),
    path("listings/<int:pk>/edit/", views.listing_edit, name="listing_edit"),
    path("listings/<int:pk>/status/", views.listing_update_status, name="listing_update_status"),
    path("listings/<int:pk>/approve/", views.listing_approve, name="listing_approve"),
    path("listings/<int:pk>/delete/", views.listing_delete, name="listing_delete"),
    path("listings/<int:pk>/photos/", views.photo_add, name="listing_photo_add"),
    path("listings/photos/<int:photo_pk>/cover/", views.photo_cover, name="listing_photo_cover"),
    path("listings/photos/<int:photo_pk>/delete/", views.photo_delete, name="listing_photo_delete"),
    path("p/<int:photo_pk>.jpg", views.photo, name="listing_photo"),
    path("feed/listings.js", views.website_feed_js, name="website_feed_js"),
    path("feed/listings.json", views.website_feed_json, name="website_feed_json"),
]
