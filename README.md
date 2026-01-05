# MQDB Service

FastAPI + MongoDB service for managing a question bank: subjects, topics, exams, and questions. The service enforces API-key authentication with per-key rate limiting and ships with a small seeded dataset on startup.

## Quickstart
- Requirements: Python 3.11+, MongoDB running and reachable via `MQDB_MONGO_URI`.
- Install deps: `python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
- Configure env: copy `.env.example` to `.env` and set `API_KEY_SALT` (required) plus DB and demo/admin keys as needed.
- Run the API: `uvicorn app.main:app --reload`
- Base URL: `http://localhost:8000/api/v1`

> On startup `init_db()` clears all collections, recreates indexes, and inserts sample Physics data. Remove/alter this call in `app/main.py` for persistent environments.

## Environment
| Variable | Default | Required | Description |
| --- | --- | --- | --- |
| `API_KEY_SALT` | none | yes | Salt used to hash/verify API keys. Service will fail without it. |
| `DEMO_API_KEY` | none | no | Optional raw key auto-registered on startup for quick testing. |
| `MQDB_MONGO_URI` | `mongodb://localhost:27017` | no | Mongo connection string. |
| `MQDB_MONGO_DB_NAME` | `mqdb` | no | Database name. |
| `ADMIN_MASTER_KEY` | none | no | Optional admin override for generating keys. |
| `CORS_ORIGINS` | `*` | no | Comma-separated list or JSON array of allowed origins for CORS (e.g. `http://localhost:3000,http://app.local`). |
| `API_PREFIX` | `/api/v1` | no | Path prefix for routers. |

## Security and Rate Limits
- **Header:** `X-API-Key: <raw_key>` for all subject/topic/exam/question routes. Keys are stored hashed in-memory.
- **Rate limiting:** Default 60 requests per minute per key for masters/exams/questions, `10/min` for the burst endpoint.
- **Generate keys:** `POST /api/v1/admin/generate-key` (requires `X-Admin-Key` matching `ADMIN_MASTER_KEY` or an existing valid `X-API-Key`). Responds with `{api_key, hashed, registered}`; store `api_key` securely.
- **Demo key:** Set `DEMO_API_KEY` to auto-register a test key on startup. Use it in the `X-API-Key` header.

## Data Models
### Subject (`SubjectCreate` / `SubjectResponse`)
| Field | Type | Notes |
| --- | --- | --- |
| `id` | string | Optional on create; auto-generated if omitted. |
| `name` | string | Display name. |
| `slug` | string | Unique, min length 2. |
| `description` | string? | Optional. |
| `tags` | string[] | Optional labels. |
| `metadata` | object? | Arbitrary JSON. |
| `is_active` | bool | Default `true`. |
| `created_at`, `updated_at` | datetime | Response only. |

### Topic (`TopicCreate` / `TopicResponse`)
| Field | Type | Notes |
| --- | --- | --- |
| `id` | string | Optional on create; auto-generated if omitted. |
| `subject_id` | string | Must exist; cannot change once created. |
| `name` | string | Topic name. |
| `slug` | string | Unique within a subject. |
| `description` | string? | Optional. |
| `difficulty_weight` | float | 0-1 weight. |
| `bloom_level` | string? | Optional Bloom taxonomy label. |
| `related_topic_ids` | string[] | Optional links; must belong to same subject. |
| `prerequisite_topic_ids` | string[] | Optional prereqs; must belong to same subject. |
| `tags`, `metadata`, `is_active`, `created_at`, `updated_at` |  | Same semantics as Subject. |

### Exam (`ExamCreate` / `ExamResponse`)
| Field | Type | Notes |
| --- | --- | --- |
| `exam_id` | string | Response only; generated. |
| `code` | string | Unique exam code. |
| `name` | string | Exam name. |
| `description` | string? | Optional. |
| `syllabus` | `ExamSyllabusItem[]` | Validated against existing subjects/topics. |
| `version` | string? | Optional. |
| `is_active` | bool | Default `true`. |
| `metadata` | object? | Arbitrary JSON. |
| `created_by` | string? | Optional creator (create only). |
| `created_at`, `updated_at` | datetime | Response only. |

`ExamSyllabusItem` fields: `subject_id` (string), `topic_ids` (string[]), `weight` (float 0-1 optional).

### Question (`QuestionCreate` / `QuestionResponse`)
| Field | Type | Notes |
| --- | --- | --- |
| `question_id` | string | Response only; generated. |
| `question_type` | enum | `MCQ`, `MSQ`, `NAT`, `SUBJECTIVE`. |
| `subject_id` | string | Must exist. |
| `topic_ids` | string[] | Each must exist and match `subject_id`. |
| `text` | string | Question statement. |
| `options` | `OptionSchema[]` | Required for MCQ/MSQ. `{id, content, rationale?}`. |
| `correct_option_id` | string? | Required for MCQ. |
| `correct_option_ids` | string[]? | Required for MSQ. |
| `answer_value` | string? | Required for NAT; not allowed for MCQ/MSQ. |
| `difficulty` | int | 1-5. |
| `target_exam_tags` | string[] | Exams the question targets. |
| `tags`, `source`, `version`, `metadata`, `solution`, `is_active` |  | Optional metadata/flags. |
| `created_at`, `updated_at` | datetime | Response only. |

Validation notes:
- MCQ: one `correct_option_id`; no `correct_option_ids` or `answer_value`.
- MSQ: `correct_option_ids` array; no `correct_option_id` or `answer_value`.
- NAT: `answer_value` required; no option-based answers.
- SUBJECTIVE: no option-based answers required.

## API Reference
Base path: `/api/v1`. Unless stated, endpoints require `X-API-Key` and are limited to `60/min`.

### Health and Security
- `GET /public/ping` — No auth. Simple health check.
- `GET /secure/data` — API key + default limiter. Returns sample secured payload.
- `GET /secure/burst` — API key + burst limiter (`10/min`).
- `POST /admin/generate-key` — Requires `X-Admin-Key` or a valid `X-API-Key`. Bodyless; optional `?register=true|false` query. Returns raw + hashed key.

### Test Series (Reference-only design)
- Tests store only `question_id` references plus denormalized lookup fields (type/subject/topics/difficulty). Question text/options/answers are fetched live from the questions collection.
- `POST /test-series` — Create series (`TestSeriesCreate`). Validates exam/subject/topic references and unique code/slug.
- `GET /test-series` — List with filters (`exam_id`, `series_type`, `status`, `is_active`, `tags`) plus pagination and sorting; returns `{items, total, skip, limit}`.
- `GET /test-series/{series_id}` — Fetch a series.
- `PUT /test-series/{series_id}` — Update metadata (code/target_exam_id immutable).
- `PATCH /test-series/{series_id}/status` — Quick status change (draft/published/archived).
- `DELETE /test-series/{series_id}` — Deletes only when no tests exist under the series.
- `GET /test-series/{series_id}/stats` — Aggregated counts/durations/difficulty across tests.
- `GET /test-series/{series_id}/tests` — List tests in a series (metadata only) with pagination/sorting; returns `{items, total, skip, limit}`.

### Tests
- `POST /tests` — Create a test with pattern/sections (`TestCreate`). Questions array can start empty; uniqueness enforced for code/slug/test_number within series.
- `GET /tests` — List tests (filters: `series_id`, `status`, `is_active`) with pagination/sorting; returns `{items, total, skip, limit}`.
- `GET /tests/{test_id}` / `PUT /tests/{test_id}` / `DELETE /tests/{test_id}` — CRUD for test metadata (questions managed via dedicated endpoints).
- `POST /tests/{test_id}/questions` — Add explicit question IDs to a section. Uses section marking scheme for marks/negative marks by default and enforces subject/topic validation.
- `POST /tests/{test_id}/questions/bulk-add` — Add N questions by criteria (subject/topic/difficulty/type) with strategies `random` (uses `$sample`), `difficulty_sorted`, `sequential`.
- `DELETE /tests/{test_id}/questions/{question_id}` — Remove a question (re-sequences to keep contiguous `seq`).
- `PATCH /tests/{test_id}/questions/reorder` — Reorder questions within a section by supplying `{question_id, seq}` pairs.
- `PUT /tests/{test_id}/questions/{old_question_id}/replace` — Swap a question (optionally keep the same sequence).
- `PATCH /tests/{test_id}/questions/{question_id}/marks` — Override marks/negative marks/bonus flags for a specific reference.
- `GET /tests/{test_id}/preview` — Returns merged test + question content **without answers/solutions** for delivery to students.
- `GET /tests/{test_id}/with-solutions` — Returns merged test with answers/solutions (honor `solutions.release_mode`/`release_at` in client).
- `GET /tests/{test_id}/answer-key` — Returns `{question_id: correct_answer}` map for evaluation.
- `GET /tests/{test_id}/validate` — Integrity check (counts, sequences, reference existence, subject alignment).
- `GET /tests/{test_id}/stats` — Aggregated difficulty/type/topic/section counts using denormalized fields.

### Subjects
- `POST /subjects` — Create subject (`SubjectCreate`). Example:
```json
{
  "name": "Physics",
  "slug": "physics",
  "description": "Physics master subject",
  "tags": ["science"],
  "metadata": {"owner": "curriculum-team"},
  "is_active": true
}
```
Returns `SubjectResponse`.
- `GET /subjects` — List subjects with filters (`is_active`, `search` on name, `tags`) plus pagination/sorting; returns `{items, total, skip, limit}`.
- `GET /subjects/{subject_id}` — Fetch single subject.
- `PUT /subjects/{subject_id}` — Update subject (`SubjectUpdate`, all fields optional). Returns updated subject.
- `DELETE /subjects/{subject_id}` — Delete subject (fails if topics exist under it).

### Topics
- `POST /topics` — Create topic (`TopicCreate`). Example:
```json
{
  "subject_id": "subject_physics",
  "name": "Thermodynamics",
  "slug": "thermodynamics",
  "description": "Thermodynamics fundamentals",
  "difficulty_weight": 0.7,
  "bloom_level": "Analyze",
  "related_topic_ids": [],
  "prerequisite_topic_ids": []
}
```
- `GET /topics?subject_id=...` — List topics, optionally filtered by subject.
- `GET /topics/{topic_id}` — Fetch single topic.
- `PUT /topics/{topic_id}` — Update topic (`TopicUpdate`, subject change is rejected). Relationship arrays validated within same subject.
- `PATCH /topics/{topic_id}/links` — Update only `related_topic_ids` / `prerequisite_topic_ids` (`TopicUpdateLinks`).
- `DELETE /topics/{topic_id}` — Delete topic.

### Exams
- `POST /exams` — Create exam (`ExamCreate`). Example:
```json
{
  "code": "JEE_MAIN",
  "name": "JEE Main",
  "description": "JEE Main core syllabus",
  "syllabus": [{"subject_id": "subject_physics", "topic_ids": ["topic_thermodynamics"], "weight": 1.0}],
  "version": "2024.1",
  "metadata": {"region": "IN"},
  "created_by": "system",
  "is_active": true
}
```
Returns `ExamResponse`.
- `GET /exams?active_only=true|false` — List exams (optionally only active).
- `GET /exams/{exam_id}` — Fetch exam by id.
- `PUT /exams/{exam_id}` — Update exam (`ExamUpdate`), validates syllabus and unique code.
- `DELETE /exams/{exam_id}` — Delete exam.
- `GET /exams/{exam_id}/syllabus` — Returns `ExamSyllabusItem[]` for an exam.

### Questions
> Display-ready question service (schema_version=2) with `/questions/discover` and `/questions/sample` is documented in `docs/question_service.md`. Legacy question schema remains for existing test-series flows.
- `POST /questions` — Create question (`QuestionCreate`). Example MCQ:
```json
{
  "question_type": "MCQ",
  "subject_id": "subject_physics",
  "topic_ids": ["topic_thermodynamics"],
  "text": "What happens to internal energy when heat is added at constant volume?",
  "options": [
    {"id": "opt1", "content": "Increase in internal energy", "rationale": "dU = Q at constant volume"},
    {"id": "opt2", "content": "Decrease in internal energy"},
    {"id": "opt3", "content": "No change in internal energy"},
    {"id": "opt4", "content": "Internal energy doubles"}
  ],
  "correct_option_id": "opt1",
  "difficulty": 2,
  "target_exam_tags": ["JEE_MAIN"],
  "tags": ["thermo", "first-law"],
  "source": "curated",
  "version": "1.0",
  "metadata": {"chapter": "First Law"},
  "solution": "Internal energy rises equal to heat added.",
  "is_active": true
}
```
Returns `QuestionResponse`.
- `GET /questions` — List questions with filters: `subject_id`, `topic_id`, `topic_ids` (repeatable query), `difficulty_min`, `difficulty_max`, `target_exam_tags` (repeatable), `active_only`.
- `GET /questions/{question_id}` — Fetch question by id.
- `PUT /questions/{question_id}` — Update question (`QuestionUpdate`). Validates relationships and answer structure.
- `DELETE /questions/{question_id}` — Delete question.

## Testing
- Run unit tests: `pytest`

## Notes
- API keys are stored hashed in-memory only; persist hashes externally if you need durability.
- Mongo indexes are created automatically on startup for uniqueness and query speed.
