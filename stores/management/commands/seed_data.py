import random
from collections import defaultdict
from datetime import date, timedelta

from django.core.management.base import BaseCommand

from reviews.models import Review
from stores.models import Keyword, Menu, ShopRecentReview, ShopRecentReviewSentiment, ShopWeekReview, ShopWeekReviewSentiment, ShopWeekReviewKeyword, Store


# 최근 N주 (year, week_num) 튜플 리스트 생성
def get_recent_weeks(count=12):
    today = date.today()
    weeks = []
    seen = set()
    d = today
    while len(weeks) < count:
        iso = d.isocalendar()
        key = (iso[0], iso[1])
        if key not in seen:
            weeks.insert(0, key)
            seen.add(key)
        d -= timedelta(days=7)
    return weeks


STORES_DATA = [
    {
        "name": "엄마손 한식당",
        "category": "korean",
        "address": "서울시 강남구 역삼동 123-4",
        "phone": "02-1234-5678",
        "image_url": "img/stores/korean_hansik.svg",
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
        "image_url": "img/stores/japanese_sushi.svg",
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
        "image_url": "img/stores/western_pasta.svg",
        "menus": [
            {"name": "까르보나라", "price": 14000, "is_popular": True, "description": ""},
            {"name": "봉골레", "price": 13000, "is_popular": False, "description": ""},
            {"name": "리조또", "price": 13000, "is_popular": False, "description": ""},
            {"name": "티라미수", "price": 7000, "is_popular": False, "description": ""},
        ],
        # 셰프 교체 시나리오: 악평 → 호평 (더 극적)
        "rating_pattern": [3.0, 2.5, 2.2, 1.8, 2.0, 1.7, 2.0, 2.5, 3.2, 3.8, 4.3, 4.7],
        "review_counts_override": [20, 20, 20, 20, 20, 20, 20, 20, 20, 20, 1, 2],
    },
    {
        "name": "황금 짜장",
        "category": "chinese",
        "address": "서울시 중구 을지로 321-5",
        "phone": "02-4567-8901",
        "image_url": "img/stores/chinese_jajang.svg",
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
        "image_url": "img/stores/chicken_basakchicken.svg",
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
        "image_url": "img/stores/japanese_donkatsu.svg",
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
        "image_url": "img/stores/korean_tteokbokki.svg",
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
    {
        "name": "나폴리 피자",
        "category": "pizza",
        "address": "서울시 홍대 와우산로 55-1",
        "phone": "02-9012-3456",
        "image_url": "img/stores/pizza_napoli.svg",
        "menus": [
            {"name": "마르게리타", "price": 16000, "is_popular": True, "description": ""},
            {"name": "페퍼로니", "price": 18000, "is_popular": True, "description": ""},
            {"name": "사계절 피자", "price": 19000, "is_popular": False, "description": ""},
            {"name": "칼초네", "price": 17000, "is_popular": False, "description": ""},
        ],
        # 신규 오픈 → 점점 알려지는 시나리오
        "rating_pattern": [3.2, 3.4, 3.5, 3.7, 3.8, 4.0, 4.1, 4.2, 4.3, 4.4, 4.5, 4.5],
        "review_counts_override": [2, 3, 3, 4, 5, 6, 8, 9, 10, 11, 12, 14],
    },
    {
        "name": "브런치 카페 모닝",
        "category": "cafe",
        "address": "서울시 성수동 뚝섬로 77-3",
        "phone": "02-8901-2345",
        "image_url": "img/stores/cafe_morning.svg",
        "menus": [
            {"name": "아메리카노", "price": 4500, "is_popular": True, "description": ""},
            {"name": "카페라떼", "price": 5000, "is_popular": True, "description": ""},
            {"name": "에그 베네딕트", "price": 13000, "is_popular": True, "description": ""},
            {"name": "아보카도 토스트", "price": 11000, "is_popular": False, "description": ""},
            {"name": "티라미수", "price": 7000, "is_popular": False, "description": ""},
        ],
        # 안정적인 고평점 유지
        "rating_pattern": [4.3, 4.4, 4.3, 4.5, 4.4, 4.3, 4.5, 4.6, 4.4, 4.5, 4.6, 4.7],
    },
    {
        "name": "강남 불판 삼겹살",
        "category": "korean",
        "address": "서울시 강남구 논현동 88-5",
        "phone": "02-0123-4567",
        "image_url": "img/stores/korean_samgyeopsal.svg",
        "menus": [
            {"name": "삼겹살", "price": 15000, "is_popular": True, "description": ""},
            {"name": "목살", "price": 15000, "is_popular": True, "description": ""},
            {"name": "냉면", "price": 8000, "is_popular": False, "description": ""},
            {"name": "된장찌개", "price": 3000, "is_popular": False, "description": ""},
        ],
        # 입소문 타고 상승 후 안정
        "rating_pattern": [3.6, 3.7, 3.9, 4.0, 4.1, 4.2, 4.3, 4.3, 4.2, 4.3, 4.4, 4.3],
    },
    {
        "name": "사천 마라탕",
        "category": "chinese",
        "address": "서울시 신촌 명물길 33-7",
        "phone": "02-1122-3344",
        "image_url": "img/stores/chinese_malatang.svg",
        "menus": [
            {"name": "마라탕 (소)", "price": 9000, "is_popular": False, "description": ""},
            {"name": "마라탕 (대)", "price": 13000, "is_popular": True, "description": ""},
            {"name": "마라샹궈", "price": 15000, "is_popular": True, "description": ""},
            {"name": "탕후루", "price": 5000, "is_popular": False, "description": ""},
        ],
        # 마라 트렌드로 꾸준한 상승세, 최근 3주 급격한 품질 하락
        "rating_pattern": [3.8, 4.0, 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 2.5, 2.3, 2.0],
        "review_counts_override": [12, 14, 15, 17, 18, 20, 22, 23, 25, 20, 12, 6],
    },
    {
        "name": "르 스테이크",
        "category": "western",
        "address": "서울시 강남구 청담동 9-11",
        "phone": "02-5566-7788",
        "image_url": "img/stores/western_steak.svg",
        "menus": [
            {"name": "채끝 스테이크", "price": 45000, "is_popular": True, "description": ""},
            {"name": "안심 스테이크", "price": 55000, "is_popular": True, "description": ""},
            {"name": "파스타", "price": 18000, "is_popular": False, "description": ""},
            {"name": "수프", "price": 8000, "is_popular": False, "description": ""},
        ],
        # 꾸준히 높은 평점 유지
        "rating_pattern": [4.4, 4.5, 4.4, 4.6, 4.5, 4.6, 4.7, 4.5, 4.6, 4.7, 4.6, 4.8],
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
    "pizza": [
        "도우가 얇고 바삭해서 정말 맛있어요. 나폴리 스타일 제대로!",
        "치즈가 진하고 탱탱해요. 한 조각만 먹을 수가 없어요!",
        "마르게리타 토마토소스가 신선하고 맛있어요.",
        "화덕에서 구운 향기가 진짜 피자집 느낌이에요.",
        "페퍼로니가 두툼하고 풍미가 깊어요!",
        "칼초네 속 재료가 듬뿍 들어있어요. 가성비 최고!",
        "사계절 피자 채소 신선도가 달라요. 건강한 맛!",
        "오픈한 지 얼마 안 됐는데 동네 맛집 등극했어요.",
    ],
    "cafe": [
        "커피 원두 향이 정말 풍부해요. 전문 로스터리 수준!",
        "에그 베네딕트가 이렇게 맛있는 건 처음이에요.",
        "아보카도 토스트 재료가 신선하고 양도 푸짐해요.",
        "인테리어도 예쁘고 커피도 맛있어요. 데이트 코스로 딱!",
        "카페라떼 우유 거품이 부드럽고 온도도 딱 좋아요.",
        "브런치 메뉴가 다양하고 가격도 합리적이에요.",
        "주말 오전에 오기 딱 좋은 분위기예요. 힐링됩니다.",
        "티라미수가 진하고 달달해요. 커피랑 완벽 조합!",
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
    "pizza": [
        "도우가 좀 두꺼워서 빵 먹는 느낌이에요.",
        "치즈가 너무 짜요. 물 많이 마시게 됨.",
        "가격에 비해 피자 크기가 작아요.",
        "배달 오면서 눅눅해졌어요. 피자는 직접 먹어야 하나봐요.",
        "토핑이 생각보다 적어요. 사진이랑 달랐어요.",
    ],
    "cafe": [
        "커피가 좀 쓴 편이에요. 원두 취향 안 맞을 수도 있어요.",
        "브런치 메뉴 가격이 좀 비싼 편이에요.",
        "주말엔 너무 붐벼서 자리 잡기 힘들어요.",
        "웨이팅이 길어요. 인기 많아서 어쩔 수 없나봐요.",
        "음식이 나오는 데 너무 오래 걸렸어요.",
    ],
}

NEUTRAL_REVIEWS = [
    "보통이에요. 나쁘지 않지만 특별하지도 않은.",
    "무난한 맛이에요. 그냥 평범합니다.",
    "가격 대비 괜찮은 편이에요.",
    "배달은 빨랐는데 맛은 그저 그래요.",
    "한 번쯤은 먹을 만한데 재주문은 모르겠어요.",
]

# ── 감성 분석용 키워드 사전 (부분 문자열 매칭) ──────────────────────────
SENTIMENT_POSITIVE_WORDS = [
    "맛있", "최고", "훌륭", "맛집", "강추", "재방문", "만족", "신선", "바삭",
    "부드럽", "환상", "완벽", "좋아", "좋고", "좋은", "일품", "쫄깃", "풍부",
    "진한", "고소", "달달", "얼큰", "시원", "따끈", "따뜻", "대만족", "미쳤",
    "정성", "합리적", "친절", "힐링", "인생", "대박", "추천", "가성비",
    "푸짐", "촉촉", "빠르", "줄 서서", "기대 이상", "완전 다른", "강추",
    "딱이", "딱 좋", "맛집 됐", "동네 최고", "리뉴얼",
]

SENTIMENT_NEGATIVE_WORDS = [
    "별로", "실망", "느끼", "맛없", "불친절", "질긴", "눅눅", "비린",
    "밍밍", "아쉽", "기름", "식었", "차갑", "딱딱", "짜요", "짠", "달아요",
    "불어서", "퍼져", "늦어", "늦었", "적어", "줄었", "작아", "최악",
    "문제", "불만", "붐벼", "오래 걸", "안 맞", "그만큼의 맛은 아님",
    "그냥 평범", "기대했는데", "이 가격", "소스도 아쉽", "눅눅해",
]


def analyze_sentiment_from_content(content: str) -> str:
    """리뷰 텍스트를 분석하여 긍정/중립/부정 반환 (키워드 룰 기반)"""
    score = 0
    for word in SENTIMENT_POSITIVE_WORDS:
        if word in content:
            score += 1
    for word in SENTIMENT_NEGATIVE_WORDS:
        if word in content:
            score -= 1

    if score > 0:
        return "positive"
    elif score < 0:
        return "negative"
    else:
        return "neutral"


KEYWORDS_MAP = {
    "positive": {
        "korean": ["맛있는", "푸짐한", "집밥", "양많은", "재방문"],
        "japanese": ["신선한", "가성비", "오마카세", "퀄리티", "셰프"],
        "western": ["크림소스", "알덴테", "바삭한", "리뉴얼", "맛집"],
        "chinese": ["깊은맛", "바삭한", "시원한", "가성비", "양많은"],
        "chicken": ["바삭한", "매콤한", "푸짐한", "맥주안주", "고소한"],
        "pizza": ["바삭한도우", "진한치즈", "신선토핑", "화덕향", "가성비"],
        "cafe": ["풍부한향", "부드러운", "인테리어", "브런치", "힐링"],
    },
    "negative": {
        "korean": ["짠맛", "배달늦음", "양적음", "식은음식"],
        "japanese": ["비린내", "불친절", "양적음", "비싼", "신선도"],
        "western": ["느끼한", "퍼진면", "밍밍한", "비싼", "불어서"],
        "chinese": ["달달한", "양줄음", "배달늦음", "눅눅한", "맛변함"],
        "chicken": ["기름진", "배달늦음", "양적음"],
        "pizza": ["눅눅한", "양적음", "비싼", "짠맛", "사진과달라"],
        "cafe": ["비싼", "웨이팅긴", "쓴커피", "느린서비스", "붐빔"],
    },
}


class Command(BaseCommand):
    help = "시드 데이터 생성: 가게, 메뉴, 리뷰, 월별 요약"

    def handle(self, *args, **options):
        self.stdout.write("기존 데이터 삭제 중...")
        ShopRecentReview.objects.all().delete()
        ShopWeekReview.objects.all().delete()
        Review.objects.all().delete()
        Menu.objects.all().delete()
        Store.objects.all().delete()

        weeks = get_recent_weeks(12)
        self.stdout.write(f"대상 주차: {weeks}")

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

            # 주별 리뷰 생성
            all_reviews = []
            pattern = store_data["rating_pattern"]

            # 주별 리뷰 수 결정
            if "review_counts_override" in store_data:
                review_counts_per_week = store_data["review_counts_override"]
            elif "review_override" in store_data:
                total_target = store_data["review_override"]
                base = total_target // len(weeks)
                remainder = total_target % len(weeks)
                review_counts_per_week = [base + (1 if i < remainder else 0) for i in range(len(weeks))]
            else:
                review_counts_per_week = [random.randint(5, 8) for _ in range(len(weeks))]

            for i, (year_num, week_num) in enumerate(weeks):
                target_rating = pattern[i]
                review_count = review_counts_per_week[i]

                weekly_reviews = []
                for j in range(review_count):
                    rating = self._generate_rating(target_rating)
                    sentiment, content, keywords = self._generate_review_content(
                        store_data["category"], rating
                    )
                    day_of_week = random.randint(1, 7)
                    review_date = date.fromisocalendar(year_num, week_num, day_of_week)

                    # 각 주 첫 번째 리뷰에만 이미지 1장 첨부
                    if j == 0:
                        images = [f"img/reviews/food_{store_data['category']}.svg"]
                    else:
                        images = []

                    review = Review.objects.create(
                        store=store,
                        rating=rating,
                        content=content,
                        sentiment=sentiment,
                        sentiment_score=self._sentiment_score(sentiment),
                        keywords=keywords,
                        week=week_num,
                        review_date=review_date,
                        source="yogiyo",
                        images=images,
                    )
                    weekly_reviews.append(review)
                    all_reviews.append(review)

                # 주차별 집계 생성
                self._create_shop_week_review(store, year_num, week_num, weekly_reviews)

            # 최근 4주 리뷰로 ShopRecentReview 생성
            recent_weeks = weeks[-4:]
            start_date = date.fromisocalendar(recent_weeks[0][0], recent_weeks[0][1], 1)
            end_date = date.fromisocalendar(recent_weeks[-1][0], recent_weeks[-1][1], 7)
            recent_reviews = [r for r in all_reviews if start_date <= r.review_date <= end_date]
            if recent_reviews:
                self._create_shop_recent_review(store, recent_reviews)

            # 가게 전체 평균 업데이트
            total = len(all_reviews)
            avg = sum(r.rating for r in all_reviews) / total if total else 0
            store.avg_rating = round(avg, 1)
            store.total_review_count = total
            store.save()

        self.stdout.write(self.style.SUCCESS("시드 데이터 생성 완료!"))
        self.stdout.write(f"  가게: {Store.objects.count()}개")
        self.stdout.write(f"  리뷰: {Review.objects.count()}개")
        self.stdout.write(f"  주차별 집계: {ShopWeekReview.objects.count()}개")
        self.stdout.write(f"  최근 리뷰 집계: {ShopRecentReview.objects.count()}개")

    def _generate_rating(self, target):
        """타겟 평점 주변으로 랜덤 평점 생성"""
        r = target + random.uniform(-0.5, 0.5)
        return max(1, min(5, round(r)))

    def _generate_review_content(self, category, rating):
        """평점에 따라 리뷰 내용 선택 후 내용 기반으로 감성 분류"""
        if rating >= 4:
            reviews = POSITIVE_REVIEWS.get(category, POSITIVE_REVIEWS["korean"])
            content = random.choice(reviews)
            kw_pool = KEYWORDS_MAP["positive"].get(
                category, KEYWORDS_MAP["positive"]["korean"]
            )
        elif rating <= 2:
            reviews = NEGATIVE_REVIEWS.get(category, NEGATIVE_REVIEWS["korean"])
            content = random.choice(reviews)
            kw_pool = KEYWORDS_MAP["negative"].get(
                category, KEYWORDS_MAP["negative"]["korean"]
            )
        else:
            content = random.choice(NEUTRAL_REVIEWS)
            kw_pool = ["보통", "무난한", "평범한"]

        # 평점이 아닌 리뷰 내용 텍스트를 분석하여 감성 결정
        sentiment = analyze_sentiment_from_content(content)

        keywords = random.sample(kw_pool, min(3, len(kw_pool)))
        return sentiment, content, keywords

    def _sentiment_score(self, sentiment):
        if sentiment == "positive":
            return round(random.uniform(0.6, 1.0), 2)
        elif sentiment == "negative":
            return round(random.uniform(-1.0, -0.4), 2)
        return round(random.uniform(-0.3, 0.3), 2)

    # 키워드 감성 판별용 사전 (KEYWORDS_MAP 기반)
    _ALL_POSITIVE_KWS = frozenset(
        kw for cat_kws in KEYWORDS_MAP["positive"].values() for kw in cat_kws
    )
    _ALL_NEGATIVE_KWS = frozenset(
        kw for cat_kws in KEYWORDS_MAP["negative"].values() for kw in cat_kws
    )

    def _create_shop_week_review(self, store, year, week_number, reviews):
        """ShopWeekReview + ShopWeekReviewSentiment + ShopWeekReviewKeyword 생성"""
        ratings = [r.rating for r in reviews]
        average = round(sum(ratings) / len(ratings), 1) if ratings else 0.0

        sentiments = defaultdict(int)
        for r in reviews:
            sentiments[r.sentiment] += 1

        keyword_counts = defaultdict(int)
        for r in reviews:
            for kw in r.keywords:
                keyword_counts[kw] += 1

        pos = sentiments.get("positive", 0)
        neg = sentiments.get("negative", 0)
        total = sum(sentiments.values()) or 1
        kw_text = ", ".join(list(keyword_counts.keys())[:3])
        summary_text = (
            f"{store.name}의 {week_number}주차 리뷰 분석 결과, "
            f"평균 평점 {average}점으로 "
            f"긍정 리뷰가 {round(pos/total*100)}%, "
            f"부정 리뷰가 {round(neg/total*100)}%를 차지합니다. "
            f"주요 키워드는 '{kw_text}'이(가) 언급되었습니다."
        )

        swr = ShopWeekReview.objects.create(
            shop=store,
            year=year,
            week_number=week_number,
            count=len(reviews),
            average=average,
            positive_count=sentiments.get("positive", 0),
            negative_count=sentiments.get("negative", 0),
            neutral_count=sentiments.get("neutral", 0),
            summary=summary_text,
        )

        # positive/negative/neutral 3개 sentiment 레코드 insert
        pos_reviews = [r for r in reviews if r.sentiment == "positive"]
        neg_reviews = [r for r in reviews if r.sentiment == "negative"]

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

        ShopWeekReviewSentiment.objects.create(
            shop_week_review=swr,
            sentiment="positive",
            content=pos_content,
            created_at=swr.updated_at,
        )
        ShopWeekReviewSentiment.objects.create(
            shop_week_review=swr,
            sentiment="negative",
            content=neg_content,
            created_at=swr.updated_at,
        )
        ShopWeekReviewSentiment.objects.create(
            shop_week_review=swr,
            sentiment="neutral",
            content=summary_text,
            created_at=swr.updated_at,
        )

        for word, cnt in keyword_counts.items():
            if word in self._ALL_POSITIVE_KWS:
                sentiment = "positive"
            elif word in self._ALL_NEGATIVE_KWS:
                sentiment = "negative"
            else:
                sentiment = "neutral"
            keyword_obj, _ = Keyword.objects.get_or_create(
                word=word, defaults={"sentiment": sentiment}
            )
            ShopWeekReviewKeyword.objects.create(
                shop_week_review=swr,
                keyword=keyword_obj,
                count=cnt,
            )

    def _create_shop_recent_review(self, store, reviews):
        """ShopRecentReview + ShopRecentReviewSentiment 3개 생성 (최근 4주 기준)"""
        dates = [r.review_date for r in reviews]
        ratings = [r.rating for r in reviews]
        average = round(sum(ratings) / len(ratings), 1)

        sentiments = defaultdict(int)
        for r in reviews:
            sentiments[r.sentiment] += 1

        pos = sentiments.get("positive", 0)
        neg = sentiments.get("negative", 0)
        total = sum(sentiments.values()) or 1

        summary_text = (
            f"{store.name}의 최근 리뷰 분석 결과, "
            f"평균 평점 {average}점으로 "
            f"긍정 리뷰가 {round(pos/total*100)}%, "
            f"부정 리뷰가 {round(neg/total*100)}%를 차지합니다. "
            f"총 {len(reviews)}건의 리뷰가 분석되었습니다."
        )

        srr = ShopRecentReview.objects.create(
            shop=store,
            review_sample_start_date=min(dates),
            review_sample_end_date=max(dates),
            total_count=len(reviews),
            positive_count=pos,
            negative_count=neg,
            neutral_count=sentiments.get("neutral", 0),
            average=average,
            summary=summary_text,
        )

        pos_reviews = [r for r in reviews if r.sentiment == "positive"]
        neg_reviews = [r for r in reviews if r.sentiment == "negative"]

        pos_kws = list(dict.fromkeys(kw for r in pos_reviews for kw in r.keywords))[:3]
        neg_kws = list(dict.fromkeys(kw for r in neg_reviews for kw in r.keywords))[:3]

        pos_content = (
            f"{store.name}의 최근 긍정 리뷰 분석: "
            f"총 {len(pos_reviews)}건의 긍정 리뷰가 접수되었습니다. "
            f"주요 키워드는 '{', '.join(pos_kws)}'이(가) 언급되었으며, "
            f"맛, 서비스, 가성비에 대한 만족도가 높았습니다."
        ) if pos_reviews else f"{store.name}의 최근 긍정 리뷰가 없습니다."

        neg_content = (
            f"{store.name}의 최근 부정 리뷰 분석: "
            f"총 {len(neg_reviews)}건의 부정 리뷰가 접수되었습니다. "
            f"주요 불만 키워드는 '{', '.join(neg_kws)}'이(가) 언급되었으며, "
            f"개선이 필요한 영역으로 파악됩니다."
        ) if neg_reviews else f"{store.name}의 최근 부정 리뷰가 없습니다."

        ShopRecentReviewSentiment.objects.create(
            shop_recent_review=srr, sentiment="positive", content=pos_content
        )
        ShopRecentReviewSentiment.objects.create(
            shop_recent_review=srr, sentiment="negative", content=neg_content
        )
        ShopRecentReviewSentiment.objects.create(
            shop_recent_review=srr, sentiment="neutral", content=summary_text
        )
