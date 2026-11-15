document.addEventListener('DOMContentLoaded', () => {
  const canvas = document.getElementById('expiryChart');
  if (!canvas) return;
  let labels, counts;
  try {
    labels = JSON.parse(canvas.dataset.labels || '[]');
    counts = JSON.parse(canvas.dataset.values || '[]').map(value => Number(value) || 0);
  } catch (error) {
    console.error('Invalid dashboard chart data:', error);
    return;
  }
  if (typeof Chart === 'undefined') {
    console.error('Chart.js could not be loaded. Check your network connection.');
    canvas.insertAdjacentHTML('afterend', '<p class="text-muted">Chart unavailable: Chart.js failed to load.</p>');
    return;
  }
  new Chart(canvas, {
    type: 'bar',
    data: { labels, datasets: [{ label: 'KYC Expiries', data: counts, backgroundColor: '#3479ec', hoverBackgroundColor: '#194bb3', borderRadius: 7, maxBarThickness: 45 }] },
    options: { responsive: true, maintainAspectRatio: false,
      animation: {
          duration: window.matchMedia(
              "(prefers-reduced-motion: reduce)"
          ).matches ? 0 : 500,
          easing: "easeOutQuart"
      },
      plugins: { legend: { display: false }, tooltip: { backgroundColor: '#172b4d', padding: 12 } },
      scales: { y: { beginAtZero: true, ticks: { precision: 0 }, grid: { color: '#edf1f7' } }, x: { grid: { display: false } } }
    }
  });
});
