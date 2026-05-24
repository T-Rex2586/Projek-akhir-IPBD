-- =============================================================================
-- 01_create_crypto_db.sql
-- Dijalankan otomatis oleh PostgreSQL container saat pertama kali start.
-- Superuser utama adalah 'airflow' (didefinisikan di docker-compose.yml).
-- Script ini membuat:
--   1. Database 'crypto_pipeline' untuk pipeline data
--   2. Role 'postgres' dengan password 'postgres' agar kompatibel dengan .env
-- =============================================================================

-- 1. Buat database crypto_pipeline (milik superuser 'airflow')
CREATE DATABASE crypto_pipeline;

-- 2. Buat role 'postgres' jika belum ada
--    Password = 'postgres'  ← harus sama dengan DB_PASSWORD di .env
--                           ← harus sama dengan database.password di debezium connector
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'postgres') THEN
        CREATE ROLE postgres WITH
            LOGIN
            PASSWORD 'postgres'
            SUPERUSER
            CREATEDB
            CREATEROLE;
    ELSE
        -- Pastikan password & privilege tetap benar jika role sudah ada
        ALTER ROLE postgres WITH
            LOGIN
            PASSWORD 'postgres'
            SUPERUSER;
    END IF;
END
$$;

-- 3. Grant hak akses ke crypto_pipeline
GRANT ALL PRIVILEGES ON DATABASE crypto_pipeline TO postgres;

-- 4. Atur ownership agar role 'postgres' bisa membuat tabel & sequence
\c crypto_pipeline
GRANT ALL ON SCHEMA public TO postgres;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO postgres;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO postgres;
