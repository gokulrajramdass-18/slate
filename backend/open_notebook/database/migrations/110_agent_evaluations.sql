-- Migration: 110 - Standalone Agent Evaluations
-- Description: Schema for evaluating standalone agents with test datasets
-- Date: 2026-05-11

-- ============================================================================
-- EVALUATION DATASETS TABLE
-- ============================================================================
-- Test datasets for evaluating agents

CREATE TABLE IF NOT EXISTS evaluation_datasets (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    agent_id TEXT,  -- Optional: associate with specific agent
    created_by TEXT,

    -- Dataset metadata
    test_case_count INTEGER DEFAULT 0,
    file_name TEXT,  -- Original uploaded file name
    file_format TEXT,  -- csv, json, jsonl

    -- Evaluation criteria
    criteria TEXT,  -- JSON: ["accuracy", "relevance", "completeness", "latency"]
    scoring_method TEXT DEFAULT 'llm_judge',  -- llm_judge, exact_match, semantic_similarity, custom

    created TEXT NOT NULL,
    updated TEXT NOT NULL,

    FOREIGN KEY (agent_id) REFERENCES standalone_agents(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_eval_datasets_agent ON evaluation_datasets(agent_id);
CREATE INDEX IF NOT EXISTS idx_eval_datasets_created ON evaluation_datasets(created DESC);

-- ============================================================================
-- EVALUATION TEST CASES TABLE
-- ============================================================================
-- Individual test cases within datasets

CREATE TABLE IF NOT EXISTS evaluation_test_cases (
    id TEXT PRIMARY KEY,
    dataset_id TEXT NOT NULL,

    -- Test case data
    input_prompt TEXT NOT NULL,
    expected_output TEXT,  -- Optional: ground truth for comparison
    context TEXT,  -- Optional: additional context/data
    metadata TEXT,  -- JSON: additional metadata

    -- Tags for filtering
    tags TEXT,  -- JSON array: ["edge_case", "critical", "basic"]
    category TEXT,  -- e.g., "data_query", "research", "analysis"

    created TEXT NOT NULL,

    FOREIGN KEY (dataset_id) REFERENCES evaluation_datasets(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_eval_cases_dataset ON evaluation_test_cases(dataset_id);
CREATE INDEX IF NOT EXISTS idx_eval_cases_category ON evaluation_test_cases(category);

-- ============================================================================
-- EVALUATION RUNS TABLE
-- ============================================================================
-- Execution of agent against a dataset

CREATE TABLE IF NOT EXISTS evaluation_runs (
    id TEXT PRIMARY KEY,
    dataset_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,

    -- Run configuration
    run_name TEXT,
    model_override TEXT,  -- Optional: test with specific model
    config_override TEXT,  -- JSON: temporary config changes

    -- Status
    status TEXT NOT NULL DEFAULT 'pending',  -- pending, running, completed, failed
    progress INTEGER DEFAULT 0,  -- 0-100

    -- Results summary
    total_cases INTEGER DEFAULT 0,
    passed_cases INTEGER DEFAULT 0,
    failed_cases INTEGER DEFAULT 0,
    avg_score REAL,  -- Average score across all cases
    avg_latency_ms REAL,  -- Average execution time

    -- Metadata
    started_at TEXT,
    completed_at TEXT,
    error_message TEXT,

    created TEXT NOT NULL,
    created_by TEXT,

    FOREIGN KEY (dataset_id) REFERENCES evaluation_datasets(id) ON DELETE CASCADE,
    FOREIGN KEY (agent_id) REFERENCES standalone_agents(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_eval_runs_dataset ON evaluation_runs(dataset_id);
CREATE INDEX IF NOT EXISTS idx_eval_runs_agent ON evaluation_runs(agent_id);
CREATE INDEX IF NOT EXISTS idx_eval_runs_status ON evaluation_runs(status);
CREATE INDEX IF NOT EXISTS idx_eval_runs_created ON evaluation_runs(created DESC);

-- ============================================================================
-- EVALUATION RESULTS TABLE
-- ============================================================================
-- Individual test case execution results

CREATE TABLE IF NOT EXISTS evaluation_results (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    test_case_id TEXT NOT NULL,

    -- Execution data
    agent_output TEXT NOT NULL,
    execution_time_ms REAL,

    -- Scoring
    passed BOOLEAN NOT NULL DEFAULT 0,
    overall_score REAL,  -- 0.0-1.0 or 0-10 depending on config
    criteria_scores TEXT,  -- JSON: {"accuracy": 0.9, "relevance": 0.85}

    -- Comparison with expected output
    similarity_score REAL,  -- For semantic similarity scoring
    exact_match BOOLEAN,

    -- Feedback
    feedback TEXT,  -- LLM judge feedback or error message
    judge_reasoning TEXT,  -- Explanation from LLM judge

    -- Metadata
    error_occurred BOOLEAN DEFAULT 0,
    error_message TEXT,

    created TEXT NOT NULL,

    FOREIGN KEY (run_id) REFERENCES evaluation_runs(id) ON DELETE CASCADE,
    FOREIGN KEY (test_case_id) REFERENCES evaluation_test_cases(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_eval_results_run ON evaluation_results(run_id);
CREATE INDEX IF NOT EXISTS idx_eval_results_case ON evaluation_results(test_case_id);
CREATE INDEX IF NOT EXISTS idx_eval_results_passed ON evaluation_results(passed);

-- ============================================================================
-- NOTES
-- ============================================================================
-- Dataset formats:
--   CSV: columns [input, expected_output, category, tags]
--   JSON: array of {input, expected_output, category, tags, metadata}
--   JSONL: one JSON object per line
--
-- Scoring methods:
--   - llm_judge: Use LLM to evaluate quality
--   - exact_match: String comparison
--   - semantic_similarity: Embedding similarity
--   - custom: User-defined scoring function
--
-- Use cases:
--   1. Upload dataset
--   2. Create evaluation run
--   3. Execute agent against all test cases
--   4. View aggregated results and individual case breakdowns
