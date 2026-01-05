# Legacy Tests Service (Authoritative `/api/v1/tests`)

This is the only Tests Master in production. It stores test structure/metadata and question references (`question_id` only), validates against Questions Master (schema_version=2), and serves preview/solutions/answer-key. The deprecated `/tests-doc` is ignored.

## Canonical Model (`app/schemas/test.py`)
- Identity: `test_id`, `code` (unique), `slug` (unique), `series_id`, `test_number` (unique per series)
- Display: `name`, `description`, `tags`, `language`, `metadata`
- Pattern/Sections: `section_id`, `section_code`, `name`, `display_order`, `subject_id`, `total_questions`, `marking_scheme` by `QuestionType`
- Questions (refs only): `seq`, `section_id`, `question_id`, `question_type`, `subject_id`, `topic_ids`, `difficulty`, `marks`, `negative_marks`, `is_bonus`, `is_optional`
- Settings: shuffle flags, palette/navigation flags
- Solutions: release config (`release_mode`, `release_at`, pdf/video URLs)
- Availability: `mode` (always/scheduled/date_range) with `starts_at`/`ends_at`
- Status: `draft|published|archived`, `is_active`, `version`, `created_at`, `updated_at`

## Validation (strict)
- Unique: `code`, `slug`; `(series_id, test_number)`
- Sections: `section_id`/`section_code` unique; `display_order` unique/continuous; `total_questions` matches actual count
- Questions: no duplicate `question_id` in a test; `seq` continuous per section; `section_id` must exist; marks resolve to question-level or section marking (otherwise error)
- Published: ≥1 section and ≥1 question per section; valid marking scheme; must pass `/validate`
- Cross-service: question existence validated against Questions Master; optional strict subject/topic alignment; store denormalized question metadata (type/subject/topic_ids/difficulty) for stats/validation

## Test APIs (only `/tests`, excludes series)
- CRUD:
  - `POST /tests` — create (pattern + optional initial questions)
  - `GET /tests` — list (filters: `series_id`, `status`, `is_active`; pagination/sorting)
  - `GET /tests/{test_id}` — fetch a test
  - `PUT /tests/{test_id}` — update metadata/pattern
  - `DELETE /tests/{test_id}` — delete (soft delete recommended via `is_active=false`, `status=archived`)
- Question management:
  - `POST /tests/{test_id}/questions` — add explicit `question_id`s to a section (validates via Questions Master)
  - `POST /tests/{test_id}/questions/bulk-add` — add by criteria (subject/topic/difficulty/type) using Questions Master `/questions/discover`; strategies `random|difficulty_sorted|sequential`
  - `PATCH /tests/{test_id}/questions/reorder` — resequence within a section (seq must be 1..N)
  - `PUT /tests/{test_id}/questions/{old_question_id}/replace` — swap a question
  - `DELETE /tests/{test_id}/questions/{question_id}` — remove a question
  - `PATCH /tests/{test_id}/questions/{question_id}/marks` — override marks/negative marks/bonus/optional flags
- Preview/read (question content fetched live from Questions Master):
  - `GET /tests/{test_id}/preview` — merged test + questions without answers/solutions
  - `GET /tests/{test_id}/with-solutions` — merged with answers/solutions
  - `GET /tests/{test_id}/answer-key` — `{question_id: correct_answer}`
- Integrity/safety:
  - `GET /tests/{test_id}/validate` — counts, sequences, existence, marking consistency
  - `GET /tests/{test_id}/stats` — difficulty/type/topic/section aggregates

## Indexes (tests collection)
- Unique: `code`, `slug`, `(series_id, test_number)`
- Filtering: `(series_id, status, is_active, test_number)`, `(series_id, status, is_active, updated_at)`, `(status, is_active)`, `tags`, `language`
- Questions array: `questions.question_id`, `questions.section_id`

## Operational stance
- Stores only `question_id` references; no question text/options/answers/solutions
- Previews/solutions fetch content from Questions Master (schema_version=2)
- `/tests-doc` is deprecated; do not use
- API-key protected; default rate limit 60 req/min/key (configurable)
