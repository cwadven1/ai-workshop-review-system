-- ============================================================
-- update_shop_week_review_incremental_reviewyo.sql
-- 목적 : Python update_weekly_summaries 커맨드의 SQL 동치 버전
--        변경된 (vendor, 주차) 조합만 감지하여 재계산 → UPSERT
--
-- 소스 테이블 : review  (reviewyo Java 모델 기준)
-- 타겟 테이블 : shop_week_review
--
-- reviewyo Review 모델 핵심 필드 (Java → DB 컬럼)
--   private Long id                          → id
--   private ZonedDateTime createdAt          → created_at
--   private ZonedDateTime updatedAt          → updated_at   ← watermark 핵심
--   private Boolean deleted        (nullable) → deleted      ← NULL = 미삭제
--   @Builder.Default Boolean blinded = false → blinded      ← NOT NULL, 기본 false
--   private ReviewRating rating              → rating (embedded 가정)
--   private Vendor vendor          (FK)      → vendor_id
--   @Deprecated Long vendorId                → vendor_id (구 필드, DB 컬럼 동일)
--
-- 삭제/블라인드 조건
--   deleted  : Boolean nullable  → IS NOT TRUE  (NULL·FALSE 모두 유효)
--   blinded  : Boolean NOT NULL  → = FALSE       (기본값 false, NULL 없음)
--
-- 증분 로직 (Python update_weekly_summaries 와 동일)
--   ┌─────────────────────────────────────────────────────────┐
--   │ 1. 변경 감지 (watermark 비교)                            │
--   │    review.updated_at > shop_week_review.updated_at      │
--   │    → deleted/blinded 포함 모든 변경을 감지               │
--   │    → deleted/blinded 변경 시에도 updated_at 갱신됨       │
--   │                                                          │
--   │ 2. 재계산 (현재 DB 상태 기준)                             │
--   │    active 리뷰만 COUNT/AVG (deleted IS NOT TRUE,        │
--   │    blinded = FALSE) → 항상 정확한 카운트                  │
--   │                                                          │
--   │ 3. 신규 (아직 집계 레코드 없는) 조합도 포함               │
--   └─────────────────────────────────────────────────────────┘
--
-- 전제 조건
--   1. shop_week_review 에 UNIQUE KEY uq_shop_year_week (shop_id, year, week_number)
--   2. MySQL 8.0+ (WITH CTE 지원)
-- ============================================================

INSERT INTO shop_week_review
    (shop_id, year, week_number, count, average,
     summary, positive_count, negative_count, neutral_count,
     created_at, updated_at)

WITH
-- ① 변경 감지: review.updated_at이 shop_week_review.updated_at 이후인 조합
--    deleted/blinded가 바뀌어도 updated_at이 갱신되므로 삭제·블라인드 변경도 감지
--    → 이 CTE는 deleted/blinded 필터 없이 전체 리뷰 대상
changed_combos AS (
    SELECT DISTINCT
        r.vendor_id,
        FLOOR(YEARWEEK(r.created_at, 3) / 100) AS year,
        MOD(YEARWEEK(r.created_at, 3), 100)    AS week_number
    FROM review r
    INNER JOIN shop_week_review swr
           ON  swr.shop_id      = r.vendor_id
           AND swr.year         = FLOOR(YEARWEEK(r.created_at, 3) / 100)
           AND swr.week_number  = MOD(YEARWEEK(r.created_at, 3), 100)
    WHERE r.updated_at > swr.updated_at   -- watermark: 마지막 집계 이후 변경분만
),

-- ② 신규 조합: shop_week_review에 아직 없는 (vendor, week)
new_combos AS (
    SELECT DISTINCT
        r.vendor_id,
        FLOOR(YEARWEEK(r.created_at, 3) / 100) AS year,
        MOD(YEARWEEK(r.created_at, 3), 100)    AS week_number
    FROM review r
    LEFT JOIN shop_week_review swr
           ON  swr.shop_id      = r.vendor_id
           AND swr.year         = FLOOR(YEARWEEK(r.created_at, 3) / 100)
           AND swr.week_number  = MOD(YEARWEEK(r.created_at, 3), 100)
    WHERE swr.shop_id IS NULL          -- 집계 레코드 없음
      AND r.deleted IS NOT TRUE        -- 유효 리뷰만 대상 (NULL·FALSE)
      AND r.blinded = FALSE
),

-- ③ 처리 대상 전체 = 변경 + 신규
target_combos AS (
    SELECT vendor_id, year, week_number FROM changed_combos
    UNION
    SELECT vendor_id, year, week_number FROM new_combos
)

-- ④ 현재 DB 상태 기준으로 활성 리뷰만 재집계
--    → deleted/blinded 변경이 반영된 정확한 count/average
SELECT
    t.vendor_id                                          AS shop_id,
    t.year,
    t.week_number,
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

FROM target_combos t
JOIN review r
  ON  r.vendor_id                              = t.vendor_id
  AND FLOOR(YEARWEEK(r.created_at, 3) / 100)  = t.year
  AND MOD(YEARWEEK(r.created_at, 3), 100)     = t.week_number
  AND r.deleted IS NOT TRUE     -- 활성 리뷰만 집계 (NULL·FALSE)
  AND r.blinded = FALSE

GROUP BY t.vendor_id, t.year, t.week_number

ON DUPLICATE KEY UPDATE
    count      = VALUES(count),
    average    = VALUES(average),
    updated_at = NOW();
    -- summary / positive_count / negative_count 등은
    -- AI 분석 별도 배치가 관리 → 여기서는 건드리지 않음


-- ============================================================
-- 케이스별 동작 흐름
-- ============================================================
-- [케이스 A] 리뷰 3개 신규 추가 (기존 100개 → 103개)
--   새 리뷰 → swr 레코드 없으면 new_combos, 있으면 updated_at 기준 changed_combos
--   → 재집계 → count = 103
--
-- [케이스 B] 리뷰 3개 deleted = TRUE (100개 → 97개)
--   deleted 변경 → updated_at 갱신 → changed_combos 감지
--   → active 리뷰만 재집계 → count = 97  (IS NOT TRUE 로 정확히 제외)
--
-- [케이스 C] 리뷰 3개 blinded = TRUE (100개 → 97개)
--   blinded 변경 → updated_at 갱신 → changed_combos 감지
--   → blinded = FALSE 필터 → count = 97
--
-- [케이스 D] 변경 없음
--   changed_combos = 0건, new_combos = 0건
--   → INSERT/UPDATE 없음 (스킵) → 성능 영향 없음
-- ============================================================
