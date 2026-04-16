-- ============================================================
-- seed_shop_week_review_today_reviewyo.sql
-- 목적 : 오늘 날짜가 속한 ISO 주차의 리뷰를 전체 재집계하여
--        shop_week_review 에 UPSERT
--
-- 소스 테이블 : review  (reviewyo Java 모델 기준)
-- 타겟 테이블 : shop_week_review
--
-- reviewyo Review 모델 핵심 필드 (Java → DB 컬럼)
--   private Long id                          → id
--   private ZonedDateTime createdAt          → created_at
--   private ZonedDateTime updatedAt          → updated_at   ← watermark 용
--   private Boolean deleted        (nullable) → deleted      ← NULL = 미삭제
--   @Builder.Default Boolean blinded = false → blinded      ← NOT NULL, 기본 false
--   private ReviewRating rating              → rating (embedded 가정, rating 컬럼)
--   private Vendor vendor          (FK)      → vendor_id
--   @Deprecated Long vendorId                → vendor_id (구 필드, DB 컬럼 동일)
--
-- 삭제/블라인드 조건
--   deleted  : Boolean nullable  → IS NOT TRUE  (NULL·FALSE 모두 유효)
--   blinded  : Boolean NOT NULL  → = FALSE       (기본값 false, NULL 없음)
--
-- 실행 조건 : MySQL 8.0+
-- 전제 조건 : shop_week_review 에 UNIQUE KEY uq_shop_year_week (shop_id, year, week_number)
-- ============================================================

INSERT INTO shop_week_review
    (shop_id, year, week_number, count, average,
     summary, positive_count, negative_count, neutral_count,
     created_at, updated_at)

SELECT
    r.vendor_id                                          AS shop_id,
    FLOOR(YEARWEEK(CURDATE(), 3) / 100)                  AS year,
    MOD(YEARWEEK(CURDATE(), 3), 100)                     AS week_number,
    COUNT(r.id)                                          AS count,
    -- ReviewRating이 embedded 타입이면 r.rating 직접 사용
    -- 별도 테이블 FK라면 JOIN 후 rating.score 등으로 교체 필요
    ROUND(AVG(r.rating), 2)                              AS average,
    NULL                                                 AS summary,
    NULL                                                 AS positive_count,
    NULL                                                 AS negative_count,
    NULL                                                 AS neutral_count,
    NOW()                                                AS created_at,
    NOW()                                                AS updated_at

FROM review r

WHERE
    -- 오늘이 속한 ISO 주차의 리뷰만 (YEARWEEK mode 3 = ISO 8601, 월요일 시작)
    FLOOR(YEARWEEK(r.created_at, 3) / 100) = FLOOR(YEARWEEK(CURDATE(), 3) / 100)
    AND MOD(YEARWEEK(r.created_at, 3), 100) = MOD(YEARWEEK(CURDATE(), 3), 100)

    -- deleted : nullable Boolean → NULL 또는 FALSE 이면 유효
    AND r.deleted IS NOT TRUE

    -- blinded : @Builder.Default false, NOT NULL → FALSE 이면 유효
    AND r.blinded = FALSE

GROUP BY r.vendor_id

ON DUPLICATE KEY UPDATE
    count      = VALUES(count),
    average    = VALUES(average),
    updated_at = NOW();

-- ============================================================
-- 확인 쿼리 (실행 후 검증)
-- ============================================================
-- SELECT shop_id,
--        year,
--        week_number,
--        count,
--        average,
--        updated_at
-- FROM shop_week_review
-- WHERE year        = FLOOR(YEARWEEK(CURDATE(), 3) / 100)
--   AND week_number = MOD(YEARWEEK(CURDATE(), 3), 100)
-- ORDER BY shop_id;
