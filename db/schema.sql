-- CURRENT CRITERIA (one active row)
CREATE TABLE IF NOT EXISTS criteria (
    id INTEGER PRIMARY KEY,
    titles TEXT, skills TEXT,            -- JSON arrays
    location TEXT, working_mode TEXT,
    pay_min REAL, pay_currency TEXT,
    score_threshold REAL DEFAULT 0.0,
    domain_keywords TEXT,                -- JSON array, user-entered (Phase 4)
    created_at TEXT, active INTEGER DEFAULT 1
);

-- CURRENT CORPUS  (cleared on criteria update)
CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY,             -- sha1( norm(company) | norm(title) | norm(location) )
    source TEXT NOT NULL, external_id TEXT,   -- external_id = source's native job id, nullable
    url TEXT, title TEXT, company TEXT, location TEXT,
    work_type TEXT,                      -- remote | hybrid | onsite | unknown
    description TEXT,
    salary_min REAL, salary_max REAL, salary_currency TEXT,
    salary_min_inr REAL, salary_max_inr REAL,  -- normalized for gating
    poster_name TEXT, poster_email TEXT, -- OPPORTUNISTIC ONLY, nullable
    posted_date TEXT, first_seen TEXT, last_seen TEXT,
    raw_json TEXT
);

CREATE TABLE IF NOT EXISTS job_score (                 -- cleared on criteria update
    job_id TEXT PRIMARY KEY REFERENCES jobs(job_id),
    gate_passed INTEGER, gate_reason TEXT,
    skills_matched INTEGER, skills_matched_list TEXT,  -- JSON
    score REAL,                          -- alignment 0..1, shown to user
    model_source TEXT,                   -- 'deterministic' | 'learner'
    domain_hits INTEGER DEFAULT 0, domain_matched_list TEXT  -- JSON (Phase 4)
);

CREATE TABLE IF NOT EXISTS review (                    -- cleared on criteria update
    job_id TEXT PRIMARY KEY REFERENCES jobs(job_id),
    status TEXT,                         -- new | relevant | irrelevant | applied
    reviewed_at TEXT, from_discard INTEGER DEFAULT 0, notes TEXT
);

-- PERSISTENT  (NOT cleared on criteria update — learner trains on this)
CREATE TABLE IF NOT EXISTS labels (
    id INTEGER PRIMARY KEY, labeled_at TEXT,
    relevant INTEGER, from_discard INTEGER,
    -- feature snapshot at label time, so labels stay criteria-independent
    title TEXT, company TEXT, source TEXT, work_type TEXT, location TEXT,
    salary_min_inr REAL, skills_matched INTEGER, skills_matched_list TEXT,
    domain_hits INTEGER, feature_json TEXT
);

CREATE TABLE IF NOT EXISTS runs (                      -- observability
    run_id INTEGER PRIMARY KEY, ts TEXT, criteria_id INTEGER, sources TEXT,
    n_fetched INTEGER, n_new INTEGER, n_gate_passed INTEGER, notes TEXT
);

-- PERSISTENT (Phase 3 -- one row per tailoring run, kept across criteria updates)
CREATE TABLE IF NOT EXISTS tailored_resumes (
    id INTEGER PRIMARY KEY, job_id TEXT REFERENCES jobs(job_id),
    created_at TEXT,
    docx_path TEXT, md_path TEXT, gap_report_path TEXT,
    lint_status TEXT,                    -- 'clean' | 'flagged'
    lint_flags TEXT                      -- JSON: offending items if flagged
);
