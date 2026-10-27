CREATE TABLE users (
    id TEXT PRIMARY KEY,
    created_at DOUBLE PRECISION NOT NULL,
    profile JSONB NOT NULL CHECK (jsonb_typeof(profile) = 'object'),
    clerk_id TEXT NOT NULL UNIQUE
);

CREATE TABLE activities (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    kind TEXT NOT NULL,
    created_at DOUBLE PRECISION NOT NULL,
    updated_at DOUBLE PRECISION NOT NULL,
    state JSONB NOT NULL CHECK (jsonb_typeof(state) = 'object')
);

CREATE TABLE events (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    activity_id TEXT REFERENCES activities(id) ON DELETE CASCADE,
    category TEXT NOT NULL,
    kind TEXT NOT NULL,
    recorded_at DOUBLE PRECISION NOT NULL,
    payload JSONB NOT NULL CHECK (jsonb_typeof(payload) = 'object')
);

CREATE INDEX activities_user ON activities(user_id, updated_at);
CREATE INDEX events_user ON events(user_id, recorded_at);
CREATE INDEX events_activity ON events(activity_id, recorded_at);
