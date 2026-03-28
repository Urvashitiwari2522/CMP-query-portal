### Repository: CMP Query Management Portal — quick guide for AI coding agents

This small Flask app serves static templates and a few simple routes in `app.py`. The goal of this file is to provide direct, concrete hints so an AI coding assistant can be productive immediately.

- Project entry: `app.py` (single Flask app). Key routes:
  - `/` -> renders `templates/index.html`
  - `/admin-login` -> GET/POST; form fields: `admin_id`, `password`; template: `templates/admin_login.html`
  - `/student-login` -> GET/POST; form fields: `student_id`, `password`; template: `templates/student_login.html`
  - `/admin-forgot-password`, `/student-forgot-password` -> simple POST handlers that expect `admin_id` or `student_id`
  - `/guest-query` -> POST expects `guest_name`, `guest_email`, `guest_query`

- Run / debug steps (Windows PowerShell):
  1. Ensure Python 3.8+ is installed and on PATH.
  2. From project root run:

```powershell
python app.py
```

  Flask runs with `debug=True` in `app.py`. For production changes, replace `app.run(debug=True)` with a proper WSGI server.

- Templates and static files:
  - Templates are in `templates/`. Use `render_template('<name>.html')` as in `app.py`.
  - Static assets live in `static/` (`css/style.css`, `js/main.js`, `images/*`). Use `url_for('static', filename='...')` in templates.

- Common patterns and gotchas (explicit, project-specific):
  - Forms must use the exact name attributes the handlers read. Example: `admin_login` reads `request.form.get('admin_id')` and `request.form.get('password')`. Templates already match these names.
  - Index page (`templates/index.html`) uses anchor tags with `href="#"` for login buttons — update them to route to `/student-login` and `/admin-login` when implementing navigation. Current behaviour: clicking those buttons does nothing.
    - Example fix: change `<a href="#" class="btn-main">Student Login</a>` to `<a href="{{ url_for('student_login') }}" class="btn-main">Student Login</a>`.
  - `student_login.html` uses `action="{{ url_for('student_login') }}"` while `admin_login.html` used `action="/admin-login"` — both work, but favor `url_for(...)` for portability.

- Editing guidance examples:
  - To wire index login links, edit `templates/index.html` and replace the three `href="#"` anchors with `{{ url_for('student_login') }}` and `{{ url_for('admin_login') }}`.
  - To add real authentication, replace the hard-coded checks in `app.py` (e.g., `if admin_id == 'admin' and password == 'admin123':`) with a call to a new `auth` module or database lookup. Keep existing route signatures for compatibility.

- Validation & testing notes:
  - The app has no tests. For quick manual verification:
    - Start server, open http://127.0.0.1:5000/ in browser, click Student/Admin Login, submit the hard-coded credentials (`student`/`student123` or `admin`/`admin123`) and confirm redirect to `/`.
  - If POST forms raise 405 or do nothing, check the `form` `method` and `action` attributes and ensure names match `request.form.get(...)` in `app.py`.

- Files to inspect when debugging:
  - `app.py` — routes and form field names
  - `templates/index.html` — login buttons currently link to `#` (likely the user's reported issue)
  - `templates/admin_login.html`, `templates/student_login.html` — form markup
  - `static/js/main.js` — front-end behaviour (no route wiring expected here)

- Minimal example change to fix reported issue (linking from index):
  - Replace in `templates/index.html`:
    - `<a href="#" class="btn-main">Student Login</a>` -> `<a href="{{ url_for('student_login') }}" class="btn-main">Student Login</a>`
    - `<a href="#" class="btn-secondary">Admin Login</a>` -> `<a href="{{ url_for('admin_login') }}" class="btn-secondary">Admin Login</a>`

If you want, I can apply that change now and run the app locally to verify the login flow. Otherwise, tell me which area you'd like me to edit first (index links, auth logic, or tests).
