import json
from collections import Counter
from datetime import date

from django.db.models import Prefetch
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone as tz
from django.views.decorators.http import require_POST

from reviews.models import Review

from .models import AIActionItem, AIAnalysisJob, Menu, ShopRecentReview, ShopRecentReviewSentiment, ShopWeekReview, ShopWeekReviewSentiment, Store


def _get_current_info(swr):
    """ShopWeekReview.updated_at과 created_at이 일치하는 최신 ShopWeekReviewSentiment 반환"""
    for info in swr.infos.all():
        if info.created_at == swr.updated_at:
            return info
    return swr.infos.order_by('-created_at').first()


def _compute_trend(recent_summaries):
    if len(recent_summaries) < 2:
        return 'neutral'
    latest = float(recent_summaries[0].average)
    prev = float(recent_summaries[1].average)
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
        'shop_week_reviews',
        queryset=ShopWeekReview.objects.order_by('-year', '-week_number'),
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
            'labels': [s.week_number for s in mini_data],
            'data': [float(s.average) for s in mini_data],
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
        ShopWeekReview.objects.filter(shop=store)
        .prefetch_related('review_keywords__keyword', 'infos')
        .order_by("-year", "-week_number")
    )

    for swr in summaries:
        dist = {
            'positive': swr.positive_count,
            'neutral': swr.neutral_count,
            'negative': swr.negative_count,
        }
        swr.sentiment_distribution = dist
        swr.sentiment_total = sum(dist.values()) or 1
        swr.top_keywords = [
            {'keyword': rk.keyword.word, 'count': rk.count}
            for rk in swr.review_keywords.all()
        ]

    week_numbers = [s.week_number for s in summaries]
    all_reviews = list(
        Review.objects.filter(store=store, week__in=week_numbers)
        .order_by("-review_date")
    )
    reviews_by_week = {}
    for review in all_reviews:
        reviews_by_week.setdefault(review.week, []).append(review)

    weekly_data = []
    for swr in summaries:
        sentiment_points = {'positive': [], 'negative': [], 'neutral': []}
        for info in swr.infos.all():
            if info.sentiment in sentiment_points:
                sentiment_points[info.sentiment].append(info.content)

        weekly_data.append({
            "summary": swr,
            "reviews": reviews_by_week.get(swr.week_number, [])[:5],
            "sentiment_points": sentiment_points,
        })

    # 이전 주차 대비 평점 diff 계산 (내림차순이므로 [i+1]이 이전 주)
    for i, item in enumerate(weekly_data):
        if i + 1 < len(weekly_data):
            curr = float(item['summary'].average)
            prev = float(weekly_data[i + 1]['summary'].average)
            item['diff'] = round(curr - prev, 1)
            item['has_diff'] = True
        else:
            item['diff'] = None
            item['has_diff'] = False

    return weekly_data


def _build_recent_analysis(store, weekly_data):
    if not weekly_data:
        return None

    recent_weeks = weekly_data[:4]

    total_reviews = sum(m['summary'].count for m in recent_weeks)
    if total_reviews == 0:
        return None

    weighted_rating = sum(
        float(m['summary'].average) * m['summary'].count
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
        r1 = float(recent_weeks[0]['summary'].average)
        r2 = float(recent_weeks[1]['summary'].average)
        if r1 - r2 >= 0.2:
            trend = 'up'
        elif r2 - r1 >= 0.2:
            trend = 'down'

    period = f"{recent_weeks[-1]['summary'].week_number}주차 ~ {recent_weeks[0]['summary'].week_number}주차"

    store_name = store.name
    avg_r = round(weighted_rating, 1)
    pos_pct = round(pos / total_sent * 100)
    neg_pct = round(neg / total_sent * 100)

    oldest_rating = float(recent_weeks[-1]['summary'].average)
    latest_rating = float(recent_weeks[0]['summary'].average)
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
    all_reviews = Review.objects.filter(store=store).exclude(keywords__isnull=True)
    kw_counter = Counter()
    for review in all_reviews:
        for kw in (review.keywords or []):
            if kw:
                kw_counter[kw] += 1
    return [{'keyword': k, 'count': c} for k, c in kw_counter.most_common(15)]


def _build_neg_keywords(weekly_data):
    """부정 리뷰에서 반복 키워드 추출 (전체 주차 기준)"""
    kw_counter = Counter()
    for item in weekly_data:
        for review in item['reviews']:
            if review.sentiment == 'negative' and review.keywords:
                for kw in review.keywords:
                    if kw:
                        kw_counter[kw] += 1
    return [{'keyword': k, 'count': c} for k, c in kw_counter.most_common(10)]


def _build_pos_keywords(weekly_data):
    """긍정 리뷰에서 반복 키워드 추출 (전체 주차 기준)"""
    kw_counter = Counter()
    for item in weekly_data:
        for review in item['reviews']:
            if review.sentiment == 'positive' and review.keywords:
                for kw in review.keywords:
                    if kw:
                        kw_counter[kw] += 1
    return [{'keyword': k, 'count': c} for k, c in kw_counter.most_common(10)]


def _generate_strength_items(weekly_data, recent_analysis, pos_keywords):
    """규칙 기반 강점 인사이트 생성"""
    strengths = []
    if not weekly_data or not recent_analysis:
        return strengths

    summaries = [item['summary'] for item in weekly_data]

    # 규칙 1: 긍정 비율 기준
    pos_pct = recent_analysis.get('pos_pct', 0)
    if pos_pct >= 70:
        strengths.append({
            'icon': 'trophy-fill',
            'title': '탁월한 고객 만족',
            'desc': f'긍정 리뷰 비율이 {pos_pct}%로 매우 높습니다. 고객 10명 중 7명 이상이 만족하고 있어 업계 최상위 수준의 서비스 품질을 유지하고 있습니다.',
        })
    elif pos_pct >= 55:
        strengths.append({
            'icon': 'emoji-smile-fill',
            'title': '양호한 고객 반응',
            'desc': f'긍정 리뷰 비율 {pos_pct}%로 고객 만족도가 안정적입니다. 과반수 이상의 고객이 긍정적인 경험을 하고 있습니다.',
        })

    # 규칙 2: 긍정 반복 키워드 top2
    if pos_keywords and len(pos_keywords) >= 2:
        kw1 = pos_keywords[0]['keyword']
        kw2 = pos_keywords[1]['keyword']
        strengths.append({
            'icon': 'chat-heart-fill',
            'title': f'고객이 자주 칭찬하는 키워드',
            'desc': f'"{kw1}", "{kw2}"가 긍정 리뷰에서 반복 등장합니다. 이 항목들이 고객이 가장 만족하는 강점입니다.',
        })
    elif pos_keywords:
        kw1 = pos_keywords[0]['keyword']
        strengths.append({
            'icon': 'chat-heart-fill',
            'title': f'고객이 자주 칭찬하는 키워드',
            'desc': f'"{kw1}"가 긍정 리뷰에서 반복 등장합니다. 이 항목이 고객이 가장 만족하는 강점입니다.',
        })

    # 규칙 3: 평점 수준
    avg_r = recent_analysis.get('avg_rating', 0)
    if avg_r >= 4.3:
        strengths.append({
            'icon': 'star-fill',
            'title': f'최상위 수준 평점 ({avg_r}점)',
            'desc': f'평균 평점 {avg_r}점으로 플랫폼 내 상위권에 해당합니다. 꾸준한 품질 관리가 고객 신뢰로 이어지고 있습니다.',
        })
    elif avg_r >= 4.0:
        strengths.append({
            'icon': 'star-half',
            'title': f'안정적 고평가 유지 ({avg_r}점)',
            'desc': f'평균 평점 {avg_r}점으로 안정적인 고평가를 유지하고 있습니다. 4점 이상은 고객에게 신뢰받는 매장임을 의미합니다.',
        })

    # 규칙 4: 상승 트렌드
    if recent_analysis.get('trend') == 'up':
        strengths.append({
            'icon': 'graph-up-arrow',
            'title': '개선 노력이 고객에게 전달되고 있음',
            'desc': '최근 평점이 상승 추세입니다. 운영 개선 노력이 실제 고객 만족도 향상으로 이어지고 있습니다.',
        })

    # 규칙 5: 없으면 기본 격려 메시지
    if not strengths:
        strengths.append({
            'icon': 'house-heart-fill',
            'title': '가게 운영 중',
            'desc': '꾸준한 리뷰 관리와 고객 응대를 통해 강점을 만들어가고 있습니다. 긍정 리뷰가 쌓이면 강점 인사이트가 표시됩니다.',
        })

    return strengths


def _generate_action_items(weekly_data, recent_analysis):
    """규칙 기반 AI 액션 추천 생성"""
    actions = []
    if not weekly_data or not recent_analysis:
        return actions

    summaries = [item['summary'] for item in weekly_data]

    # 규칙 1: 3주 연속 하락
    if len(summaries) >= 3:
        ratings = [float(s.average) for s in summaries[:3]]  # 최신 3개 (내림차순)
        if ratings[0] < ratings[1] < ratings[2]:
            actions.append({
                'level': 'danger',
                'icon': 'exclamation-triangle-fill',
                'title': f'평점 3주 연속 하락 중',
                'desc': f'W{summaries[2].week_number}({ratings[2]}점) → W{summaries[1].week_number}({ratings[1]}점) → W{summaries[0].week_number}({ratings[0]}점)으로 연속 하락하고 있습니다. 즉각적인 개선이 필요합니다.',
                'action': '최근 부정 리뷰를 확인하고 반복 키워드 중심으로 운영 개선 계획을 수립하세요.',
            })

    # 규칙 2: 부정 비율 30% 이상
    if recent_analysis.get('neg_pct', 0) >= 30:
        actions.append({
            'level': 'warning',
            'icon': 'emoji-frown',
            'title': f'부정 리뷰 비율 {recent_analysis["neg_pct"]}% 경고',
            'desc': f'최근 {recent_analysis["period"]} 기간 중 부정 리뷰가 전체의 {recent_analysis["neg_pct"]}%를 차지합니다. 평균적으로 20% 이하 유지가 권장됩니다.',
            'action': '반복 부정 키워드를 확인하고 해당 항목(배달 시간, 음식 품질 등)을 집중 개선하세요.',
        })
    elif recent_analysis.get('neg_pct', 0) >= 20:
        actions.append({
            'level': 'warning',
            'icon': 'exclamation-circle',
            'title': f'부정 리뷰 비율 주시 필요 ({recent_analysis["neg_pct"]}%)',
            'desc': f'부정 리뷰 비율이 {recent_analysis["neg_pct"]}%로 다소 높습니다. 추이를 주의 깊게 관찰하세요.',
            'action': '이번 주 부정 리뷰 내용을 직접 읽고 개선 가능한 항목을 파악하세요.',
        })

    # 규칙 3: 반복 부정 키워드 상위 1개
    neg_kws = _build_neg_keywords(weekly_data)
    if neg_kws and neg_kws[0]['count'] >= 3:
        top = neg_kws[0]
        actions.append({
            'level': 'warning',
            'icon': 'chat-square-text',
            'title': f'"{top["keyword"]}" 반복 언급 ({top["count"]}회)',
            'desc': f'"{top["keyword"]}" 키워드가 부정 리뷰에서 {top["count"]}번 반복 등장하고 있습니다. 고객이 지속적으로 불만을 느끼는 항목입니다.',
            'action': f'"{top["keyword"]}" 관련 운영 프로세스를 점검하고 즉시 개선 방안을 마련하세요.',
        })

    # 규칙 4: 상승 트렌드 (긍정 신호)
    if recent_analysis.get('trend') == 'up' and recent_analysis.get('neg_pct', 100) < 20:
        actions.append({
            'level': 'success',
            'icon': 'trophy',
            'title': '긍정적 트렌드 유지 중!',
            'desc': f'평점이 상승 중이며 부정 리뷰 비율도 {recent_analysis["neg_pct"]}%로 낮습니다. 현재 운영 방식이 고객에게 좋은 반응을 얻고 있습니다.',
            'action': '현재 강점(음식 품질, 서비스 등)을 유지하고 긍정 키워드를 메뉴 소개에 활용해 보세요.',
        })

    # 규칙 5: 아무 경고도 없으면 기본 인포
    if not actions:
        actions.append({
            'level': 'info',
            'icon': 'info-circle',
            'title': '운영 안정 상태',
            'desc': f'평균 평점 {recent_analysis.get("avg_rating", "-")}점으로 안정적인 운영이 유지되고 있습니다.',
            'action': '꾸준한 품질 유지와 고객 응답률을 높이면 더 좋은 평가를 받을 수 있습니다.',
        })

    return actions


def owner_dashboard(request, store_id):
    store = get_object_or_404(Store, pk=store_id)

    weekly_data = _build_weekly_data(store)
    recent_analysis = _build_recent_analysis(store, weekly_data)
    # DB에 저장된 AI 액션 아이템 (open / in_progress만, action 타입)
    db_action_items = list(
        AIActionItem.objects.filter(store=store, item_type="action", status__in=["open", "in_progress"])
        .order_by("status", "-created_at")
    )
    # DB 아이템 없으면 rule-based를 이번 주차 기준으로 DB에 자동 저장 (주 1회)
    if not db_action_items:
        year, week, _ = date.today().isocalendar()
        already_seeded = AIActionItem.objects.filter(
            store=store, item_type="action",
            week_year=year, week_number=week, is_ai_generated=False
        ).exists()
        if not already_seeded:
            rule_items = _generate_action_items(weekly_data, recent_analysis)
            level_to_priority = {"danger": "high", "warning": "medium", "success": "low", "info": "low"}
            for r in rule_items:
                AIActionItem.objects.create(
                    store=store,
                    source_job=None,
                    title=r["title"],
                    description=r["desc"],
                    action_detail=r["action"],
                    level=r["level"],
                    priority=level_to_priority.get(r["level"], "medium"),
                    item_type="action",
                    week_year=year,
                    week_number=week,
                    is_ai_generated=False,
                )
        db_action_items = list(
            AIActionItem.objects.filter(store=store, item_type="action", status__in=["open", "in_progress"])
            .order_by("status", "-created_at")
        )
    action_items = None
    ai_action_items = db_action_items if db_action_items else None

    # DB에 저장된 AI 강점 아이템 (open만, strength 타입)
    ai_strength_items = list(
        AIActionItem.objects.filter(store=store, item_type="strength", status="open")
        .order_by("-created_at")
    )

    # 확인 완료된 강점 아이템 (confirmed, 최대 30개)
    confirmed_strength_items = list(
        AIActionItem.objects.filter(store=store, item_type="strength", status="confirmed")
        .order_by("-updated_at")[:30]
    )

    # 완료 아이템 (action 타입, 최대 50개)
    completed_action_items = list(
        AIActionItem.objects.filter(store=store, item_type="action", status="completed")
        .order_by("-completed_at")[:50]
    )

    # 기각 아이템 (action 타입, 최대 50개)
    dismissed_action_items = list(
        AIActionItem.objects.filter(store=store, item_type="action", status="dismissed")
        .order_by("-updated_at")[:50]
    )

    # 진행 중인 분석 작업 여부
    analysis_running = AIAnalysisJob.objects.filter(store=store, status="running").exists()

    neg_keywords = _build_neg_keywords(weekly_data)
    pos_keywords = _build_pos_keywords(weekly_data)
    strength_items = _generate_strength_items(weekly_data, recent_analysis, pos_keywords)

    recent_negative_reviews = list(
        Review.objects.filter(store=store, sentiment='negative')
        .order_by('-review_date')[:10]
    )
    recent_positive_reviews = list(
        Review.objects.filter(store=store, sentiment='positive')
        .order_by('-review_date')[:10]
    )

    chart_weeks = list(reversed(weekly_data))
    chart_data = [
        {
            'label': item['summary'].week_number,
            'score': float(item['summary'].average),
            'reviews': item['summary'].count,
        }
        for item in chart_weeks
    ]

    action_items_rule_based = bool(
        ai_action_items and any(not item.is_ai_generated for item in ai_action_items)
    )

    return render(request, 'stores/owner_dashboard.html', {
        'store': store,
        'recent_analysis': recent_analysis,
        'action_items': action_items,           # 규칙 기반 (폴백 — 사실상 항상 None)
        'ai_action_items': ai_action_items,     # DB 기반 AI 아이템
        'action_items_rule_based': action_items_rule_based,  # rule-based 여부
        'completed_action_items': completed_action_items,
        'dismissed_action_items': dismissed_action_items,
        'analysis_running': analysis_running,
        'ai_strength_items': ai_strength_items,           # DB 기반 AI 강점 (open)
        'confirmed_strength_items': confirmed_strength_items,  # 확인 완료된 강점
        'strength_items': strength_items,                      # 규칙 기반 폴백
        'weekly_data': weekly_data,
        'neg_keywords': neg_keywords,
        'pos_keywords': pos_keywords,
        'recent_negative_reviews': recent_negative_reviews,
        'recent_positive_reviews': recent_positive_reviews,
        'chart_data_json': json.dumps(chart_data, ensure_ascii=False),
    })


@require_POST
def trigger_analysis(request, store_id):
    """사장님 대시보드 수동 분석 트리거 (Celery 있으면 비동기, 없으면 동기 폴백)"""
    from stores.tasks import _run_analysis

    store = get_object_or_404(Store, pk=store_id)

    # 이미 실행 중이면 중복 방지
    if AIAnalysisJob.objects.filter(store=store, status="running").exists():
        return JsonResponse({"ok": False, "error": "이미 분석이 진행 중입니다."}, status=409)

    # Celery 비동기 시도 → 실패 시 동기 실행 폴백
    try:
        from stores.tasks import run_store_analysis
        run_store_analysis.delay(store_id, triggered_by="manual")
        return JsonResponse({"ok": True, "sync": False})
    except Exception:
        pass

    # 동기 폴백: Celery/Redis 없을 때
    job = AIAnalysisJob.objects.create(store=store, status="running", triggered_by="manual")
    try:
        _run_analysis(job)
        return JsonResponse({"ok": True, "sync": True})
    except Exception as exc:
        job.status = "failed"
        job.error_message = str(exc)
        job.completed_at = tz.now()
        job.save()
        return JsonResponse({"ok": False, "error": str(exc)}, status=500)


@require_POST
def update_action_item(request, item_id):
    """액션 아이템 상태 변경 (완료 / 기각 / 진행 중)"""
    item = get_object_or_404(AIActionItem, pk=item_id)
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"ok": False, "error": "invalid JSON"}, status=400)

    new_status = body.get("status")
    allowed = {s for s, _ in AIActionItem.STATUS_CHOICES}
    if new_status not in allowed:
        return JsonResponse({"ok": False, "error": "invalid status"}, status=400)

    item.status = new_status
    if new_status == "completed":
        item.completed_at = tz.now()
        item.completed_note = body.get("note", "")
    item.save(update_fields=["status", "completed_at", "completed_note", "updated_at"])
    return JsonResponse({"ok": True, "status": item.get_status_display()})


def store_reviews(request, store_id):
    store = get_object_or_404(Store, pk=store_id)
    menus = Menu.objects.filter(store=store)

    return render(request, "stores/reviews.html", {
        "store": store,
        "menus": menus,
    })


def _get_recent_sentiments(store):
    """ShopRecentReview 최신 1건의 sentiments를 {type: [content]} 딕셔너리로 반환.
    각 sentiment row 1개 = 리스트 항목 1개."""
    srr = ShopRecentReview.objects.filter(shop=store).order_by('-created_at').first()
    if not srr:
        return None, None
    sentiments = {}
    for s in srr.sentiments.all():
        if s.sentiment not in sentiments:
            sentiments[s.sentiment] = []
        sentiments[s.sentiment].append(s.content)
    return srr, sentiments


def store_timeline(request, store_id):
    store = get_object_or_404(Store, pk=store_id)
    q = request.GET.get('q', '').strip()

    srr, recent_sentiments = _get_recent_sentiments(store)

    if q:
        import json as _json
        from django.db.models import Q
        q_escaped = _json.dumps(q, ensure_ascii=True)[1:-1]
        reviews_qs = Review.objects.filter(
            Q(store=store) & (Q(content__icontains=q) | Q(keywords__icontains=q_escaped))
        ).order_by('-week', '-review_date')

        grouped_dict = {}
        for r in reviews_qs:
            grouped_dict.setdefault(r.week, []).append(r)
        search_grouped = [
            {'week': w, 'reviews': revs}
            for w, revs in grouped_dict.items()
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
            'recent_sentiments': recent_sentiments,
            'srr': srr,
            'all_top_keywords': all_top_keywords,
            'chart_data_json': '[]',
        }
    else:
        weekly_data = _build_weekly_data(store)
        recent_analysis = _build_recent_analysis(store, weekly_data)
        all_top_keywords = _build_all_keywords(store)

        chart_weeks = list(reversed(weekly_data))
        chart_data = [
            {
                'label': item['summary'].week_number,
                'score': float(item['summary'].average),
                'reviews': item['summary'].count,
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
            'recent_sentiments': recent_sentiments,
            'srr': srr,
            'all_top_keywords': all_top_keywords,
            'chart_data_json': json.dumps(chart_data, ensure_ascii=False),
        }

    return render(request, 'stores/timeline.html', context)
