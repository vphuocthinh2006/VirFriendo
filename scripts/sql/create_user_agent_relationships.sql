-- Run once if the table was never created (e.g. DB predates the model).
-- psql $DATABASE_URL -f scripts/sql/create_user_agent_relationships.sql

CREATE TABLE IF NOT EXISTS user_agent_relationships (
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    agent_id VARCHAR(64) NOT NULL,
    user_message_count INTEGER NOT NULL DEFAULT 0,
    last_fun_fact_level_ack INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, agent_id)
);
