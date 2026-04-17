from django.contrib import admin
from django.urls import path

from reviews import views as review_views
from stores import views as store_views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", store_views.index, name="index"),
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
    path(
        "stores/<int:store_id>/owner/",
        store_views.owner_dashboard,
        name="owner-dashboard",
    ),
    path(
        "stores/<int:store_id>/owner/trigger-analysis/",
        store_views.trigger_analysis,
        name="trigger-analysis",
    ),
    path(
        "stores/<int:store_id>/owner/analysis-status/",
        store_views.analysis_status,
        name="analysis-status",
    ),
    path(
        "action-items/<int:item_id>/update/",
        store_views.update_action_item,
        name="update-action-item",
    ),
    path(
        "stores/<int:store_id>/owner/week/<int:year>/<int:week>/reviews/",
        store_views.owner_week_reviews,
        name="owner-week-reviews",
    ),
]
