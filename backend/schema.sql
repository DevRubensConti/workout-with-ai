BEGIN;

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> 0001

CREATE TABLE users (
    id UUID NOT NULL, 
    name VARCHAR(120) NOT NULL, 
    email VARCHAR(255) NOT NULL, 
    password_hash VARCHAR(255) NOT NULL, 
    role VARCHAR(20) DEFAULT 'user' NOT NULL, 
    is_active BOOLEAN DEFAULT true NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id)
);

CREATE UNIQUE INDEX ix_users_email ON users (email);

CREATE TABLE password_reset_tokens (
    id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    token_hash VARCHAR(64) NOT NULL, 
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    used_at TIMESTAMP WITH TIME ZONE, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX ix_password_reset_tokens_token_hash ON password_reset_tokens (token_hash);

CREATE INDEX ix_password_reset_tokens_user_id ON password_reset_tokens (user_id);

INSERT INTO alembic_version (version_num) VALUES ('0001') RETURNING alembic_version.version_num;

-- Running upgrade 0001 -> 0002

ALTER TABLE users ENABLE ROW LEVEL SECURITY;

ALTER TABLE password_reset_tokens ENABLE ROW LEVEL SECURITY;

UPDATE alembic_version SET version_num='0002' WHERE alembic_version.version_num = '0001';

-- Running upgrade 0002 -> 0003

CREATE TABLE exercises (
    id UUID NOT NULL, 
    name VARCHAR(160) NOT NULL, 
    muscle_group VARCHAR(60) NOT NULL, 
    equipment VARCHAR(80), 
    description TEXT, 
    video_url VARCHAR(500), 
    owner_user_id UUID, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(owner_user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_exercises_owner_user_id_name ON exercises (owner_user_id, name);

CREATE TABLE workout_plans (
    id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    name VARCHAR(160) NOT NULL, 
    description TEXT, 
    goal VARCHAR(80), 
    level VARCHAR(40), 
    source VARCHAR(20) DEFAULT 'manual' NOT NULL, 
    ai_metadata JSON, 
    status VARCHAR(20) DEFAULT 'active' NOT NULL, 
    started_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    archived_at TIMESTAMP WITH TIME ZONE, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_workout_plans_status CHECK (status IN ('active', 'archived')), 
    CONSTRAINT ck_workout_plans_source CHECK (source IN ('manual', 'ai')), 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_workout_plans_user_id ON workout_plans (user_id);

CREATE UNIQUE INDEX uq_workout_plans_one_active_per_user ON workout_plans (user_id) WHERE status = 'active';

CREATE TABLE workout_days (
    id UUID NOT NULL, 
    plan_id UUID NOT NULL, 
    name VARCHAR(80) NOT NULL, 
    position INTEGER NOT NULL, 
    notes TEXT, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_workout_days_position CHECK (position >= 0), 
    FOREIGN KEY(plan_id) REFERENCES workout_plans (id) ON DELETE CASCADE, 
    CONSTRAINT uq_workout_days_plan_id_position UNIQUE (plan_id, position)
);

CREATE TABLE workout_day_exercises (
    id UUID NOT NULL, 
    day_id UUID NOT NULL, 
    exercise_id UUID NOT NULL, 
    position INTEGER NOT NULL, 
    sets INTEGER NOT NULL, 
    reps_min INTEGER NOT NULL, 
    reps_max INTEGER, 
    target_weight_kg NUMERIC(6, 2), 
    rest_seconds INTEGER, 
    tempo VARCHAR(20), 
    notes TEXT, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_workout_day_exercises_position CHECK (position >= 0), 
    CONSTRAINT ck_workout_day_exercises_sets CHECK (sets > 0), 
    CONSTRAINT ck_workout_day_exercises_reps_min CHECK (reps_min >= 0), 
    CONSTRAINT ck_workout_day_exercises_reps_max CHECK (reps_max IS NULL OR reps_max >= reps_min), 
    CONSTRAINT ck_workout_day_exercises_target_weight CHECK (target_weight_kg IS NULL OR target_weight_kg >= 0), 
    CONSTRAINT ck_workout_day_exercises_rest CHECK (rest_seconds IS NULL OR rest_seconds >= 0), 
    FOREIGN KEY(day_id) REFERENCES workout_days (id) ON DELETE CASCADE, 
    FOREIGN KEY(exercise_id) REFERENCES exercises (id) ON DELETE NO ACTION, 
    CONSTRAINT uq_workout_day_exercises_day_id_position UNIQUE (day_id, position)
);

CREATE INDEX ix_workout_day_exercises_exercise_id ON workout_day_exercises (exercise_id);

CREATE TABLE workout_sessions (
    id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    plan_id UUID, 
    day_id UUID, 
    plan_name VARCHAR(160), 
    day_name VARCHAR(80), 
    started_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    finished_at TIMESTAMP WITH TIME ZONE, 
    notes TEXT, 
    perceived_effort INTEGER, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_workout_sessions_perceived_effort CHECK (perceived_effort IS NULL OR perceived_effort BETWEEN 1 AND 10), 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
    FOREIGN KEY(plan_id) REFERENCES workout_plans (id) ON DELETE SET NULL, 
    FOREIGN KEY(day_id) REFERENCES workout_days (id) ON DELETE SET NULL
);

CREATE INDEX ix_workout_sessions_plan_id ON workout_sessions (plan_id);

CREATE INDEX ix_workout_sessions_day_id ON workout_sessions (day_id);

CREATE INDEX ix_workout_sessions_user_id_started_at ON workout_sessions (user_id, started_at DESC);

CREATE TABLE workout_set_logs (
    id UUID NOT NULL, 
    session_id UUID NOT NULL, 
    exercise_id UUID NOT NULL, 
    exercise_name VARCHAR(160) NOT NULL, 
    set_number INTEGER NOT NULL, 
    reps INTEGER NOT NULL, 
    weight_kg NUMERIC(6, 2), 
    completed BOOLEAN DEFAULT true NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_workout_set_logs_set_number CHECK (set_number > 0), 
    CONSTRAINT ck_workout_set_logs_reps CHECK (reps >= 0), 
    CONSTRAINT ck_workout_set_logs_weight CHECK (weight_kg IS NULL OR weight_kg >= 0), 
    FOREIGN KEY(session_id) REFERENCES workout_sessions (id) ON DELETE CASCADE, 
    FOREIGN KEY(exercise_id) REFERENCES exercises (id) ON DELETE NO ACTION
);

CREATE INDEX ix_workout_set_logs_session_id ON workout_set_logs (session_id);

CREATE INDEX ix_workout_set_logs_exercise_id ON workout_set_logs (exercise_id);

ALTER TABLE exercises ENABLE ROW LEVEL SECURITY;

ALTER TABLE workout_plans ENABLE ROW LEVEL SECURITY;

ALTER TABLE workout_days ENABLE ROW LEVEL SECURITY;

ALTER TABLE workout_day_exercises ENABLE ROW LEVEL SECURITY;

ALTER TABLE workout_sessions ENABLE ROW LEVEL SECURITY;

ALTER TABLE workout_set_logs ENABLE ROW LEVEL SECURITY;

UPDATE alembic_version SET version_num='0003' WHERE alembic_version.version_num = '0002';

-- Running upgrade 0003 -> 0004

CREATE TABLE user_profiles (
    id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    username VARCHAR(30) NOT NULL, 
    display_name VARCHAR(120) NOT NULL, 
    bio TEXT, 
    avatar_url VARCHAR(500), 
    is_private BOOLEAN DEFAULT true NOT NULL, 
    nearby_enabled BOOLEAN DEFAULT false NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT (CURRENT_TIMESTAMP) NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT (CURRENT_TIMESTAMP) NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_user_profiles_username CHECK (username = lower(username) AND length(trim(username)) BETWEEN 3 AND 30 AND username = trim(username)), 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
    UNIQUE (user_id), 
    UNIQUE (username)
);

CREATE TABLE user_blocks (
    id UUID NOT NULL, 
    blocker_id UUID NOT NULL, 
    blocked_id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT (CURRENT_TIMESTAMP) NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT (CURRENT_TIMESTAMP) NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_user_blocks_not_self CHECK (blocker_id <> blocked_id), 
    FOREIGN KEY(blocked_id) REFERENCES user_profiles (user_id) ON DELETE CASCADE, 
    FOREIGN KEY(blocker_id) REFERENCES user_profiles (user_id) ON DELETE CASCADE, 
    CONSTRAINT uq_user_blocks_pair UNIQUE (blocker_id, blocked_id)
);

CREATE INDEX ix_user_blocks_blocked_id ON user_blocks (blocked_id);

CREATE TABLE user_follows (
    id UUID NOT NULL, 
    follower_id UUID NOT NULL, 
    following_id UUID NOT NULL, 
    status VARCHAR(20) DEFAULT 'pending' NOT NULL, 
    accepted_at TIMESTAMP WITH TIME ZONE, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT (CURRENT_TIMESTAMP) NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT (CURRENT_TIMESTAMP) NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_user_follows_accepted_at CHECK ((status = 'pending' AND accepted_at IS NULL) OR (status = 'accepted' AND accepted_at IS NOT NULL)), 
    CONSTRAINT ck_user_follows_status CHECK (status IN ('pending', 'accepted')), 
    CONSTRAINT ck_user_follows_not_self CHECK (follower_id <> following_id), 
    FOREIGN KEY(follower_id) REFERENCES user_profiles (user_id) ON DELETE CASCADE, 
    FOREIGN KEY(following_id) REFERENCES user_profiles (user_id) ON DELETE CASCADE, 
    CONSTRAINT uq_user_follows_pair UNIQUE (follower_id, following_id)
);

CREATE INDEX ix_user_follows_following_id_status ON user_follows (following_id, status);

CREATE TABLE user_locations (
    id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    latitude NUMERIC(9, 6) NOT NULL, 
    longitude NUMERIC(9, 6) NOT NULL, 
    recorded_at TIMESTAMP WITH TIME ZONE DEFAULT (CURRENT_TIMESTAMP) NOT NULL, 
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT (CURRENT_TIMESTAMP) NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT (CURRENT_TIMESTAMP) NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_user_locations_approximate CHECK (abs(latitude * 100 - round(latitude * 100)) < 0.000001 AND abs(longitude * 100 - round(longitude * 100)) < 0.000001), 
    CONSTRAINT ck_user_locations_expiration CHECK (expires_at > recorded_at), 
    CONSTRAINT ck_user_locations_coordinates CHECK (latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180), 
    FOREIGN KEY(user_id) REFERENCES user_profiles (user_id) ON DELETE CASCADE, 
    UNIQUE (user_id)
);

CREATE INDEX ix_user_locations_expires_at ON user_locations (expires_at);

CREATE INDEX ix_user_locations_latitude_longitude ON user_locations (latitude, longitude);

ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;

ALTER TABLE user_blocks ENABLE ROW LEVEL SECURITY;

ALTER TABLE user_follows ENABLE ROW LEVEL SECURITY;

ALTER TABLE user_locations ENABLE ROW LEVEL SECURITY;

UPDATE alembic_version SET version_num='0004' WHERE alembic_version.version_num = '0003';

-- Running upgrade 0004 -> 0005

CREATE TABLE exercise_translations (
    id UUID NOT NULL, 
    exercise_id UUID NOT NULL, 
    locale VARCHAR(10) NOT NULL, 
    name VARCHAR(160) NOT NULL, 
    description TEXT, 
    instructions JSON NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT (CURRENT_TIMESTAMP) NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT (CURRENT_TIMESTAMP) NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_exercise_translations_locale CHECK (locale IN ('en', 'pt-BR')), 
    CONSTRAINT ck_exercise_translations_name CHECK (length(trim(name)) > 0), 
    FOREIGN KEY(exercise_id) REFERENCES exercises (id) ON DELETE CASCADE, 
    CONSTRAINT uq_exercise_translations_exercise_locale UNIQUE (exercise_id, locale)
);

CREATE INDEX ix_exercise_translations_locale_name ON exercise_translations (locale, name);

ALTER TABLE exercises ADD COLUMN source VARCHAR(80);

ALTER TABLE exercises ADD COLUMN source_id VARCHAR(160);

ALTER TABLE exercises ADD COLUMN force VARCHAR(40);

ALTER TABLE exercises ADD COLUMN level VARCHAR(40);

ALTER TABLE exercises ADD COLUMN mechanic VARCHAR(40);

ALTER TABLE exercises ADD COLUMN category VARCHAR(60);

ALTER TABLE exercises ADD COLUMN primary_muscles JSON;

ALTER TABLE exercises ADD COLUMN secondary_muscles JSON;

ALTER TABLE exercises ADD COLUMN images JSON;

ALTER TABLE exercises ADD CONSTRAINT uq_exercises_source_source_id UNIQUE (source, source_id);

ALTER TABLE exercises ADD CONSTRAINT ck_exercises_source_pair CHECK ((source IS NULL AND source_id IS NULL) OR (source IS NOT NULL AND source_id IS NOT NULL));

ALTER TABLE exercise_translations ENABLE ROW LEVEL SECURITY;

UPDATE alembic_version SET version_num='0005' WHERE alembic_version.version_num = '0004';

-- Running upgrade 0005 -> 0006

CREATE TABLE muscle_targets (
    id UUID NOT NULL,
    code VARCHAR(80) NOT NULL,
    name_pt VARCHAR(120) NOT NULL,
    kind VARCHAR(20) NOT NULL,
    parent_id UUID,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT (CURRENT_TIMESTAMP) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT (CURRENT_TIMESTAMP) NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT ck_muscle_targets_kind CHECK (kind IN ('group', 'muscle', 'region')),
    CONSTRAINT ck_muscle_targets_parent CHECK (parent_id IS NULL OR parent_id != id),
    FOREIGN KEY(parent_id) REFERENCES muscle_targets (id) ON DELETE RESTRICT,
    CONSTRAINT uq_muscle_targets_code UNIQUE (code)
);

CREATE INDEX ix_muscle_targets_parent_id ON muscle_targets (parent_id);

CREATE TABLE exercise_muscle_effects (
    id UUID NOT NULL,
    exercise_id UUID NOT NULL,
    muscle_target_id UUID NOT NULL,
    role VARCHAR(20) NOT NULL,
    relative_share_pct NUMERIC(5, 2) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT (CURRENT_TIMESTAMP) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT (CURRENT_TIMESTAMP) NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT ck_exercise_muscle_effects_role CHECK (role IN ('primary', 'auxiliary')),
    CONSTRAINT ck_exercise_muscle_effects_share_pct CHECK (relative_share_pct >= 0 AND relative_share_pct <= 100),
    FOREIGN KEY(exercise_id) REFERENCES exercises (id) ON DELETE CASCADE,
    FOREIGN KEY(muscle_target_id) REFERENCES muscle_targets (id) ON DELETE RESTRICT,
    CONSTRAINT uq_exercise_muscle_effects_target UNIQUE (exercise_id, muscle_target_id)
);

CREATE INDEX ix_exercise_muscle_effects_muscle_target_id ON exercise_muscle_effects (muscle_target_id);

ALTER TABLE muscle_targets ENABLE ROW LEVEL SECURITY;

ALTER TABLE exercise_muscle_effects ENABLE ROW LEVEL SECURITY;

UPDATE alembic_version SET version_num='0006' WHERE alembic_version.version_num = '0005';

-- Running upgrade 0006 -> 0007

ALTER TABLE muscle_targets DROP CONSTRAINT ck_muscle_targets_kind;

ALTER TABLE muscle_targets ADD CONSTRAINT ck_muscle_targets_kind
    CHECK (kind IN ('group', 'muscle_group', 'muscle', 'region'));

UPDATE alembic_version SET version_num='0007' WHERE alembic_version.version_num = '0006';

-- Running upgrade 0007 -> 0008

ALTER TABLE muscle_targets ADD COLUMN sort_order INTEGER DEFAULT '0' NOT NULL;

ALTER TABLE muscle_targets ADD CONSTRAINT ck_muscle_targets_sort_order CHECK (sort_order >= 0);

CREATE INDEX ix_muscle_targets_sort_order ON muscle_targets (sort_order, name_pt);

UPDATE alembic_version SET version_num='0008' WHERE version_num = '0007';

-- Running upgrade 0008 -> 0009

CREATE TABLE training_profiles (
    user_id UUID NOT NULL PRIMARY KEY REFERENCES users (id) ON DELETE CASCADE,
    age INTEGER NOT NULL,
    weight_kg NUMERIC(5, 2) NOT NULL,
    height_cm INTEGER NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT ck_training_profiles_age CHECK (age BETWEEN 18 AND 100),
    CONSTRAINT ck_training_profiles_weight CHECK (weight_kg BETWEEN 20 AND 400),
    CONSTRAINT ck_training_profiles_height CHECK (height_cm BETWEEN 100 AND 250)
);

ALTER TABLE training_profiles ENABLE ROW LEVEL SECURITY;

UPDATE alembic_version SET version_num='0009' WHERE version_num = '0008';

-- Running upgrade 0009 -> 0010
CREATE TABLE disabled_exercises (
    user_id UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    exercise_id UUID NOT NULL REFERENCES exercises (id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, exercise_id)
);
ALTER TABLE disabled_exercises ENABLE ROW LEVEL SECURITY;
UPDATE alembic_version SET version_num='0010' WHERE version_num = '0009';

-- Running upgrade 0010 -> 0011
ALTER TABLE users ADD COLUMN rest_timer_enabled BOOLEAN DEFAULT false NOT NULL;
UPDATE alembic_version SET version_num='0011' WHERE version_num = '0010';

COMMIT;
