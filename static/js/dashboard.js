(function(){
  const ids = {
    total: 'total-count',
    pending: 'pending-count',
    inprogress: 'inprogress-count',
    resolved: 'resolved-count'
  };

  function setText(id, value){
    const el = document.getElementById(id);
    if(el) el.textContent = value;
  }

  function ensureChart(canvasEl, labels, data){
    if(typeof window.Chart !== 'function'){
      const fb = document.getElementById('chart-fallback');
      if(fb){ fb.style.display = 'block'; }
      return null;
    }

    // Create gradient fill if supported
    const ctx2d = canvasEl.getContext('2d');
    let bg = '#2563eb';
    try {
      const grad = ctx2d.createLinearGradient(0, 0, 0, canvasEl.height || 300);
      grad.addColorStop(0, 'rgba(37,99,235,0.85)');
      grad.addColorStop(1, 'rgba(37,99,235,0.25)');
      bg = grad;
    } catch(_) { /* fallback to solid */ }

    return new window.Chart(canvasEl, {
      type: 'bar',
      data: {
        labels,
        datasets: [{
          label: 'Queries',
          data,
          backgroundColor: bg,
          borderColor: '#2563eb',
          borderWidth: 1,
          borderRadius: 10,
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        layout: { padding: 0 },
        scales: {
          x: {
            display: true,
            grid: { display: false, drawBorder: false },
            ticks: { autoSkip: true, maxTicksLimit: 10 }
          },
          y: {
            display: true,
            beginAtZero: true,
            grid: { color: 'rgba(0,0,0,0.06)', drawBorder: false },
            ticks: { precision: 0 }
          }
        },
        plugins: {
          legend: { display: false },
          title: {
            display: true,
            text: 'Queries Over Time',
            color: '#1f2937',
            font: { weight: '700', size: 14 }
          }
        }
      }
    });
  }

  async function loadDashboard(){
    try{
      const res = await fetch('/api/admin/dashboard', { credentials: 'same-origin' });
      if(!res.ok) throw new Error('Bad response');
      const data = await res.json();

      const counts = data.counts || {};
      setText(ids.total, counts.total ?? 0);
      setText(ids.pending, counts.pending ?? 0);
      setText(ids.inprogress, counts.in_progress ?? 0);
      setText(ids.resolved, counts.resolved ?? 0);

      const ts = Array.isArray(data.timeseries) ? data.timeseries : [];
      const labels = ts.map(d => d.date);
      const series = ts.map(d => d.count);
      const canvas = document.getElementById('queryTrendChart');
      if(canvas){ ensureChart(canvas, labels, series); }
    } catch(err){
      setText(ids.total, '-');
      setText(ids.pending, '-');
      setText(ids.inprogress, '-');
      setText(ids.resolved, '-');
      const fb = document.getElementById('chart-fallback');
      if(fb){ fb.style.display = 'block'; }
    }
  }

  if(document.readyState === 'loading'){
    document.addEventListener('DOMContentLoaded', loadDashboard);
  } else {
    loadDashboard();
  }
})();
