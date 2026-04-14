from django.http import JsonResponse
from django.shortcuts import get_object_or_404

from stores.models import Store

from .models import WeeklySummary


def trends_data(request, store_id):
    store = get_object_or_404(Store, pk=store_id)
    summaries = (
        WeeklySummary.objects.filter(store=store)
        .order_by("year_week")
    )

    data = {
        "labels": [],
        "ratings": [],
        "review_counts": [],
        "positive_pcts": [],
        "negative_pcts": [],
    }

    for s in summaries:
        data["labels"].append(s.year_week)
        data["ratings"].append(round(s.avg_rating, 1))
        data["review_counts"].append(s.review_count)
        dist = s.sentiment_distribution or {}
        total = sum(dist.values()) if dist else 1
        data["positive_pcts"].append(
            round(dist.get("positive", 0) / max(total, 1) * 100, 1)
        )
        data["negative_pcts"].append(
            round(dist.get("negative", 0) / max(total, 1) * 100, 1)
        )

    return JsonResponse(data)
