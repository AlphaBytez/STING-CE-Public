-- STING Consolidated Database Schema
-- Replaces incremental migrations with clean, unified schema
-- Prevents trigger conflicts and ensures proper relationships

-- Drop existing tables if they exist (fresh install approach)
DROP TABLE IF EXISTS documents CASCADE;
DROP TABLE IF EXISTS honey_jars CASCADE;
DROP TABLE IF EXISTS reports CASCADE;

-- Drop existing functions/triggers
DROP FUNCTION IF EXISTS update_honey_jar_document_count() CASCADE;
DROP FUNCTION IF EXISTS update_updated_at_column() CASCADE;

-- Create honey_jars table with proper structure
CREATE TABLE honey_jars (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    type VARCHAR(50) DEFAULT 'private',
    status VARCHAR(50) DEFAULT 'active',
    owner VARCHAR(255) NOT NULL,
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    tags JSONB DEFAULT '[]'::jsonb,
    permissions JSONB DEFAULT '{}'::jsonb,

    -- Statistics (properly maintained by triggers)
    document_count INTEGER DEFAULT 0,
    embedding_count INTEGER DEFAULT 0,
    total_size_bytes BIGINT DEFAULT 0,
    query_count INTEGER DEFAULT 0,
    average_query_time FLOAT DEFAULT 0.0
);

-- Create documents table with proper structure
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    honey_jar_id UUID NOT NULL REFERENCES honey_jars(id) ON DELETE CASCADE,
    filename VARCHAR(255) NOT NULL,
    content_type VARCHAR(100),
    size_bytes INTEGER,
    upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(50) DEFAULT 'pending',
    doc_metadata JSONB DEFAULT '{}'::jsonb,
    tags JSONB DEFAULT '[]'::jsonb,
    embedding_count INTEGER DEFAULT 0,
    processing_time FLOAT,
    error_message TEXT,
    file_path VARCHAR(500)
);

-- Create reports table with proper honey jar integration
CREATE TABLE reports (
    id VARCHAR(255) PRIMARY KEY,
    template_id VARCHAR(255),
    user_id VARCHAR(255),
    title VARCHAR(255),
    description TEXT,
    status report_status DEFAULT 'queued',
    priority report_priority DEFAULT 'normal',
    progress_percentage INTEGER DEFAULT 0,
    queue_position INTEGER,
    estimated_completion TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    parameters JSONB DEFAULT '{}'::jsonb,
    output_format VARCHAR(50) DEFAULT 'pdf',
    honey_jar_id VARCHAR(255), -- Links reports to specific honey jars
    scrambling_enabled BOOLEAN DEFAULT false,
    scrambling_mapping_id VARCHAR(255),
    risk_level VARCHAR(50) DEFAULT 'low',
    pii_detected BOOLEAN DEFAULT false,
    generated_by VARCHAR(255),
    access_grants JSONB DEFAULT '[]'::jsonb,
    access_type report_access_type DEFAULT 'user-owned',
    result_file_id VARCHAR(255),
    result_size_bytes INTEGER,
    download_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP
);

-- Create unified trigger function for honey jar statistics
CREATE OR REPLACE FUNCTION update_honey_jar_document_count()
RETURNS TRIGGER AS $$
BEGIN
    -- For INSERT
    IF TG_OP = 'INSERT' THEN
        UPDATE honey_jars
        SET document_count = COALESCE(document_count, 0) + 1,
            total_size_bytes = COALESCE(total_size_bytes, 0) + COALESCE(NEW.size_bytes, 0),
            last_updated = CURRENT_TIMESTAMP
        WHERE id = NEW.honey_jar_id;
        RETURN NEW;

    -- For DELETE
    ELSIF TG_OP = 'DELETE' THEN
        UPDATE honey_jars
        SET document_count = GREATEST(COALESCE(document_count, 0) - 1, 0),
            total_size_bytes = GREATEST(COALESCE(total_size_bytes, 0) - COALESCE(OLD.size_bytes, 0), 0),
            last_updated = CURRENT_TIMESTAMP
        WHERE id = OLD.honey_jar_id;
        RETURN OLD;

    -- For UPDATE (if honey_jar_id changes)
    ELSIF TG_OP = 'UPDATE' AND OLD.honey_jar_id IS DISTINCT FROM NEW.honey_jar_id THEN
        -- Decrement old honey jar
        IF OLD.honey_jar_id IS NOT NULL THEN
            UPDATE honey_jars
            SET document_count = GREATEST(COALESCE(document_count, 0) - 1, 0),
                total_size_bytes = GREATEST(COALESCE(total_size_bytes, 0) - COALESCE(OLD.size_bytes, 0), 0),
                last_updated = CURRENT_TIMESTAMP
            WHERE id = OLD.honey_jar_id;
        END IF;

        -- Increment new honey jar
        IF NEW.honey_jar_id IS NOT NULL THEN
            UPDATE honey_jars
            SET document_count = COALESCE(document_count, 0) + 1,
                total_size_bytes = COALESCE(total_size_bytes, 0) + COALESCE(NEW.size_bytes, 0),
                last_updated = CURRENT_TIMESTAMP
            WHERE id = NEW.honey_jar_id;
        END IF;
        RETURN NEW;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create single, unified trigger (no conflicts)
CREATE TRIGGER unified_honey_jar_stats_trigger
    AFTER INSERT OR DELETE OR UPDATE OF honey_jar_id ON documents
    FOR EACH ROW
    EXECUTE FUNCTION update_honey_jar_document_count();

-- Create indexes for performance
CREATE INDEX idx_documents_honey_jar_id ON documents(honey_jar_id);
CREATE INDEX idx_documents_status ON documents(status);
CREATE INDEX idx_documents_upload_date ON documents(upload_date);
CREATE INDEX idx_honey_jars_owner ON honey_jars(owner);
CREATE INDEX idx_honey_jars_type ON honey_jars(type);
CREATE INDEX idx_reports_honey_jar_id ON reports(honey_jar_id);
CREATE INDEX idx_reports_status ON reports(status);

-- Create necessary enums
DO $$ BEGIN
    CREATE TYPE report_status AS ENUM ('queued', 'processing', 'completed', 'failed', 'cancelled');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE report_priority AS ENUM ('low', 'normal', 'high', 'urgent');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE report_access_type AS ENUM ('user-owned', 'service-generated');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Insert metadata about this baseline
INSERT INTO schema_migrations (version, description, applied_at)
VALUES ('001_baseline', 'Consolidated baseline schema with unified triggers', CURRENT_TIMESTAMP)
ON CONFLICT (version) DO NOTHING;