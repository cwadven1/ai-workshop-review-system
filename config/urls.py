from django.contrib import admin
from django.urls import path

from reviews import views as review_views
from stores import views as store_views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", store_views.index, name="index"),
    path("stores/recent/", store_views.recent_stores, name="recent-stores"),
    path(
        "stores/<int:store_id>/reviews/",
        store_views.store_reviews,
        name="store-reviews",
    ),
    path(
        "stores/<int:store_id>/timeline/",
        store_views.store_timeline,
        name="store-timeline",
    ),
    path(
        "stores/<int:store_id>/trends/data/",
        review_views.trends_data,
        name="trends-data",
    ),
]
