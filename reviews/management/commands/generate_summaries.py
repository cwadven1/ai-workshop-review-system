import json
from collections import defaultdict

from django.conf import settings
from django.core.management.base import BaseCommand

from reviews.models import Review, WeeklySummary
from stores.models import Store


class Command(BaseCommand):
    help = "특정 가게의 특정 주차 리뷰를 AI로 요약 생성"

    def add_arguments(self, parser):
        parser.add_argument("--store_id", type=int, required=True, help="가게 ID")
        parser.add_argument(
            "--year_week", type=str, required=True, help="연주차 (예: 2025-W14)"
        )

    def handle(self, *args, **options):
        store_id = options["store_id"]
        year_week = options["year_week"]

        try:
            store = Store.objects.get(pk=store_id)
        except Store.DoesNotExist:
            self.stderr.write(f"가게 ID {store_id}을(를) 찾을 수 없습니다.")
            return

        reviews = Review.objects.filter(store=store, year_week=year_week)
        if not reviews.exists():
            self.stderr.write(
                f"{store.name}의 {year_week} 리뷰가 없습니다."
            )
            return

        self.stdout.write(
            f"{store.name}의 {year_week} 리뷰 {reviews.count()}개 요약 생성 중..."
        )

        # 리뷰 통계 계산
        ratings = [r.rating for r in reviews]
        avg_rating = round(sum(ratings) / len(ratings), 1)

        sentiments = defaultdict(int)
        for r in reviews:
            sentiments[r.sentiment] += 1

        all_keywords = []
        for r in reviews:
            all_keywords.extend(r.keywords)
        keyword_counts = defaultdict(int)
        for kw in all_keywords:
            keyword_counts[kw] += 1
        top_keywords = sorted(keyword_counts.items(), key=lambda x: -x[1])[:5]
        top_keywords = [{"keyword": kw, "count": cnt} for kw, cnt in top_keywords]

        # 전주 평점과 비교
        prev_summary = (
            WeeklySummary.objects.filter(store=store, year_week__lt=year_week)
            .order_by("-year_week")
            .first()
        )
        rating_change = 0.0
        if prev_summary:
            rating_change = round(avg_rating - prev_summary.avg_rating, 1)

        # 리뷰 텍스트 모아서 요약 시도
        review_texts = [r.content for r in reviews]

        api_key = settings.OPENAI_API_KEY
        if api_key:
            summary_text, highlights = self._generate_with_openai(
                api_key, store.name, year_week, review_texts, avg_rating, sentiments
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    "OpenAI API 키가 없습니다. 더미 요약을 생성합니다."
                )
            )
            summary_text, highlights = self._generate_dummy(
                store.name, year_week, avg_rating, sentiments, top_keywords, rating_change
            )

        # WeeklySummary 저장 (upsert)
        summary, created = WeeklySummary.objects.update_or_create(
            store=store,
            year_week=year_week,
            defaults={
                "summary": summary_text,
                "highlights": highlights,
                "avg_rating": avg_rating,
                "review_count": reviews.count(),
                "sentiment_distribution": dict(sentiments),
                "top_keywords": top_keywords,
                "rating_change": rating_change,
            },
        )

        action = "생성" if created else "업데이트"
        self.stdout.write(
            self.style.SUCCESS(f"주별 요약이 {action}되었습니다: {summary}")
        )

    def _generate_with_openai(
        self, api_key, store_name, year_week, review_texts, avg_rating, sentiments
    ):
        """OpenAI GPT-4o-mini로 요약 생성"""
        try:
            from openai import OpenAI

            client = OpenAI(api_key=api_key)

            reviews_block = "\n".join(f"- {text}" for text in review_texts[:30])
            total = sum(sentiments.values()) or 1
            pos_pct = round(sentiments.get("positive", 0) / total * 100)
            neg_pct = round(sentiments.get("negative", 0) / total * 100)

            prompt = f"""다음은 '{store_name}'의 {year_week} 리뷰들입니다.

리뷰 목록:
{reviews_block}

통계:
- 평균 평점: {avg_rating}/5.0
- 긍정 리뷰: {pos_pct}%
- 부정 리뷰: {neg_pct}%

아래 JSON 형식으로 응답해주세요:
{{
  "summary": "3-4문장의 종합 요약",
  "highlights": {{
    "good_points": ["좋은 점 1", "좋은 점 2"],
    "bad_points": ["아쉬운 점 1", "아쉬운 점 2"]
  }}
}}"""

            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "당신은 음식점 리뷰 분석 전문가입니다. 한국어로 응답하세요.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=500,
            )

            result = json.loads(response.choices[0].message.content)
            return result["summary"], result["highlights"]

        except Exception as e:
            self.stderr.write(f"OpenAI API 오류: {e}")
            self.stdout.write("더미 요약으로 대체합니다.")
            return self._generate_dummy(
                store_name,
                year_week,
                avg_rating,
                sentiments,
                [],
                0.0,
            )

    def _generate_dummy(
        self, store_name, year_week, avg_rating, sentiments, top_keywords, rating_change
    ):
        """더미 요약 생성 (OpenAI 없을 때)"""
        pos = sentiments.get("positive", 0)
        neg = sentiments.get("negative", 0)
        total = sum(sentiments.values()) or 1
        kw_text = ", ".join(kw["keyword"] for kw in top_keywords[:3]) if top_keywords else "맛, 서비스, 배달"

        summary = (
            f"{store_name}의 {year_week} 리뷰 분석 결과, "
            f"평균 평점 {avg_rating}점으로 "
            f"긍정 리뷰가 {round(pos/total*100)}%, "
            f"부정 리뷰가 {round(neg/total*100)}%를 차지합니다. "
            f"주요 키워드는 '{kw_text}'입니다."
        )

        good_points = []
        bad_points = []

        if pos / total > 0.5:
            good_points.append("전반적으로 긍정적인 평가가 우세합니다.")
        if rating_change > 0:
            good_points.append("평점이 상승 추세에 있습니다.")
        if not good_points:
            good_points.append("일부 긍정적인 리뷰가 있습니다.")

        if neg / total > 0.3:
            bad_points.append("부정 리뷰 비율이 높아 개선이 필요합니다.")
        if rating_change < 0:
            bad_points.append("평점이 하락 추세입니다.")
        if not bad_points:
            bad_points.append("지속적인 모니터링이 필요합니다.")

        highlights = {
            "good_points": good_points,
            "bad_points": bad_points,
        }

        return summary, highlights
