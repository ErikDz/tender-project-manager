-- =============================================
-- Tender Project Manager - Initial Schema
-- =============================================

-- Organizations (tenants)
CREATE TABLE organizations (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT now()
);

-- Organization members (links auth.users to orgs)
CREATE TABLE org_members (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id         UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    role            TEXT NOT NULL DEFAULT 'member',  -- admin, member
    created_at      TIMESTAMPTZ DEFAULT now(),
    UNIQUE(organization_id, user_id)
);

-- Projects
CREATE TABLE projects (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    description     TEXT DEFAULT '',
    tender_number   TEXT DEFAULT '',
    status          TEXT NOT NULL DEFAULT 'active',
    deadline        TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_projects_org ON projects(organization_id);

-- Documents
CREATE TABLE documents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    filename        TEXT NOT NULL,
    storage_path    TEXT NOT NULL,
    file_type       TEXT,
    file_size       BIGINT,
    content_hash    TEXT,
    extracted_text  TEXT,
    is_filled       BOOLEAN DEFAULT FALSE,
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_documents_project ON documents(project_id);

-- Graph nodes (requirements, checkboxes, fields, etc.)
CREATE TABLE nodes (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    document_id     UUID REFERENCES documents(id) ON DELETE SET NULL,
    type            TEXT NOT NULL,  -- document, requirement, condition, checkbox, signature, field, attachment, deadline
    title           TEXT NOT NULL,
    description     TEXT DEFAULT '',
    status          TEXT NOT NULL DEFAULT 'not_started',  -- not_started, in_progress, completed, not_applicable, blocked
    source_text     TEXT DEFAULT '',
    source_location TEXT DEFAULT '',
    is_required     BOOLEAN DEFAULT TRUE,
    is_checked      BOOLEAN,
    deadline        TIMESTAMPTZ,
    confidence      REAL DEFAULT 1.0,
    tags            JSONB DEFAULT '[]',
    metadata        JSONB DEFAULT '{}',
    notes           TEXT,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_nodes_project ON nodes(project_id);
CREATE INDEX idx_nodes_document ON nodes(document_id);
CREATE INDEX idx_nodes_type ON nodes(project_id, type);
CREATE INDEX idx_nodes_status ON nodes(project_id, status);

-- Graph edges (relationships between nodes)
CREATE TABLE edges (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    source_node_id  UUID NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    target_node_id  UUID NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    type            TEXT NOT NULL,  -- requires, required_by, conditional_on, triggers, part_of, references, mutually_exclusive, depends_on
    description     TEXT DEFAULT '',
    confidence      REAL DEFAULT 1.0,
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_edges_project ON edges(project_id);
CREATE INDEX idx_edges_source ON edges(source_node_id);
CREATE INDEX idx_edges_target ON edges(target_node_id);

-- Processing jobs (track background AI extraction)
CREATE TABLE processing_jobs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id          UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    job_type            TEXT NOT NULL,  -- extract, scan, fill_suggest, learn
    status              TEXT NOT NULL DEFAULT 'pending',  -- pending, running, completed, failed
    progress            REAL DEFAULT 0.0,
    current_step        TEXT,
    total_documents     INT,
    processed_documents INT DEFAULT 0,
    error_message       TEXT,
    started_at          TIMESTAMPTZ,
    completed_at        TIMESTAMPTZ,
    created_at          TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_jobs_project ON processing_jobs(project_id);

-- Knowledge base entries (Q&A from filled tenders)
CREATE TABLE knowledge_entries (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id     UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    question_text       TEXT NOT NULL,
    question_context    TEXT,
    field_type          TEXT,  -- text, date, number, boolean, selection
    answer_text         TEXT NOT NULL,
    answer_metadata     JSONB,
    source_document_id  UUID REFERENCES documents(id) ON DELETE SET NULL,
    source_tender_id    UUID REFERENCES projects(id) ON DELETE SET NULL,
    source_location     TEXT,
    confidence          REAL DEFAULT 1.0,
    is_verified         BOOLEAN DEFAULT FALSE,
    is_manual           BOOLEAN DEFAULT FALSE,
    times_used          INT DEFAULT 0,
    last_used_at        TIMESTAMPTZ,
    category            TEXT,
    tags                JSONB DEFAULT '[]',
    created_at          TIMESTAMPTZ DEFAULT now(),
    updated_at          TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_knowledge_org ON knowledge_entries(organization_id);
CREATE INDEX idx_knowledge_question ON knowledge_entries USING gin(to_tsvector('german', question_text));
CREATE INDEX idx_knowledge_category ON knowledge_entries(organization_id, category);

-- Fill suggestions (AI-matched answers for empty tender fields)
CREATE TABLE fill_suggestions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id          UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    node_id             UUID REFERENCES nodes(id) ON DELETE CASCADE,
    knowledge_entry_id  UUID REFERENCES knowledge_entries(id) ON DELETE SET NULL,
    suggested_value     TEXT NOT NULL,
    confidence          REAL,
    status              TEXT NOT NULL DEFAULT 'pending',  -- pending, accepted, rejected, modified
    accepted_value      TEXT,
    created_at          TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_suggestions_project ON fill_suggestions(project_id);

-- =============================================
-- Row-Level Security (multi-tenancy)
-- =============================================

ALTER TABLE organizations ENABLE ROW LEVEL SECURITY;
ALTER TABLE org_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE nodes ENABLE ROW LEVEL SECURITY;
ALTER TABLE edges ENABLE ROW LEVEL SECURITY;
ALTER TABLE processing_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE knowledge_entries ENABLE ROW LEVEL SECURITY;
ALTER TABLE fill_suggestions ENABLE ROW LEVEL SECURITY;

-- Helper function: get user's org IDs
CREATE OR REPLACE FUNCTION user_org_ids()
RETURNS SETOF UUID AS $$
    SELECT organization_id FROM org_members WHERE user_id = auth.uid()
$$ LANGUAGE SQL SECURITY DEFINER STABLE;

-- Organizations: members can see their own orgs
CREATE POLICY "org_select" ON organizations
    FOR SELECT USING (id IN (SELECT user_org_ids()));

-- Org members: can see members of their own orgs
CREATE POLICY "org_members_select" ON org_members
    FOR SELECT USING (organization_id IN (SELECT user_org_ids()));

-- Projects: scoped to user's org
CREATE POLICY "projects_select" ON projects
    FOR SELECT USING (organization_id IN (SELECT user_org_ids()));
CREATE POLICY "projects_insert" ON projects
    FOR INSERT WITH CHECK (organization_id IN (SELECT user_org_ids()));
CREATE POLICY "projects_update" ON projects
    FOR UPDATE USING (organization_id IN (SELECT user_org_ids()));
CREATE POLICY "projects_delete" ON projects
    FOR DELETE USING (organization_id IN (SELECT user_org_ids()));

-- Documents: scoped via project's org
CREATE POLICY "documents_all" ON documents
    FOR ALL USING (
        project_id IN (SELECT id FROM projects WHERE organization_id IN (SELECT user_org_ids()))
    );

-- Nodes: scoped via project's org
CREATE POLICY "nodes_all" ON nodes
    FOR ALL USING (
        project_id IN (SELECT id FROM projects WHERE organization_id IN (SELECT user_org_ids()))
    );

-- Edges: scoped via project's org
CREATE POLICY "edges_all" ON edges
    FOR ALL USING (
        project_id IN (SELECT id FROM projects WHERE organization_id IN (SELECT user_org_ids()))
    );

-- Processing jobs: scoped via project's org
CREATE POLICY "jobs_all" ON processing_jobs
    FOR ALL USING (
        project_id IN (SELECT id FROM projects WHERE organization_id IN (SELECT user_org_ids()))
    );

-- Knowledge entries: scoped to org
CREATE POLICY "knowledge_all" ON knowledge_entries
    FOR ALL USING (organization_id IN (SELECT user_org_ids()));

-- Fill suggestions: scoped via project's org
CREATE POLICY "suggestions_all" ON fill_suggestions
    FOR ALL USING (
        project_id IN (SELECT id FROM projects WHERE organization_id IN (SELECT user_org_ids()))
    );

-- =============================================
-- Storage bucket for documents
-- =============================================

INSERT INTO storage.buckets (id, name, public) VALUES ('documents', 'documents', false);

-- Storage policies: users can manage files in their org's projects
CREATE POLICY "documents_storage_select" ON storage.objects
    FOR SELECT USING (
        bucket_id = 'documents'
    );

CREATE POLICY "documents_storage_insert" ON storage.objects
    FOR INSERT WITH CHECK (
        bucket_id = 'documents'
    );

CREATE POLICY "documents_storage_delete" ON storage.objects
    FOR DELETE USING (
        bucket_id = 'documents'
    );

-- =============================================
-- Auto-update updated_at timestamps
-- =============================================

CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER projects_updated_at BEFORE UPDATE ON projects
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER documents_updated_at BEFORE UPDATE ON documents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER nodes_updated_at BEFORE UPDATE ON nodes
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER knowledge_updated_at BEFORE UPDATE ON knowledge_entries
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
