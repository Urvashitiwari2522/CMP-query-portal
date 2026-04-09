# CMP Query Portal Fix - Step-by-Step Implementation Plan

## Status: [IN PROGRESS] 

**Completed Steps:**
- [x] Analyzed issues (IntegrityError email NULL, duplicate code, None fields)
- [x] Fixed models.py (Query.email nullable=True)
- [x] Cleaned app.py /submit_query (single robust logic, print debug, dummy email students, try/except DB)
- [x] Retained guest/student separation & validation

**Status:** READY TO TEST - All fixes applied

**Test Commands:**
```
python app.py
```
1. Guest: /guest-query → fill → submit (check terminal SUCCESS)
2. Student login → dashboard → submit (check own list)
3. Admin dashboard → see both sections

**Expected Terminal Output:**
```
=== SUBMIT_QUERY DEBUG ===
SUCCESS: Query #X saved (guest/student)
```

Files fixed. Run tests to verify no errors/data flow.

