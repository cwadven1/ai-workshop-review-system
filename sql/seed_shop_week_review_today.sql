-- ============================================================
-- seed_shop_week_review_today.sql
-- 목적 : 오늘 날짜가 속한 ISO 주차의 리뷰를 전체 재집계하여
--        stores_shopweekreview 에 UPSERT
--
-- 소스 테이블 : reviews_review  (reviewtime Django 로컬 모델)
-- 타겟 테이블 : stores_shopweekreview
--
-- ShopWeekReview 모델 핵심 필드
--   shop_id      : ForeignKey(Store)
--   year         : IntegerField  (예: 2025)
--   week_number  : IntegerField  (ISO 주차, 1–53)
--   count        : IntegerField
--   average      : FloatField
--   UNIQUE KEY   : uq_store_year_week (shop_id, year, week_number)
--
-- ISO 주차 계산 (MySQL)
--   YEARWEEK(date, 3) → YYYYWW  (mode 3 = ISO 8601, 월요일 시작)
--   year        = FLOOR(YEARWEEK(date, 3) / 100)
--   week_number = MOD(YEARWEEK(date, 3), 100)
--
-- 실행 시점 : 스케줄러가 주기적으로 실행 (매시간 또는 주기 설정)
-- 실행 조건 : MySQL 8.0+
-- ============================================================

INSERT INTO stores_shopweekreview
    (shop_id, year, week_number, count, average, created_at, updated_at)

SELECT
    r.store_id,
    FLOOR(YEARWEEK(CURDATE(), 3) / 100)     AS year,
    MOD(YEARWEEK(CURDATE(), 3), 100)        AS week_number,
    COUNT(r.id)                              AS count,
    ROUND(AVG(r.rating), 2)                  AS average,
    NOW()                                    AS created_at,
    NOW()                                    AS updated_at

FROM reviews_review r

WHERE
    -- 오늘이 속한 ISO 주차의 리뷰만 (created_at 기준 계산)
    FLOOR(YEARWEEK(r.created_at, 3) / 100) = FLOOR(YEARWEEK(CURDATE(), 3) / 100)
    AND MOD(YEARWEEK(r.created_at, 3), 100) = MOD(YEARWEEK(CURDATE(), 3), 100)

    -- 삭제된 리뷰 제외: nullable Boolean → NULL·FALSE 모두 유효
    AND r.deleted IS NOT TRUE

    -- 블라인드 리뷰 제외: NOT NULL Boolean → FALSE 이면 유효
    AND r.blinded = FALSE

GROUP BY r.store_id

ON DUPLICATE KEY UPDATE
    count      = VALUES(count),
    average    = VALUES(average),
    updated_at = NOW();

-- ============================================================
-- 확인 쿼리 (실행 후 검증)
-- ============================================================
-- SELECT shop_id, year, week_number, count, average, updated_at
-- FROM stores_shopweekreview
-- WHERE year        = FLOOR(YEARWEEK(CURDATE(), 3) / 100)
--   AND week_number = MOD(YEARWEEK(CURDATE(), 3), 100)
-- ORDER BY shop_id;
