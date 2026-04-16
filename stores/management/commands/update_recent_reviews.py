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

        # Gemini API 호출 시도
        api_key = getattr(settings, "GEMINI_API_KEY", None)
        ai_summary, ai_pos_content, ai_neg_content = None, None, None
        if api_key:
            ai_summary, ai_pos_content, ai_neg_content = self._generate_with_gemini(
                api_key, store, pos_reviews, neg_reviews
            )

        # AI 실패 또는 API 키 없으면 더미 텍스트 사용
        pos_kws = list(dict.fromkeys(kw for r in pos_reviews for kw in r.keywords))[:3]
        neg_kws = list(dict.fromkeys(kw for r in neg_reviews for kw in r.keywords))[:3]

        summary_text = ai_summary or (
            f"{store.name}의 최근 리뷰에서 고객들은 "
            f"'{', '.join(pos_kws)}' 등을 주로 언급하며 만족감을 표현했습니다."
            if pos_kws else f"{store.name}의 최근 리뷰 집계가 완료되었습니다."
        )

        pos_content = ai_pos_content or (
            f"고객들이 '{', '.join(pos_kws)}' 등을 반복적으로 칭찬했습니다."
            if pos_kws else f"{store.name}의 최근 긍정 리뷰가 없습니다."
        )

        neg_content = ai_neg_content or (
            f"'{', '.join(neg_kws)}' 관련 개선 요청이 반복적으로 확인됩니다."
            if neg_kws else f"{store.name}의 최근 부정 리뷰가 없습니다."
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

        ShopRecentReviewSentiment.objects.create(
            shop_recent_review=srr, sentiment="positive", content=pos_content
        )
        ShopRecentReviewSentiment.objects.create(
            shop_recent_review=srr, sentiment="negative", content=neg_content
        )
        ShopRecentReviewSentiment.objects.create(
            shop_recent_review=srr, sentiment="neutral", content=summary_text
        )

    def _generate_with_gemini(self, api_key, store, pos_reviews, neg_reviews):
        """Gemini로 최근 리뷰 요약 생성. 성공 시 (summary, pos_content, neg_content) 반환, 실패 시 (None, None, None)"""
        try:
            import google.generativeai as genai

            # 리뷰 텍스트 샘플 (긍정 10건 + 부정 5건, 비어있는 것 제외)
            pos_texts = [r.content for r in pos_reviews if r.content and r.content.strip()][:10]
            neg_texts = [r.content for r in neg_reviews if r.content and r.content.strip()][:5]
            sample_block = "\n".join(f"- {t}" for t in pos_texts + neg_texts) or "리뷰 텍스트 없음"

            pos_kws = list(dict.fromkeys(kw for r in pos_reviews for kw in r.keywords))[:5]
            neg_kws = list(dict.fromkeys(kw for r in neg_reviews for kw in r.keywords))[:5]

            system_instruction = (
                "당신은 음식점 리뷰 분석 전문가입니다. "
                "반드시 아래 제공된 실제 리뷰 텍스트를 직접 읽고 분석하세요. "
                "절대 금지: 별점·건수·긍정/부정/중립 비율 등 수치를 그대로 서술하는 것. "
                "화면에 이미 표시된 통계 수치를 단순 반복하지 마세요. "
                "대신: 리뷰 텍스트에서만 발견할 수 있는 패턴, 반복되는 맥락, 고객 경험의 본질을 분석하세요."
            )

            prompt = f"""가게: {store.name} (최근 리뷰 분석)

[실제 리뷰 샘플]
{sample_block}

[상위 키워드]
- 긍정: {', '.join(pos_kws) or '없음'}
- 부정: {', '.join(neg_kws) or '없음'}

아래 JSON 형식으로만 응답해주세요.
{{
  "summary": "이 가게만의 특색과 고객이 반복적으로 언급하는 핵심 경험을 3문장으로. 수치 언급 절대 금지.",
  "positive_content": "고객들이 칭찬하는 구체적 이유와 맥락 (2-3문장)",
  "negative_content": "고객 불만의 구체적 맥락과 반복 요청 개선 포인트 (2-3문장, 없으면 빈 문자열)"
}}"""

            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(
                model_name="gemini-2.0-flash",
                system_instruction=system_instruction,
            )
            response = model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.7,
                    max_output_tokens=600,
                    response_mime_type="application/json",
                ),
            )
            result = json.loads(response.text)
            return (
                result.get("summary") or None,
                result.get("positive_content") or None,
                result.get("negative_content") or None,
            )
        except Exception as e:
            self.stderr.write(f"  Gemini API 오류 ({store.name}): {e}")
            return None, None, None
