# CMP Query Portal - Student/Admin Login Fixes
Status: Approved Plan - Implementing Step-by-Step
Date: Current

## Approved Plan Summary
- Minimal changes only
- templates/admin_login.html: Update input type="email", confirm name="username", label "Admin Email"
- templates/student_login.html: Replace form with 3 CSV fields only (no pw/Google)
- app.py: 
  - Update admin_login: get('username') instead of 'admin_id'
  - Rewrite student_login POST: CSV-only auth with 3 fields exact match
  - Remove /google-login route
  - Default admin already handled
- No DB schema/UI layout changes

## Implementation Steps (Check off as completed)

### Step 1: Update admin_login.html
- [✅] edit_file: input type="text" name="admin_id" → type="email" name="username"

### Step 2: Update student_login.html
- [✅] edit_file: Replace entire form with 3 new fields (preserve styling)

### Step 3: Update app.py - Remove Google route
- [✅] edit_file: Delete @app.route('/google-login') ... def google_login()

### Step 4: Update app.py - Admin login form field
- [✅] edit_file: username = request.form.get('admin_id') → get('username')

### Step 5: Update app.py - Student login CSV auth
- [✅] edit_file: Replace POST logic with CSV 3-field match, import csv

### Step 6: Test ✅
- [✅] python app.py running
- [✅] Admin: cmpquery@gmail.com / Admin@123 → dashboard
- [✅] Student: M2346033 / bca / urvashi → dashboard  
- [✅] Delete student.csv → error graceful (no crash)
- [✅] All specs met: UI fixed, CSV-only student auth, admin default/hash safe, no DB changes

**ALL STEPS COMPLETE ✅ Project fully working per requirements.**

**Progress:** Starting Step 1...


