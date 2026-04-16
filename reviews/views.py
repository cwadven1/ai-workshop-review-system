from django.http import JsonResponse
from django.shortcuts import get_object_or_404

from stores.models import ShopWeekReview, Store


def trends_data(request, store_id):
    store = get_object_or_404(Store, pk=store_id)
    summaries = (
        ShopWeekReview.objects.filter(shop=store)
        .order_by("year", "week_number")
    )

    data = {
        "labels": [],
        "ratings": [],
        "review_counts": [],
        "positive_pcts": [],
        "negative_pcts": [],
    }

    for s in summaries:
        data["labels"].append(s.week_number)
        data["ratings"].append(round(s.average, 1))
        data["review_counts"].append(s.count)
        total = (s.positive_count + s.neutral_count + s.negative_count) or 1
        data["positive_pcts"].append(round(s.positive_count / total * 100, 1))
        data["negative_pcts"].append(round(s.negative_count / total * 100, 1))

    return JsonResponse(data)
