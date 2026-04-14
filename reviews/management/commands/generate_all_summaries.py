from django.core.management.base import BaseCommand

from reviews.models import Review, WeeklySummary
from stores.models import Store


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

        # 처리 대상 (store, year_week) 조합 조회
        qs = (
            Review.objects.values("store", "year_week")
            .distinct()
            .order_by("store", "year_week")
        )
        if store_id:
            qs = qs.filter(store_id=store_id)

        combos = list(qs)

        if not combos:
            self.stdout.write("처리할 리뷰가 없습니다.")
            return

        # force가 아닐 경우 이미 summary가 있는 조합 제외
        if not force:
            existing = set(
                WeeklySummary.objects.values_list("store_id", "year_week")
            )
            combos = [
                c for c in combos if (c["store"], c["year_week"]) not in existing
            ]

        total = len(combos)
        if total == 0:
            self.stdout.write("처리할 항목이 없습니다. (--force 옵션으로 재생성 가능)")
            return

        self.stdout.write(f"총 {total}개 (store, year_week) 조합을 처리합니다.")

        # generate_summaries Command 재사용
        from reviews.management.commands.generate_summaries import (
            Command as GenerateSummariesCommand,
        )

        sub_cmd = GenerateSummariesCommand(stdout=self.stdout, stderr=self.stderr)

        for idx, combo in enumerate(combos, start=1):
            s_id = combo["store"]
            year_week = combo["year_week"]

            try:
                store = Store.objects.get(pk=s_id)
            except Store.DoesNotExist:
                self.stderr.write(f"가게 ID {s_id}를 찾을 수 없습니다. 건너뜁니다.")
                continue

            self.stdout.write(f"{idx}/{total} 처리 중: {store.name} {year_week}")
            sub_cmd.handle(store_id=s_id, year_week=year_week)
            self.stdout.write(
                self.style.SUCCESS(f"{idx}/{total} 완료: {store.name} {year_week}")
            )

        self.stdout.write(self.style.SUCCESS(f"\n전체 {total}개 요약 생성 완료."))
