import json
import logging

from google import genai
from google.genai import types as genai_types
from celery import shared_task
from django.conf import settings
from django.utils import timezone as tz

logger = logging.getLogger(__name__)

MAX_ACTION_ITEMS = 5
MAX_STRENGTH_ITEMS = 3


def _build_prompt(store, weekly_data):
    weeks_lines = []
    for wr in weekly_data:
        total = wr.count or 1
        neg_pct = round(wr.negative_count / total * 100)
        pos_pct = round(wr.positive_count / total * 100)
        weeks_lines.append(
            f"W{wr.week_number}: 평점 {wr.average:.1f}, 리뷰 {wr.count}개, "
            f"긍정 {pos_pct}% / 부정 {neg_pct}%"
        )

    kw_pos, kw_neg = [], []
    if weekly_data:
        latest = weekly_data[0]
        for kwrel in latest.review_keywords.select_related("keyword").order_by("-count")[:10]:
            kw = kwrel.keyword
            if kw.sentiment == "positive":
                kw_pos.append(f"{kw.word}({kwrel.count}회)")
            elif kw.sentiment == "negative":
                kw_neg.append(f"{kw.word}({kwrel.count}회)")

    weeks_text = "\n".join(weeks_lines) if weeks_lines else "데이터 없음"

    return f"""당신은 배달 음식점 사장님을 위한 리뷰 분석 전문가입니다.
아래 데이터를 분석하여 두 가지 섹션을 JSON으로 출력하세요.

## 가게 정보
- 가게명: {store.name}
- 카테고리: {store.get_category_display()}
- 현재 평균 평점: {store.avg_rating:.1f}점

## 최근 주차별 현황
{weeks_text}

## 최근 주 반복 키워드
- 긍정: {", ".join(kw_pos) if kw_pos else "없음"}
- 부정: {", ".join(kw_neg) if kw_neg else "없음"}

## 출력 형식 (JSON만 출력, 다른 텍스트 없이)
{{
  "actions": [
    {{
      "title": "짧은 제목 (20자 이내)",
      "description": "문제 상황 설명 (2~3문장)",
      "action_detail": "구체적 조치 방법 (1~2문장)",
      "level": "danger 또는 warning 또는 info",
      "priority": "high 또는 medium 또는 low",
      "link_label": "관련 리뷰 보기 버튼 텍스트 (없으면 빈 문자열)"
    }}
  ],
  "strengths": [
    {{
      "title": "짧은 강점 제목 (20자 이내)",
      "description": "고객이 자주 칭찬하는 내용 설명 (2~3문장)",
      "action_detail": "이 강점을 더 살릴 수 있는 방법 (1~2문장)"
    }}
  ]
}}

## 규칙
### actions (개선 할일)
- 시급한 개선 사항만 포함, success 레벨 사용 금지
- 가장 시급한 항목부터 priority high → low 순으로 정렬
- 모호한 조언 제외, 구체적으로 작성
- 최대 {MAX_ACTION_ITEMS}개

### strengths (강점 인사이트)
- 고객 리뷰에서 반복적으로 칭찬받는 항목을 기반으로 작성
- 현재 잘 유지되고 있는 것, 지속·강화해야 할 것
- 최대 {MAX_STRENGTH_ITEMS}개
"""


def _resolve_link_url(store, level):
    if level in ("danger", "warning"):
        return f"/stores/{store.pk}/reviews/?sentiment=negative"
    elif level == "success":
        return f"/stores/{store.pk}/reviews/?sentiment=positive"
    return ""


def _run_analysis(job):
    from stores.models import AIActionItem, ShopWeekReview

    store = job.store

    weekly_data = list(
        ShopWeekReview.objects.filter(shop=store)
        .prefetch_related("review_keywords__keyword")
        .order_by("-year", "-week_number")[:4]
    )

    source_week = weekly_data[0] if weekly_data else None
    now = tz.now()
    iso = now.isocalendar()
    week_year, week_number = iso[0], iso[1]

    prompt = _build_prompt(store, weekly_data)

    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt,
        config=genai_types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.3,
        ),
    )

    raw = response.text
    job.raw_response = raw

    data = json.loads(raw)
    actions = data.get("actions", [])[:MAX_ACTION_ITEMS]
    strengths = data.get("strengths", [])[:MAX_STRENGTH_ITEMS]

    for action in actions:
        level = action.get("level", "info")
        if level == "success":
            level = "info"  # actions 섹션에는 success 사용 금지
        AIActionItem.objects.create(
            store=store,
            source_job=job,
            item_type="action",
            title=action.get("title", "")[:200],
            description=action.get("description", ""),
            action_detail=action.get("action_detail", ""),
            level=level,
            priority=action.get("priority", "medium"),
            link_label=action.get("link_label", ""),
            link_url=_resolve_link_url(store, level),
            week_year=week_year,
            week_number=week_number,
        )

    for strength in strengths:
        AIActionItem.objects.create(
            store=store,
            source_job=job,
            item_type="strength",
            title=strength.get("title", "")[:200],
            description=strength.get("description", ""),
            action_detail=strength.get("action_detail", ""),
            level="success",
            priority="low",
            link_url=f"/stores/{store.pk}/reviews/?sentiment=positive",
            link_label="긍정 리뷰 보기",
            week_year=week_year,
            week_number=week_number,
        )

    job.source_week = source_week
    job.status = "completed"
    job.completed_at = tz.now()
    job.save()


@shared_task(bind=True, max_retries=2)
def run_store_analysis(self, store_id, triggered_by="schedule"):
    """단일 가게 AI 분석 실행 (스케줄/수동 공용)"""
    from stores.models import AIAnalysisJob, Store

    try:
        store = Store.objects.get(pk=store_id)
    except Store.DoesNotExist:
        logger.error(f"Store {store_id} not found")
        return

    job = AIAnalysisJob.objects.create(
        store=store,
        status="running",
        triggered_by=triggered_by,
    )

    try:
        _run_analysis(job)
        logger.info(f"Analysis completed: store={store_id} job={job.pk}")
    except Exception as exc:
        job.status = "failed"
        job.error_message = str(exc)
        job.completed_at = tz.now()
        job.save()
        logger.error(f"Analysis failed: store={store_id} job={job.pk} error={exc}")
        raise self.retry(exc=exc, countdown=60)


@shared_task
def run_weekly_analysis():
    """celery-beat 스케줄: 매주 월요일 오전 9시 전체 가게 분석"""
    from stores.models import Store

    store_ids = list(Store.objects.values_list("pk", flat=True))
    for store_id in store_ids:
        run_store_analysis.delay(store_id, triggered_by="schedule")
    logger.info(f"Weekly analysis scheduled for {len(store_ids)} stores")
