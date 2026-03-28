(function(){
  const form = document.getElementById('admin-login-form');
  const usernameEl = document.getElementById('username');
  const passwordEl = document.getElementById('password');
  const submitBtn = document.getElementById('login-btn');
  const errorEl = document.getElementById('form-error');

  function setError(msg){
    if(!errorEl) return;
    errorEl.textContent = msg || '';
    errorEl.style.display = msg ? 'block' : 'none';
  }

  async function handleSubmit(e){
    e.preventDefault();
    setError('');

    const username = (usernameEl?.value || '').trim();
    const password = (passwordEl?.value || '').trim();

    if(!username || !password){
      setError('Please enter both username and password.');
      return;
    }

    submitBtn.disabled = true;
    submitBtn.textContent = 'Logging in...';

    try {
      const resp = await fetch('/api/admin/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin',
        body: JSON.stringify({ username, password })
      });

      let data = null;
      try { data = await resp.json(); } catch(_) { data = null; }

      const ok = resp.ok && data && (data.success === true || data.status === 'success');
      if(ok){
        window.location.assign('/admin/dashboard');
        return;
      }

      const msg = (data && (data.message || data.error)) || 'Invalid username or password';
      setError(msg);
    } catch (err){
      setError('Network error. Please try again.');
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = 'Login';
    }
  }

  if(form){
    form.addEventListener('submit', handleSubmit);
  }
})();
