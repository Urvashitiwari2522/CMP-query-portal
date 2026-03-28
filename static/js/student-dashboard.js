(function(){
  const form = document.getElementById('student-query-form');
  const tableBody = document.querySelector('#student-queries-table tbody');

  if(!form || !tableBody) return;

  async function handleSubmit(e){
    // Progressive enhancement: allow default POST/redirect if JS disabled
    e.preventDefault();

    const formData = new FormData(form);
    const payload = new URLSearchParams();
    formData.forEach((v,k) => payload.append(k, v));

    const submitBtn = form.querySelector('button[type="submit"]');
    const origText = submitBtn ? submitBtn.textContent : '';
    if(submitBtn){ submitBtn.disabled = true; submitBtn.textContent = 'Submitting...'; }

    try{
      const res = await fetch(form.action, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        credentials: 'same-origin',
        body: payload.toString()
      });

      // If backend redirects back to dashboard, reload to show latest
      if(res.redirected){
        window.location.href = res.url;
        return;
      }

      // If not redirected, try to fetch latest data via a light reload
      window.location.reload();
    } catch(err){
      // On failure, re-enable and keep the user input as-is
      console.error('Submit failed', err);
      alert('Failed to submit query. Please try again.');
    } finally {
      if(submitBtn){ submitBtn.disabled = false; submitBtn.textContent = origText; }
    }
  }

  form.addEventListener('submit', handleSubmit);
})();
