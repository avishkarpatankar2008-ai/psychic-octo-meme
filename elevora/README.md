# Elevora — Phase 8 (Interview Profiles)

Adaptive AI mock interview platform. This delivers **Phases 1–8**: auth,
dashboard, interview configuration, a text/voice AI interviewer, a
webcam-equipped interview room, resume/JD grounding, scored performance
reports, real speech/webcam analytics, and now a reusable **Interview
Profile** system — interviews are no longer tied to a hardcoded category
list; anyone can select a named, storable profile or build their own.

## What's actually verified vs. what isn't

This phase has an unusually wide confidence spread — it contains both the
best-tested code in the project and, by a real margin, the least-tested.

| Component | Verified how | Confidence |
|---|---|---|
| Backend logic (state machine, endpoint plumbing, all phases' orchestration) | Full pytest suite (**163 tests** — 135 from Phases 1–7 plus **28 new Phase 8 tests**) against an in-memory Mongo and a scripted fake AI client | High |
| **PDF/DOCX text extraction** | Tested against real generated files | High |
| **Scoring/weighting math** (Phase 6) | Pure unit tests, no AI/DB | High |
| **Speech analytics** (`app/services/speech_analytics.py`) | **Tested against real generated audio** — ffmpeg is installed in this sandbox, so tests build actual audio clips with known silence gaps (via pydub's tone/silence generators), export them to real webm/wav bytes, and confirm the detected pauses/duration/WPM match. Caught and fixed a real bug (punctuation broke multi-word filler matching) before it shipped. | **High — same category as the PDF/DOCX parsing, genuinely not "unverified"** |
| **Delivery/Webcam deterministic scoring** (`app/services/deterministic_scoring.py`) | Pure unit tests, no AI/DB — 16 tests check every threshold | **High** |
| **End-to-end voice → Delivery score** | Integration test posts real generated audio through the actual `/answer/audio` endpoint and confirms a real (non-placeholder) Delivery score comes out the other end of a generated report | High |
| Frontend | `tsc --noEmit`, `eslint`, full `next build` — all 9 routes compile, including the new MediaPipe dependency | High for compilation |
| **The MediaPipe API calls themselves** (`lib/webcamAnalytics.ts`) | Checked against the *actual installed package's real TypeScript definitions* (not recalled from training data) — the method names, option shapes, and result types are confirmed correct as of `@mediapipe/tasks-vision@1.0.1`. | Medium for API correctness |
| **Whether the webcam analytics actually work in a browser** | **Not verified at all — no camera, no browser.** Model loading from the CDN, `detectForVideo` against a live stream, and the head-orientation math (see the file's own extensive comments) have never run. | **The single least-verified piece in the entire project — more uncertain than VoiceControls or CameraPreview, which wrap simpler, longer-stable browser APIs** |
| **OpenAI text/voice integration** | Not tested against the real API | Unverified — smoke-test before trusting |
| **Browser audio/camera** (`VoiceControls`, `CameraPreview`) | Type-checked and linted only. No browser available. | Unverified |
| End-to-end in a browser | Not done | Untested |

## A scope decision you should know about: I did not build realtime/WebRTC

The build brief says Phase 3 is "microphone-based interviewing using
realtime voice/WebRTC." I did not build that. Here's what I built instead,
and why.

The product spec's own Week 3 section recommends **not** starting with
realtime WebRTC:

> "Do NOT start with the most complicated architecture. Step A: Record →
> Upload audio → Transcribe → Analyze → Generate text response → TTS → Play
> response. Step B: upgrade to realtime."

And its own mistake list: *"Mistake 4 — Overengineering voice: Get a
functional voice loop first. Optimize latency later."*

I built **Step A**: record a full answer in the browser, upload it, transcribe
it, run it through the same (tested) Phase 2 engine, then fetch synthesized
speech for the next question. Not **Step B** (a persistent WebRTC connection
doing live streaming speech-to-speech).

The honest reason, beyond following the spec's own sequencing advice: Step B
requires a browser, a microphone, and a live network connection to OpenAI's
Realtime endpoint to build against at all — none of which exist in the
sandbox this was built in. Writing WebRTC signaling and audio-streaming code
with zero ability to run it isn't a smaller version of the feature, it's a
guess at the feature. Step A is at least testable in the ways that matter
(the engine logic, end to end except the actual OpenAI calls); a blind
WebRTC implementation would just be more unverified surface area with a much
higher chance of being subtly wrong in ways neither of us could catch here.

If you want true realtime after trying this: the migration path is
`answer_audio_endpoint` gets replaced by a WebSocket/WebRTC session that
streams audio both ways, but `submit_answer()` and everything in
`interview_engine.py` stays exactly as it is — the engine doesn't know or
care whether text arrived by typing, file upload, or a live stream.

## What Phase 5 actually does

- **Upload**: `POST /interviews/{id}/resume` (PDF or .docx, magic-byte
  validated, 8MB cap) and `POST /interviews/{id}/job-description` (pasted
  text **or** a file — job postings are usually copy-pasted, so both paths
  are supported rather than forcing an upload). Both are restricted to
  `draft` interviews, matching the spec's own flow: configure → upload →
  start.
- **Extraction**: raw text goes through OpenAI structured outputs into a
  `CandidateProfile` (skills, education, experience, projects, technologies,
  achievements, claims) or `JobProfile` (role, company, industry, required/
  preferred skills, responsibilities, seniority) — the exact shapes from the
  spec's DB structure section. The extraction prompt is explicit: empty
  list if a section isn't present, never invent a skill or employer that
  isn't in the text.
- **The extracted profile is shown back to the candidate immediately**
  (`ResumeJdUpload` component) before the interview starts — every skill,
  project, and claim it found, nothing summarized or hidden. This is the
  practical version of the spec's anti-hallucination information-class
  distinction (verified / candidate-provided / AI-inference / unknown):
  showing the extraction lets the candidate catch a wrong or invented item
  before it ever reaches a question.
- **Grounding**: once uploaded, every question-generation call (opening
  question, later baseline questions, follow-ups) includes a
  "CANDIDATE-PROVIDED BACKGROUND" and/or "JOB DESCRIPTION CONTEXT" block in
  the system prompt, with an explicit instruction to reference a specific
  project/skill/claim by name when relevant to the current topic, and to
  never attribute anything not in that block. Tests confirm the content
  actually reaches the prompt (see the table above) — they can't confirm
  the model uses it well, only that it has the chance to.

## A deliberate deviation: no separate `candidate_profiles`/`job_profiles` collections

The spec's DB structure section defines these as their own collections with
their own `userId`/`resumeId` fields, implying resumes could be reused
across multiple interviews. This build stores `candidateProfile` and
`jobProfile` embedded directly on the interview document instead — same
pattern as all the other interview-scoped state since Phase 2. Trade-off:
no "reuse my resume for a new practice session" feature; uploading again is
currently the only path. If resume reuse becomes a real feature request,
that's when these become first-class objects — not before, per the spec's
own guidance against building ahead of demonstrated need.

## What Phase 5 deliberately does not do

- **No raw file storage.** The uploaded PDF/DOCX is parsed in-memory and
  discarded — only the extracted structured profile is persisted. No
  Cloudflare R2/Supabase integration exists yet, and skipping it here
  keeps PII exposure minimal (the spec's own privacy principle: "collect
  minimum required data"). It also sidesteps several of the spec's file-
  security checklist items entirely (random filenames, expiring unused
  files) because there's no stored file to protect.
- **No OCR.** A scanned resume with no text layer fails extraction with a
  clear error rather than silently returning nothing.
- **No prompt-injection hardening beyond "treat it as data."** The
  extraction prompts don't have special defenses against a resume that
  contains something like "ignore previous instructions" — they rely on
  the structured-output schema constraining what can come back (only the
  seven CandidateProfile fields, all string arrays) rather than trying to
  detect injection attempts. Worth revisiting if this becomes a public-
  facing product; low-risk for an MVP where the uploader is the same
  person the extraction is about.

## What Phase 6 actually does

- **`POST /interviews/{id}/report`** generates a report from the completed
  transcript; **`GET`** returns the cached one. Restricted to `completed`
  interviews — `abandoned` sessions are explicitly not scored (matches the
  copy already shown in the Phase 4 abandoned-interview view).
- **Five dimensions scored 0-5 with mandatory evidence**: Knowledge,
  Communication, Relevance, Problem Solving, Interview Handling. The schema
  requires an evidence string for every score — there's no way for the
  model to return a bare number.
- **Delivery and Webcam are always "not available," never faked.** Real
  speech-timing and facial-metrics analytics are Phase 7/8, not built yet.
  Rather than asking the model to guess at a pace/eye-contact score with no
  underlying data (which would be exactly the "random AI score" the spec
  warns against), those two dimensions carry `score: null` and an evidence
  string explaining why — visible in the UI as "Not available" with a
  hatched bar, not hidden or defaulted to a misleading number.
- **Deterministic weighting, not an AI-picked 0-100.** The model scores five
  0-5 dimensions; a plain Python function (`compute_weighted_score`)
  combines them into the final 0-100 using per-category weight profiles
  (technical/behavioral/general), renormalizing weights among whatever
  dimensions are actually available rather than treating a missing one as
  a zero. This is the highest-confidence code in the whole project — see
  the table above.
- **Confidence is computed, not self-rated.** `low`/`medium`/`high` comes
  from turn count and topic breadth (a fact about the transcript), not from
  asking the model how confident it feels (a notoriously unreliable thing
  to ask an LLM to judge about its own output).
- **Report generation is a deliberate user action**, not automatic on
  completion. The results page shows a "Generate report" button rather than
  silently running the evaluation call — sending the full transcript to the
  AI evaluator is a real API call, and the person should decide when that
  happens rather than it firing the moment they finish answering.

## What Phase 7 actually does

- **Speech analytics** (`app/services/speech_analytics.py`): for every voice
  answer, computes real duration, words-per-minute, pause count/average/
  longest (via ffmpeg silence detection), filler word count/rate
  (language-configurable vocabulary, defaults to English), and immediately-
  repeated-word count — all from the actual audio, decoded before it's
  discarded (this project never stores raw audio or video, see Phase 5's
  equivalent decision about resumes).
- **Webcam analytics** (`lib/webcamAnalytics.ts` + `POST
  /interviews/{id}/webcam-metrics`): face-visible rate, an approximate
  "looking away" rate, and a movement rate — computed **client-side** via
  MediaPipe's FaceLandmarker, exactly matching the spec's own preferred
  architecture (Camera → Browser → MediaPipe → aggregate metrics → Backend,
  never raw frames uploaded). Only the final aggregate numbers ever reach
  the server.
- **Delivery and Webcam are now scored deterministically, not by AI**
  (`app/services/deterministic_scoring.py`). Both dimensions are pure,
  objective numbers — there's nothing for a language model to interpret
  that a threshold rule can't, and asking one to would risk exactly the
  kind of overclaiming ("sounds nervous") the spec prohibits. Every score
  cites the specific numbers behind it (e.g. "pace was 135 WPM, within a
  comfortable range; filler words made up 1.8% of words spoken, low").
- **Both dimensions genuinely say "Not available" when the data doesn't
  exist** — an all-text interview has no Delivery score (no audio to
  measure), and a session where the camera was never enabled or the
  client-side measurement didn't complete has no Webcam score. Nothing is
  estimated or defaulted to fill the gap.

## The MediaPipe integration is the least-verified code in this project — more than the other browser APIs

Every other piece of unverified browser code in this project (`VoiceControls`,
`CameraPreview`) wraps simple, long-stable Web APIs — `getUserMedia` and
`MediaRecorder` haven't meaningfully changed in years, and I have high
confidence in those calls independent of any package version.

`lib/webcamAnalytics.ts` is different: it depends on a specific version of
`@mediapipe/tasks-vision`, an actively-developed ML package, plus a model
file hosted on a Google Cloud Storage URL. What I could verify: this
sandbox has no camera but does have `npm`, so I installed the real package
and read its actual `.d.ts` type definitions rather than relying on
training data — the method names, option shapes (`FilesetResolver.
forVisionTasks`, `FaceLandmarker.createFromOptions`, `detectForVideo`,
`outputFacialTransformationMatrixes`) are confirmed correct as of the
installed version, and the whole thing type-checks and builds. What I
could NOT verify: whether the model actually downloads and runs correctly
in a real browser against a live camera feed.

The head-orientation math deserves its own callout. Extracting a signed
yaw/pitch/roll from MediaPipe's facial transformation matrix requires
knowing its exact row-major-vs-column-major convention and axis signs —
get that wrong and "looking left" silently reads as "looking right,"
forever, with no error to catch it. Instead, `estimateForwardAlignment()`
reads a single diagonal matrix entry, which represents the same value
regardless of row/column-major convention (transposing a matrix doesn't
change its diagonal), and uses it as a magnitude ("how far from facing the
camera") rather than a signed direction. This trades precision for
robustness against exactly the kind of silent, uncatchable bug this
sandbox has no way to detect. Full reasoning is in the file's own comments.

**If webcam analytics don't work when you test this**, the failure mode is
designed to be safe: everything in `lib/webcamAnalytics.ts` is wrapped in
try/catch that fails silently, so a broken integration means Webcam stays
"Not available" on the report — it should never break the interview itself.
If it does break something else, that's a real bug to report, not an
intended fallback.

## Setup (adds ffmpeg + a system dependency; one new frontend package)

```bash
cd backend
pip install -r requirements.txt   # now includes pydub
pytest -q   # 135 tests. Speech analytics and deterministic scoring (29 of
            # them) need no OpenAI key or mock — real audio, real arithmetic.
python -m scripts.smoke_test_ai
```

**pydub needs ffmpeg installed on the system** (not just pip-installed) to
decode real audio — `apt-get install ffmpeg` on Debian/Ubuntu, `brew
install ffmpeg` on macOS. Without it, `answer_audio_endpoint` still works
(transcription doesn't need it) but speech metrics silently won't compute
for any turn — that's the graceful-degradation path working as designed,
not a bug, but worth knowing ffmpeg is why.

```bash
cd frontend
npm install   # now includes @mediapipe/tasks-vision
```

No new backend environment variables.

## Known gaps carried over

- **No logo asset was ever attached** — `Logo.tsx` is still a placeholder.
- Settings page is still read-only (no `PATCH /users/me`).
- No rate limiting, password reset, or email verification — Phase 9's job.
- Realtime/WebRTC voice — see the Phase 3 scope decision above.
- No raw resume/JD file storage, no resume reuse across interviews.
- Delivery/Webcam scoring thresholds are reasonable starting points, not
  calibrated against real recordings — expect to tune them.
- The webcam analytics pipeline has never run against a real camera — see
  the dedicated section above before relying on it for anything.

## Recap: what Phases 1–5 already do

- **Auth**: JWT in an HTTP-only cookie. **Interviews**: full CRUD, owned per user.
- **InterviewProfile**: a small static lookup (`app/services/profiles.py`) mapping
  each interview category to subjects, question types, and an interviewer
  style — a deliberate stand-in for the full reusable profile system the
  spec describes for Phase 8/9.
- **Question generation / answer analysis**: one question at a time via
  OpenAI structured outputs; each answer scored 1–5 with strengths,
  weaknesses, and a follow-up decision, mirroring the spec's Day-9 shape.
- **Conversation state**: stored on the interview document — topic,
  difficulty (1–5, adaptive ±1 per turn), asked topics/questions, follow-up
  counts. Completed turns live in `interview_turns` (`GET
  /interviews/{id}/turns` returns the transcript).
- **Repeat-question prevention**: cheap word-overlap check, one retry on
  collision — no embeddings, per the spec's own guidance not to reach for
  those yet.
- **The follow-up decision is deterministic, not model-chosen**: the model
  suggests `followUpNeeded`; a plain Python function decides whether to act
  on it. Separates deterministic logic (state, budgets) from probabilistic
  logic (phrasing, judgment), per the spec's own architecture rule.
- **No live score is shown to the candidate mid-interview** — evaluations
  are stored for the Phase 6 report, not surfaced as a running scoreboard.
- **Voice (Phase 3)**: STT/TTS live in the same `AIClient` interface as
  question generation and answer analysis, all covered by the same
  `FakeAIClient` test pattern. Transcript is always surfaced to the
  candidate rather than hidden. Text input stays available alongside voice
  as a fallback for an integration that's never been tested against a real
  browser.
- **Webcam (Phase 4)**: a local, unanalyzed self-view (`CameraPreview`) plus
  a status bar (mic/camera/timer/AI-speaking/exit). The timer is
  informational only — the engine still ends sessions by question count,
  not wall clock. Exiting early (`POST /interviews/{id}/exit`) marks the
  interview `abandoned` rather than deleting it, so a partial transcript
  survives.
- **Resume/JD (Phase 5)**: PDF/DOCX parsed locally (genuinely tested, not
  mocked) into `CandidateProfile`/`JobProfile` via OpenAI structured
  outputs, shown back to the candidate before the interview starts so a
  hallucinated extraction is catchable early. Once uploaded, every
  question-generation call includes the resume/JD content and is
  instructed to ground questions in it by name. Stored embedded on the
  interview document rather than the spec's separate
  `candidate_profiles`/`job_profiles` collections — no raw file storage,
  no cross-interview resume reuse yet.

Endpoints so far:

```
POST   /auth/register, /auth/login, /auth/logout      GET /auth/me
POST   /interviews          GET /interviews           GET/DELETE /interviews/{id}
POST   /interviews/{id}/start                          — generates the opening question
POST   /interviews/{id}/answer      body: {"answer"}   — text answer -> next question or completion
GET    /interviews/{id}/turns                          — full transcript
GET    /interviews/{id}/question-audio                 — TTS for the pending question (Phase 3)
POST   /interviews/{id}/answer/audio  multipart file    — voice answer -> same engine as text (Phase 3)
POST   /interviews/{id}/exit                           — leave early, marks abandoned (Phase 4)
POST   /interviews/{id}/resume         multipart file   — extract + store CandidateProfile (Phase 5)
POST   /interviews/{id}/job-description  text or file   — extract + store JobProfile (Phase 5)
POST   /interviews/{id}/report                         — generate the evaluation report (Phase 6)
GET    /interviews/{id}/report                         — retrieve the cached report (Phase 6)
POST   /interviews/{id}/webcam-metrics                 — submit client-computed aggregate (Phase 7)
```

Evaluation (Phase 6) recap: five dimensions AI-scored 0-5 with mandatory
evidence (Knowledge, Communication, Relevance, Problem Solving, Interview
Handling); weighting/normalization to a 0-100 overall score is pure,
tested Python, not an AI-picked number; `confidence` is computed from turn
count, not self-rated by the model. Phase 7 adds real Delivery/Webcam
scores on top of that foundation — see above.

Before trusting any of the OpenAI text calls (`generate_question`,
`analyze_answer`, `extract_candidate_profile`, `extract_job_profile`,
`generate_evaluation`), run `python -m scripts.smoke_test_ai` with a real
key and read its output — every automated test here uses a scripted fake,
so none of these have been called against the real API from this
environment.

## Phase 8 — Interview Profiles

Phase 2 already anticipated this: `app/schemas/profile.py`'s docstring says
outright that the real, storable `InterviewProfile` system was "Phase 8/9
work," and the Phase 2 `CATEGORY_DEFAULTS` lookup in
`app/services/profiles.py` was an explicit stand-in for it. Phase 8 is that
upgrade — a new database-backed collection, a CRUD API, and an engine that
reads engine controls (max questions, follow-ups, adaptive difficulty,
resume/JD grounding) from a stored profile instead of hardcoded constants.
Nothing about how the engine keeps interview state (still plain,
deterministic Python — see Phase 2's notes) changed; only *where its
configuration comes from* did.

### Architecture

A **system profile** (`isSystem: true`, `createdBy: null`) is one of the six
seeded defaults, visible to everyone, editable/deletable by no one. A
**custom profile** (`isSystem: false`) belongs to the user who created it
(`createdBy: <userId>`) — visible and editable only to them.

```
InterviewProfile
├── name, description, category         — identity/display
├── subjects[], questionTypes[]         — what the engine asks about
├── interviewerStyle                    — tone in the system prompt
├── difficulty                          — easy | medium | hard | adaptive (informational default)
├── maxQuestions                        — overrides the duration-based heuristic when set
├── followUpEnabled                     — engine skips the follow-up branch entirely when false
├── adaptiveDifficulty                  — engine holds difficultyLevel fixed when false
├── resumeGrounding / jdGrounding       — engine withholds candidate/job context when false
├── isActive                            — false after a soft delete
├── isSystem, createdBy                 — ownership/protection
└── createdAt, updatedAt
```

`app/services/profiles.py` now exposes `load_profile(db, interview)`,
called from both `interview_engine.py` and `evaluation.py`. It's the single
place that decides, per interview:

- **Has a `profileId`, and that profile still exists?** → build the prompt
  profile from the stored document, and hand back its engine-control flags.
- **No `profileId` (or it points at a profile that's gone)?** → fall back to
  the original Phase 2 `derive_profile()` category lookup, with legacy
  engine defaults (`maxQuestions=None` → duration heuristic,
  `followUpEnabled/adaptiveDifficulty/resumeGrounding/jdGrounding=True`).

That fallback is what makes every interview created before Phase 8 — which
has no `profileId` field on its Mongo document at all — behave exactly as
it did in Phase 7, with zero migration required.

### API

| Method | Path | Notes |
|---|---|---|
| `POST` | `/interview-profiles` | Creates a custom profile owned by the caller. |
| `GET` | `/interview-profiles` | Lists active system profiles + the caller's own active custom profiles. |
| `GET` | `/interview-profiles/{id}` | 404 if the profile is inactive, or is another user's custom profile. |
| `PATCH` | `/interview-profiles/{id}` | Owner-only; 403 on a system profile, 404 if not visible. Partial updates only. |
| `DELETE` | `/interview-profiles/{id}` | Owner-only; **soft delete** (`isActive: false`) — see below. 403 on a system profile. |

`POST /interviews` now accepts `profileId` as an alternative to `category`
(at least one is required). When `profileId` is given, `category` is
backfilled from the profile automatically (used for display and for the
existing report-weighting heuristic in `evaluation.py`); the interview
document stores both `profileId` and the resolved `category`.

### Why deletion is soft, not hard

An in-progress or completed interview keeps its `profileId` forever, and
`load_profile()` still needs to resolve it to regenerate a report or (for an
in-progress interview) ask the next question. A hard delete would silently
fall back to the wrong (generic "other") profile mid-interview. So
`DELETE` sets `isActive: false`: the profile disappears from the picker and
from `GET`/`PATCH`/`DELETE`, but `load_profile()` — which queries
`interview_profiles` directly, not through the visibility helper — still
finds it.

### Database structure

New collection: `interview_profiles`, indexed on `(isSystem, name)` (used by
idempotent seeding) and `createdBy` (used by the "my profiles" list).
`interviews` gains one new, optional field: `profileId: string | null`.

### Seeding

Seeding is idempotent and runs automatically on every app startup
(`app/main.py`'s lifespan, right after `ensure_indexes`) via an atomic
`update_one(..., upsert=True)` keyed on `(name, isSystem)` — safe to restart
the app, or run multiple workers, without ever duplicating a system profile.

To seed explicitly (e.g. from deploy tooling, or against a specific
database) without booting the API:

```
cd backend
source venv/bin/activate
python -m scripts.seed_interview_profiles
```

The six seeded profiles: **Software Engineer**, **Frontend Developer**,
**Backend Developer**, **Data Analyst**, **HR / Behavioral**, **System
Design**. Their full definitions live in
`app/services/interview_profiles.py::DEFAULT_PROFILES`.

### Custom profiles

From `/interview-profiles` in the app, any signed-in user can build their
own, e.g.:

```
name: "My Full Stack Interview"
subjects: React, Node.js, MongoDB
questionTypes: technical, scenario, behavioral
difficulty: adaptive
maxQuestions: 10
```

Selecting it on `/interviews/new` and starting the interview actually
changes behavior: `interview_engine.py` reads `subjects`/`questionTypes`
into the AI prompts, honors `maxQuestions` over the duration heuristic, and
switches off follow-ups / difficulty adaptation / resume / JD grounding
per-flag — all covered by `tests/test_interview_profiles.py`'s engine-level
tests, not just the CRUD surface.

### What's next (Phase 9, per the spec)

Interview Profiles were the last piece both the build brief and the
roadmap PDF group under "universal interview framework." What's left is
Phase 9 territory — the brief doesn't specify it further from here, so the
natural candidates (multi-profile interview packs, org-shared profiles,
profile analytics) are open design questions, not committed work.

