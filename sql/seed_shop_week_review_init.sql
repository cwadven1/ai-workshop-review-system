-- ============================================================
-- seed_shop_week_review_init.sql
-- 목적 : 각 가게(vendor_id)의 첫 번째 리뷰가 속한 ISO 주차부터
--        12주치 shop_week_review 초기 데이터 삽입
--
-- 소스 테이블 : reviewyo.review
--   - vendor_id : 가게 ID (shop_week_review.shop_id 에 대응)
--   - rating    : 별점 (1–5)
--   - created_at: 리뷰 작성 시각
--   - deleted   : 삭제 여부 (0 = 유효)
--   - blinded   : 블라인드 여부 (0 = 유효)
--
-- 타겟 테이블 : shop_week_review
--   필드: shop_id, year, week_number, count, average,
--         summary(NULL), positive_count(NULL),
--         negative_count(NULL), neutral_count(NULL),
--         created_at, updated_at
--
-- ISO 주차 계산 (MySQL)
--   YEARWEEK(date, 3) → YYYYWW  (mode 3 = ISO 8601, 월요일 시작)
--   year        = FLOOR(YEARWEEK(date, 3) / 100)
--   week_number = MOD(YEARWEEK(date, 3), 100)
--
-- 실행 조건 : MySQL 8.0+ (WITH CTE 지원)
-- ============================================================

INSERT INTO shop_week_review
    (shop_id, year, week_number, count, average,
     summary, positive_count, negative_count, neutral_count,
     created_at, updated_at)

WITH
-- ① 삭제·블라인드를 제외한 유효 리뷰의 (vendor, ISO주차) 조합 추출
distinct_vendor_weeks AS (
    SELECT DISTINCT
        vendor_id,
        YEARWEEK(created_at, 3) AS yw
    FROM review
    WHERE deleted  = 0
      AND blinded  = 0
),

-- ② 각 가게별 ISO 주차에 순번 부여 (오름차순)
ranked_weeks AS (
    SELECT
        vendor_id,
        yw,
        ROW_NUMBER() OVER (PARTITION BY vendor_id ORDER BY yw) AS rn
    FROM distinct_vendor_weeks
),

-- ③ 각 가게의 첫 12주차만 추출
first_12_weeks AS (
    SELECT vendor_id, yw
    FROM ranked_weeks
    WHERE rn <= 12
)

-- ④ 12주 범위 내 리뷰를 집계하여 INSERT
SELECT
    r.vendor_id                              AS shop_id,
    FLOOR(f.yw / 100)                        AS year,
    MOD(f.yw, 100)                           AS week_number,
    COUNT(r.id)                              AS count,
    ROUND(AVG(r.rating), 2)                  AS average,
    NULL                                     AS summary,
    NULL                                     AS positive_count,
    NULL                                     AS negative_count,
    NULL                                     AS neutral_count,
    NOW()                                    AS created_at,
    NOW()                                    AS updated_at
FROM review r
JOIN first_12_weeks f
  ON  r.vendor_id = f.vendor_id
  AND YEARWEEK(r.created_at, 3) = f.yw
WHERE r.deleted = 0
  AND r.blinded = 0
GROUP BY
    r.vendor_id,
    f.yw
ORDER BY
    r.vendor_id,
    f.yw;
