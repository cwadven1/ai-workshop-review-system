from collections import Counter

from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render

from reviews.models import MonthlySummary, Review

from .models import Menu, Store


def _compute_trend(recent_summaries, overall_avg):
    if len(recent_summaries) < 2:
        return 'neutral'
    recent_3 = recent_summaries[:3]
    recent_avg = sum(float(s.avg_rating) for s in recent_3) / len(recent_3)
    if recent_avg - overall_avg >= 0.3:
        return 'up'
    elif overall_avg - recent_avg >= 0.3:
        return 'down'
    return 'neutral'


def index(request):
    q = request.GET.get('q', '').strip()
    category = request.GET.get('category', '').strip()
    trend_filter = request.GET.get('trend', '').strip()

    stores = Store.objects.all()
    if q:
        stores = stores.filter(name__icontains=q)
    if category:
        stores = stores.filter(category=category)
    stores = stores.order_by('-avg_rating')

    category_choices = dict(Store.CATEGORY_CHOICES)
    raw_categories = Store.objects.values_list('category', flat=True).distinct().order_by('category')
    categories = [{'value': c, 'label': category_choices.get(c, c)} for c in raw_categories]

    store_list_raw = []
    sparkline_data = {}
    for store in stores:
        recent_summaries = list(
            MonthlySummary.objects.filter(store=store).order_by('-year_month')[:6]
        )
        trend = _compute_trend(recent_summaries, float(store.avg_rating))
        mini_data = list(reversed(recent_summaries))

        store_list_raw.append({
            'store': store,
            'trend': trend,
            'mini_data': mini_data,
        })
        sparkline_data[str(store.pk)] = {
            'labels': [s.year_month for s in mini_data],
            'data': [float(s.avg_rating) for s in mini_data],
            'trend': trend,
        }

    if trend_filter == 'up':
        store_list = [item for item in store_list_raw if item['trend'] == 'up']
    elif trend_filter == 'high':
        store_list = [item for item in store_list_raw if float(item['store'].avg_rating) >= 4.0]
    else:
        store_list = store_list_raw

    is_home = not q and not category and not trend_filter
    trending_stores = []
    if is_home:
        trending_stores = sorted(
            [item for item in store_list_raw if item['trend'] == 'up'],
            key=lambda x: x['store'].avg_rating,
            reverse=True,
        )[:6]

    return render(request, 'index.html', {
        'store_list': store_list,
        'q': q,
        'category': category,
        'trend_filter': trend_filter,
        'categories': categories,
        'total_count': len(store_list),
        'trending_stores': trending_stores,
        'is_home': is_home,
        'sparkline_data': sparkline_data,
    })


def recent_stores(request):
    ids_param = request.GET.get('ids', '').strip()
    if not ids_param:
        return JsonResponse({'stores': []})

    try:
        ids = [int(x) for x in ids_param.split(',') if x.strip().isdigit()][:5]
    except (ValueError, AttributeError):
        return JsonResponse({'stores': []})

    store_map = {s.pk: s for s in Store.objects.filter(pk__in=ids)}
    result = []
    for sid in ids:
        store = store_map.get(sid)
        if not store:
            continue
        recent_summaries = list(
            MonthlySummary.objects.filter(store=store).order_by('-year_month')[:3]
        )
        trend = _compute_trend(recent_summaries, float(store.avg_rating))
        result.append({
            'id': store.pk,
            'name': store.name,
            'category': store.get_category_display(),
            'avg_rating': float(store.avg_rating),
            'total_review_count': store.total_review_count,
            'trend': trend,
            'url': f'/stores/{store.pk}/reviews/',
        })

    return JsonResponse({'stores': result})


def _build_monthly_data(store):
    summaries = list(
        MonthlySummary.objects.filter(store=store).order_by("-year_month")
    )

    for summary in summaries:
        dist = summary.sentiment_distribution or {}
        dist.setdefault("positive", 0)
        dist.setdefault("neutral", 0)
        dist.setdefault("negative", 0)
        summary.sentiment_distribution = dist
        summary.sentiment_total = sum(dist.values()) or 1

    monthly_data = []
    for summary in summaries:
        reviews = (
            store.reviews.filter(year_month=summary.year_month)
            .order_by("-review_date")[:5]
        )
        monthly_data.append({
            "summary": summary,
            "reviews": reviews,
        })

    return monthly_data


def _build_recent_analysis(store, monthly_data):
    """최근 3개월 데이터를 기반으로 분석 요약 생성"""
    if not monthly_data:
        return None

    recent_months = monthly_data[:3]

    total_reviews = sum(m['summary'].review_count for m in recent_months)
    if total_reviews == 0:
        return None

    weighted_rating = sum(
        float(m['summary'].avg_rating) * m['summary'].review_count
        for m in recent_months
    ) / total_reviews

    pos = sum(m['summary'].sentiment_distribution.get('positive', 0) for m in recent_months)
    neu = sum(m['summary'].sentiment_distribution.get('neutral', 0) for m in recent_months)
    neg = sum(m['summary'].sentiment_distribution.get('negative', 0) for m in recent_months)
    total_sent = pos + neu + neg or 1

    kw_counter = Counter()
    for m in recent_months:
        for kw in (m['summary'].top_keywords or []):
            kw_counter[kw['keyword']] += kw.get('count', 1)
    top_keywords = [{'keyword': k, 'count': c} for k, c in kw_counter.most_common(8)]

    trend = 'neutral'
    if len(recent_months) >= 2:
        r1 = float(recent_months[0]['summary'].avg_rating)
        r2 = float(recent_months[1]['summary'].avg_rating)
        if r1 - r2 >= 0.2:
            trend = 'up'
        elif r2 - r1 >= 0.2:
            trend = 'down'

    latest_summary_text = recent_months[0]['summary'].summary if recent_months else ''
    latest_month = recent_months[0]['summary'].year_month if recent_months else ''

    return {
        'avg_rating': round(weighted_rating, 1),
        'total_reviews': total_reviews,
        'period': f"{recent_months[-1]['summary'].year_month} ~ {recent_months[0]['summary'].year_month}",
        'pos_pct': round(pos / total_sent * 100),
        'neg_pct': round(neg / total_sent * 100),
        'neu_pct': round(neu / total_sent * 100),
        'top_keywords': top_keywords,
        'trend': trend,
        'latest_summary': latest_summary_text,
        'latest_month': latest_month,
    }


def store_reviews(request, store_id):
    store = get_object_or_404(Store, pk=store_id)
    menus = Menu.objects.filter(store=store)

    return render(request, "stores/reviews.html", {
        "store": store,
        "menus": menus,
    })


def store_timeline(request, store_id):
    store = get_object_or_404(Store, pk=store_id)
    q = request.GET.get('q', '').strip()

    if q:
        reviews_qs = Review.objects.filter(
            store=store,
            content__icontains=q,
        ).order_by('-year_month', '-review_date')

        grouped_dict = {}
        for r in reviews_qs:
            grouped_dict.setdefault(r.year_month, []).append(r)
        search_grouped = [
            {'year_month': ym, 'reviews': revs}
            for ym, revs in grouped_dict.items()
        ]
        search_total = sum(len(g['reviews']) for g in search_grouped)

        monthly_data_for_analysis = _build_monthly_data(store)
        recent_analysis = _build_recent_analysis(store, monthly_data_for_analysis)

        context = {
            'store': store,
            'q': q,
            'search_grouped': search_grouped,
            'search_total': search_total,
            'monthly_data': [],
            'recent_analysis': recent_analysis,
        }
    else:
        monthly_data = _build_monthly_data(store)
        recent_analysis = _build_recent_analysis(store, monthly_data)
        context = {
            'store': store,
            'q': '',
            'search_grouped': None,
            'search_total': 0,
            'monthly_data': monthly_data,
            'recent_analysis': recent_analysis,
        }

    return render(request, 'stores/timeline.html', context)
