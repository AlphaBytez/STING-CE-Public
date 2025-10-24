-- STING Complete Database Initialization Script
-- This script initializes the complete STING database schema for fresh installations
-- Includes all preference management columns and recent schema updates
-- 
-- ⚠️  CRITICAL: This file is used during fresh installations!
--     Any changes here will affect new STING installations.
--     For existing installations, use migration scripts instead.

-- First connect to postgres database
\c postgres;

-- Create all required databases (ignore errors if they already exist)
SELECT 'CREATE DATABASE sting_app' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'sting_app')\gexec
SELECT 'CREATE DATABASE kratos' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'kratos')\gexec  
SELECT 'CREATE DATABASE sting_messaging' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'sting_messaging')\gexec

-- Create dedicated database users with secure passwords
-- These passwords should match docker-compose.yml connection strings
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'kratos_user') THEN
        CREATE USER kratos_user WITH PASSWORD 'kratos_secure_password_change_me';
    END IF;
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'app_user') THEN
        CREATE USER app_user WITH PASSWORD 'app_secure_password_change_me';
    END IF;
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'messaging_user') THEN
        CREATE USER messaging_user WITH PASSWORD 'messaging_secure_password_change_me';
    END IF;
END
$$;

-- Set up Kratos database with proper permissions
\c kratos;
GRANT ALL PRIVILEGES ON DATABASE kratos TO kratos_user;
GRANT ALL PRIVILEGES ON SCHEMA public TO kratos_user;
GRANT CREATE ON SCHEMA public TO kratos_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO kratos_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO kratos_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON FUNCTIONS TO kratos_user;

-- Set up application database with proper permissions
\c sting_app;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

GRANT ALL PRIVILEGES ON DATABASE sting_app TO app_user;
GRANT ALL PRIVILEGES ON SCHEMA public TO app_user;
GRANT CREATE ON SCHEMA public TO app_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO app_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO app_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON FUNCTIONS TO app_user;

-- Set up messaging database with proper permissions
\c sting_messaging;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

GRANT ALL PRIVILEGES ON DATABASE sting_messaging TO messaging_user;
GRANT ALL PRIVILEGES ON SCHEMA public TO messaging_user;
GRANT CREATE ON SCHEMA public TO messaging_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO messaging_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO messaging_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON FUNCTIONS TO messaging_user;

-- Grant app_user access to messaging database as well (for cross-service operations)
GRANT ALL PRIVILEGES ON DATABASE sting_messaging TO app_user;
GRANT ALL PRIVILEGES ON SCHEMA public TO app_user;
GRANT CREATE ON SCHEMA public TO app_user;

-- Ensure postgres superuser has full access to all databases
GRANT ALL PRIVILEGES ON DATABASE kratos TO postgres;
GRANT ALL PRIVILEGES ON DATABASE sting_app TO postgres;
GRANT ALL PRIVILEGES ON DATABASE sting_messaging TO postgres;

-- Back to sting_app database for table creation
\c sting_app;

-- Create schema if it doesn't exist (should already exist)
CREATE SCHEMA IF NOT EXISTS public;

-- Set up proper ownership and permissions for all databases
ALTER DATABASE sting_app OWNER TO postgres;
ALTER DATABASE kratos OWNER TO postgres;
ALTER DATABASE sting_messaging OWNER TO postgres;

-- Ensure postgres has all permissions
GRANT ALL PRIVILEGES ON SCHEMA public TO postgres;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO postgres;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO postgres;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON FUNCTIONS TO postgres;

-- Create enum types
CREATE TYPE user_role AS ENUM ('user', 'admin', 'super_admin');
CREATE TYPE user_status AS ENUM ('active', 'inactive', 'pending', 'suspended');
CREATE TYPE report_status AS ENUM ('queued', 'processing', 'completed', 'failed', 'cancelled');
CREATE TYPE report_priority AS ENUM ('low', 'normal', 'high', 'urgent');
CREATE TYPE report_access_type AS ENUM ('user-owned', 'service-generated');
CREATE TYPE passkey_status AS ENUM ('ACTIVE', 'REVOKED', 'EXPIRED');

-- =============================================
-- CORE USER AND AUTHENTICATION TABLES
-- =============================================

-- Users table (main user records)
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    kratos_id VARCHAR(255) UNIQUE,
    email VARCHAR(255) UNIQUE NOT NULL,
    username VARCHAR(255) UNIQUE,
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    display_name VARCHAR(255),
    organization VARCHAR(255),
    role user_role DEFAULT 'user',
    status user_status DEFAULT 'active',
    is_admin BOOLEAN DEFAULT FALSE,
    is_super_admin BOOLEAN DEFAULT FALSE,
    requires_password_change BOOLEAN DEFAULT FALSE,
    is_first_user BOOLEAN DEFAULT FALSE,
    emergency_recovery_codes JSONB,
    recovery_email_verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_login_at TIMESTAMP WITHOUT TIME ZONE,
    password_changed_at TIMESTAMP WITHOUT TIME ZONE,
    user_metadata JSONB DEFAULT '{}'::jsonb
);

-- User Settings table (preferences and configuration)
-- ⚠️  CRITICAL: This includes the preference management columns added in August 2025
CREATE TABLE IF NOT EXISTS user_settings (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) UNIQUE NOT NULL,
    email VARCHAR(255),
    force_password_change BOOLEAN DEFAULT FALSE,
    password_changed_at TIMESTAMP WITHOUT TIME ZONE,
    role VARCHAR(50),
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    -- ✅ NEW PREFERENCE MANAGEMENT COLUMNS (Added August 2025)
    navigation_config JSONB DEFAULT '{}'::jsonb,
    navigation_version INTEGER DEFAULT 1,
    theme_preferences JSONB DEFAULT '{}'::jsonb,
    ui_preferences JSONB DEFAULT '{}'::jsonb
);

-- User Sessions table
CREATE TABLE IF NOT EXISTS user_sessions (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(255) UNIQUE NOT NULL,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    ip_address VARCHAR(45),
    user_agent TEXT,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_activity_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITHOUT TIME ZONE NOT NULL
);

-- System Settings table
CREATE TABLE IF NOT EXISTS system_settings (
    id SERIAL PRIMARY KEY,
    key VARCHAR(255) UNIQUE NOT NULL,
    value JSONB NOT NULL,
    description TEXT,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_by VARCHAR(255)
);

-- =============================================
-- PASSKEY AND BIOMETRIC AUTHENTICATION
-- =============================================

-- Passkeys table
CREATE TABLE IF NOT EXISTS passkeys (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    credential_id VARCHAR(255) UNIQUE NOT NULL,
    public_key TEXT NOT NULL,
    sign_count INTEGER DEFAULT 0,
    name VARCHAR(255),
    device_type VARCHAR(100),
    user_agent TEXT,
    ip_address VARCHAR(45),
    status passkey_status DEFAULT 'ACTIVE',
    is_backup_eligible BOOLEAN DEFAULT FALSE,
    is_backup_state BOOLEAN DEFAULT FALSE,
    usage_count INTEGER DEFAULT 0,
    last_used_at TIMESTAMP WITHOUT TIME ZONE,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    revoked_at TIMESTAMP WITHOUT TIME ZONE
);

-- Passkey Registration Challenges table
CREATE TABLE IF NOT EXISTS passkey_registration_challenges (
    id SERIAL PRIMARY KEY,
    challenge VARCHAR(255) UNIQUE NOT NULL,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    user_agent TEXT,
    ip_address VARCHAR(45),
    expires_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    used BOOLEAN DEFAULT FALSE,
    used_at TIMESTAMP WITHOUT TIME ZONE
);

-- Passkey Authentication Challenges table
CREATE TABLE IF NOT EXISTS passkey_authentication_challenges (
    id SERIAL PRIMARY KEY,
    challenge VARCHAR(255) UNIQUE NOT NULL,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    username VARCHAR(255),
    expires_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    used BOOLEAN DEFAULT FALSE,
    used_at TIMESTAMP WITHOUT TIME ZONE
);

-- Biometric Authentications table
CREATE TABLE IF NOT EXISTS biometric_authentications (
    id SERIAL PRIMARY KEY,
    identity_id VARCHAR(255) NOT NULL,
    credential_id VARCHAR(255),
    user_verified BOOLEAN DEFAULT FALSE,
    auth_time TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    session_id VARCHAR(255),
    user_agent TEXT,
    ip_address INET,
    authenticator_type VARCHAR(100),
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Credential Metadata table
CREATE TABLE IF NOT EXISTS credential_metadata (
    id SERIAL PRIMARY KEY,
    credential_id VARCHAR(255) UNIQUE NOT NULL,
    identity_id VARCHAR(255) NOT NULL,
    credential_name VARCHAR(255),
    is_biometric BOOLEAN DEFAULT FALSE,
    authenticator_type VARCHAR(100),
    last_used TIMESTAMP WITHOUT TIME ZONE,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- =============================================
-- API KEYS AND USAGE TRACKING
-- =============================================

-- API Keys table
CREATE TABLE IF NOT EXISTS api_keys (
    id VARCHAR(255) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    key_id VARCHAR(255) UNIQUE NOT NULL,
    key_hash VARCHAR(255) NOT NULL,
    user_id VARCHAR(255),
    user_email VARCHAR(255),
    permissions JSONB DEFAULT '[]'::jsonb,
    scopes JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITHOUT TIME ZONE,
    last_used_at TIMESTAMP WITHOUT TIME ZONE,
    is_active BOOLEAN DEFAULT TRUE,
    usage_count INTEGER DEFAULT 0,
    rate_limit_per_minute INTEGER DEFAULT 60,
    description TEXT,
    key_metadata JSONB DEFAULT '{}'::jsonb
);

-- API Key Usage table
CREATE TABLE IF NOT EXISTS api_key_usage (
    id VARCHAR(255) PRIMARY KEY,
    api_key_id VARCHAR(255) REFERENCES api_keys(id) ON DELETE CASCADE,
    key_id VARCHAR(255),
    endpoint VARCHAR(255),
    method VARCHAR(10),
    status_code INTEGER,
    response_time_ms INTEGER,
    user_agent TEXT,
    ip_address VARCHAR(45),
    request_size_bytes INTEGER,
    response_size_bytes INTEGER,
    timestamp TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    error_message TEXT
);

-- =============================================
-- HONEY JARS AND DOCUMENTS
-- =============================================

-- Honey Jars table
CREATE TABLE IF NOT EXISTS honey_jars (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    type VARCHAR(100),
    status VARCHAR(50) DEFAULT 'active',
    owner VARCHAR(255),
    created_date TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_updated TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    tags JSONB DEFAULT '[]'::jsonb,
    permissions JSONB DEFAULT '{}'::jsonb,
    document_count INTEGER DEFAULT 0,
    embedding_count INTEGER DEFAULT 0,
    total_size_bytes BIGINT DEFAULT 0,
    query_count INTEGER DEFAULT 0,
    average_query_time DOUBLE PRECISION DEFAULT 0.0
);

-- Documents table
CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    honey_jar_id UUID REFERENCES honey_jars(id) ON DELETE CASCADE,
    filename VARCHAR(255) NOT NULL,
    content_type VARCHAR(255),
    size_bytes INTEGER,
    upload_date TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(50) DEFAULT 'pending',
    doc_metadata JSONB DEFAULT '{}'::jsonb,
    tags JSONB DEFAULT '[]'::jsonb,
    embedding_count INTEGER DEFAULT 0,
    processing_time DOUBLE PRECISION,
    error_message TEXT,
    file_path VARCHAR(500)
);

-- =============================================
-- REPORTING SYSTEM
-- =============================================

-- Report Templates table
CREATE TABLE IF NOT EXISTS report_templates (
    id VARCHAR(255) PRIMARY KEY,
    name VARCHAR(255) UNIQUE NOT NULL,
    display_name VARCHAR(255),
    description TEXT,
    category VARCHAR(100),
    generator_class VARCHAR(255),
    parameters JSONB DEFAULT '{}'::jsonb,
    template_config JSONB DEFAULT '{}'::jsonb,
    output_formats JSONB DEFAULT '["pdf"]'::jsonb,
    estimated_time_minutes INTEGER DEFAULT 5,
    requires_scrambling BOOLEAN DEFAULT FALSE,
    scrambling_profile VARCHAR(100),
    security_level VARCHAR(50) DEFAULT 'standard',
    is_active BOOLEAN DEFAULT TRUE,
    is_premium BOOLEAN DEFAULT FALSE,
    required_role VARCHAR(50),
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(255)
);

-- Reports table
CREATE TABLE IF NOT EXISTS reports (
    id VARCHAR(255) PRIMARY KEY,
    template_id VARCHAR(255) REFERENCES report_templates(id),
    user_id VARCHAR(255),
    title VARCHAR(255),
    description TEXT,
    status report_status DEFAULT 'queued',
    priority report_priority DEFAULT 'normal',
    progress_percentage INTEGER DEFAULT 0,
    queue_position INTEGER,
    estimated_completion TIMESTAMP WITHOUT TIME ZONE,
    started_at TIMESTAMP WITHOUT TIME ZONE,
    completed_at TIMESTAMP WITHOUT TIME ZONE,
    parameters JSONB DEFAULT '{}'::jsonb,
    output_format VARCHAR(50) DEFAULT 'pdf',
    honey_jar_id VARCHAR(255),
    scrambling_enabled BOOLEAN DEFAULT FALSE,
    scrambling_mapping_id VARCHAR(255),
    pii_detected BOOLEAN DEFAULT FALSE,
    risk_level VARCHAR(50),
    generated_by VARCHAR(255),
    access_grants JSONB DEFAULT '[]'::jsonb,
    access_type report_access_type DEFAULT 'user-owned',
    result_file_id VARCHAR(255),
    result_summary JSONB DEFAULT '{}'::jsonb,
    result_size_bytes BIGINT,
    download_count INTEGER DEFAULT 0,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITHOUT TIME ZONE
);

-- Report Queue table
CREATE TABLE IF NOT EXISTS report_queue (
    id VARCHAR(255) PRIMARY KEY,
    report_id VARCHAR(255) UNIQUE REFERENCES reports(id) ON DELETE CASCADE,
    worker_id VARCHAR(255),
    queue_name VARCHAR(100) DEFAULT 'default',
    assigned_at TIMESTAMP WITHOUT TIME ZONE,
    heartbeat_at TIMESTAMP WITHOUT TIME ZONE,
    timeout_at TIMESTAMP WITHOUT TIME ZONE,
    attempt_number INTEGER DEFAULT 1,
    last_error TEXT,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- =============================================
-- NECTAR BOTS (AI ASSISTANTS)
-- =============================================

-- Nectar Bots table
CREATE TABLE IF NOT EXISTS nectar_bots (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    owner_id UUID,
    owner_email VARCHAR(255),
    honey_jar_ids JSONB DEFAULT '[]'::jsonb,
    system_prompt TEXT,
    max_conversation_length INTEGER DEFAULT 10,
    confidence_threshold DOUBLE PRECISION DEFAULT 0.7,
    api_key VARCHAR(255) UNIQUE,
    rate_limit_per_hour INTEGER DEFAULT 100,
    rate_limit_per_day INTEGER DEFAULT 1000,
    status VARCHAR(50) DEFAULT 'active',
    is_public BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_used_at TIMESTAMP WITH TIME ZONE,
    handoff_enabled BOOLEAN DEFAULT FALSE,
    handoff_keywords JSONB DEFAULT '[]'::jsonb,
    handoff_confidence_threshold DOUBLE PRECISION DEFAULT 0.5,
    total_conversations INTEGER DEFAULT 0,
    total_messages INTEGER DEFAULT 0,
    total_handoffs INTEGER DEFAULT 0,
    average_confidence DOUBLE PRECISION DEFAULT 0.0
);

-- Nectar Bot Usage table
CREATE TABLE IF NOT EXISTS nectar_bot_usage (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    bot_id UUID REFERENCES nectar_bots(id) ON DELETE CASCADE,
    conversation_id VARCHAR(255),
    message_id VARCHAR(255),
    user_id VARCHAR(255),
    user_ip VARCHAR(45),
    user_agent TEXT,
    user_message TEXT,
    bot_response TEXT,
    confidence_score DOUBLE PRECISION,
    response_time_ms INTEGER,
    honey_jars_queried JSONB DEFAULT '[]'::jsonb,
    knowledge_matches INTEGER DEFAULT 0,
    rate_limit_hit BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Nectar Bot Handoffs table
CREATE TABLE IF NOT EXISTS nectar_bot_handoffs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    bot_id UUID REFERENCES nectar_bots(id) ON DELETE CASCADE,
    conversation_id VARCHAR(255),
    user_id VARCHAR(255),
    user_info JSONB DEFAULT '{}'::jsonb,
    reason VARCHAR(255),
    urgency VARCHAR(50) DEFAULT 'normal',
    status VARCHAR(50) DEFAULT 'pending',
    conversation_history JSONB DEFAULT '[]'::jsonb,
    honey_jars_used JSONB DEFAULT '[]'::jsonb,
    trigger_message TEXT,
    bot_response TEXT,
    confidence_score DOUBLE PRECISION,
    assigned_to VARCHAR(255),
    resolved_at TIMESTAMP WITH TIME ZONE,
    resolution_notes TEXT,
    resolution_time_minutes INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- =============================================
-- MARKETPLACE
-- =============================================

-- Marketplace Listings table
CREATE TABLE IF NOT EXISTS marketplace_listings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    honey_jar_id UUID REFERENCES honey_jars(id) ON DELETE CASCADE,
    honey_jar_name VARCHAR(255),
    seller_id VARCHAR(255),
    seller_name VARCHAR(255),
    price DOUBLE PRECISION DEFAULT 0.0,
    license_type VARCHAR(100) DEFAULT 'standard',
    description TEXT,
    preview_enabled BOOLEAN DEFAULT FALSE,
    downloads INTEGER DEFAULT 0,
    rating DOUBLE PRECISION DEFAULT 0.0,
    reviews INTEGER DEFAULT 0,
    created_date TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    tags JSONB DEFAULT '[]'::jsonb,
    sample_documents JSONB DEFAULT '[]'::jsonb
);

-- =============================================
-- ORGANIZATION PREFERENCES
-- =============================================

-- Organization Preferences table
CREATE TABLE IF NOT EXISTS organization_preferences (
    id SERIAL PRIMARY KEY,
    preference_type VARCHAR(100) NOT NULL,
    config JSONB DEFAULT '{}'::jsonb,
    version INTEGER DEFAULT 1,
    created_by VARCHAR(255),
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

-- User Preference History table
CREATE TABLE IF NOT EXISTS user_preference_history (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    preference_type VARCHAR(100) NOT NULL,
    old_config JSONB,
    new_config JSONB,
    old_version INTEGER,
    new_version INTEGER,
    changed_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    changed_by VARCHAR(255),
    change_reason TEXT
);

-- =============================================
-- UTILITY FUNCTIONS AND TRIGGERS
-- =============================================

-- Create function to update timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers for updated_at on key tables
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_user_settings_updated_at BEFORE UPDATE ON user_settings FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_system_settings_updated_at BEFORE UPDATE ON system_settings FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_passkeys_updated_at BEFORE UPDATE ON passkeys FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_credential_metadata_updated_at BEFORE UPDATE ON credential_metadata FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_honey_jars_updated_at BEFORE UPDATE ON honey_jars FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_report_templates_updated_at BEFORE UPDATE ON report_templates FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_reports_updated_at BEFORE UPDATE ON reports FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_report_queue_updated_at BEFORE UPDATE ON report_queue FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_nectar_bots_updated_at BEFORE UPDATE ON nectar_bots FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_nectar_bot_handoffs_updated_at BEFORE UPDATE ON nectar_bot_handoffs FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_organization_preferences_updated_at BEFORE UPDATE ON organization_preferences FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =============================================
-- INDEXES FOR PERFORMANCE
-- =============================================

-- User indexes
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_kratos_id ON users(kratos_id);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
CREATE INDEX IF NOT EXISTS idx_users_status ON users(status);

-- User settings indexes (including preference columns)
CREATE INDEX IF NOT EXISTS idx_user_settings_user_id ON user_settings(user_id);
CREATE INDEX IF NOT EXISTS idx_user_settings_email ON user_settings(email);

-- Session indexes
CREATE INDEX IF NOT EXISTS idx_user_sessions_user_id ON user_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_user_sessions_session_id ON user_sessions(session_id);
CREATE INDEX IF NOT EXISTS idx_user_sessions_expires_at ON user_sessions(expires_at);

-- Passkey indexes
CREATE INDEX IF NOT EXISTS idx_passkeys_user_id ON passkeys(user_id);
CREATE INDEX IF NOT EXISTS idx_passkeys_credential_id ON passkeys(credential_id);
CREATE INDEX IF NOT EXISTS idx_passkeys_status ON passkeys(status);

-- API key indexes
CREATE INDEX IF NOT EXISTS idx_api_keys_key_id ON api_keys(key_id);
CREATE INDEX IF NOT EXISTS idx_api_keys_user_id ON api_keys(user_id);
CREATE INDEX IF NOT EXISTS idx_api_key_usage_api_key_id ON api_key_usage(api_key_id);
CREATE INDEX IF NOT EXISTS idx_api_key_usage_timestamp ON api_key_usage(timestamp);

-- Honey jar and document indexes
CREATE INDEX IF NOT EXISTS idx_honey_jars_owner ON honey_jars(owner);
CREATE INDEX IF NOT EXISTS idx_honey_jars_status ON honey_jars(status);
CREATE INDEX IF NOT EXISTS idx_documents_honey_jar_id ON documents(honey_jar_id);
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);

-- Report indexes
CREATE INDEX IF NOT EXISTS idx_reports_user_id ON reports(user_id);
CREATE INDEX IF NOT EXISTS idx_reports_status ON reports(status);
CREATE INDEX IF NOT EXISTS idx_reports_created_at ON reports(created_at);
CREATE INDEX IF NOT EXISTS idx_report_queue_status ON report_queue(assigned_at);

-- Nectar bot indexes
CREATE INDEX IF NOT EXISTS idx_nectar_bots_owner_id ON nectar_bots(owner_id);
CREATE INDEX IF NOT EXISTS idx_nectar_bots_api_key ON nectar_bots(api_key);
CREATE INDEX IF NOT EXISTS idx_nectar_bot_usage_bot_id ON nectar_bot_usage(bot_id);
CREATE INDEX IF NOT EXISTS idx_nectar_bot_handoffs_bot_id ON nectar_bot_handoffs(bot_id);

-- Grant permissions on all created objects to all relevant users
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO postgres;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO postgres;
GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO postgres;

-- Grant permissions to app_user on sting_app database tables
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO app_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO app_user;
GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO app_user;

-- =============================================
-- INSTALLATION VERIFICATION
-- =============================================

-- Log successful completion
\echo '✅ STING database schema initialization completed successfully!'
\echo '📊 Created all tables, indexes, and functions for fresh installation'
\echo '🔑 Preference management columns included in user_settings table'
\echo '🛡️  Full authentication system (users, passkeys, biometric auth)'
\echo '📈 Complete reporting and analytics infrastructure'
\echo '🤖 Nectar bot and AI assistant support'
\echo '🏪 Marketplace and honey jar management'
\echo ''
\echo 'Fresh installation database schema is ready!'