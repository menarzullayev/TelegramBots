-- TezMath Initial Schema

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Users
CREATE TABLE IF NOT EXISTS users (
    id               BIGSERIAL PRIMARY KEY,
    telegram_id      BIGINT UNIQUE NOT NULL,
    username         VARCHAR(64),
    full_name        VARCHAR(256) NOT NULL,
    language         CHAR(2) NOT NULL DEFAULT 'uz',
    is_premium       BOOLEAN NOT NULL DEFAULT FALSE,
    is_banned        BOOLEAN NOT NULL DEFAULT FALSE,
    subscription_end TIMESTAMPTZ,
    referral_code    VARCHAR(16) UNIQUE DEFAULT substr(md5(random()::text), 1, 8),
    referred_by      BIGINT REFERENCES users(id) ON DELETE SET NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_users_telegram_id   ON users(telegram_id);
CREATE INDEX idx_users_is_premium    ON users(is_premium);
CREATE INDEX idx_users_referral_code ON users(referral_code);
CREATE INDEX idx_users_full_name_trgm ON users USING GIN (full_name gin_trgm_ops);

-- Solutions
CREATE TABLE IF NOT EXISTS solutions (
    id            BIGSERIAL PRIMARY KEY,
    user_id       BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    input_type    VARCHAR(16) NOT NULL CHECK (input_type IN ('text', 'photo')),
    input_text    TEXT NOT NULL DEFAULT '',
    solution_text TEXT NOT NULL,
    model_used    VARCHAR(64) NOT NULL DEFAULT '',
    tokens_used   INT NOT NULL DEFAULT 0,
    rating        SMALLINT CHECK (rating BETWEEN 1 AND 5),
    render_url    TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_solutions_user_id    ON solutions(user_id);
CREATE INDEX idx_solutions_created_at ON solutions(created_at DESC);

-- Daily usage tracking (for rate limiting)
CREATE TABLE IF NOT EXISTS daily_usage (
    id          BIGSERIAL PRIMARY KEY,
    user_id     BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    usage_date  DATE NOT NULL DEFAULT CURRENT_DATE,
    count       INT NOT NULL DEFAULT 0,
    UNIQUE (user_id, usage_date)
);

CREATE INDEX idx_daily_usage_user_date ON daily_usage(user_id, usage_date);

-- Transactions
CREATE TABLE IF NOT EXISTS transactions (
    id          TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    user_id     BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    amount      INT NOT NULL,
    method      VARCHAR(32) NOT NULL CHECK (method IN ('payme', 'click', 'stars')),
    status      VARCHAR(32) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'cancelled')),
    period      VARCHAR(16) NOT NULL DEFAULT 'monthly',
    payme_id    TEXT,
    cancel_time TIMESTAMPTZ,
    perform_time TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_transactions_user_id    ON transactions(user_id);
CREATE INDEX idx_transactions_status     ON transactions(status);
CREATE INDEX idx_transactions_created_at ON transactions(created_at DESC);

-- Subscriptions audit log
CREATE TABLE IF NOT EXISTS subscription_log (
    id         BIGSERIAL PRIMARY KEY,
    user_id    BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    action     VARCHAR(32) NOT NULL,
    details    JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
