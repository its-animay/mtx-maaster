# Question Service (schema_version=2)

Display-ready questions API. No user/session data; optimized for fast browse/search/sample and render-ready payloads.

## Key capabilities
- Create/update/deactivate questions (admin/internal).
- Fetch a single question with optional answer/solution.
- Discover/search with filters, pagination, stable sorting.
- Random/deterministic sampling for practice feeds.

## Data model (collection: `questions`)
Canonical document:
```json
{
  "_id": "q_<uuid>",
  "question_id": "q_<uuid>",
  "schema_version": 2,
  "version": 1,
  "text": "Question statement",
  "type": "single_choice | multi_choice | integer | short_text | true_false",
  "options": [{"id":"A","text":"..."}, {"id":"B","text":"..."}],
  "answer_key": {"type":"single|multi|value","option_id":"A","option_ids":["A","C"],"value":"42"},
  "solution": {"explanation": "...", "steps": [], "references": []},
  "taxonomy": {"subject_id": "subj_1", "topic_ids": ["t1","t2"], "target_exam_ids": ["exam_1"]},
  "difficulty": 1,
  "tags": ["tag1","tag2"],
  "language": "en",
  "usage": {"status": "draft|published", "is_active": true, "visibility": "public|private"},
  "meta": {"estimated_time_sec": 60, "source": "internal", "created_by": "admin_id"},
  "rand_key": 0.1234,
  "search_blob": "normalized text/options/tags",
  "created_at": "...",
  "updated_at": "..."
}
```

### Enums
- `type`: `single_choice`, `multi_choice`, `integer`, `short_text`, `true_false`.
- `answer_key.type`: `single`, `multi`, `value`.
- `usage.status`: `draft`, `published`.
- `usage.visibility`: `public`, `private`.

### Validation rules
- `single_choice` / `true_false`: options required (except preset T/F); `answer_key.type=single`; `answer_key.option_id` must exist.
- `multi_choice`: options required; `answer_key.type=multi`; all `option_ids` must exist.
- `integer` / `short_text`: `answer_key.type=value`; `answer_key.value` required; options must be empty.
- `usage.status=published` requires `taxonomy.subject_id`.
- Option IDs must be unique.

### Search blob
Lowercased concat of: `text`, option texts, `tags`, `taxonomy.subject_id`, `taxonomy.topic_ids`, `taxonomy.target_exam_ids`.

### Indexes (Database._init_indexes)
- Single: `schema_version`, `taxonomy.subject_id`, `taxonomy.topic_ids`, `taxonomy.target_exam_ids`, `difficulty`, `tags`, `usage.is_active`, `usage.status`.
- Compound: `(usage.is_active, usage.status, taxonomy.subject_id, difficulty)`; `(taxonomy.subject_id, taxonomy.topic_ids, difficulty)`.
- Text: `search_blob` (`question_search_text`).

## API (base `/api/v1`, header `X-API-Key`)

### POST `/questions`
Create question. Body: `QuestionDocCreate`. Returns full view (answer + solution included). Auto-sets `schema_version=2`, `rand_key`, `search_blob`, `created_at/updated_at`.

### PATCH `/questions/{question_id}`
Partial update. Revalidates types, bumps `version`/`updated_at`, recomputes `search_blob` if text/options/tags/taxonomy change.

### GET `/questions/{question_id}`
Query: `include_solution` (bool, default false), `include_answer_key` (bool, default false).
- Default: public view (no answer/solution).
- `include_answer_key=true`: preview view (answer only).
- `include_solution=true`: full view (solution + answer).

### GET `/questions/discover`
Filters: `subject_id`, `topic_ids[]` (ANY), `target_exam_ids[]`, `difficulty_min/max`, `tags[]`, `status` (default `published`), `is_active` (default `true`), `search` (text).
Pagination: `skip` (0), `limit` (default 20, max 200).
Sorting: `sort_by=created_at|difficulty|updated_at`, `sort_order=asc|desc` (stable with `_id` tie-break).
Search: uses text index on `search_blob`; sorts by text score then `created_at`/`_id`.
Response: `PaginatedQuestions {items, total, skip, limit}` (public view).

### GET `/questions/list`
Same params as discover, but defaults `status_value=None`, `is_active=None` to include all (v2 + legacy) when unfiltered. Response: `PaginatedQuestions`.

### GET `/questions/sample`
Filters: same as discover. `limit`: 1–50 (default 1). `seed`: optional for deterministic sampling (uses stored `rand_key` wrap-around). Without seed: Mongo `$sample` after `$match`. Response: public view list.

## Projections (responses)
- Public: hides `answer_key`, `solution`, `search_blob`, `rand_key`, `schema_version`.
- Preview: includes `answer_key`, hides `solution`, `search_blob`, `rand_key`, `schema_version`.
- Full: includes everything except `search_blob`, `rand_key`, `schema_version`.

## Examples
### Single-choice create
```json
{
  "text": "What is 2+2?",
  "type": "single_choice",
  "options": [
    {"id": "A", "text": "3"},
    {"id": "B", "text": "4"}
  ],
  "answer_key": {"type": "single", "option_id": "B"},
  "taxonomy": {"subject_id": "subject_math", "topic_ids": ["topic_arith"]},
  "difficulty": 1,
  "tags": ["arithmetic"],
  "usage": {"status": "published", "is_active": true}
}
```
### Numeric (integer) create
```json
{
  "text": "Acceleration due to gravity on Earth (m/s^2)?",
  "type": "integer",
  "options": [],
  "answer_key": { "type": "value", "value": "9.8" },
  "taxonomy": { "subject_id": "subject_physics", "topic_ids": ["topic_mechanics"] },
  "difficulty": 1,
  "tags": ["gravity"],
  "usage": { "status": "published", "is_active": true }
}
```
### Discover request
`GET /api/v1/questions/discover?subject_id=subject_math&difficulty_max=3&tags=arithmetic&skip=0&limit=20`

## Implementation notes
- Service: `app/services/question_service.py` (create/update/get/discover/sample). Includes legacy tolerance (records without `schema_version` are included; invalid legacy docs are skipped on read).
- Repo: `app/db/questions_repo.py` (insert/update/find/count/search/sample; in-memory repo for tests).
- Soft delete: set `usage.is_active=false`.
- Rate limits: default 60 req/min per key (see `api.py`); adjust as needed.
