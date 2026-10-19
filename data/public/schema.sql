-- Schema only. No participant rows or SQLite sequence values.
CREATE TABLE annotations (
    annotation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    sample_id     TEXT REFERENCES samples(sample_id),
    annotator     TEXT,              -- A / B
    score_A       INTEGER,
    score_L       INTEGER,
    score_S       INTEGER,
    score_P       INTEGER,
    dep_level     TEXT,              -- high/medium/low/接受引导-非提问
    is_disputed   INTEGER DEFAULT 0,
    annotated_at  TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE samples (
    sample_id    TEXT PRIMARY KEY,   -- 如 S0001（沿用 v2 的样本ID）
    student_id   TEXT,               -- 真实样本指向 students.student_id，其余为空
    session_id   TEXT,
    round        TEXT,               -- R1 / R3
    pair_id      TEXT,               -- R3 指向其 R1 的 sample_id
    task_type    TEXT,               -- 数学解题
    source       TEXT,               -- 真实收集/LLM扩展/Eedi翻译/合成R3
    src_real     INTEGER DEFAULT 0,
    src_llm      INTEGER DEFAULT 0,
    src_eedi     INTEGER DEFAULT 0,
    src_synth    INTEGER DEFAULT 0,
    prompt_text  TEXT,
    en_text      TEXT,
    ai_type      TEXT,               -- A/B/C 引导类型
    ai_label     TEXT,
    prev_level   TEXT,               -- 上轮依赖等级
    dep_change   TEXT,               -- 依赖变化
    pre_A INTEGER, pre_L INTEGER, pre_S INTEGER, pre_P INTEGER,
    ref_level    TEXT,               -- 预标注参考等级(含"接受引导/非提问")
    note         TEXT
, final_level TEXT, subject TEXT);

CREATE TABLE students (
    student_id   TEXT PRIMARY KEY,   -- 如 ST001（真实学生）
    grade        TEXT,
    gender       TEXT DEFAULT 'unknown',
    ai_frequency TEXT DEFAULT 'not_collected'
);
