from django.core.management.base import BaseCommand

from reviews.models import Review
from stores.models import ShopWeekReview, Store


class Command(BaseCommand):
    help = "모든 가게의 모든 주차 리뷰를 일괄 요약 생성"

    def add_arguments(self, parser):
        parser.add_argument(
            "--store_id", type=int, required=False, help="특정 가게 ID만 처리"
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="이미 summary가 있어도 재생성",
        )

    def handle(self, *args, **options):
        store_id = options.get("store_id")
        force = options["force"]

        # (store_id, year, week_number) 조합 추출
        qs = (
            Review.objects.values("store_id", "review_date", "week")
            .distinct()
            .order_by("store_id", "review_date")
        )
        if store_id:
            qs = qs.filter(store_id=store_id)

        combo_set = set()
        for row in qs:
            iso = row["review_date"].isocalendar()
            combo_set.add((row["store_id"], iso[0], iso[1]))
        combos = sorted(combo_set)

        if not combos:
            self.stdout.write("처리할 리뷰가 없습니다.")
            return

        if not force:
            existing = set(
                ShopWeekReview.objects.values_list("shop_id", "year", "week_number")
            )
            combos = [c for c in combos if c not in existing]

        total = len(combos)
        if total == 0:
            self.stdout.write("처리할 항목이 없습니다. (--force 옵션으로 재생성 가능)")
            return

        self.stdout.write(f"총 {total}개 (shop, year, week_number) 조합을 처리합니다.")

        from reviews.management.commands.generate_summaries import (
            Command as GenerateSummariesCommand,
        )

        sub_cmd = GenerateSummariesCommand(stdout=self.stdout, stderr=self.stderr)

        for idx, (s_id, year, week_number) in enumerate(combos, start=1):
            try:
                store = Store.objects.get(pk=s_id)
            except Store.DoesNotExist:
                self.stderr.write(f"가게 ID {s_id}를 찾을 수 없습니다. 건너뜁니다.")
                continue

            self.stdout.write(f"{idx}/{total} 처리 중: {store.name} {year}-W{week_number:02d}")
            sub_cmd.handle(store_id=s_id, week=week_number)
            self.stdout.write(self.style.SUCCESS(
                f"{idx}/{total} 완료: {store.name} {year}-W{week_number:02d}"
            ))

        self.stdout.write(self.style.SUCCESS(f"\n전체 {total}개 요약 생성 완료."))
