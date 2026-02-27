import random
from collections import defaultdict
from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from reviews.models import MonthlySummary, Review
from stores.models import Menu, Store

# 최근 12개월 연월 리스트 생성
def get_recent_months(count=12):
    today = date.today()
    months = []
    for i in range(count - 1, -1, -1):
        d = today.replace(day=1) - timedelta(days=i * 30)
        ym = d.strftime("%Y-%m")
        if ym not in months:
            months.append(ym)
    # 중복 제거 후 정확히 count개 보장
    if len(months) < count:
        first = date.fromisoformat(months[0] + "-01")
        while len(months) < count:
            first = (first.replace(day=1) - timedelta(days=1)).replace(day=1)
            months.insert(0, first.strftime("%Y-%m"))
    return months[-count:]


STORES_DATA = [
    {
        "name": "엄마손 한식당",
        "category": "korean",
        "address": "서울시 강남구 역삼동 123-4",
        "phone": "02-1234-5678",
        "image_url": "",
        "menus": [
            {"name": "된장찌개", "price": 8000, "is_popular": False, "description": ""},
            {"name": "비빔밥", "price": 9000, "is_popular": True, "description": ""},
            {"name": "불고기", "price": 12000, "is_popular": True, "description": ""},
            {"name": "김치찌개", "price": 8000, "is_popular": False, "description": ""},
        ],
        # 꾸준히 좋은 가게
        "rating_pattern": [4.0, 4.1, 4.2, 4.3, 4.1, 4.2, 4.2, 4.3, 4.1, 4.4, 4.5, 4.6],
    },
    {
        "name": "스시 오마카세 쿄",
        "category": "japanese",
        "address": "서울시 마포구 연남동 456-7",
        "phone": "02-2345-6789",
        "image_url": "",
        "menus": [
            {"name": "런치 오마카세", "price": 45000, "is_popular": True, "description": ""},
            {"name": "디너 오마카세", "price": 85000, "is_popular": True, "description": ""},
            {"name": "유부초밥", "price": 12000, "is_popular": False, "description": ""},
        ],
        # 셰프 교체 시나리오: 악평 → 호평
        "rating_pattern": [2.8, 2.5, 2.3, 2.1, 1.8, 2.0, 2.5, 2.8, 3.5, 4.2, 4.5, 4.6],
    },
    {
        "name": "파스타 팩토리",
        "category": "western",
        "address": "서울시 서초구 반포동 789-0",
        "phone": "02-3456-7890",
        "image_url": "",
        "menus": [
            {"name": "까르보나라", "price": 14000, "is_popular": True, "description": ""},
            {"name": "봉골레", "price": 13000, "is_popular": False, "description": ""},
            {"name": "리조또", "price": 13000, "is_popular": False, "description": ""},
            {"name": "티라미수", "price": 7000, "is_popular": False, "description": ""},
        ],
        # 셰프 교체 시나리오: 악평 → 호평 (더 극적)
        "rating_pattern": [3.0, 2.5, 2.2, 1.8, 2.0, 1.7, 2.0, 2.5, 3.2, 3.8, 4.3, 4.7],
    },
    {
        "name": "황금 짜장",
        "category": "chinese",
        "address": "서울시 중구 을지로 321-5",
        "phone": "02-4567-8901",
        "image_url": "",
        "menus": [
            {"name": "짜장면", "price": 7000, "is_popular": True, "description": ""},
            {"name": "짬뽕", "price": 8000, "is_popular": False, "description": ""},
            {"name": "탕수육", "price": 18000, "is_popular": True, "description": ""},
            {"name": "볶음밥", "price": 8000, "is_popular": False, "description": ""},
        ],
        # 완만하게 하락하는 가게
        "rating_pattern": [4.5, 4.4, 4.3, 4.5, 4.3, 4.0, 3.8, 3.5, 3.9, 3.8, 3.5, 3.3],
    },
    {
        "name": "바삭치킨",
        "category": "chicken",
        "address": "서울시 송파구 잠실동 654-2",
        "phone": "02-5678-9012",
        "image_url": "",
        "menus": [
            {"name": "후라이드치킨", "price": 18000, "is_popular": True, "description": ""},
            {"name": "양념치킨", "price": 19000, "is_popular": True, "description": ""},
            {"name": "반반", "price": 19000, "is_popular": False, "description": ""},
            {"name": "치킨무", "price": 1000, "is_popular": False, "description": ""},
        ],
        # 안정적인 중상위
        "rating_pattern": [3.7, 3.8, 3.9, 3.8, 3.9, 4.0, 3.9, 3.8, 4.0, 3.9, 4.1, 4.0],
    },
    {
        "name": "맛있는 돈까스",
        "category": "japanese",
        "address": "서울시 용산구 이태원동 111-2",
        "phone": "02-6789-0123",
        "image_url": "",
        "menus": [
            {"name": "로스카츠", "price": 11000, "is_popular": True, "description": ""},
            {"name": "치즈카츠", "price": 12000, "is_popular": True, "description": ""},
            {"name": "새우카츠", "price": 13000, "is_popular": False, "description": ""},
            {"name": "카레돈까스", "price": 12000, "is_popular": False, "description": ""},
        ],
        "rating_pattern": [3.8, 3.5, 2.8, 2.1, 1.5, 1.8, 2.3, 3.0, 3.8, 4.3, 4.6, 4.8],
        "review_override": 100,
    },
    {
        "name": "소문난 떡볶이",
        "category": "korean",
        "address": "서울시 마포구 망원동 222-3",
        "phone": "02-7890-1234",
        "image_url": "",
        "menus": [
            {"name": "국물떡볶이", "price": 6000, "is_popular": True, "description": ""},
            {"name": "로제떡볶이", "price": 7000, "is_popular": True, "description": ""},
            {"name": "튀김", "price": 4000, "is_popular": False, "description": ""},
            {"name": "순대", "price": 4000, "is_popular": False, "description": ""},
        ],
        # SNS 바이럴 시나리오:
        # 1~4월: 동네 떡볶이집, 리뷰 2~4개, 평점 3.3~3.6 (평범)
        # 5월: 틱톡/인스타 바이럴 → 리뷰 28개 폭증, 평점 4.2 (기대감 높음)
        # 6월: 바이럴 정점 → 리뷰 35개, 평점 4.5 (호평 최고)
        # 7월: 여전히 많음 → 25개, 평점 4.3
        # 8월: 줄어들기 시작 → 12개, 평점 3.9 (기대 대비 실망 리뷰 등장)
        # 9~12월: 다시 동네 떡볶이집 → 3~8개, 평점 3.4~3.7
        "rating_pattern": [3.5, 3.3, 3.6, 3.4, 4.2, 4.5, 4.3, 3.9, 3.7, 3.5, 3.6, 3.4],
        "review_counts_override": [3, 2, 4, 3, 28, 35, 25, 12, 8, 5, 4, 3],  # 총 132개, 5~6월에 몰림
    },
]


# 리뷰 내용 템플릿
POSITIVE_REVIEWS = {
    "korean": [
        "된장찌개가 정말 깊은 맛이에요. 집밥 느낌 그대로!",
        "제육볶음 양도 많고 맛도 최고. 직장인 점심으로 딱이에요.",
        "반찬이 정말 푸짐하고 맛있어요. 재방문 의사 100%!",
        "불고기가 입에서 살살 녹아요. 가격 대비 최고입니다.",
        "어머니가 해주시는 것 같은 따뜻한 맛이에요.",
        "항상 한결같은 맛이라 믿고 주문해요.",
        "배달도 빠르고 음식도 따끈따끈하게 왔어요.",
        "로제 떡볶이 크림소스가 환상적이에요! SNS에서 보고 왔는데 대만족",
        "떡볶이인데 이렇게 고급스러운 맛이 나다니! 인생 떡볶이",
        "순대도 찰지고 튀김도 바삭해요. 세트 메뉴 강추!",
        "틱톡에서 유명하길래 왔는데 진짜 맛있어요. 줄 서서 먹을 만함",
        "치즈 김밥이 의외로 떡볶이랑 완벽 조합이에요",
    ],
    "japanese": [
        "신선한 네타에 셰프의 정성이 느껴집니다.",
        "런치 오마카세 가성비가 미쳤어요. 이 가격에 이 퀄리티!",
        "사시미 신선도가 정말 좋아요. 입안에서 녹아요.",
        "우동 국물이 깊고 시원해요. 면도 쫄깃!",
        "분위기도 좋고 음식도 좋고, 특별한 날에 딱이에요.",
        "셰프가 바뀌고 나서 퀄리티가 확 올라갔어요!",
        "새 셰프분이 오시고 나서 완전 다른 가게가 됐어요.",
        "등심 돈까스가 두툼하고 바삭해요! 소스도 일품",
        "히레 돈까스 부드러움이 미쳤어요. 입에서 녹아요",
        "새 셰프 오시고 나서 튀김옷이 확 달라졌어요",
        "치즈 돈까스 치즈가 쭉쭉 늘어나요. 최고!",
        "카레도 직접 만드시는데 깊은 맛이에요",
        "리뉴얼 후 완전 맛집 됐어요! 매일 가고 싶은",
    ],
    "western": [
        "까르보나라 크림 소스가 진짜 부드럽고 맛있어요!",
        "파스타 면이 알덴테로 딱 좋았어요.",
        "피자 도우가 얇고 바삭해서 맛있어요.",
        "셰프가 바뀌고 나서 맛이 확 좋아졌어요! 완전 달라짐.",
        "새로운 메뉴들이 추가되면서 맛집이 됐네요.",
        "리뉴얼 후 재방문했는데 완전 다른 가게 같아요!",
        "요즘 여기 파스타가 동네 최고라고 소문났어요.",
    ],
    "chinese": [
        "짜장면 춘장 맛이 깊어요. 옛날 맛 그대로!",
        "탕수육 바삭함이 살아있어요. 배달인데도!",
        "짬뽕 국물이 얼큰하고 시원해요. 해장에 딱!",
        "볶음밥도 맛있고 양이 넉넉해요.",
        "가격도 착하고 맛도 좋아서 자주 시켜먹어요.",
    ],
    "chicken": [
        "후라이드 바삭함이 최고에요. 맥주 안주로 딱!",
        "양념치킨 소스가 달달하면서 매콤해요.",
        "치킨이 정말 크고 살이 통통해요.",
        "배달 빠르고 치킨도 바삭바삭!",
        "간장치킨이 짭짤하면서 고소해요. 중독성 있음!",
    ],
}

NEGATIVE_REVIEWS = {
    "korean": [
        "음식이 너무 짜요. 건강 생각하면 좀...",
        "배달이 늦어서 음식이 식었어요.",
        "양이 좀 적은 것 같아요. 가격 대비 아쉬움.",
        "SNS 보고 기대했는데 그냥 평범한 떡볶이에요",
        "줄이 너무 길어요. 40분 기다렸는데 그만큼의 맛은 아님",
        "양이 적어요. 가격 대비 아쉬움. SNS 마케팅만 잘하는 듯",
    ],
    "japanese": [
        "네타가 신선하지 않았어요. 비린내가 남.",
        "가격에 비해 양이 너무 적어요.",
        "서비스가 불친절했어요. 기분 나빴음.",
        "회가 신선하지 않고 질겼어요. 실망.",
        "이 가격 주고 먹을 퀄리티가 아닙니다.",
        "돈까스가 기름에 절은 느낌이에요. 느끼함",
        "고기가 질기고 튀김옷이 눅눅했어요",
        "예전 셰프가 나가고 맛이 확 떨어졌어요",
        "이 가격에 이 퀄리티는 실망입니다",
        "소스가 달기만 하고 깊은 맛이 없어요",
    ],
    "western": [
        "파스타가 퍼져서 왔어요. 배달 문제인지...",
        "소스가 너무 느끼해요. 크림이 과하게 들어간 느낌.",
        "맛이 예전만 못해요. 셰프가 바뀐 건지...",
        "이 가격이면 다른 데서 더 맛있게 먹을 수 있어요.",
        "면이 불어서 왔고 소스도 밍밍했어요.",
    ],
    "chinese": [
        "짜장면이 너무 달아요. 설탕을 왜 이렇게 많이...",
        "양이 줄었어요. 예전엔 이렇지 않았는데.",
        "배달 시간이 너무 오래 걸려요.",
        "탕수육이 눅눅해서 실망이에요.",
        "최근에 맛이 변한 것 같아요. 아쉽습니다.",
    ],
    "chicken": [
        "치킨이 좀 기름져요. 소스도 아쉬움.",
        "배달이 좀 늦었어요. 1시간 넘게 기다림.",
        "양이 좀 적은 느낌이에요.",
    ],
}

NEUTRAL_REVIEWS = [
    "보통이에요. 나쁘지 않지만 특별하지도 않은.",
    "무난한 맛이에요. 그냥 평범합니다.",
    "가격 대비 괜찮은 편이에요.",
    "배달은 빨랐는데 맛은 그저 그래요.",
    "한 번쯤은 먹을 만한데 재주문은 모르겠어요.",
]

KEYWORDS_MAP = {
    "positive": {
        "korean": ["맛있는", "푸짐한", "집밥", "양많은", "재방문"],
        "japanese": ["신선한", "가성비", "오마카세", "퀄리티", "셰프"],
        "western": ["크림소스", "알덴테", "바삭한", "리뉴얼", "맛집"],
        "chinese": ["깊은맛", "바삭한", "시원한", "가성비", "양많은"],
        "chicken": ["바삭한", "매콤한", "푸짐한", "맥주안주", "고소한"],
    },
    "negative": {
        "korean": ["짠맛", "배달늦음", "양적음", "식은음식"],
        "japanese": ["비린내", "불친절", "양적음", "비싼", "신선도"],
        "western": ["느끼한", "퍼진면", "밍밍한", "비싼", "불어서"],
        "chinese": ["달달한", "양줄음", "배달늦음", "눅눅한", "맛변함"],
        "chicken": ["기름진", "배달늦음", "양적음"],
    },
}


class Command(BaseCommand):
    help = "시드 데이터 생성: 가게, 메뉴, 리뷰, 월별 요약"

    def handle(self, *args, **options):
        self.stdout.write("기존 데이터 삭제 중...")
        MonthlySummary.objects.all().delete()
        Review.objects.all().delete()
        Menu.objects.all().delete()
        Store.objects.all().delete()

        months = get_recent_months(12)
        self.stdout.write(f"대상 월: {months}")

        for store_data in STORES_DATA:
            store = Store.objects.create(
                name=store_data["name"],
                category=store_data["category"],
                address=store_data["address"],
                phone=store_data["phone"],
                image_url=store_data["image_url"],
            )
            self.stdout.write(f"  가게 생성: {store.name}")

            for menu_data in store_data["menus"]:
                Menu.objects.create(store=store, **menu_data)

            # 월별 리뷰 생성
            all_reviews = []
            pattern = store_data["rating_pattern"]

            # 월별 리뷰 수 결정
            if "review_counts_override" in store_data:
                # 월별 리뷰 수 직접 지정
                review_counts_per_month = store_data["review_counts_override"]
            elif "review_override" in store_data:
                # 총 리뷰 수 균등 분배
                total_target = store_data["review_override"]
                base = total_target // len(months)
                remainder = total_target % len(months)
                review_counts_per_month = [base + (1 if i < remainder else 0) for i in range(len(months))]
            else:
                # 기본: 랜덤
                review_counts_per_month = [random.randint(7, 12) for _ in range(len(months))]

            for i, ym in enumerate(months):
                target_rating = pattern[i]
                review_count = review_counts_per_month[i]

                monthly_reviews = []
                for j in range(review_count):
                    rating = self._generate_rating(target_rating)
                    sentiment, content, keywords = self._generate_review_content(
                        store_data["category"], rating
                    )
                    year, month_num = ym.split("-")
                    day = random.randint(1, 28)
                    review_date = date(int(year), int(month_num), day)

                    review = Review.objects.create(
                        store=store,
                        rating=rating,
                        content=content,
                        sentiment=sentiment,
                        sentiment_score=self._sentiment_score(sentiment),
                        keywords=keywords,
                        year_month=ym,
                        review_date=review_date,
                        source="yogiyo",
                    )
                    monthly_reviews.append(review)
                    all_reviews.append(review)

                # 월별 요약 생성
                self._create_monthly_summary(store, ym, monthly_reviews, pattern, i)

            # 가게 전체 평균 업데이트
            total = len(all_reviews)
            avg = sum(r.rating for r in all_reviews) / total if total else 0
            store.avg_rating = round(avg, 1)
            store.total_review_count = total
            store.save()

        self.stdout.write(self.style.SUCCESS("시드 데이터 생성 완료!"))
        self.stdout.write(f"  가게: {Store.objects.count()}개")
        self.stdout.write(f"  리뷰: {Review.objects.count()}개")
        self.stdout.write(f"  월별 요약: {MonthlySummary.objects.count()}개")

    def _generate_rating(self, target):
        """타겟 평점 주변으로 랜덤 평점 생성"""
        r = target + random.uniform(-1.0, 1.0)
        return max(1, min(5, round(r)))

    def _generate_review_content(self, category, rating):
        """평점에 따라 리뷰 내용, 감정, 키워드 생성"""
        if rating >= 4:
            sentiment = "positive"
            reviews = POSITIVE_REVIEWS.get(category, POSITIVE_REVIEWS["korean"])
            content = random.choice(reviews)
            kw_pool = KEYWORDS_MAP["positive"].get(
                category, KEYWORDS_MAP["positive"]["korean"]
            )
        elif rating <= 2:
            sentiment = "negative"
            reviews = NEGATIVE_REVIEWS.get(category, NEGATIVE_REVIEWS["korean"])
            content = random.choice(reviews)
            kw_pool = KEYWORDS_MAP["negative"].get(
                category, KEYWORDS_MAP["negative"]["korean"]
            )
        else:
            sentiment = "neutral"
            content = random.choice(NEUTRAL_REVIEWS)
            kw_pool = ["보통", "무난한", "평범한"]

        keywords = random.sample(kw_pool, min(3, len(kw_pool)))
        return sentiment, content, keywords

    def _sentiment_score(self, sentiment):
        if sentiment == "positive":
            return round(random.uniform(0.6, 1.0), 2)
        elif sentiment == "negative":
            return round(random.uniform(-1.0, -0.4), 2)
        return round(random.uniform(-0.3, 0.3), 2)

    def _create_monthly_summary(self, store, year_month, reviews, pattern, month_idx):
        """월별 요약 데이터 생성"""
        ratings = [r.rating for r in reviews]
        avg_rating = round(sum(ratings) / len(ratings), 1) if ratings else 0

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

        rating_change = 0.0
        if month_idx > 0:
            rating_change = round(pattern[month_idx] - pattern[month_idx - 1], 1)

        summary_text = self._generate_dummy_summary(
            store, year_month, avg_rating, sentiments, top_keywords, rating_change
        )

        highlights = self._generate_highlights(sentiments, top_keywords, rating_change)

        MonthlySummary.objects.create(
            store=store,
            year_month=year_month,
            summary=summary_text,
            highlights=highlights,
            avg_rating=avg_rating,
            review_count=len(reviews),
            sentiment_distribution=dict(sentiments),
            top_keywords=top_keywords,
            rating_change=rating_change,
        )

    def _generate_dummy_summary(
        self, store, year_month, avg_rating, sentiments, top_keywords, rating_change
    ):
        """더미 AI 요약 텍스트 생성"""
        pos = sentiments.get("positive", 0)
        neg = sentiments.get("negative", 0)
        total = sum(sentiments.values()) or 1

        kw_text = ", ".join(kw["keyword"] for kw in top_keywords[:3])

        if rating_change > 0.5:
            trend_text = "전월 대비 크게 상승한 평점으로 긍정적인 변화가 감지됩니다."
        elif rating_change > 0:
            trend_text = "전월 대비 소폭 상승하여 안정적인 호평을 유지하고 있습니다."
        elif rating_change < -0.5:
            trend_text = "전월 대비 평점이 하락하여 개선이 필요한 시점입니다."
        elif rating_change < 0:
            trend_text = "전월 대비 소폭 하락하였으나 큰 변동은 없습니다."
        else:
            trend_text = "전월과 비슷한 수준을 유지하고 있습니다."

        return (
            f"{store.name}의 {year_month} 리뷰 분석 결과, "
            f"평균 평점 {avg_rating}점으로 "
            f"긍정 리뷰가 {round(pos/total*100)}%, "
            f"부정 리뷰가 {round(neg/total*100)}%를 차지합니다. "
            f"{trend_text} "
            f"주요 키워드는 '{kw_text}'이(가) 언급되었습니다."
        )

    def _generate_highlights(self, sentiments, top_keywords, rating_change):
        """하이라이트 데이터 생성"""
        pos = sentiments.get("positive", 0)
        neg = sentiments.get("negative", 0)
        total = sum(sentiments.values()) or 1

        good_points = []
        bad_points = []

        if pos / total > 0.5:
            good_points.append("전반적으로 긍정적인 평가가 우세합니다.")
        if rating_change > 0:
            good_points.append("평점이 상승 추세에 있습니다.")

        kw_names = [kw["keyword"] for kw in top_keywords[:2]]
        if kw_names:
            good_points.append(f"'{', '.join(kw_names)}' 관련 언급이 많습니다.")

        if neg / total > 0.3:
            bad_points.append("부정 리뷰 비율이 높아 개선이 필요합니다.")
        if rating_change < -0.3:
            bad_points.append("평점이 하락 추세여서 원인 파악이 필요합니다.")
        if not bad_points:
            bad_points.append("큰 불만 사항은 없으나 지속적 모니터링이 필요합니다.")

        return {
            "good_points": good_points,
            "bad_points": bad_points,
        }
