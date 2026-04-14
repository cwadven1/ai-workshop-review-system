import json
from collections import Counter

from django.db.models import Prefetch
from django.shortcuts import get_object_or_404, render

from reviews.models import Review, WeeklySummary

from .models import Menu, Store


def _compute_trend(recent_summaries):
    if len(recent_summaries) < 2:
        return 'neutral'
    latest = float(recent_summaries[0].avg_rating)
    prev = float(recent_summaries[1].avg_rating)
    if round(latest - prev, 1) >= 0.1:
        return 'up'
    elif round(prev - latest, 1) >= 0.1:
        return 'down'
    return 'neutral'


def index(request):
    q = request.GET.get('q', '').strip()
    category = request.GET.get('category', '').strip()
    trend_filter = request.GET.get('trend', '').strip()

    weekly_prefetch = Prefetch(
        'weekly_summaries',
        queryset=WeeklySummary.objects.order_by('-year_week'),
        to_attr='prefetched_summaries',
    )
    stores = Store.objects.prefetch_related(weekly_prefetch)
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
        recent_summaries = store.prefetched_summaries[:8]
        trend = _compute_trend(recent_summaries)
        mini_data = list(reversed(recent_summaries))

        store_list_raw.append({
            'store': store,
            'trend': trend,
            'mini_data': mini_data,
        })
        sparkline_data[str(store.pk)] = {
            'labels': [s.year_week for s in mini_data],
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



def _build_weekly_data(store):
    summaries = list(
        WeeklySummary.objects.filter(store=store).order_by("-year_week")
    )

    for summary in summaries:
        dist = summary.sentiment_distribution or {}
        dist.setdefault("positive", 0)
        dist.setdefault("neutral", 0)
        dist.setdefault("negative", 0)
        summary.sentiment_distribution = dist
        summary.sentiment_total = sum(dist.values()) or 1

    year_weeks = [s.year_week for s in summaries]
    all_reviews = list(
        Review.objects.filter(store=store, year_week__in=year_weeks)
        .order_by("-review_date")
    )
    reviews_by_week = {}
    for review in all_reviews:
        reviews_by_week.setdefault(review.year_week, []).append(review)

    weekly_data = []
    for summary in summaries:
        weekly_data.append({
            "summary": summary,
            "reviews": reviews_by_week.get(summary.year_week, [])[:5],
        })

    return weekly_data


def _build_recent_analysis(store, weekly_data):
    """최근 4주 데이터를 기반으로 분석 요약 생성"""
    if not weekly_data:
        return None

    recent_weeks = weekly_data[:4]

    total_reviews = sum(m['summary'].review_count for m in recent_weeks)
    if total_reviews == 0:
        return None

    weighted_rating = sum(
        float(m['summary'].avg_rating) * m['summary'].review_count
        for m in recent_weeks
    ) / total_reviews

    pos = sum(m['summary'].sentiment_distribution.get('positive', 0) for m in recent_weeks)
    neu = sum(m['summary'].sentiment_distribution.get('neutral', 0) for m in recent_weeks)
    neg = sum(m['summary'].sentiment_distribution.get('negative', 0) for m in recent_weeks)
    total_sent = pos + neu + neg or 1

    kw_counter = Counter()
    for m in recent_weeks:
        for kw in (m['summary'].top_keywords or []):
            kw_counter[kw['keyword']] += kw.get('count', 1)
    top_keywords = [{'keyword': k, 'count': c} for k, c in kw_counter.most_common(8)]

    trend = 'neutral'
    if len(recent_weeks) >= 2:
        r1 = float(recent_weeks[0]['summary'].avg_rating)
        r2 = float(recent_weeks[1]['summary'].avg_rating)
        if r1 - r2 >= 0.2:
            trend = 'up'
        elif r2 - r1 >= 0.2:
            trend = 'down'

    period = f"{recent_weeks[-1]['summary'].year_week} ~ {recent_weeks[0]['summary'].year_week}"

    # 기간 종합 요약 텍스트 생성
    store_name = store.name
    avg_r = round(weighted_rating, 1)
    pos_pct = round(pos / total_sent * 100)
    neg_pct = round(neg / total_sent * 100)

    oldest_rating = float(recent_weeks[-1]['summary'].avg_rating)
    latest_rating = float(recent_weeks[0]['summary'].avg_rating)
    rating_diff = latest_rating - oldest_rating

    if rating_diff >= 1.0:
        trend_text = f"기간 내 평점이 {oldest_rating}점에서 {latest_rating}점으로 큰 폭 상승하며 빠른 개선세를 보이고 있습니다"
    elif rating_diff >= 0.3:
        trend_text = f"기간 내 평점이 {oldest_rating}점에서 {latest_rating}점으로 꾸준히 상승하고 있습니다"
    elif rating_diff <= -1.0:
        trend_text = f"기간 내 평점이 {oldest_rating}점에서 {latest_rating}점으로 큰 폭 하락하며 주의가 필요합니다"
    elif rating_diff <= -0.3:
        trend_text = f"기간 내 평점이 {oldest_rating}점에서 {latest_rating}점으로 소폭 하락 추세입니다"
    else:
        trend_text = f"평점 {avg_r}점을 중심으로 안정적인 평가를 유지하고 있습니다"

    kw_text = ', '.join(k['keyword'] for k in top_keywords[:3]) if top_keywords else ''
    kw_sentence = f" 자주 언급된 키워드는 '{kw_text}'입니다." if kw_text else ''

    if neg_pct == 0:
        sent_text = f"긍정 리뷰 {pos_pct}%, 부정 리뷰 없음"
    else:
        sent_text = f"긍정 {pos_pct}%, 부정 {neg_pct}%"

    period_summary = (
        f"{store_name}의 {period} 리뷰를 종합 분석한 결과, "
        f"평균 평점 {avg_r}점({sent_text})을 기록했습니다. "
        f"{trend_text}.{kw_sentence}"
    )

    return {
        'avg_rating': round(weighted_rating, 1),
        'total_reviews': total_reviews,
        'period': period,
        'pos_pct': round(pos / total_sent * 100),
        'neg_pct': round(neg / total_sent * 100),
        'neu_pct': round(neu / total_sent * 100),
        'top_keywords': top_keywords,
        'trend': trend,
        'period_summary': period_summary,
    }


def _build_all_keywords(store):
    """전체 리뷰 keywords 배열을 집계하여 상위 키워드 반환"""
    all_reviews = Review.objects.filter(store=store).exclude(keywords__isnull=True)
    kw_counter = Counter()
    for review in all_reviews:
        for kw in (review.keywords or []):
            if kw:
                kw_counter[kw] += 1
    return [{'keyword': k, 'count': c} for k, c in kw_counter.most_common(15)]


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
        import json as _json
        from django.db.models import Q
        # SQLite JSONField stores Korean as unicode escapes (e.g. \uc2e0\uc120\ud55c)
        # so we must search using the same escaped form
        q_escaped = _json.dumps(q, ensure_ascii=True)[1:-1]
        reviews_qs = Review.objects.filter(
            Q(store=store) & (Q(content__icontains=q) | Q(keywords__icontains=q_escaped))
        ).order_by('-year_week', '-review_date')

        grouped_dict = {}
        for r in reviews_qs:
            grouped_dict.setdefault(r.year_week, []).append(r)
        search_grouped = [
            {'year_week': yw, 'reviews': revs}
            for yw, revs in grouped_dict.items()
        ]
        search_total = sum(len(g['reviews']) for g in search_grouped)

        weekly_data_for_analysis = _build_weekly_data(store)
        recent_analysis = _build_recent_analysis(store, weekly_data_for_analysis)
        all_top_keywords = _build_all_keywords(store)

        context = {
            'store': store,
            'q': q,
            'search_grouped': search_grouped,
            'search_total': search_total,
            'weekly_data': [],
            'recent_analysis': recent_analysis,
            'all_top_keywords': all_top_keywords,
            'chart_data_json': '[]',
        }
    else:
        weekly_data = _build_weekly_data(store)
        recent_analysis = _build_recent_analysis(store, weekly_data)
        all_top_keywords = _build_all_keywords(store)

        # 차트용 데이터: 오래된 주차 → 최근 순으로 정렬
        chart_weeks = list(reversed(weekly_data))
        chart_data = [
            {
                'label': item['summary'].year_week,
                'score': float(item['summary'].avg_rating),
                'reviews': item['summary'].review_count,
            }
            for item in chart_weeks
        ]

        context = {
            'store': store,
            'q': '',
            'search_grouped': None,
            'search_total': 0,
            'weekly_data': weekly_data,
            'recent_analysis': recent_analysis,
            'all_top_keywords': all_top_keywords,
            'chart_data_json': json.dumps(chart_data, ensure_ascii=False),
        }

    return render(request, 'stores/timeline.html', context)
