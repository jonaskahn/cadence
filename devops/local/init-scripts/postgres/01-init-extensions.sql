-- PostgreSQL initialization script for Cadence
-- This script runs automatically when the database is first created

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";      -- UUID generation
CREATE EXTENSION IF NOT EXISTS "pgcrypto";       -- Encryption functions
CREATE EXTENSION IF NOT EXISTS "hstore";          -- Key-value storage

-- Create additional databases for testing if needed
-- CREATE DATABASE cadence_test OWNER cadence;

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE cadence_dev TO cadence;

-- Create schema for Cadence tables (optional, can use public)
-- CREATE SCHEMA IF NOT EXISTS cadence;
-- GRANT ALL ON SCHEMA cadence TO cadence;

-- Log initialization
SELECT 'Cadence PostgreSQL database initialized successfully' AS status;
