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

-- Running upgrade 0011 -> 0012
CREATE TABLE biomechanical_scale_versions (
    version INTEGER NOT NULL PRIMARY KEY,
    definition JSON NOT NULL,
    change_reason VARCHAR(1000) NOT NULL,
    created_by UUID REFERENCES users (id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    CONSTRAINT ck_biomechanical_scale_version CHECK (version > 0),
    CONSTRAINT ck_biomechanical_scale_reason CHECK (length(trim(change_reason)) > 0)
);

INSERT INTO biomechanical_scale_versions (version, definition, change_reason, created_by) VALUES (1, '{"title": "Escala de Demanda Biomecânica Regional", "disclaimer": "Classificação interna e ordinal da exigência mecânica estimada, não da probabilidade de lesão. Não é uma escala clínica validada. Nota alta não significa contraindicação e nota baixa não garante segurança. A classificação inicial requer revisão profissional.", "reference_conditions": "Avaliar a variação específica, equipamento, apoios e amplitude descritos no cadastro. Considerar técnica controlada conforme as instruções, sem pressupor carga máxima, fadiga extrema ou execução inadequada. A carga real, o volume, a recuperação e as condições individuais devem ser considerados separadamente.", "evaluation_criteria": "Justificar a nota considerando: movimento resistido; sustentação e transmissão de carga; exigência de estabilização; apoios e alavancas; amplitude e posição. Esses fatores orientam a avaliação, mas não devem ser somados automaticamente. Comparar variações semelhantes sob as mesmas condições de referência.", "consistency_rules": "Não copiar notas apenas pelo grupo muscular. Participação estabilizadora pode ter demanda alta. Não converter notas em percentuais de risco, nem somar regiões para produzir risco total. Notas 4 e 5 exigem justificativa biomecânica explícita; nota 5 exige revisão profissional. Sugestões da IA permanecem pendentes até revisão humana. Registrar a versão dos critérios, a origem e a justificativa de cada avaliação.", "unassessed_guidance": "Informação insuficiente significa não avaliado: nota NULL e motivo registrado. Não inventar notas, não assumir zero e não tratar ausência de avaliação como segurança. Nota zero só pode resultar de avaliação explícita.", "regions": [{"code": "shoulder", "label": "Ombros", "description": "Demanda mecânica na região dos ombros."}, {"code": "lumbar_spine", "label": "Coluna lombar", "description": "Demanda mecânica na região lombar, incluindo estabilização do tronco."}, {"code": "cervical_spine", "label": "Coluna cervical", "description": "Demanda mecânica na região cervical, incluindo sustentação e estabilização."}, {"code": "knee", "label": "Joelhos", "description": "Demanda mecânica na região dos joelhos."}, {"code": "elbow", "label": "Cotovelos", "description": "Demanda mecânica na região dos cotovelos."}], "roles": [{"code": "direct", "label": "Direta", "description": "Região envolvida no movimento resistido principal."}, {"code": "secondary", "label": "Secundária", "description": "Região que participa de movimentos associados."}, {"code": "stabilizing", "label": "Estabilizadora", "description": "Região que mantém posição e alinhamento; pode receber nota alta."}], "scores": [{"score": 0, "label": "Desprezível", "description": "Sem participação mecânica relevante na execução descrita. Exige avaliação explícita e nunca deve ser usada como valor padrão."}, {"score": 1, "label": "Baixa", "description": "Participação discreta, com pouca exigência de movimento ou estabilização regional."}, {"score": 2, "label": "Moderada", "description": "Participação perceptível no movimento ou na estabilização, sem ser uma das principais regiões mecanicamente exigidas."}, {"score": 3, "label": "Relevante", "description": "Sustenta ou transmite resistência de forma importante; sua demanda deve ser considerada na organização do treino."}, {"score": 4, "label": "Alta", "description": "Entre as principais regiões exigidas, por movimento resistido ou estabilização substancial. Exige justificativa biomecânica explícita."}, {"score": 5, "label": "Muito alta", "description": "Demanda especialmente acentuada na variação descrita, em comparação com alternativas semelhantes. Uso excepcional, com justificativa detalhada e revisão profissional."}]}', 'Formalização inicial; critérios sujeitos a revisão profissional.', NULL);

ALTER TABLE biomechanical_scale_versions ENABLE ROW LEVEL SECURITY;
UPDATE alembic_version SET version_num='0012' WHERE version_num = '0011';

-- Running upgrade 0012 -> 0013
CREATE TABLE exercise_biomechanical_assessments (
    id UUID NOT NULL PRIMARY KEY,
    exercise_id UUID NOT NULL REFERENCES exercises (id) ON DELETE RESTRICT,
    scale_version INTEGER NOT NULL REFERENCES biomechanical_scale_versions (version) ON DELETE RESTRICT,
    supersedes_id UUID,
    assessment_method VARCHAR(10) NOT NULL,
    assessment_source VARCHAR(500) NOT NULL,
    execution_context TEXT NOT NULL,
    created_by UUID REFERENCES users (id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    CONSTRAINT uq_biomechanical_assessment_exercise UNIQUE (id, exercise_id),
    CONSTRAINT fk_biomechanical_assessment_predecessor FOREIGN KEY (supersedes_id, exercise_id)
        REFERENCES exercise_biomechanical_assessments (id, exercise_id) ON DELETE RESTRICT,
    CONSTRAINT ck_biomechanical_assessment_predecessor CHECK (supersedes_id IS NULL OR supersedes_id != id),
    CONSTRAINT ck_biomechanical_assessment_method CHECK (assessment_method IN ('manual', 'ai', 'rule')),
    CONSTRAINT ck_biomechanical_assessment_source CHECK (length(trim(assessment_source)) > 0),
    CONSTRAINT ck_biomechanical_assessment_context CHECK (length(trim(execution_context)) > 0)
);

CREATE INDEX ix_biomechanical_assessment_exercise_created ON exercise_biomechanical_assessments (exercise_id, created_at);
CREATE INDEX ix_biomechanical_assessment_scale ON exercise_biomechanical_assessments (scale_version);

CREATE TABLE exercise_region_demands (
    assessment_id UUID NOT NULL REFERENCES exercise_biomechanical_assessments (id) ON DELETE CASCADE,
    region_code VARCHAR(30) NOT NULL,
    assessment_status VARCHAR(15) NOT NULL,
    demand_score INTEGER,
    demand_role VARCHAR(20),
    justification TEXT NOT NULL,
    PRIMARY KEY (assessment_id, region_code),
    CONSTRAINT ck_exercise_region_demand_region CHECK (region_code IN ('shoulder', 'lumbar_spine', 'cervical_spine', 'knee', 'elbow')),
    CONSTRAINT ck_exercise_region_demand_result CHECK (
        (assessment_status = 'assessed' AND demand_score IS NOT NULL AND demand_score BETWEEN 0 AND 5
         AND demand_role IS NOT NULL AND demand_role IN ('direct', 'secondary', 'stabilizing'))
        OR (assessment_status = 'unassessed' AND demand_score IS NULL AND demand_role IS NULL)
    ),
    CONSTRAINT ck_exercise_region_demand_reason CHECK (length(trim(justification)) > 0)
);

CREATE TABLE biomechanical_assessment_reviews (
    assessment_id UUID NOT NULL PRIMARY KEY REFERENCES exercise_biomechanical_assessments (id) ON DELETE RESTRICT,
    decision VARCHAR(15) NOT NULL,
    notes TEXT NOT NULL,
    reviewed_by UUID REFERENCES users (id) ON DELETE SET NULL,
    reviewed_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    CONSTRAINT ck_biomechanical_review_decision CHECK (decision IN ('reviewed', 'rejected')),
    CONSTRAINT ck_biomechanical_review_notes CHECK (length(trim(notes)) > 0)
);

ALTER TABLE exercise_biomechanical_assessments ENABLE ROW LEVEL SECURITY;
ALTER TABLE exercise_region_demands ENABLE ROW LEVEL SECURITY;
ALTER TABLE biomechanical_assessment_reviews ENABLE ROW LEVEL SECURITY;

CREATE FUNCTION check_biomechanical_assessment_regions() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE target_id uuid;
BEGIN
    IF TG_TABLE_NAME = 'exercise_biomechanical_assessments' THEN
        target_id := NEW.id;
    ELSIF TG_OP = 'DELETE' THEN
        target_id := OLD.assessment_id;
    ELSE
        target_id := NEW.assessment_id;
    END IF;
    IF EXISTS (SELECT 1 FROM exercise_biomechanical_assessments WHERE id = target_id)
       AND (SELECT count(*) FROM exercise_region_demands WHERE assessment_id = target_id) != 5 THEN
        RAISE EXCEPTION 'A biomechanical assessment must contain exactly five regions';
    END IF;
    IF TG_OP = 'UPDATE' AND TG_TABLE_NAME = 'exercise_region_demands' THEN
        IF OLD.assessment_id != NEW.assessment_id
           AND EXISTS (SELECT 1 FROM exercise_biomechanical_assessments WHERE id = OLD.assessment_id)
           AND (SELECT count(*) FROM exercise_region_demands WHERE assessment_id = OLD.assessment_id) != 5 THEN
            RAISE EXCEPTION 'The original assessment must retain five regions';
        END IF;
    END IF;
    RETURN NULL;
END $$;

CREATE CONSTRAINT TRIGGER exercise_biomechanical_assessments_complete
AFTER INSERT OR UPDATE ON exercise_biomechanical_assessments
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
EXECUTE FUNCTION check_biomechanical_assessment_regions();

CREATE CONSTRAINT TRIGGER exercise_region_demands_complete
AFTER INSERT OR UPDATE OR DELETE ON exercise_region_demands
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
EXECUTE FUNCTION check_biomechanical_assessment_regions();

CREATE FUNCTION guard_biomechanical_assessment() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF EXISTS (SELECT 1 FROM biomechanical_assessment_reviews WHERE assessment_id = OLD.id) THEN
        IF TG_OP = 'UPDATE' THEN
            IF NEW.created_by IS NULL AND OLD.created_by IS NOT NULL
               AND (to_jsonb(NEW) - 'created_by') = (to_jsonb(OLD) - 'created_by') THEN
                RETURN NEW;
            END IF;
        END IF;
        RAISE EXCEPTION 'Reviewed assessments are immutable; create a new assessment';
    END IF;
    IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER biomechanical_assessment_immutable
BEFORE UPDATE OR DELETE ON exercise_biomechanical_assessments
FOR EACH ROW EXECUTE FUNCTION guard_biomechanical_assessment();

CREATE FUNCTION guard_biomechanical_region() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE target_id uuid;
BEGIN
    IF TG_OP = 'DELETE' THEN target_id := OLD.assessment_id;
    ELSE target_id := NEW.assessment_id; END IF;
    IF TG_OP = 'UPDATE' AND NEW.assessment_id != OLD.assessment_id THEN
        RAISE EXCEPTION 'A region cannot be moved to another assessment';
    END IF;
    PERFORM id FROM exercise_biomechanical_assessments WHERE id = target_id FOR UPDATE;
    IF EXISTS (SELECT 1 FROM biomechanical_assessment_reviews WHERE assessment_id = target_id) THEN
        RAISE EXCEPTION 'Reviewed region results are immutable';
    END IF;
    IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
    RETURN NEW;
END $$;

CREATE TRIGGER biomechanical_region_immutable
BEFORE INSERT OR UPDATE OR DELETE ON exercise_region_demands
FOR EACH ROW EXECUTE FUNCTION guard_biomechanical_region();

CREATE FUNCTION guard_biomechanical_review() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        PERFORM id FROM exercise_biomechanical_assessments
        WHERE id = NEW.assessment_id FOR UPDATE;
        IF (SELECT count(*) FROM exercise_region_demands WHERE assessment_id = NEW.assessment_id) != 5 THEN
            RAISE EXCEPTION 'An assessment must contain five regions before review';
        END IF;
        RETURN NEW;
    END IF;
    IF TG_OP = 'UPDATE' THEN
        IF NEW.reviewed_by IS NULL AND OLD.reviewed_by IS NOT NULL
           AND (to_jsonb(NEW) - 'reviewed_by') = (to_jsonb(OLD) - 'reviewed_by') THEN
            RETURN NEW;
        END IF;
    END IF;
    RAISE EXCEPTION 'Review decisions are immutable';
END $$;

CREATE TRIGGER biomechanical_review_immutable
BEFORE INSERT OR UPDATE OR DELETE ON biomechanical_assessment_reviews
FOR EACH ROW EXECUTE FUNCTION guard_biomechanical_review();

UPDATE alembic_version SET version_num='0013' WHERE version_num = '0012';

-- Running upgrade 0013 -> 0014
ALTER TABLE exercise_region_demands DROP CONSTRAINT ck_exercise_region_demand_reason;
ALTER TABLE biomechanical_assessment_reviews DROP CONSTRAINT ck_biomechanical_review_notes;
UPDATE alembic_version SET version_num='0014' WHERE version_num = '0013';

COMMIT;
