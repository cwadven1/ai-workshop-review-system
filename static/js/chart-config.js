/**
 * SVG 기반 주차별 별점 트렌드 차트
 * - 상단 62%: 평점 직선+면적 차트 (점별 평점 레이블)
 * - 하단 38%: 리뷰수 원(circle) 차트 (원 아래 N건 레이블, 검정 농도 표현)
 * - 점선 구분선
 * - 신뢰도: 리뷰 수 기반 (10건+ 높음 / 5~9건 보통 / 5건 미만 낮음)
 */
function initTrendChart(containerId, data) {
    const container = document.getElementById(containerId);
    if (!container) return;

    const MAX_WEEKS = 10;
    const rawLabels = data.labels || [];
    const rawRatings = data.ratings || [];
    const rawCounts = data.review_counts || [];
    const labels = rawLabels.slice(-MAX_WEEKS);
    const ratings = rawRatings.slice(-MAX_WEEKS);
    const counts = rawCounts.slice(-MAX_WEEKS);
    const n = labels.length;

    if (n === 0) {
        container.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:#aaa;font-size:13px;">데이터가 없습니다</div>';
        return;
    }

    // ── 좌표계 (고정 뷰박스) ──
    const VW = 400, VH = 220;
    const pL = 28, pR = 8, pT = 22, pB = 26;
    const chartW = VW - pL - pR;
    const totalH = VH - pT - pB;
    const divY = pT + Math.round(totalH * 0.62);   // 점선 구분 Y
    const ratingH = divY - pT;                      // 평점 영역 높이
    const countH = VH - pB - divY;                  // 리뷰수 영역 높이

    // X 위치 계산
    const step = chartW / n;
    const xOf = i => pL + step * i + step / 2;

    // 평점 Y 매핑: 1~5 → divY~pT (위로 갈수록 높은 평점)
    const yRating = r => divY - ((r - 1) / 4) * ratingH;

    // 리뷰수 Y 매핑: 막대 상단 좌표
    const maxC = Math.max(...counts, 1);

    // 평점별 색상
    function ratingColor(r) {
        return '#222';
    }

    // 신뢰도 레벨 (리뷰 수 기반)
    function confLevel(c) {
        if (c >= 10) return 'high';
        if (c >= 5)  return 'mid';
        return 'low';
    }

    // ── 평점 면적 경로 ──
    const pts = ratings.map((r, i) => [xOf(i), yRating(r)]);
    const areaD = `M${pts[0][0].toFixed(1)},${divY} `
        + pts.map(p => `L${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(' ')
        + ` L${pts[pts.length - 1][0].toFixed(1)},${divY} Z`;

    // ── SVG 생성 ──
    const uid = containerId.replace(/[^a-z0-9]/gi, '_');
    let s = `<svg width="100%" height="100%" viewBox="0 0 ${VW} ${VH}" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMid meet" style="display:block;">`;

    // 그라디언트 정의
    s += `<defs>
        <linearGradient id="ag_${uid}" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="#FA2D43" stop-opacity="0.14"/>
            <stop offset="100%" stop-color="#FA2D43" stop-opacity="0.02"/>
        </linearGradient>
    </defs>`;

    // 평점 영역 그리드 라인 (2~5)
    [2, 3, 4, 5].forEach(v => {
        const y = yRating(v);
        s += `<line x1="${pL}" y1="${y.toFixed(1)}" x2="${VW - pR}" y2="${y.toFixed(1)}" stroke="#f0f0f0" stroke-width="0.8"/>`;
        s += `<text x="${(pL - 3).toFixed(1)}" y="${(y + 3.5).toFixed(1)}" text-anchor="end" font-size="8.5" fill="#ccc">${v}</text>`;
    });

    // 면적 채우기
    s += `<path d="${areaD}" fill="url(#ag_${uid})" stroke="none"/>`;

    // 평점 연결선 — 세그먼트별 신뢰도 반영
    for (let i = 0; i < pts.length - 1; i++) {
        const cl = (confLevel(counts[i]) === 'low' || confLevel(counts[i + 1]) === 'low') ? 'low'
                 : (confLevel(counts[i]) === 'mid' || confLevel(counts[i + 1]) === 'mid') ? 'mid'
                 : 'high';
        let attrs = `stroke="#FA2D43" stroke-width="2" stroke-linecap="round"`;
        if (cl === 'low')      attrs += ` stroke-dasharray="4,3" stroke-opacity="0.4"`;
        else if (cl === 'mid') attrs += ` stroke-opacity="0.7"`;
        s += `<line x1="${pts[i][0].toFixed(1)}" y1="${pts[i][1].toFixed(1)}" x2="${pts[i+1][0].toFixed(1)}" y2="${pts[i+1][1].toFixed(1)}" ${attrs}/>`;
    }

    // 점 + 평점 레이블 — 신뢰도별 스타일
    pts.forEach(([cx, cy], i) => {
        const r = ratings[i];
        const col = ratingColor(r);
        const cl = confLevel(counts[i]);
        if (cl === 'low') {
            // hollow circle — 불확실 데이터
            s += `<circle cx="${cx.toFixed(1)}" cy="${cy.toFixed(1)}" r="3.5" fill="#fff" stroke="${col}" stroke-width="1.5" stroke-opacity="0.55"/>`;
            s += `<text x="${cx.toFixed(1)}" y="${(cy - 7).toFixed(1)}" text-anchor="middle" font-size="9.5" font-weight="600" fill="${col}" fill-opacity="0.45">${r.toFixed(1)}</text>`;
        } else if (cl === 'mid') {
            s += `<circle cx="${cx.toFixed(1)}" cy="${cy.toFixed(1)}" r="3.5" fill="${col}" fill-opacity="0.6" stroke="#fff" stroke-width="1.5"/>`;
            s += `<text x="${cx.toFixed(1)}" y="${(cy - 7).toFixed(1)}" text-anchor="middle" font-size="9.5" font-weight="600" fill="${col}" fill-opacity="0.7">${r.toFixed(1)}</text>`;
        } else {
            s += `<circle cx="${cx.toFixed(1)}" cy="${cy.toFixed(1)}" r="3.5" fill="${col}" stroke="#fff" stroke-width="1.5"/>`;
            s += `<text x="${cx.toFixed(1)}" y="${(cy - 7).toFixed(1)}" text-anchor="middle" font-size="9.5" font-weight="600" fill="${col}">${r.toFixed(1)}</text>`;
        }
    });

    // 점선 구분선
    s += `<line x1="${pL - 4}" y1="${divY}" x2="${VW - pR}" y2="${divY}" stroke="#ddd" stroke-width="1" stroke-dasharray="4,3"/>`;

    // 리뷰수 원(circle) + N건 레이블 — 검정색, 리뷰 수 비율로 연속 농도 표현
    const circleR  = Math.min(step * 0.30, 10);
    const circleCY = divY + countH * 0.42;
    counts.forEach((c, i) => {
        const cx      = xOf(i);
        const opacity = +(0.10 + (c / maxC) * 0.80).toFixed(3);   // 리뷰 수 비율로 선형 보간 (0.10 ~ 0.90)
        s += `<circle cx="${cx.toFixed(1)}" cy="${circleCY.toFixed(1)}" r="${circleR.toFixed(1)}" fill="#FA2D43" fill-opacity="${opacity}"/>`;
        s += `<text x="${cx.toFixed(1)}" y="${(circleCY + circleR + 9).toFixed(1)}" text-anchor="middle" font-size="8.5" fill="#888">${c}건</text>`;
    });

    // X축 레이블 (WXX 형식만 추출)
    labels.forEach((lbl, i) => {
        const match = String(lbl).match(/W\d+/);
        const shortLbl = match ? match[0] : lbl;
        s += `<text x="${xOf(i).toFixed(1)}" y="${(circleCY - circleR - 4).toFixed(1)}" text-anchor="middle" font-size="9" fill="#999">${shortLbl}</text>`;
    });

    s += '</svg>';

    container.innerHTML = s;
}
