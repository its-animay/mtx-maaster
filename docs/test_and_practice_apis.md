# Tests & Practice API Blueprint

Design for supporting the “Test Series” and “Practice Questions” UX shown in the mocks. Existing masters/questions/tests APIs stay as-is; this adds thin, FE-friendly endpoints and the backing services/collections they need.

## Existing building blocks
- Test series browse: `GET /api/v1/test-series` (filters: `target_exam_id`, `series_type`, `status`, `is_active`, `tags`, pagination/sorting).
- Tests browse: `GET /api/v1/test-series/{series_id}/tests` (or `GET /api/v1/tests` with `series_id`).
- Test preview & answers: `GET /api/v1/tests/{test_id}/preview`, `GET /api/v1/tests/{test_id}/with-solutions`, `GET /api/v1/tests/{test_id}/answer-key`.
- Questions search: `GET /api/v1/questions` (filters by subject/topic(s), difficulty range, tags, target_exam_tags, active_only).

## New data to persist
- `user_id`: required on practice and attempt endpoints (string from your auth layer).
- `practice_sessions` collection:
  - `session_id`, `user_id`, `mode` (`practice`), `filters` (subject/topic/difficulty/tags/search), `created_at`, `completed_at?`, `question_ids` (optional pre-selected), `progress` (`asked`, `answered`, `correct` counts), `last_question_id?`.
- `practice_events` collection (append-only):
  - `event_id`, `session_id`, `user_id`, `question_id`, `answer` (ids/value), `is_correct`, `time_ms`, `created_at`.
- `test_attempts` collection:
  - `attempt_id`, `test_id`, `user_id`, `mode` (`full|practice|review`), `status` (`in_progress|submitted`), `answers` [{`question_id`, `answer`, `is_correct`, `time_ms`}], `score`, `started_at`, `submitted_at?`.

## Endpoints to add
Base path `/api/v1` and protected by `X-API-Key` like existing routes. All responses are JSON.

### Test discovery (cards in mock)
- `GET /test-series/discover`
  - Query: `search?`, `series_type?` (Full Test / Practice / Topic Test), `tags?[]`, `status?`, `is_active?`, `skip/limit`, `sort_by` (`display_order|created_at`), `sort_order`.
  - Response: `{items: [{series_id, name, description, series_type, tags, target_exam_id, total_tests, syllabus_coverage, stats: {avg_score?, attempts?, avg_duration?}}], total, skip, limit}`
  - Service: wrap `list_test_series` + enrich with `aggregate_series_stats` (already in `db.aggregate_series_stats`).

- `GET /tests/discover`
  - Query: `series_id?`, `status?`, `is_active?`, `subject_id?`, `topic_id?`, `difficulty_min?`, `difficulty_max?`, `tags?[]`, `skip/limit`, `sort_by` (`created_at|test_number|name`), `sort_order`.
  - Response: `PaginatedTests` but add lightweight stats: `avg_score?`, `attempt_count?` pulled from `test_attempts`.
  - Service: new method `discover_tests` that calls `db.list_tests(..., include_questions=False)` and joins attempt aggregates.

### Practice question feed (right screen)
- `POST /practice/sessions`
  - Body: `{user_id, subject_id?, topic_ids?, difficulty_min?, difficulty_max?, tags?[], search? string, limit?: int}`.
  - Behavior: create a session, optionally preselect `question_ids` by running the existing `get_questions` with filters (and optional text search if added later). `limit` caps preselected set; otherwise pull lazily.
  - Response: `{session_id, filters, total_available, created_at}`.

- `GET /practice/sessions/{session_id}/next`
  - Query: `exclude_question_ids?[]` (client-side seen items), `shuffle?bool` (default true).
  - Response: `{question: QuestionResponse, position: {asked: int, correct: int}}`.
  - Behavior: choose the next question from preselected list or by calling `find_questions` with the stored filters; record `asked++` in `practice_sessions`.

- `POST /practice/sessions/{session_id}/answers`
  - Body: `{question_id, answer_option_id?, answer_option_ids?, answer_value?, time_ms?}`.
  - Response: `{is_correct, correct_answer, explanation?: question.solution, progress: {asked, answered, correct}}`.
  - Behavior: check correctness using stored question answers; append to `practice_events`; update session counters.

- `GET /practice/sessions/{session_id}/summary`
  - Response: `{asked, answered, correct, accuracy_pct, per_topic: [{topic_id, correct, total}], per_subject: [...]}` aggregated from `practice_events`.

### Test attempts (for “Start/Continue/Review results” buttons)
- `POST /tests/{test_id}/attempts`
  - Body: `{user_id, mode?: "full"|"practice"|"review"}`; creates an attempt with status `in_progress`, returns `{attempt_id, started_at}`.
- `POST /tests/{test_id}/attempts/{attempt_id}/answers`
  - Body: `{question_id, answer_option_id?, answer_option_ids?, answer_value?, time_ms?}`; records/overwrites the answer for that attempt.
- `POST /tests/{test_id}/attempts/{attempt_id}/submit`
  - Body: none; evaluates answers, computes `score`, `correct_count`, `incorrect_count`, `skipped_count`, `duration_ms`; sets status `submitted`.
  - Response: `{score, totals, per_section breakdown, percent}`.
- `GET /tests/{test_id}/attempts/{attempt_id}`
  - Returns attempt with answers and evaluation.
- `GET /tests/{test_id}/attempts/summary?user_id=...`
  - Returns `{latest_attempt, best_attempt, avg_score, attempts}` for the user/test to populate card badges.

## Service layer changes
- `db.session.Database`:
  - Add collections helpers for `practice_sessions`, `practice_events`, `test_attempts` (insert/get/update/list/aggregate).
  - Add text search in questions (optional): store a text index on `text` and `tags`, support `search` param in `find_questions`.
- New service module `practice_service.py`:
  - `create_session`, `next_question`, `submit_practice_answer`, `practice_summary`.
  - Uses existing `question_service.get_questions` for filtering; can fall back to random `$sample` via `find_questions(sample=N)`.
- Extend `test_service`:
  - Add `create_attempt`, `record_answer`, `submit_attempt`, `get_attempt`, `summarize_attempts_for_user`.

## Frontend wiring (per mock)
- Tests page:
  - Load series cards via `GET /test-series/discover` (filter by `series_type` to map badges “Full Test/Practice/Topic Test”).
  - On card click “View details”: fetch `GET /test-series/{series_id}` and `GET /test-series/{series_id}/tests`.
  - On “Start/Continue/Review results”: use attempts endpoints to create or resume.
- Practice page:
  - Build dropdowns from `GET /subjects` and `GET /topics?subject_id=...`.
  - On filter change, call `POST /practice/sessions` (or reuse a session with same filters) then `GET /practice/sessions/{id}/next`.
  - On answer, call `POST /practice/sessions/{id}/answers`; show explanation from response; update summary via `GET /practice/sessions/{id}/summary`.

## Security & limits
- Same `X-API-Key` and rate limiting as existing routers.
- Add simple per-user throttling if needed (e.g., `POST` endpoints limited to 30/min).
- Validate `user_id` presence on practice/attempt endpoints; reject requests without it.

## Migration checklist
- Create new collections/indexes:
  - `practice_sessions(session_id pk, user_id, created_at desc)`
  - `practice_events(session_id, user_id, question_id, created_at desc)`
  - `test_attempts(test_id, user_id, status, submitted_at desc)`
  - Optional text index on `questions.text`, `questions.tags`.
- Implement `practice_service.py` and new endpoints under `app/api/v1/endpoints/practice.py`.
- Implement attempt endpoints under `app/api/v1/endpoints/test_attempts.py` or extend `tests.py`.
- Add schemas for sessions, events, attempts under `app/schemas/practice.py` and `app/schemas/attempts.py`.
