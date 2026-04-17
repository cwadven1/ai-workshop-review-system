import json
from collections import defaultdict

from django.conf import settings
from django.core.management.base import BaseCommand

from reviews.models import Review
from stores.models import Keyword, ShopWeekReview, ShopWeekReviewSentiment, ShopWeekReviewKeyword, Store


class Command(BaseCommand):
    help = "특정 가게의 특정 주차 리뷰를 AI로 요약 생성"

    def add_arguments(self, parser):
        parser.add_argument("--store_id", type=int, required=True, help="가게 ID")
        parser.add_argument("--week", type=int, required=True, help="주차 (예: 14)")

    def handle(self, *args, **options):
        store_id = options["store_id"]
        week_number = options["week"]

        try:
            store = Store.objects.get(pk=store_id)
        except Store.DoesNotExist:
            self.stderr.write(f"가게 ID {store_id}을(를) 찾을 수 없습니다.")
            return

        reviews = Review.objects.filter(store=store, week=week_number, is_deleted=False, is_blinded=False)
        if not reviews.exists():
            self.stderr.write(f"{store.name}의 {week_number}주차 리뷰가 없습니다.")
            return

        self.stdout.write(f"{store.name}의 {week_number}주차 리뷰 {reviews.count()}개 요약 생성 중...")

        # year 도출
        first = reviews.order_by('review_date').first()
        year = first.review_date.isocalendar()[0]

        active_reviews = list(reviews)
        ratings = [r.rating for r in active_reviews]
        average = round(sum(ratings) / len(ratings), 1)

        sentiments = defaultdict(int)
        for r in active_reviews:
            sentiments[r.sentiment] += 1

        keyword_counts = defaultdict(int)
        positive_keyword_counts = defaultdict(int)
        negative_keyword_counts = defaultdict(int)
        for r in active_reviews:
            for kw in r.keywords:
                keyword_counts[kw] += 1
                if r.sentiment == "positive":
                    positive_keyword_counts[kw] += 1
                elif r.sentiment == "negative":
                    negative_keyword_counts[kw] += 1

        top_pos_kw = ", ".join(k for k, _ in sorted(positive_keyword_counts.items(), key=lambda x: -x[1])[:5]) or "없음"
        top_neg_kw = ", ".join(k for k, _ in sorted(negative_keyword_counts.items(), key=lambda x: -x[1])[:5]) or "없음"

        review_texts = [r.content for r in active_reviews]
        api_key = getattr(settings, "GEMINI_API_KEY", None)
        if api_key:
            summary_text = self._generate_with_gemini(
                api_key, store.name, week_number, review_texts, average, sentiments, top_pos_kw, top_neg_kw
            )
        else:
            self.stdout.write(self.style.WARNING("Gemini API 키가 없습니다. 더미 요약을 생성합니다."))
            summary_text = self._generate_dummy(store.name, week_number, average, sentiments, top_pos_kw, top_neg_kw)

        swr, was_created = ShopWeekReview.objects.update_or_create(
            shop=store,
            year=year,
            week_number=week_number,
            defaults={
                "count": len(active_reviews),
                "average": average,
                "positive_count": sentiments.get("positive", 0),
                "negative_count": sentiments.get("negative", 0),
                "neutral_count": sentiments.get("neutral", 0),
            },
        )

        if isinstance(summary_text, dict):
            positive_contents = summary_text.get("positive_contents", [])
            if isinstance(positive_contents, str):
                positive_contents = [positive_contents]
            negative_contents = summary_text.get("negative_contents", [])
            if isinstance(negative_contents, str):
                negative_contents = [negative_contents]
            neutral_contents = summary_text.get("neutral_contents", [])
            if isinstance(neutral_contents, str):
                neutral_contents = [neutral_contents]
            overall = summary_text.get("summary", "")
        else:
            positive_contents = []
            negative_contents = []
            neutral_contents = []
            overall = summary_text

        swr.summary = overall
        swr.save(update_fields=["summary"])

        # 재실행 시 중복 방지: 기존 sentiment rows 삭제
        ShopWeekReviewSentiment.objects.filter(shop_week_review=swr).delete()

        sentiment_rows = (
            [ShopWeekReviewSentiment(shop_week_review=swr, sentiment="positive", content=c, created_at=swr.updated_at) for c in positive_contents]
            + [ShopWeekReviewSentiment(shop_week_review=swr, sentiment="negative", content=c, created_at=swr.updated_at) for c in negative_contents]
            + [ShopWeekReviewSentiment(shop_week_review=swr, sentiment="neutral", content=c, created_at=swr.updated_at) for c in neutral_contents]
        )
        ShopWeekReviewSentiment.objects.bulk_create(sentiment_rows)

        swr.review_keywords.all().delete()
        for word, cnt in keyword_counts.items():
            keyword_obj, _ = Keyword.objects.get_or_create(word=word)
            ShopWeekReviewKeyword.objects.create(
                shop_week_review=swr, keyword=keyword_obj, count=cnt
            )

        action = "생성" if was_created else "업데이트"
        self.stdout.write(self.style.SUCCESS(
            f"ShopWeekReview {action}됨: {store.name} {year}-W{week_number:02d}"
        ))

    def _generate_with_gemini(self, api_key, store_name, week_number, review_texts, average, sentiments, top_pos_kw, top_neg_kw):
        try:
            from google import genai
            from google.genai import types

            # 실제 리뷰 텍스트 샘플 (최대 15건, 비어있는 것 제외)
            non_empty = [t for t in review_texts if t and t.strip()]
            sample_texts = non_empty[:15]
            sample_block = "\n".join(f"- {t}" for t in sample_texts) if sample_texts else "리뷰 텍스트 없음"

            system_instruction = (
                "당신은 음식점 리뷰 분석 전문가입니다. "
                "반드시 아래 제공된 실제 리뷰 텍스트를 직접 읽고 분석하세요. "
                "절대 금지: 별점·건수·긍정/부정/중립 비율 등 수치를 그대로 서술하는 것. "
                "화면에 이미 표시된 통계 수치를 단순 반복하지 마세요. "
                "대신: 리뷰 텍스트에서만 발견할 수 있는 패턴, 반복되는 맥락, 고객 경험의 본질을 분석하세요."
            )

            prompt = f"""가게: {store_name} ({week_number}주차)

[실제 리뷰 샘플]
{sample_block}

[상위 키워드]
- 긍정: {top_pos_kw}
- 부정: {top_neg_kw}

아래 JSON 형식으로만 응답해주세요.
각 배열의 항목은 반드시 하나의 구체적 포인트만 담은 1문장이어야 합니다. 여러 내용을 한 항목에 묶지 마세요.
배열이 비어있는 경우 빈 리스트([])로 응답해주세요.
{{
  "summary": "이 가게만의 특색과 고객이 반복적으로 언급하는 핵심 경험을 3문장으로. 수치 언급 절대 금지.",
  "positive_contents": ["고객이 칭찬하는 단일 포인트1 (1문장)", "고객이 칭찬하는 단일 포인트2 (1문장)"],
  "negative_contents": ["고객 불만의 단일 포인트1 (1문장)", "반복 요청되는 개선 단일 포인트2 (1문장)"],
  "neutral_contents": ["중립적 관찰 또는 개선 제안 단일 포인트 (1문장)"]
}}"""

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
            raw = response.text
            return json.loads(raw)

        except Exception as e:
            self.stderr.write(f"Gemini API 오류: {e}")
            self.stdout.write("더미 요약으로 대체합니다.")
            return self._generate_dummy(store_name, week_number, average, sentiments, top_pos_kw, top_neg_kw)

    def _generate_dummy(self, store_name, week_number, average, sentiments, top_pos_kw, top_neg_kw):
        summary = (
            f"{store_name}의 {week_number}주차 리뷰를 분석한 결과, "
            f"평균 평점 {average}점을 기록했습니다. "
            f"고객들은 {top_pos_kw} 등을 주로 긍정적으로 평가했으며, "
            f"{top_neg_kw} 관련 의견도 확인되었습니다."
        )
        pos_contents = [f"{top_pos_kw} 등이 긍정적으로 언급되었습니다."] if top_pos_kw != "없음" else []
        neg_contents = [f"{top_neg_kw} 관련 개선 의견이 있었습니다."] if top_neg_kw != "없음" else []
        return {
            "summary": summary,
            "positive_contents": pos_contents,
            "negative_contents": neg_contents,
            "neutral_contents": [],
        }
