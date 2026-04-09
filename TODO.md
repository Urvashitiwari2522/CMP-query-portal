# CMP Query Portal Stats Dynamic Update - Task Progress

## Plan (Approved)
1. ✅ **Understand files** - app.py home(), models.py Query, templates/index.html stats analyzed
2. **Update app.py**: Add stats calculation + pass vars to home() render_template
3. **Update templates/index.html**: Replace hardcoded stats with Jinja2 vars
4. **Test**: Submit queries → verify stats update on homepage
5. **Demo**: Confirm real-time growth visible

## Current Step: 5/5 Complete ✅

**Stats Section Dynamic Update Complete!**

- ✅ app.py home(): Added real DB stats calculation (total/resolved/active/avg time)
- ✅ templates/index.html: Replaced hardcoded → `{{ resolved_queries }}`, `{{ avg_response_time }} Hours`, `{{ active_queries }}`
- ✅ Edge cases: No div/0, case-insensitive status, null created_at handled
- ✅ Auto-updates on query submit/resolve (no polling needed)

**Test:** 
1. Visit http://127.0.0.1:5000/ → see real stats from DB
2. Submit guest query → refresh home → Active Queries +1  
3. Admin resolve query → refresh → Resolved +1, Active -1, Avg time updates

**Demo Ready** 🚀

