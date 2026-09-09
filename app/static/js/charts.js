// Chart.js helpers - consistent, restrained styling shared by all pages.
window.AIA = window.AIA || {};

AIA.palette = ['#5b5bd6', '#16794c', '#9a6700', '#b42318', '#0e7490', '#7c3aed',
               '#a16207', '#475569'];

AIA.baseOptions = function (extra) {
  const base = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false, labels: { font: { family: 'Segoe UI, sans-serif', size: 11 } } },
      tooltip: {
        backgroundColor: '#16161a', padding: 9, cornerRadius: 7,
        titleFont: { size: 12 }, bodyFont: { size: 12 }, rtl: true, displayColors: false
      }
    },
    scales: {
      x: { grid: { display: false }, ticks: { font: { size: 10.5 }, color: '#9a9aa6' } },
      y: {
        beginAtZero: true,
        grid: { color: '#f1f1f4', drawBorder: false },
        ticks: { font: { size: 10.5 }, color: '#9a9aa6' }
      }
    }
  };
  return Object.assign(base, extra || {});
};

AIA.line = function (id, data, color) {
  const el = document.getElementById(id);
  if (!el || !data.labels.length) return;
  new Chart(el, {
    type: 'line',
    data: {
      labels: data.labels,
      datasets: [{
        data: data.values, borderColor: color || AIA.palette[0],
        backgroundColor: 'rgba(91,91,214,.08)', fill: true,
        tension: .35, borderWidth: 2, pointRadius: 0, pointHoverRadius: 4
      }]
    },
    options: AIA.baseOptions()
  });
};

AIA.bar = function (id, data, color, horizontal) {
  const el = document.getElementById(id);
  if (!el || !data.labels.length) return;
  new Chart(el, {
    type: 'bar',
    data: {
      labels: data.labels,
      datasets: [{
        data: data.values,
        backgroundColor: color || AIA.palette[0],
        borderRadius: 5, borderSkipped: false, maxBarThickness: 34
      }]
    },
    options: AIA.baseOptions({ indexAxis: horizontal ? 'y' : 'x' })
  });
};

AIA.doughnut = function (id, data) {
  const el = document.getElementById(id);
  if (!el || !data.labels.length) return;
  new Chart(el, {
    type: 'doughnut',
    data: {
      labels: data.labels,
      datasets: [{ data: data.values, backgroundColor: AIA.palette, borderWidth: 0 }]
    },
    options: {
      responsive: true, maintainAspectRatio: false, cutout: '62%',
      plugins: {
        legend: { position: 'bottom', rtl: true,
          labels: { boxWidth: 9, boxHeight: 9, padding: 11, font: { size: 11.5 } } },
        tooltip: { backgroundColor: '#16161a', cornerRadius: 7, rtl: true }
      }
    }
  });
};
