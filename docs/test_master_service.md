# Tests Master Service (schema_version=1)

Authoritative service for test structures and metadata (no user attempts, no question content). Tests reference questions by `question_id` only; question text/options/answers remain in the Questions Master Service.

## Scope
- ✅ Create/Update/Delete tests (admin/internal).
- ✅ Fetch a single test with sections and ordered `question_ids`.
- ✅ Discover/List tests with filters (exam/subject/tags/difficulty/language).
- ✅ Lightweight stats (total questions, estimated duration).
- ✅ Enforce section-wise ordering and uniqueness constraints.
- ❌ No user answers/attempts/scores.
- ❌ No question text/options/answers/solutions.
- ❌ No `user_id` anywhere.

## Data Model (collection: `tests`)
Canonical document:
```json
{
  "_id": "t_<uuid>",
  "test_id": "t_<uuid>",
  "schema_version": 1,
  "version": 1,

  "name": "Polity Mock Test 1",
  "description": "Indian Polity — Full Coverage",

  "target_exam_id": "exam_upsc",
  "subject_ids": ["polity"],
  "tags": ["polity","mains","2026"],
  "difficulty_estimate": 2.3,
  "language": "en",

  "metadata": {
    "duration_min": 120,
    "total_marks": 200,
    "negative_marking": true,
    "marking_scheme": {
      "correct": 2,
      "incorrect": -0.66
    }
  },

  "structure": [
    {
      "section_id": "sec_constitution",
      "name": "Indian Constitution",
      "description": "Questions from Constitution",
      "question_ids": ["q_1","q_2","q_4"],
      "count": 3,
      "order": 1
    },
    {
      "section_id": "sec_governance",
      "name": "Governance",
      "description": "Governance and Polity",
      "question_ids": ["q_5","q_7"],
      "count": 2,
      "order": 2
    }
  ],

  "display": {
    "estimated_time_min": 120,
    "total_questions": 5
  },

  "usage": {
    "status": "draft | published",
    "is_active": true
  },

  "created_at": "...",
  "updated_at": "..."
}
```

### Fields (semantics)
- `test_id`: stable business ID (mirrors `_id`).
- `name` / `description`: display strings.
- `target_exam_id`: primary exam tag.
- `subject_ids`: array of subject references.
- `tags`: arbitrary labels for filtering.
- `difficulty_estimate`: numeric average (admin-set or derived).
- `language`: ISO-ish language code (e.g., `en`).
- `metadata`: duration/marks/marking rules; `negative_marking=true` requires `marking_scheme.incorrect`.
- `structure`: ordered sections with ordered `question_ids`.
  - `section_id`: unique per test.
  - `question_ids`: ordered list; unique within a section.
  - `count`: must equal `len(question_ids)`.
  - `order`: unique per section; defines section display order.
- `display`: computed helpers.
  - `estimated_time_min`: typically `metadata.duration_min`.
  - `total_questions`: sum of section counts.
- `usage`: `status` (`draft`|`published`), `is_active` flag.

### Enums / allowed values
- `usage.status`: `draft`, `published`.
- `usage.is_active`: boolean.
- `structure.section_id`: string (unique per test).
- `language`: free-form string; consider constraining to known codes.

## Validation rules
- Sections must have unique `section_id`.
- `order` must be unique per section.
- `count` must equal `len(question_ids)` for each section.
- Question IDs within a section must be unique (may repeat across sections if desired).
- `metadata.duration_min` > 0.
- If `negative_marking=true`, `marking_scheme.incorrect` is required.
- `usage.status=published` requires:
  - non-empty `structure`,
  - each section has at least 1 `question_id`.
- Optional difficulty estimation: if integrating with Questions Master, you may average question difficulties; otherwise use provided `difficulty_estimate`.

## Indexes (Database._init_indexes)
- Single-field: `test_id`, `target_exam_id`, `subject_ids`, `tags`, `usage.is_active`, `usage.status`.
- Compound: `(usage.is_active, usage.status, target_exam_id)`, `(subject_ids, tags, usage.is_active)`.
- Optional: `(language, usage.is_active)`.

## Projections (response views)
- Public: hide internals if needed; keep metadata/structure/display.
- Full: full document.
- Lite: `test_id`, `name`, `tags`, `display`, optionally `target_exam_id`.

## API (base `/api/v1`, `X-API-Key` required)

### POST `/tests` — Create
- Body: `TestDocCreate` (matches model above).
- Behavior: validate; compute `display.total_questions` (sum of counts), `display.estimated_time_min` (from metadata), set IDs/version/timestamps; optionally compute `difficulty_estimate`.
- Response: full test view.

Example payload:
```json
{
  "name": "Polity Mock Test 1",
  "description": "Polity — Constitution + Governance",
  "target_exam_id": "exam_upsc",
  "subject_ids": ["polity"],
  "tags": ["polity","mains"],
  "metadata": {
    "duration_min": 120,
    "total_marks": 200,
    "negative_marking": true,
    "marking_scheme": { "correct": 2, "incorrect": -0.66 }
  },
  "structure": [
    {
      "section_id": "sec_constitution",
      "name": "Constitution",
      "question_ids": ["q_1","q_3","q_4"],
      "order": 1
    }
  ],
  "usage": { "status": "published", "is_active": true }
}
```

### PATCH `/tests/{test_id}` — Update
- Partial update; revalidate structure/metadata rules.
- Increment `version`, set `updated_at`, recompute `display.total_questions` and `display.estimated_time_min`.
- Optional: recompute `difficulty_estimate` if structure changes and question difficulties are available.

### DELETE `/tests/{test_id}`
- Hard delete or soft-delete variant (recommended: set `usage.is_active=false` via PATCH).

### GET `/tests/{test_id}`
- Returns full test document (structure with ordered `question_ids`, metadata, display, usage).

### GET `/tests/{test_id}/question-ids` (optional convenience)
- Returns `{ test_id, question_ids: [...] }` flattened across sections (preserving section order then question order).

### GET `/tests/discover`
- Filters:
  - `target_exam_id?`
  - `subject_id?` (matches any in `subject_ids`)
  - `tags?[]`
  - `status?` (default `published`)
  - `is_active?` (default `true`)
  - `language?`
- Pagination: `skip` (default 0), `limit` (default 20).
- Sorting: `sort_by=created_at|name`, `sort_order=asc|desc`.
- Response: `PaginatedTests {items, total, skip, limit}` with lite/public projection (e.g., `test_id`, `name`, `tags`, `metadata`, `display`).

### GET `/tests/list`
- Same params as discover, but defaults to all statuses and `is_active=null` when unfiltered, so it returns all tests (draft + published) unless filtered.

## Service / Repo design
- Repo (`app/db/tests_repo.py`):
  - `insert(doc)`, `update(test_id, patch)`, `find_by_id(test_id, projection)`, `find_many(filters, projection, sort, skip, limit)`, `count(filters)`.
- Service (`app/services/test_service.py`):
  - `create_test`, `update_test`, `delete_test` (or soft-delete), `get_test`, `discover_tests`, `list_tests`, `get_question_ids_flat` (optional).
  - Enforce validation rules and compute display fields.
  - Optional hook to call Questions Master for difficulty averaging.

## Operational notes
- Soft delete by setting `usage.is_active=false` (preferred over hard delete).
- Rate limiting/security: same as Questions service (default 60 req/min per key via router dependency).
- Input hardening: validate `test_id` format; reject malformed UUIDs early.

## Full example (published test)
```json
{
  "name": "Polity Test Series #1",
  "description": "Polity — Constitution and Governance",
  "target_exam_id": "exam_upsc",
  "subject_ids": ["polity","general_studies"],
  "tags": ["mains","2026"],
  "metadata": {
    "duration_min": 120,
    "total_marks": 200,
    "negative_marking": true,
    "marking_scheme": { "correct": 2, "incorrect": -0.66 }
  },
  "structure": [
    {
      "section_id": "constitution",
      "name": "Constitution",
      "question_ids": ["q_1","q_2","q_3"],
      "order": 1
    },
    {
      "section_id": "governance",
      "name": "Governance",
      "question_ids": ["q_4","q_5"],
      "order": 2
    }
  ],
  "usage": { "status": "published", "is_active": true }
}
```
