# JobHorizon

A local, single-user, deterministic job-search and triage pipeline. Runs once daily,
pulls listings from free job-board APIs/feeds (and optionally scraped sources via
JobSpy), normalizes + dedupes them, scores them against your criteria, and stores
everything in a local SQLite file for review.

## Status

- **Phase 1 — pipeline core.** Adapters → normalize → dedup → deterministic filter →
  skill score → SQLite, with a CSV export and console summary of today's new
  gate-passed jobs.
- **Phase 2 — dashboard + learner.** Flask dashboard (Kept/Discarded tabs, mark
  relevant/irrelevant, threshold slider, update-criteria button) + nightly learner
  that refits a LogisticRegression on your labels once `scoring.learner_min_labels`
  is reached, with a feature-weight transparency report and precision@K /
  discard-rescue metrics printed each run.
- **Phase 3 — resume tailoring.** Bring-your-own Anthropic API key. For any job marked
  relevant, `POST /api/tailor` (or the "Tailor resume" button on its card) extracts JD
  requirements, selects + reorders the most relevant bullets from your master resume
  (`data/master_resume.yaml`, gitignored), rephrases them in the JD's vocabulary, runs a
  deterministic + LLM fabrication lint against your master resume's fact set, and renders
  a `.docx`/`.md` plus a gap report to `outputs/tailored/` (gitignored). If the lint flags
  anything, the whole batch falls back to your original wording rather than risk shipping
  an unverifiable claim. This is the only phase that touches an LLM; nothing in the daily
  pipeline loop does.

JobHorizon is complete through Phase 3.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate          # or: source .venv/bin/activate on macOS/Linux
pip install -r requirements.txt
copy .env.example .env          # or: cp .env.example .env
```

Edit `.env` with any API keys you have (Adzuna, Jooble — both optional, the no-key
Tier A sources work without them). Edit `config.yaml` to enable/disable sources and
tune the filter/scoring knobs.

For Phase 3 resume tailoring, also copy `data/master_resume.example.yaml` to
`data/master_resume.yaml`, fill in your real history, and set `ANTHROPIC_API_KEY` in
`.env`. Both files are gitignored since they hold personal data.

## Run

```bash
python -m jobhorizon.run
```

First run prompts for your search criteria (job titles, skills, location, working
mode, minimum pay, currency) and persists them to `data/jobhorizon.db`. Every run
after that fetches, normalizes, dedupes, gates, and scores today's listings, writes
them to SQLite, exports a CSV to `data/exports/`, and prints a console summary of
new gate-passed jobs.

```bash
python -m jobhorizon.run --update-criteria   # re-prompt for criteria; clears jobs/job_score/review,
                                              # keeps your learned label history
python -m jobhorizon.run --full-reset        # same, but also wipes label history
```

## Review

```bash
python -m jobhorizon.dashboard
```

Opens a local web app at `http://127.0.0.1:5000` with **Kept** and **Discarded** tabs.
Mark jobs relevant/irrelevant in either tab — every mark updates the current review
state and appends to the persistent `labels` history the learner trains on. Drag the
score-threshold slider to re-partition Kept/Discarded instantly (no pipeline re-run).
"Update criteria" re-prompts for titles/skills/location/mode/pay and clears the current
corpus (`jobs`/`job_score`/`review`) while keeping your label history, unless you also
check "full reset". Export the current corpus to CSV from the dashboard at any time.

Once you've collected `scoring.learner_min_labels` labels (default 40), the next
`python -m jobhorizon.run` retrains a LogisticRegression on them and switches scoring
from `deterministic` to `learner` for the current corpus — printing the top feature
weights plus precision@K and discard-rescue-rate metrics to the console.

## Sources

**Tier A (free, no scraping):** Adzuna and Jooble need API keys in `.env`. RemoteOK,
Himalayas, Remotive, Arbeitnow, Jobicy, and We Work Remotely need no key and are
enabled by default.

**Tier B (JobSpy, opt-in):** LinkedIn, Naukri, Indeed, Google Jobs, Glassdoor via
scraping. Off by default (`sources.jobspy.enabled: false` in `config.yaml`) — scraping
may violate the source's terms; you are responsible for compliance in your
jurisdiction. Keep `results_wanted` low, especially for LinkedIn.

**Out of scope:** Instahyre, iimjobs, Wellfound, Cutshort, Hirect — no clean API,
login-walled, or anti-scraping. Not built.

## Notes

- The deterministic filter is **recall-biased**: when a gate can't confidently
  classify a job (unclear work type, unparseable location, missing salary), the job
  passes through to the corpus rather than being silently dropped.
- `poster_name`/`poster_email` are populated **only** when a source already provides
  them in structured data. No recruiter-contact scraping or enrichment is built.
