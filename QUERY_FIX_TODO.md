# Query Mapping Fix - Approved
Status: Plan Approved - Step-by-Step Implementation

## Plan Summary
Student login: CSV match → lookup/create Student(enrollment_no as student_id) → session['student_id']=s.id (numeric FK)
submit_query: attaches to Query.student_id 
Dashboards: already filter by student_id FK ✓

## Steps
### 1. [✅] Edit app.py student_login: Add Student lookup/create + session['student_id']
### 2. [✅] Test: login → submit → student dashboard shows / admin student section
### 3. [✅] Complete ✓

**Fixed:** Student queries now link via student_id FK → appear in student dashboard + admin student section (not guest).

