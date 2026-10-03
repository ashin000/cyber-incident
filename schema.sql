-- ============================================================
-- Cyber Incident Reporting Portal — SQLite Database Schema
-- Auto-initialized by the database.py connector.
-- ============================================================

-- ── Users ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name       VARCHAR(150)    NOT NULL,
    email           VARCHAR(255)    NOT NULL UNIQUE,
    phone           VARCHAR(20)     DEFAULT NULL,
    password_hash   VARCHAR(512)    NOT NULL,
    reset_token     VARCHAR(255)    DEFAULT NULL,
    reset_token_expires DATETIME     DEFAULT NULL,
    role            VARCHAR(50)     NOT NULL DEFAULT 'citizen', -- 'citizen', 'officer', 'admin'
    address         TEXT            DEFAULT NULL,
    is_active       TINYINT         NOT NULL DEFAULT 1,
    avatar          VARCHAR(512)    DEFAULT NULL,
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users (email);
CREATE INDEX IF NOT EXISTS idx_users_role ON users (role);

-- ── Officers ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS officers (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER         NOT NULL UNIQUE,
    badge_number    VARCHAR(50)     NOT NULL UNIQUE,
    department      VARCHAR(150)    DEFAULT NULL,
    specialization  VARCHAR(200)    DEFAULT NULL,
    cases_limit     INTEGER         NOT NULL DEFAULT 20,
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- ── Incident Categories ───────────────────────────────────────
CREATE TABLE IF NOT EXISTS incident_categories (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            VARCHAR(100)    NOT NULL UNIQUE,
    description     TEXT            DEFAULT NULL,
    is_active       TINYINT         NOT NULL DEFAULT 1,
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ── Incidents ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS incidents (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id             VARCHAR(20)     NOT NULL UNIQUE,
    user_id             INTEGER         NOT NULL,
    category_id         INTEGER         DEFAULT NULL,
    title               VARCHAR(255)    NOT NULL,
    incident_type       VARCHAR(100)    NOT NULL,
    description         TEXT            NOT NULL,
    incident_date       DATE            NOT NULL,
    incident_time       TIME            DEFAULT NULL,
    location            VARCHAR(255)    DEFAULT NULL,
    website_involved    VARCHAR(500)    DEFAULT NULL,
    email_involved      VARCHAR(255)    DEFAULT NULL,
    phone_involved      VARCHAR(50)     DEFAULT NULL,
    social_media        VARCHAR(500)    DEFAULT NULL,
    financial_loss      DECIMAL(15, 2)  DEFAULT 0.00,
    additional_comments TEXT            DEFAULT NULL,
    priority            VARCHAR(50)     NOT NULL DEFAULT 'medium', -- 'low', 'medium', 'high', 'critical'
    status              VARCHAR(50)     NOT NULL DEFAULT 'Pending', -- 'Pending', 'Assigned', 'Under Investigation', 'Resolved', 'Closed'
    assigned_officer_id INTEGER         DEFAULT NULL,
    resolution_remarks  TEXT            DEFAULT NULL,
    created_at          DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id)             REFERENCES users(id)               ON DELETE CASCADE,
    FOREIGN KEY (category_id)         REFERENCES incident_categories(id) ON DELETE SET NULL,
    FOREIGN KEY (assigned_officer_id) REFERENCES users(id)               ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_incidents_case_id ON incidents (case_id);
CREATE INDEX IF NOT EXISTS idx_incidents_user_id ON incidents (user_id);
CREATE INDEX IF NOT EXISTS idx_incidents_status ON incidents (status);
CREATE INDEX IF NOT EXISTS idx_incidents_priority ON incidents (priority);
CREATE INDEX IF NOT EXISTS idx_incidents_officer ON incidents (assigned_officer_id);
CREATE INDEX IF NOT EXISTS idx_incidents_created ON incidents (created_at);

-- ── Evidence ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS evidence (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    incident_id     INTEGER         NOT NULL,
    file_name       VARCHAR(255)    NOT NULL,
    original_name   VARCHAR(255)    NOT NULL,
    file_path       VARCHAR(512)    NOT NULL,
    file_type       VARCHAR(50)     NOT NULL,
    file_size       BIGINT          NOT NULL DEFAULT 0,
    uploaded_by     INTEGER         NOT NULL,
    notes           TEXT            DEFAULT NULL,
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (incident_id) REFERENCES incidents(id) ON DELETE CASCADE,
    FOREIGN KEY (uploaded_by) REFERENCES users(id)     ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_evidence_incident ON evidence (incident_id);

-- ── Case Status History ───────────────────────────────────────
CREATE TABLE IF NOT EXISTS case_status_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    incident_id     INTEGER         NOT NULL,
    old_status      VARCHAR(50)     DEFAULT NULL,
    new_status      VARCHAR(50)     NOT NULL,
    changed_by      INTEGER         NOT NULL,
    notes           TEXT            DEFAULT NULL,
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (incident_id) REFERENCES incidents(id) ON DELETE CASCADE,
    FOREIGN KEY (changed_by)  REFERENCES users(id)     ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_status_history_incident ON case_status_history (incident_id);

-- ── Investigation Notes ───────────────────────────────────────
CREATE TABLE IF NOT EXISTS investigation_notes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    incident_id     INTEGER         NOT NULL,
    officer_id      INTEGER         NOT NULL,
    note            TEXT            NOT NULL,
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (incident_id) REFERENCES incidents(id) ON DELETE CASCADE,
    FOREIGN KEY (officer_id)  REFERENCES users(id)     ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_inv_notes_incident ON investigation_notes (incident_id);

-- ── Notifications ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS notifications (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER         NOT NULL,
    title           VARCHAR(255)    NOT NULL,
    message         TEXT            NOT NULL,
    type            VARCHAR(50)     DEFAULT 'info',
    is_read         TINYINT         NOT NULL DEFAULT 0,
    incident_id     INTEGER         DEFAULT NULL,
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id)     REFERENCES users(id)     ON DELETE CASCADE,
    FOREIGN KEY (incident_id) REFERENCES incidents(id)  ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications (user_id);
CREATE INDEX IF NOT EXISTS idx_notifications_read ON notifications (is_read);

-- ── Audit Logs ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS audit_logs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER         DEFAULT NULL,
    action          VARCHAR(100)    NOT NULL,
    details         TEXT            DEFAULT NULL,
    ip_address      VARCHAR(45)     DEFAULT NULL,
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_logs (user_id);
CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_logs (action);
CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_logs (created_at);

-- ── Report History ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS report_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    admin_id        INTEGER         NOT NULL,
    report_type     VARCHAR(50)     NOT NULL,
    file_path       VARCHAR(512)    NOT NULL,
    parameters      TEXT            DEFAULT NULL,
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (admin_id) REFERENCES users(id) ON DELETE CASCADE
);
