# FAQ Auto-Update Feature Implementation

## Tasks
- [x] Update FAQ Model: Add `frequency` (Integer, default=1) and `category` (String, nullable=True) fields to the FAQ model in models.py.
- [x] Implement Auto-Update Logic: In the `submit_query` route, after saving the query, check for exact matches on the query message in existing FAQs. If found, increment frequency; if not, create a new FAQ with frequency=1, question=message, answer=None, category=category.
- [ ] Update Admin FAQ Management: Modify `/admin/faq` route to order FAQs by frequency descending and display frequency in the template.
- [ ] Update Public FAQ Page: Modify `/faq` route to order FAQs by frequency descending.
- [ ] Create Missing Templates: Create `admin_faq.html` for admin management (with frequency display and edit capabilities) and `faq.html` for public viewing.
- [x] Database Migration: Ensure the new fields are added via migration logic.
- [x] Test query submission and FAQ auto-creation.
- [x] Test admin FAQ management.
- [x] Test public FAQ page.
