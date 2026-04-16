-- ============================================================
-- update_shop_week_review_incremental.sql
-- 목적 : 변경된 (shop, year, week) 조합만 감지하여 증분 재집계
--        update_weekly_summaries.py 와 동일한 로직을 순수 SQL 로 구현
--
-- 소스 테이블 : reviews_review  (reviewtime Django 로컬 모델)
-- 타겟 테이블 : stores_shopweekreview
--
-- Django Review 모델 핵심 필드 (→ DB 컬럼)
--   store_id    : ForeignKey(Store) → store_id
--   created_at  : DateTimeField     → created_at
--   updated_at  : DateTimeField     → updated_at
--   deleted_at  : DateTimeField(nullable) → deleted_at  ← watermark 용
--   blinded_at  : DateTimeField(nullable) → blinded_at  ← watermark 용
--   is_deleted  : BooleanField      → is_deleted
--   is_blinded  : BooleanField      → is_blinded
--   rating      : IntegerField      → rating
--
-- 증분 로직 (update_weekly_summaries.py 와 동일)
--   ┌────────────────────────────────────────────────────────────────┐
--   │ 1. 변경 감지 (watermark = stores_shopweekreview.updated_at)    │
--   │    created_at / updated_at / deleted_at / blinded_at 중 하나가 │
--   │    swr.updated_at 이후이면 해당 (shop, year, week) 재계산       │
--   │                                                                │
--   │ 2. 신규 조합 (집계 row 없는 경우도 포함)                         │
--   │                                                                │
--   │ 3. 재계산: is_deleted=FALSE AND is_blinded=FALSE 활성 리뷰만    │
--   │    → 삭제/블라인드 발생 시 다음 실행에 자동 반영                  │
--   │                                                                │
--   │ 4. updated_at = NOW() → watermark 갱신                        │
--   │    → 다음 실행 시 이미 반영된 변경은 스킵                         │
--   └────────────────────────────────────────────────────────────────┘
--
-- 실행 주기 : 짧은 주기 (5분, 10분 등) 권장
--            변경 없으면 INSERT/UPDATE 0건 → 성능 영향 없음
-- 전제 조건 : UNIQUE KEY uq_shop_year_week (shop_id, year, week_number)
--            MySQL 8.0+ (WITH CTE 지원)
-- ============================================================

INSERT INTO stores_shopweekreview (shop_id, year, week_number, count, average)

WITH
-- ① 변경 감지: watermark(swr.updated_at) 이후 변경된 리뷰가 있는 (shop, year, week)
--    created_at / updated_at / deleted_at / blinded_at 모두 감지
--    → 신규 리뷰, 수정, 삭제, 블라인드 모두 커버
changed_combos AS (
    SELECT DISTINCT
        r.store_id,
        FLOOR(YEARWEEK(r.created_at, 3) / 100) AS year,
        MOD(YEARWEEK(r.created_at, 3), 100)    AS week_number
    FROM reviews_review r
    INNER JOIN stores_shopweekreview swr
           ON  swr.shop_id      = r.store_id
           AND swr.year         = FLOOR(YEARWEEK(r.created_at, 3) / 100)
           AND swr.week_number  = MOD(YEARWEEK(r.created_at, 3), 100)
    WHERE r.created_at  > swr.updated_at   -- 새 리뷰
       OR r.updated_at  > swr.updated_at   -- 수정된 리뷰
       OR r.deleted_at  > swr.updated_at   -- 삭제된 리뷰
       OR r.blinded_at  > swr.updated_at   -- 블라인드된 리뷰
),

-- ② 신규 조합: stores_shopweekreview에 아직 없는 (shop, week)
new_combos AS (
    SELECT DISTINCT
        r.store_id,
        FLOOR(YEARWEEK(r.created_at, 3) / 100) AS year,
        MOD(YEARWEEK(r.created_at, 3), 100)    AS week_number
    FROM reviews_review r
    LEFT JOIN stores_shopweekreview swr
           ON  swr.shop_id      = r.store_id
           AND swr.year         = FLOOR(YEARWEEK(r.created_at, 3) / 100)
           AND swr.week_number  = MOD(YEARWEEK(r.created_at, 3), 100)
    WHERE swr.shop_id IS NULL   -- 집계 레코드 없음
),

-- ③ 처리 대상 = 변경된 조합 + 신규 조합
target_combos AS (
    SELECT store_id, year, week_number FROM changed_combos
    UNION
    SELECT store_id, year, week_number FROM new_combos
)

-- ④ 현재 DB 상태 기준으로 활성 리뷰만 재집계
--    → 삭제/블라인드 변경이 반영된 정확한 count/average
SELECT
    t.store_id                AS shop_id,
    t.year,
    t.week_number,
    COUNT(r.id)               AS count,
    ROUND(AVG(r.rating), 2)   AS average

FROM target_combos t
JOIN reviews_review r
  ON  r.store_id                             = t.store_id
  AND FLOOR(YEARWEEK(r.created_at, 3) / 100) = t.year
  AND MOD(YEARWEEK(r.created_at, 3), 100)   = t.week_number
  AND r.is_deleted = FALSE   -- 삭제된 리뷰 제외
  AND r.is_blinded = FALSE   -- 블라인드된 리뷰 제외

GROUP BY t.store_id, t.year, t.week_number

ON DUPLICATE KEY UPDATE
    count      = VALUES(count),
    average    = VALUES(average),
    updated_at = NOW();   -- watermark 갱신 → 다음 실행 시 이미 처리된 변경은 스킵


-- ============================================================
-- 케이스별 동작 흐름 (update_weekly_summaries.py 주석과 동일 로직)
-- ============================================================
-- [케이스 A] 리뷰 3개 신규 추가 (기존 100개 → 103개)
--   created_at > swr.updated_at → changed_combos 감지
--   → 활성 리뷰 재집계 → count = 103
--
-- [케이스 B] 리뷰 3개 is_deleted=True (100개 → 97개)
--   deleted_at > swr.updated_at → changed_combos 감지
--   → is_deleted=FALSE 필터 → count = 97
--
-- [케이스 C] 리뷰 3개 is_blinded=True (100개 → 97개)
--   blinded_at > swr.updated_at → changed_combos 감지
--   → is_blinded=FALSE 필터 → count = 97
--
-- [케이스 D] 변경 없음
--   changed_combos = 0건, new_combos = 0건
--   → INSERT/UPDATE 0건 (스킵) → 성능 영향 없음
-- ============================================================
