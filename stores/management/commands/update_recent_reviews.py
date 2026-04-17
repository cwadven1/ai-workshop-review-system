"""
최근 리뷰 AI 업데이트 커맨드.

각 가게별로 최근 N주(기본 4주)의 리뷰를 집계하여
ShopRecentReview + ShopRecentReviewSentiment 3개를 insert.
delete 없이 insert → created_at 기준 최신 1건을 조회 시 사용.
"""

import json
from collections import defaultdict
from datetime import date, timedelta

from django.conf import settings
from django.core.management.base import BaseCommand

from reviews.models import Review
from stores.models import ShopRecentReview, ShopRecentReviewSentiment, Store


def get_recent_week_range(n_weeks=4):
    """최근 N주의 (start_date, end_date) 반환"""
    today = date.today()
    iso = today.isocalendar()
    # 이번 주 월요일
    this_monday = today - timedelta(days=iso[2] - 1)
    # N주 전 월요일
    start_monday = this_monday - timedelta(weeks=n_weeks - 1)
    # 이번 주 일요일
    end_sunday = this_monday + timedelta(days=6)
    return start_monday, end_sunday


class Command(BaseCommand):
    help = "ShopRecentReview 업데이트 (최근 N주 리뷰 insert)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--store-id",
            type=int,
            help="특정 가게 ID만 처리 (생략 시 전체)",
        )
        parser.add_argument(
            "--weeks",
            type=int,
            default=4,
            help="최근 몇 주를 샘플링할지 (기본 4)",
        )

    def handle(self, *args, **options):
        store_qs = Store.objects.all()
        if options["store_id"]:
            store_qs = store_qs.filter(pk=options["store_id"])

        n_weeks = options["weeks"]
        start_date, end_date = get_recent_week_range(n_weeks)
        self.stdout.write(f"샘플링 기간: {start_date} ~ {end_date} ({n_weeks}주)")

        total = 0
        for store in store_qs:
            reviews = list(
                Review.objects.filter(
                    store=store,
                    review_date__gte=start_date,
                    review_date__lte=end_date,
                    is_deleted=False,
                    is_blinded=False,
                )
            )
            if not reviews:
                self.stdout.write(f"  [스킵] {store.name} — 기간 내 리뷰 없음")
                continue

            self._insert_recent_review(store, reviews, start_date, end_date)
            self.stdout.write(f"  [생성] {store.name} — {len(reviews)}건")
            total += 1

        self.stdout.write(self.style.SUCCESS(f"완료: {total}개 가게 최근 리뷰 집계 생성"))

    def _insert_recent_review(self, store, reviews, start_date, end_date):
        ratings = [r.rating for r in reviews]
        average = round(sum(ratings) / len(ratings), 1)

        sentiments = defaultdict(int)
        for r in reviews:
            sentiments[r.sentiment] += 1

        pos = sentiments.get("positive", 0)
        neg = sentiments.get("negative", 0)

        pos_reviews = [r for r in reviews if r.sentiment == "positive"]
        neg_reviews = [r for r in reviews if r.sentiment == "negative"]

        # 트렌드 계산 (기간 내 전반부 vs 후반부 평균 평점 비교)
        sorted_reviews = sorted(reviews, key=lambda r: r.review_date)
        mid = len(sorted_reviews) // 2
        if mid > 0:
            first_half_avg = sum(r.rating for r in sorted_reviews[:mid]) / mid
            second_half_avg = sum(r.rating for r in sorted_reviews[mid:]) / (len(sorted_reviews) - mid)
            diff = second_half_avg - first_half_avg
            if diff <= -0.3:
                trend = "하락세"
            elif diff >= 0.3:
                trend = "개선세"
            else:
                trend = "유지"
        else:
            trend = "유지"

        # Gemini API 호출 시도
        api_key = getattr(settings, "GEMINI_API_KEY", None)
        ai_summary, ai_pos_points, ai_neg_points = None, None, None
        if api_key:
            ai_summary, ai_pos_points, ai_neg_points = self._generate_with_gemini(
                api_key, store, pos_reviews, neg_reviews, trend
            )

        # AI 실패 또는 API 키 없으면 더미 텍스트 사용
        pos_kws = list(dict.fromkeys(kw for r in pos_reviews for kw in r.keywords))[:3]
        neg_kws = list(dict.fromkeys(kw for r in neg_reviews for kw in r.keywords))[:3]

        summary_text = ai_summary or (
            f"{store.name}의 최근 리뷰에서 고객들은 "
            f"'{', '.join(pos_kws)}' 등을 주로 언급하며 만족감을 표현했습니다."
            if pos_kws else f"{store.name}의 최근 리뷰 집계가 완료되었습니다."
        )

        pos_points = ai_pos_points or (
            [f"고객들이 '{', '.join(pos_kws)}' 등을 반복적으로 칭찬했습니다."]
            if pos_kws else [f"{store.name}의 최근 긍정 리뷰가 없습니다."]
        )

        neg_points = ai_neg_points or (
            [f"'{', '.join(neg_kws)}' 관련 개선 요청이 반복적으로 확인됩니다."]
            if neg_kws else [f"{store.name}의 최근 부정 리뷰가 없습니다."]
        )

        srr = ShopRecentReview.objects.create(
            shop=store,
            review_sample_start_date=start_date,
            review_sample_end_date=end_date,
            total_count=len(reviews),
            positive_count=pos,
            negative_count=neg,
            neutral_count=sentiments.get("neutral", 0),
            average=average,
            summary=summary_text,
        )

        sentiment_rows = []
        for point in pos_points:
            if point and point.strip():
                sentiment_rows.append(ShopRecentReviewSentiment(
                    shop_recent_review=srr, sentiment="positive", content=point.strip()
                ))
        for point in neg_points:
            if point and point.strip():
                sentiment_rows.append(ShopRecentReviewSentiment(
                    shop_recent_review=srr, sentiment="negative", content=point.strip()
                ))
        sentiment_rows.append(ShopRecentReviewSentiment(
            shop_recent_review=srr, sentiment="neutral", content=summary_text
        ))
        ShopRecentReviewSentiment.objects.bulk_create(sentiment_rows)

    def _generate_with_gemini(self, api_key, store, pos_reviews, neg_reviews, trend="유지"):
        """Gemini로 최근 리뷰 요약 생성. 성공 시 (summary, pos_points, neg_points) 반환, 실패 시 (None, None, None)
        pos_points, neg_points 는 각각 문자열 리스트 (1 항목 = 1 row)
        """
        try:
            from google import genai
            from google.genai import types

            # 리뷰 텍스트 샘플 (긍정 10건 + 부정 10건, 비어있는 것 제외)
            pos_texts = [r.content for r in pos_reviews if r.content and r.content.strip()][:10]
            neg_texts = [r.content for r in neg_reviews if r.content and r.content.strip()][:10]
            sample_block = "\n".join(f"- {t}" for t in pos_texts + neg_texts) or "리뷰 텍스트 없음"

            pos_kws = list(dict.fromkeys(kw for r in pos_reviews for kw in r.keywords))[:5]
            neg_kws = list(dict.fromkeys(kw for r in neg_reviews for kw in r.keywords))[:5]

            system_instruction = (
                "당신은 음식점 리뷰 분석 전문가입니다. "
                "반드시 아래 제공된 실제 리뷰 텍스트를 직접 읽고 분석하세요. "
                "절대 금지: 별점·건수·긍정/부정/중립 비율 등 수치를 그대로 서술하는 것. "
                "화면에 이미 표시된 통계 수치를 단순 반복하지 마세요. "
                "대신: 리뷰 텍스트에서만 발견할 수 있는 패턴, 반복되는 맥락, 고객 경험의 본질을 분석하세요. "
                "트렌드가 하락세라면 솔직하게 표현하고, 긍정과 부정을 균형 있게 반영하세요."
            )

            prompt = f"""가게: {store.name} (최근 리뷰 분석)
최근 트렌드: {trend}

[실제 리뷰 샘플]
{sample_block}

[상위 키워드]
- 긍정: {', '.join(pos_kws) or '없음'}
- 부정: {', '.join(neg_kws) or '없음'}

아래 JSON 형식으로만 응답해주세요.
각 배열 항목은 반드시 독립적인 단일 포인트 1문장으로 작성하세요. 여러 포인트를 하나의 문자열에 합치지 마세요.
{{
  "summary": "최근 고객 경험의 전반적인 흐름({trend})을 포함하여, 긍정과 부정을 균형 있게 반영한 3문장 요약. 트렌드가 하락세라면 솔직하게 표현할 것. 수치 언급 절대 금지.",
  "positive_points": [
    "긍정 포인트 1 (1문장, 독립적인 칭찬 맥락)",
    "긍정 포인트 2 (1문장, 독립적인 칭찬 맥락)",
    "긍정 포인트 3 (1문장, 독립적인 칭찬 맥락)"
  ],
  "negative_points": [
    "부정 포인트 1 (1문장, 독립적인 불만/개선 맥락)",
    "부정 포인트 2 (1문장, 독립적인 불만/개선 맥락)"
  ]
}}
주의: positive_points / negative_points 는 반드시 배열이어야 합니다. 없으면 빈 배열 [] 로 주세요."""

            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.7,
                    max_output_tokens=800,
                    response_mime_type="application/json",
                ),
            )
            result = json.loads(response.text)

            pos_points = result.get("positive_points")
            neg_points = result.get("negative_points")

            # 배열이 아닌 경우 (문자열 등) 리스트로 감싸기
            if isinstance(pos_points, str):
                pos_points = [pos_points] if pos_points.strip() else []
            if isinstance(neg_points, str):
                neg_points = [neg_points] if neg_points.strip() else []

            return (
                result.get("summary") or None,
                pos_points if pos_points else None,
                neg_points if neg_points else None,
            )
        except Exception as e:
            self.stderr.write(f"  Gemini API 오류 ({store.name}): {e}")
            return None, None, None
