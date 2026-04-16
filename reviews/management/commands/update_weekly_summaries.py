"""
증분 주차별 집계 업데이트 커맨드

동작 방식:
1. 각 (shop, year, week_number) 조합의 ShopWeekReview.updated_at 을 watermark로 사용
2. 해당 시각 이후로 변경된 Review가 있으면 재계산
3. 변경 없으면 스킵 → 전체 재계산 대비 매우 빠름
4. ShopWeekReview 자체가 없으면 새로 생성
5. 재계산 시 is_deleted=False, is_blinded=False 활성 리뷰 기준으로 정확한 카운트/통계 산출
"""

import json
from collections import defaultdict

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Q

from reviews.models import Review
from stores.models import Keyword, ShopWeekReview, ShopWeekSentimentReveiw, ShopWeekReviewKeyword, Store


class Command(BaseCommand):
    help = "증분 방식으로 ShopWeekReview 업데이트 (변경된 가게/주차만 재계산)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--store-id",
            dest="store_id",
            type=int,
            default=None,
            help="특정 가게 ID만 처리 (생략 시 전체)",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="변경 감지 없이 전체 강제 재계산",
        )

    def handle(self, *args, **options):
        store_id = options["store_id"]
        force = options["force"]

        # 처리 대상 (store_id, year, week_number) 목록
        qs = (
            Review.objects.values("store_id", "review_date", "week")
            .distinct()
            .order_by("store_id", "review_date")
        )
        if store_id:
            qs = qs.filter(store_id=store_id)

        # (store_id, year, week_number) 조합 추출
        combo_set = set()
        for row in qs:
            iso = row["review_date"].isocalendar()
            combo_set.add((row["store_id"], iso[0], iso[1]))
        combos = sorted(combo_set)

        if not combos:
            self.stdout.write("처리할 리뷰 데이터가 없습니다.")
            return

        swr_map = {
            (s.shop_id, s.year, s.week_number): s
            for s in ShopWeekReview.objects.filter(
                shop_id__in={c[0] for c in combos}
            )
        }
        store_map = {
            s.pk: s for s in Store.objects.filter(pk__in={c[0] for c in combos})
        }

        updated = skipped = created = 0

        for sid, year, week_number in combos:
            store = store_map.get(sid)
            if not store:
                continue

            existing = swr_map.get((sid, year, week_number))

            if existing and not force:
                has_changes = Review.objects.filter(
                    store_id=sid,
                    review_date__week=week_number,
                ).filter(
                    Q(created_at__gt=existing.updated_at)
                    | Q(updated_at__gt=existing.updated_at)
                    | Q(deleted_at__gt=existing.updated_at)
                    | Q(blinded_at__gt=existing.updated_at)
                ).exists()

                if not has_changes:
                    skipped += 1
                    continue

            active_reviews = list(
                Review.objects.filter(
                    store_id=sid,
                    review_date__week=week_number,
                    is_deleted=False,
                    is_blinded=False,
                )
            )

            if not active_reviews and existing:
                existing.count = 0
                existing.average = 0.0
                existing.positive_count = 0
                existing.negative_count = 0
                existing.neutral_count = 0
                existing.save()
                ShopWeekSentimentReveiw.objects.create(
                    shop_week_review=existing,
                    sentiment="neutral",
                    content="",
                    created_at=existing.updated_at,
                )
                updated += 1
                self.stdout.write(f"  [갱신] {store.name} {year}-W{week_number:02d} — 활성 리뷰 0건")
                continue

            stats = self._calc_stats(active_reviews)
            summary_text, _ = self._generate_summary(store, week_number, active_reviews, stats)

            if existing is None:
                swr = ShopWeekReview.objects.create(
                    shop=store,
                    year=year,
                    week_number=week_number,
                    count=stats["count"],
                    average=stats["average"],
                    positive_count=stats["positive_count"],
                    negative_count=stats["negative_count"],
                    neutral_count=stats["neutral_count"],
                )
                created += 1
                self.stdout.write(self.style.SUCCESS(
                    f"  [신규] {store.name} {year}-W{week_number:02d} — {stats['count']}건"
                ))
            else:
                swr = existing
                swr.count = stats["count"]
                swr.average = stats["average"]
                swr.positive_count = stats["positive_count"]
                swr.negative_count = stats["negative_count"]
                swr.neutral_count = stats["neutral_count"]
                swr.save()
                updated += 1
                self.stdout.write(f"  [갱신] {store.name} {year}-W{week_number:02d} — {stats['count']}건")

            ShopWeekSentimentReveiw.objects.create(
                shop_week_review=swr,
                sentiment="neutral",
                content=summary_text,
                created_at=swr.updated_at,
            )

            swr.review_keywords.all().delete()
            for word, cnt in stats["keyword_counts"].items():
                keyword_obj, _ = Keyword.objects.get_or_create(word=word)
                ShopWeekReviewKeyword.objects.create(
                    shop_week_review=swr,
                    keyword=keyword_obj,
                    count=cnt,
                )

        self.stdout.write(self.style.SUCCESS(
            f"\n완료: 신규 {created}건, 갱신 {updated}건, 스킵 {skipped}건"
        ))

    def _calc_stats(self, active_reviews):
        ratings = [r.rating for r in active_reviews]
        average = round(sum(ratings) / len(ratings), 1) if ratings else 0.0

        sentiments = defaultdict(int)
        for r in active_reviews:
            sentiments[r.sentiment] += 1

        keyword_counts = defaultdict(int)
        for r in active_reviews:
            for kw in r.keywords:
                keyword_counts[kw] += 1

        return {
            "count": len(active_reviews),
            "average": average,
            "positive_count": sentiments.get("positive", 0),
            "negative_count": sentiments.get("negative", 0),
            "neutral_count": sentiments.get("neutral", 0),
            "keyword_counts": dict(keyword_counts),
        }

    def _generate_summary(self, store, week_number, active_reviews, stats):
        api_key = getattr(settings, "GEMINI_API_KEY", None)
        review_texts = [r.content for r in active_reviews]

        if api_key:
            return self._generate_with_gemini(
                api_key, store.name, week_number, review_texts,
                stats["average"], stats["positive_count"], stats["negative_count"],
            )
        return self._generate_dummy(store.name, week_number, stats), None

    def _generate_with_gemini(self, api_key, store_name, week_number, review_texts, average, pos, neg):
        try:
            import google.generativeai as genai

            reviews_block = "\n".join(f"- {text}" for text in review_texts[:30])

            prompt = f"""다음은 '{store_name}'의 {week_number}주차 리뷰들입니다.

리뷰 목록:
{reviews_block}

통계:
- 평균 평점: {average}/5.0

3-4문장의 종합 요약을 작성해주세요."""

            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(
                model_name="gemini-2.0-flash",
                system_instruction="당신은 음식점 리뷰 분석 전문가입니다. 한국어로 응답하세요.",
            )
            response = model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.7,
                    max_output_tokens=300,
                ),
            )
            return response.text, None

        except Exception as e:
            self.stderr.write(f"Gemini API 오류: {e} — 더미 요약으로 대체")
            return self._generate_dummy(store_name, week_number, {
                "average": average,
                "positive_count": pos,
                "negative_count": neg,
                "neutral_count": 0,
                "keyword_counts": {},
            }), None

    def _generate_dummy(self, store_name, week_number, stats):
        pos = stats["positive_count"]
        neg = stats["negative_count"]
        total = (pos + neg + stats.get("neutral_count", 0)) or 1
        kw_text = ", ".join(list(stats.get("keyword_counts", {}).keys())[:3]) or "맛, 서비스, 배달"
        return (
            f"{store_name}의 {week_number}주차 리뷰 분석 결과, "
            f"평균 평점 {stats['average']}점으로 "
            f"긍정 리뷰가 {round(pos/total*100)}%, "
            f"부정 리뷰가 {round(neg/total*100)}%를 차지합니다. "
            f"주요 키워드는 '{kw_text}'입니다."
        )
