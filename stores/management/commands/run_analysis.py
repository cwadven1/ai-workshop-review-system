from django.core.management.base import BaseCommand, CommandError

from stores.models import Store
from stores.tasks import run_store_analysis


class Command(BaseCommand):
    help = "AI 분석을 수동으로 실행합니다 (--store-id 생략 시 전체 가게)"

    def add_arguments(self, parser):
        parser.add_argument("--store-id", type=int, help="특정 가게 ID")
        parser.add_argument(
            "--sync",
            action="store_true",
            help="Celery 큐 없이 동기 실행 (개발/테스트용)",
        )

    def handle(self, *args, **options):
        store_id = options.get("store_id")
        sync = options.get("sync", False)

        if store_id:
            if not Store.objects.filter(pk=store_id).exists():
                raise CommandError(f"Store id={store_id} 가 존재하지 않습니다.")
            store_ids = [store_id]
        else:
            store_ids = list(Store.objects.values_list("pk", flat=True))

        mode = "동기 실행" if sync else "Celery 큐 등록"
        self.stdout.write(f"{len(store_ids)}개 가게 AI 분석 {mode} 시작...")

        for sid in store_ids:
            if sync:
                run_store_analysis(sid, triggered_by="manual")
                self.stdout.write(f"  ✓ store_id={sid} 완료")
            else:
                run_store_analysis.delay(sid, triggered_by="manual")
                self.stdout.write(f"  → store_id={sid} 큐 등록")

        self.stdout.write(self.style.SUCCESS("완료"))
