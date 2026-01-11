Master Service – Catalog & Content (MongoDB)
===========================================

Scope
-----
- Authoritative catalog for series → papers/tests → sections → questions.
- No user attempts/progress/scores (owned by User Service).
- Validates JWT (Auth) and enforces RBAC for admin flows.
- Future-ready for pricing/entitlements metadata; multilingual content.

Collections (MongoDB)
---------------------
- exams  
  - `_id`/`exam_id` (string, pk), `code` (unique), `name` {lang: text}, `description` {lang: text}, `is_active`, `created_at`, `updated_at`.

- tags (subjects/tags)  
  - `_id` (string), `type` ("subject"|"tag"), `name` {lang}, `slug` (unique), `is_active`, `metadata`.

- taxonomy  
  - `_id` (topic id), `subject_id` (ref tags), `name` {lang}, `slug`, `parent_id`, `depth`, `tags` [], `is_active`.

- questions (question bank, schema_version=2)  
  - `question_id`, `type`, `text` {lang}, `options` [{id,text{lang}}], `answer_key`, `solution`, `taxonomy` (subject_id, topic_ids, target_exam_ids), `difficulty`, `tags`, `language`, `usage` (status, is_active, visibility), `meta` (estimated_time_sec, source), `search_blob`, `rand_key`, `created_at`, `updated_at`.

- series  
  - `series_id`, `code` (unique), `slug` (unique), `title` {lang}, `description` {lang}, `exam_id`, `subjects` [], `tags` [], `difficulty`, `language_codes` [], `status` (DRAFT|PUBLISHED|ARCHIVED), `published_at`, `archived_at`, `version`, `active_version`, `is_active`, `new_until`, `availability` (available_from, available_to, regions), `access` (access_type, product_id, currency, base_price, discount, validity_days), `counters` (total_papers, total_questions, total_duration_mins), `metadata`, `created_at`, `updated_at`.

- papers (versioned snapshots)  
  - `_id`: paper_id + version, `paper_id`, `series_id`, `version`, `status`, `name` {lang}, `description` {lang}, `language_codes` [], `pattern` (sections[], totals), `settings`, `availability`, `questions` (refs with seq, section_id, question_type, subject_id, topic_ids, difficulty, marks, negative_marks, is_bonus, is_optional), `published_at`, `archived_at`, `created_at`, `updated_at`.

- pricing_products (metadata only)  
  - `_id`, `name`, `currency`, `base_price`, `discount`, `metadata`.

- content_revisions (audit, optional)  
  - `_id`, `entity`, `entity_id`, `version`, `snapshot`, `created_at`, `created_by`.

Publishing & Versioning
-----------------------
- Snapshot-by-version: papers stored with `{paper_id, version, status}`; series has `active_version`. Publishing creates new version docs; published snapshots immutable.
- Status lifecycle: DRAFT → PUBLISHED → ARCHIVED. Fields: `published_at`, `archived_at`.
- Attempts bind to `{paper_id, version}` to stay stable.

“New” Label
-----------
- Field `new_until` on series. UI shows “New” if `now < new_until` (set to `published_at + N days` at publish time).

Pricing / Availability
----------------------
- Series embeds `access` (`access_type`: FREE|PAID|SUBSCRIPTION|INVITE_ONLY, `product_id`, `currency`, `base_price`, `discount`, `validity_days`) and `availability` (`available_from`, `available_to`, `regions`). Master derives `availability_status`: AVAILABLE|LOCKED|EXPIRED.

Listing DTO (GET /v1/series)
----------------------------
- Fields: `series_id`, `title`, `exam_id`, `tags`, `subjects`, `difficulty`, `language_codes`, `status`, `published_at`, `new_until`, `availability_status`, `access.access_type`, `counters.total_papers`, `counters.total_questions`, `counters.total_duration_mins`.
- Filters: exam_id, difficulty, language, tags, status (published), search (title). Sort: published_at desc (newest). Pagination: skip/limit or cursor.
- Counters denormalized on series; update when publishing papers or via batch job. Avoid $lookup in listing.

Attempt vs Review Payload (GET /v1/papers/{paperId}/payload)
------------------------------------------------------------
- Multilingual fields stored as `{ en: "...", hi: "..." }`; server selects requested language with fallback.
- Attempt mode excludes `answer_key`/`solution`. Review mode includes them.
- Shuffle optional when allowed by settings; maintain `seq` stability for attempts.

Admin Content APIs (outline)
----------------------------
- POST `/v1/admin/series` (create draft), PATCH `/v1/admin/series/{id}`, POST `/v1/admin/series/{id}/publish`, POST `/v1/admin/series/{id}/archive`.
- POST `/v1/admin/series/{id}/papers` (create draft paper), PATCH `/v1/admin/papers/{paperId}`, POST `/v1/admin/papers/{paperId}/publish`.
- POST `/v1/admin/questions`, PATCH `/v1/admin/questions/{id}`, POST `/v1/admin/import/questions` (bulk).
- Errors: `{ "error": "VALIDATION_ERROR", "details": [...] }`.

Events / Outbox (integration with User Service)
-----------------------------------------------
- Events emitted via outbox: `series.published`, `series.updated`, `paper.published|updated`, `question.updated`.
- Payload example: `{ "series_id": "...", "version": 3, "status": "PUBLISHED", "published_at": "...", "counters": {...}, "changed_fields": [...] }`.
- IDs never reused; stable references for User Service caches.

Security / RBAC
---------------
- JWT verification via Auth JWKS; roles enforced.
- Roles: ADMIN (full), CONTENT_MANAGER (create/update/publish), REVIEWER (review mode), PUBLIC (read published only).
- Review mode gated by role or entitlement token from User Service.

Indexes (MongoDB)
-----------------
- series: `{status, is_active, published_at}`, `{exam_id, status, is_active}`, `{tags}`, `{language_codes}`, `{difficulty}`, text index on `title.en`, unique `{code}`, `{slug}`.
- papers: `{paper_id, version}` unique; `{series_id, status, is_active}`; `{status, published_at}`.
- questions: `{taxonomy.subject_id}`, `{taxonomy.topic_ids}`, `{difficulty}`, `{language}`, text index on `search_blob`.
- pricing_products: `_id`.
- Avoid $lookup for listing by using denormalized counters.

Performance Notes
-----------------
- Keep papers bounded; embed question references, not content.
- Denormalize counters; cache listings; invalidate via events.
- Bulk imports with ordered=false; projection on listings to avoid heavy payloads.
- Stable IDs (UUID/ULID) and immutable published snapshots prevent breaking attempts.
