# Frontend Listing Guide (Subjects, Topics, Exams)

How the FE should call the list/read endpoints for core masters. All routes sit under the API prefix (`/api/v1`) and require `X-API-Key` plus the default rate limit (60 req/min per key).

## Common setup
- Base URL (default): `http://localhost:8000/api/v1`
- Auth header: `X-API-Key: <raw_key>` (see README for generating a key).
- Content type: `application/json` for all requests.
- Rate limiting: 60 req/min; cache list results client-side when possible.

## Subjects
- Endpoint: `GET /subjects`
- Query params:
  - `is_active` (bool, optional) — filter active/inactive.
  - `search` (str, optional) — case-insensitive match on `name`.
  - `tags` (repeatable) — all tags must match (e.g. `?tags=science&tags=physics`).
  - `skip`/`limit` (int, defaults 0/50) — pagination.
  - `sort_by` (`name|created_at|updated_at|slug`, default `name`), `sort_order` (`asc|desc`).
- Response: `PaginatedSubjects` — `{items: SubjectResponse[], total, skip, limit}`.
- SubjectResponse fields: `id`, `name`, `slug`, `description?`, `tags[]`, `metadata?`, `is_active`, `created_at`, `updated_at`.
- Example call (JS):
```js
await fetch("http://localhost:8000/api/v1/subjects?is_active=true&limit=100", {
  headers: { "X-API-Key": apiKey }
}).then(r => r.json());
```
- Local seed example (if `init_db` is not removed): one subject exists — `"Physics"` with `id: "subject_physics"`, `slug: "physics"`.

## Topics
- Endpoint: `GET /topics`
- Query params:
  - `subject_id` (str, optional) — filters topics for a subject; omit to get all topics.
- Response: `TopicResponse[]`.
- TopicResponse fields: `id`, `subject_id`, `name`, `slug`, `description?`, `difficulty_weight (0-1)`, `bloom_level?`, `related_topic_ids[]`, `prerequisite_topic_ids[]`, `tags[]`, `metadata?`, `is_active`, `created_at`, `updated_at`.
- Example call:
```js
await fetch(`http://localhost:8000/api/v1/topics?subject_id=subject_physics`, {
  headers: { "X-API-Key": apiKey }
}).then(r => r.json());
```
- Local seed example: one topic — `id: "topic_thermodynamics"`, `subject_id: "subject_physics"`, `slug: "thermodynamics"`.

## Exams
- Endpoint: `GET /exams`
- Query params:
  - `active_only` (bool, default `false`) — set `true` to hide inactive exams.
- Response: `ExamResponse[]`.
- ExamResponse fields: `exam_id`, `code`, `name`, `description?`, `syllabus: ExamSyllabusItem[]`, `version?`, `is_active`, `metadata?`, `created_by?`, `created_at`, `updated_at`.
- ExamSyllabusItem: `{subject_id, topic_ids: string[], weight?: number}`.
- Example call:
```js
await fetch("http://localhost:8000/api/v1/exams?active_only=true", {
  headers: { "X-API-Key": apiKey }
}).then(r => r.json());
```
- Local seed example: exam `"JEE Main"` with `exam_id: "exam_jee_main"`, `code: "JEE_MAIN"`, syllabus covering `subject_physics` -> `topic_thermodynamics`.

### Exam syllabus only
- Endpoint: `GET /exams/{exam_id}/syllabus`
- Returns `ExamSyllabusItem[]` (same shape as above). Useful when you already have an exam id and need just the subject/topic mapping.

## UI usage patterns
- Subject dropdowns: call `/subjects?is_active=true&limit=200&sort_by=name` once, cache the results; use `total` to show count.
- Topic selectors: call `/topics?subject_id=<subject_id>` after subject selection; fall back to `/topics` only for admin views.
- Exams listing: default to `/exams?active_only=true`; show code + name; link to `/exams/{exam_id}/syllabus` to render coverage chips.
- Error handling: `403` means missing/invalid API key; `429` means rate limit reached — back off and retry after `Retry-After` header if present.
