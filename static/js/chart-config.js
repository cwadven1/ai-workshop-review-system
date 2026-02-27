/**
 * Chart.js 트렌드 차트 초기화
 * 평점 기준 색상 코딩 바 차트 + 리뷰 수 라인 (mixed chart)
 */
function initTrendChart(canvasId, data) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return;

    // 평점에 따른 색상 (빨강 → 초록 그라데이션)
    function getRatingColor(rating) {
        if (rating >= 4.5) return 'rgba(27, 158, 62, 0.85)';    // 진초록
        if (rating >= 4.0) return 'rgba(76, 175, 80, 0.85)';    // 초록
        if (rating >= 3.5) return 'rgba(139, 195, 74, 0.85)';   // 연두
        if (rating >= 3.0) return 'rgba(255, 193, 7, 0.85)';    // 노랑
        if (rating >= 2.5) return 'rgba(255, 152, 0, 0.85)';    // 주황
        if (rating >= 2.0) return 'rgba(255, 87, 34, 0.85)';    // 빨간주황
        return 'rgba(244, 67, 54, 0.85)';                       // 빨강
    }

    function getRatingBorderColor(rating) {
        if (rating >= 4.5) return '#1B9E3E';
        if (rating >= 4.0) return '#4CAF50';
        if (rating >= 3.5) return '#8BC34A';
        if (rating >= 3.0) return '#FFC107';
        if (rating >= 2.5) return '#FF9800';
        if (rating >= 2.0) return '#FF5722';
        return '#F44336';
    }

    const bgColors = data.ratings.map(r => getRatingColor(r));
    const bdColors = data.ratings.map(r => getRatingBorderColor(r));

    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: data.labels,
            datasets: [
                {
                    label: '월 평균 평점',
                    data: data.ratings,
                    backgroundColor: bgColors,
                    borderColor: bdColors,
                    borderWidth: 2,
                    borderRadius: 6,
                    borderSkipped: false,
                    barPercentage: 0.65,
                    order: 1,  // 바가 라인 앞에 그려짐
                },
                {
                    label: '리뷰 수',
                    data: data.review_counts,
                    type: 'line',  // mixed chart: bar + line
                    borderColor: 'rgba(108, 117, 125, 0.6)',
                    backgroundColor: 'rgba(108, 117, 125, 0.1)',
                    fill: true,
                    tension: 0.3,
                    pointRadius: 3,
                    pointBackgroundColor: 'rgba(108, 117, 125, 0.8)',
                    pointHoverRadius: 5,
                    borderWidth: 1.5,
                    yAxisID: 'y1',
                    order: 0,  // 바 뒤에 그려짐
                },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            layout: {
                padding: { top: 30 },
            },
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: 'rgba(0,0,0,0.8)',
                    titleFont: { size: 14, weight: 'bold' },
                    bodyFont: { size: 13 },
                    padding: 12,
                    cornerRadius: 8,
                    callbacks: {
                        title: function(items) {
                            return items[0].label;
                        },
                        label: function(context) {
                            if (context.dataset.label === '월 평균 평점') {
                                const idx = context.dataIndex;
                                return '  평균 평점: ★ ' + data.ratings[idx].toFixed(1) + '점';
                            } else {
                                return '  리뷰 수: ' + context.parsed.y + '건';
                            }
                        },
                    },
                },
            },
            scales: {
                y: {
                    min: 0,
                    max: 5,
                    ticks: {
                        stepSize: 1,
                        callback: function(value) {
                            const labels = ['', '★', '★★', '★★★', '★★★★', '★★★★★'];
                            return labels[value] || value;
                        },
                        font: { size: 12 },
                        color: '#666',
                    },
                    grid: {
                        color: 'rgba(0,0,0,0.05)',
                    },
                },
                y1: {
                    type: 'linear',
                    display: true,
                    position: 'right',
                    min: 0,
                    ticks: {
                        callback: function(value) {
                            return value + '건';
                        },
                        font: { size: 10 },
                        color: '#aaa',
                    },
                    grid: {
                        drawOnChartArea: false,
                    },
                    title: {
                        display: true,
                        text: '리뷰 수',
                        font: { size: 10 },
                        color: '#aaa',
                    },
                },
                x: {
                    ticks: {
                        font: { size: 11 },
                        color: '#666',
                    },
                    grid: { display: false },
                },
            },
            animation: {
                duration: 800,
                easing: 'easeOutQuart',
                onComplete: function() {
                    const chart = this;
                    const chartCtx = chart.ctx;
                    const meta = chart.getDatasetMeta(0);  // 바 dataset (index 0)

                    meta.data.forEach(function(bar, index) {
                        const rating = data.ratings[index];
                        const count = data.review_counts[index];

                        // 평점 숫자
                        chartCtx.save();
                        chartCtx.font = 'bold 12px -apple-system, sans-serif';
                        chartCtx.textAlign = 'center';
                        chartCtx.textBaseline = 'bottom';
                        chartCtx.fillStyle = '#333';
                        chartCtx.fillText(rating.toFixed(1), bar.x, bar.y - 16);

                        // 리뷰 수
                        chartCtx.font = '10px -apple-system, sans-serif';
                        chartCtx.fillStyle = '#999';
                        chartCtx.fillText(count + '건', bar.x, bar.y - 4);
                        chartCtx.restore();
                    });
                },
            },
        },
    });
}
