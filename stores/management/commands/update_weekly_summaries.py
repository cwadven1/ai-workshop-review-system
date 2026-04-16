"""
증분 업데이트 커맨드: ShopWeekReview / ShopWeekSentimentReveiw를 변경된 리뷰만 감지해서 재계산.

변경 감지 기준 (OR):
  - Review.created_at  > ShopWeekReview.updated_at  (새 리뷰)
  - Review.updated_at  > ShopWeekReview.updated_at  (수정된 리뷰)
  - Review.deleted_at  > ShopWeekReview.updated_at  (삭제된 리뷰)
  - Review.blinded_at  > ShopWeekReview.updated_at  (블라인드된 리뷰)

재계산 시 카운트:
  - is_deleted=False AND is_blinded=False 인 리뷰만 집계
"""

from collections import defaultdict

from django.core.management.base import BaseCommand
from django.db.models import Q

from reviews.models import Review
from stores.models import Keyword, ShopWeekReview, ShopWeekSentimentReveiw, ShopWeekReviewKeyword, Store


class Command(BaseCommand):
    help = "ShopWeekReview 증분 업데이트 (변경된 리뷰가 있는 가게/주차만 재계산)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--store-id",
            type=int,
            help="특정 가게 ID만 처리 (생략 시 전체)",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="변경 감지 없이 전체 강제 재계산",
        )

    def handle(self, *args, **options):
        store_qs = Store.objects.all()
        if options["store_id"]:
            store_qs = store_qs.filter(pk=options["store_id"])

        force = options["force"]
        total_updated = 0
        total_skipped = 0
        total_created = 0

        for store in store_qs:
            # review_date 기준 (year, week_number) 조합 추출
            review_dates = (
                Review.objects.filter(store=store)
                .values_list('review_date', flat=True)
                .distinct()
            )
            year_week_pairs = set()
            for d in review_dates:
                iso = d.isocalendar()
                year_week_pairs.add((iso[0], iso[1]))

            for year, week_number in sorted(year_week_pairs):
                result = self._sync_shop_week_review(store, year, week_number, force)
                if result == "created":
                    total_created += 1
                elif result == "updated":
                    total_updated += 1
                else:
                    total_skipped += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"완료: 신규 생성 {total_created}건 / 재계산 {total_updated}건 / 변경없음 스킵 {total_skipped}건"
            )
        )

    def _sync_shop_week_review(self, store, year, week_number, force):
        swr = ShopWeekReview.objects.filter(
            shop=store, year=year, week_number=week_number
        ).first()

        if swr is None:
            active_reviews = list(
                Review.objects.filter(
                    store=store,
                    review_date__week=week_number,
                    is_deleted=False,
                    is_blinded=False,
                )
            )
            swr = self._upsert(store, year, week_number, active_reviews, existing=None)
            self.stdout.write(f"  [신규] {store.name} {year}-W{week_number:02d} (리뷰 {len(active_reviews)}건)")
            return "created"

        if not force:
            has_changes = Review.objects.filter(
                store=store,
                review_date__week=week_number,
            ).filter(
                Q(created_at__gt=swr.updated_at)
                | Q(updated_at__gt=swr.updated_at)
                | Q(deleted_at__gt=swr.updated_at)
                | Q(blinded_at__gt=swr.updated_at)
            ).exists()

            if not has_changes:
                return "skipped"

        active_reviews = list(
            Review.objects.filter(
                store=store,
                review_date__week=week_number,
                is_deleted=False,
                is_blinded=False,
            )
        )
        self._upsert(store, year, week_number, active_reviews, existing=swr)
        self.stdout.write(f"  [갱신] {store.name} {year}-W{week_number:02d} (활성 리뷰 {len(active_reviews)}건)")
        return "updated"

    def _upsert(self, store, year, week_number, active_reviews, existing):
        ratings = [r.rating for r in active_reviews]
        average = round(sum(ratings) / len(ratings), 1) if ratings else 0.0

        sentiments = defaultdict(int)
        for r in active_reviews:
            sentiments[r.sentiment] += 1

        keyword_counts = defaultdict(int)
        for r in active_reviews:
            for kw in r.keywords:
                keyword_counts[kw] += 1

        pos = sentiments.get("positive", 0)
        neg = sentiments.get("negative", 0)
        total = sum(sentiments.values()) or 1
        kw_text = ", ".join(list(keyword_counts.keys())[:3])
        summary_text = (
            f"{store.name}의 {week_number}주차 리뷰 분석 결과, "
            f"평균 평점 {average}점으로 "
            f"긍정 {round(pos/total*100)}%, 부정 {round(neg/total*100)}%를 차지합니다. "
            f"주요 키워드: '{kw_text}'"
        ) if active_reviews else ""

        if existing is None:
            swr = ShopWeekReview.objects.create(
                shop=store,
                year=year,
                week_number=week_number,
                count=len(active_reviews),
                average=average,
                positive_count=sentiments.get("positive", 0),
                negative_count=sentiments.get("negative", 0),
                neutral_count=sentiments.get("neutral", 0),
                summary=summary_text,
            )
        else:
            swr = existing
            swr.count = len(active_reviews)
            swr.average = average
            swr.positive_count = sentiments.get("positive", 0)
            swr.negative_count = sentiments.get("negative", 0)
            swr.neutral_count = sentiments.get("neutral", 0)
            swr.summary = summary_text
            swr.save()

        # positive/negative/neutral 3개 sentiment 레코드 insert (delete 없이 append)
        pos_reviews = [r for r in active_reviews if r.sentiment == "positive"]
        neg_reviews = [r for r in active_reviews if r.sentiment == "negative"]

        pos_kws = list(dict.fromkeys(kw for r in pos_reviews for kw in r.keywords))[:3]
        neg_kws = list(dict.fromkeys(kw for r in neg_reviews for kw in r.keywords))[:3]

        if pos_reviews:
            pos_content = (
                f"{store.name}의 {week_number}주차 긍정 리뷰 분석: "
                f"총 {len(pos_reviews)}건의 긍정 리뷰가 접수되었습니다. "
                f"주요 키워드는 '{', '.join(pos_kws)}'이(가) 언급되었으며, "
                f"맛, 서비스, 가성비에 대한 만족도가 높았습니다."
            )
        else:
            pos_content = f"{store.name}의 {week_number}주차 긍정 리뷰가 없습니다."

        if neg_reviews:
            neg_content = (
                f"{store.name}의 {week_number}주차 부정 리뷰 분석: "
                f"총 {len(neg_reviews)}건의 부정 리뷰가 접수되었습니다. "
                f"주요 불만 키워드는 '{', '.join(neg_kws)}'이(가) 언급되었으며, "
                f"개선이 필요한 영역으로 파악됩니다."
            )
        else:
            neg_content = f"{store.name}의 {week_number}주차 부정 리뷰가 없습니다."

        ShopWeekSentimentReveiw.objects.create(
            shop_week_review=swr,
            sentiment="positive",
            content=pos_content,
            created_at=swr.updated_at,
        )
        ShopWeekSentimentReveiw.objects.create(
            shop_week_review=swr,
            sentiment="negative",
            content=neg_content,
            created_at=swr.updated_at,
        )
        ShopWeekSentimentReveiw.objects.create(
            shop_week_review=swr,
            sentiment="neutral",
            content=summary_text,
            created_at=swr.updated_at,
        )

        # 키워드 재집계
        swr.review_keywords.all().delete()
        for word, cnt in keyword_counts.items():
            keyword_obj, _ = Keyword.objects.get_or_create(word=word)
            ShopWeekReviewKeyword.objects.create(
                shop_week_review=swr,
                keyword=keyword_obj,
                count=cnt,
            )

        return swr
