CMP Query Management Portal — Firebase prototype setup

Goal
----
Create a lightweight, deployable prototype using Firebase (Firestore + Auth + Hosting). Keep the UI as the current Flask templates (static HTML/CSS) or export to static files and host on Firebase Hosting. Use Firestore as the database and Firebase Authentication for student/admin sign-in (email/password).

Architecture
------------
- Firebase Authentication: manage Student and Admin accounts (email/password). Guest can submit queries without logging in or optionally register.
- Firestore (NoSQL): store `queries` collection and `users` collection.
- Firebase Hosting: host the prototype static site or the built Flask frontend exported to static files.
- (Optional) Cloud Functions: server-side actions (send email notifications when admin responds) — out of scope for initial prototype; document steps.

Data model (Firestore)
-----------------------
collections:
- users (document id = uid)
  - displayName: string
  - email: string
  - role: 'student' | 'admin' | 'guest'
  - createdAt: timestamp

- queries (auto-id documents)
  - userId: string | null (guest)
  - name: string
  - email: string
  - category: string (optional)
  - message: string
  - status: 'pending' | 'resolved' | 'in-progress'
  - response: string
  - createdAt: timestamp
  - resolvedAt: timestamp (optional)

Workflows
---------
1. Query submission (Student/Guest): UI collects name, email, message, creates a Firestore document in `queries` with status `pending`.
2. Admin dashboard: fetch queries (real-time) and update `status` and `response` fields. Optionally write `resolvedAt` timestamp.
3. User view: query list filters by userId (or email for guests) and shows `response` when present.
4. (Optional) Notification: Cloud Function triggers on `queries` update and sends email via SMTP or third-party API.

Prioritized plan (first 3 steps)
--------------------------------
1. Implement Firestore data model and a simple client-side script to `POST` guest queries directly to Firestore using Firebase Web SDK. (Low friction; no server required.)
2. Add Firebase Authentication for Students (email/password) and protect the student dashboard (require login). Create a simple Admin rule (admin users flagged in `users` collection).
3. Create an Admin dashboard UI that lists queries and allows status/response editing. Optionally use Firestore rules to restrict writes.

Security notes
--------------
- Use Firestore Security Rules to ensure only admins can update `response` and `status` fields.
- Require authenticated users for student-specific data reads/writes.
- Do not store secrets in client-side code; use environment config via Firebase Hosting.

How I can help next (pick one)
------------------------------
- A: Add Firebase Web SDK snippets and a small JS file to the repo that posts guest queries to Firestore (minimal changes to current templates).
- B: Scaffold Authentication (client-side) and add a protected student dashboard page using Firebase Auth.
- C: Scaffold an Admin dashboard page that reads/writes queries using Firestore (plus notes on security rules).

If you pick one, I will implement it and provide step-by-step deploy/test instructions for Firebase Hosting. If you want the backend to remain Flask with Firestore integration (instead of client-side Firebase SDK), say so and I will instead add server-side Firestore usage (requires service account credentials and a small backend change).
