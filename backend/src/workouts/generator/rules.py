"""
Base de regras de treinamento (conhecimento versionado e citado).

IMPORTANTE: os números abaixo são heurísticas práticas derivadas da literatura citada,
não prescrições individuais. As faixas de séries por semana, em particular, resumem
tendências de dose-resposta e foram escolhidas de forma conservadora. Antes de publicar
para além de amigos e familiares, esta base deve ser revisada por um profissional de
educação física (REVIEW_STATUS) e as referências conferidas nas fontes originais.

Mudou uma regra? Atualize RULES_VERSION: ele é gravado em cada treino gerado.
"""

from dataclasses import dataclass
from typing import Literal

RULES_VERSION = "2026.11-sem-filtro-queixas"
REVIEW_STATUS = "pendente_revisao_profissional"

Goal = Literal["hypertrophy", "strength", "fat_loss", "general_health"]
Level = Literal["beginner", "intermediate", "expert"]
LEVELS: tuple[Level, ...] = ("beginner", "intermediate", "expert")

REFERENCES: dict[str, str] = {
    "R1": (
        "Schoenfeld BJ, Ogborn D, Krieger JW. Dose-response relationship between weekly "
        "resistance training volume and increases in muscle mass: a systematic review and "
        "meta-analysis. J Sports Sci. 2017;35(11):1073-1082."
    ),
    "R2": (
        "Schoenfeld BJ, Ogborn D, Krieger JW. Effects of resistance training frequency on "
        "measures of muscle hypertrophy: a systematic review and meta-analysis. "
        "Sports Med. 2016;46(11):1689-1697."
    ),
    "R3": (
        "American College of Sports Medicine. Progression models in resistance training "
        "for healthy adults. Med Sci Sports Exerc. 2009;41(3):687-708."
    ),
    "R4": (
        "Schoenfeld BJ, Grgic J, Ogborn D, Krieger JW. Strength and hypertrophy adaptations "
        "between low- vs. high-load resistance training: a systematic review and "
        "meta-analysis. J Strength Cond Res. 2017;31(12):3508-3523."
    ),
    "R5": (
        "Schoenfeld BJ, Pope ZK, Benik FM, et al. Longer interset rest periods enhance "
        "muscle strength and hypertrophy in resistance-trained men. "
        "J Strength Cond Res. 2016;30(7):1805-1812."
    ),
    "R6": (
        "Bull FC, Al-Ansari SS, Biddle S, et al. World Health Organization 2020 guidelines "
        "on physical activity and sedentary behaviour. Br J Sports Med. 2020;54(24):1451-1462."
    ),
    "R7": (
        "Currier BS, McLeod JC, Banfield L, et al. Resistance training prescription for "
        "muscle strength and hypertrophy in healthy adults: a systematic review and "
        "Bayesian network meta-analysis. Br J Sports Med. 2023;57(18):1211-1220."
    ),
    "R8": (
        "Refalo MC, Helms ER, Trexler ET, Hamilton DL, Fyfe JJ. Influence of resistance "
        "training proximity-to-failure on skeletal muscle hypertrophy: a systematic review "
        "with meta-analysis. Sports Med. 2023;53(3):649-665."
    ),
    "R9": (
        "Schoenfeld BJ, Grgic J, Krieger J. How many times per week should a muscle be "
        "trained to maximize muscle hypertrophy? A systematic review and meta-analysis of "
        "studies examining the effects of resistance training frequency. "
        "J Sports Sci. 2019;37(11):1286-1295."
    ),
}

MUSCLE_LABELS: dict[str, str] = {
    "chest": "Peito",
    "lats": "Dorsais",
    "middle back": "Meio das costas",
    "shoulders": "Ombros",
    "quadriceps": "Quadríceps",
    "hamstrings": "Posteriores de coxa",
    "glutes": "Glúteos",
    "biceps": "Bíceps",
    "triceps": "Tríceps",
    "calves": "Panturrilhas",
    "abdominals": "Abdômen",
}

# Grupos treinados pelo gerador. "back" divide a meta entre dorsais e meio das costas.
TIER: dict[str, Literal["major", "back", "minor"]] = {
    "chest": "major",
    "shoulders": "major",
    "quadriceps": "major",
    "hamstrings": "major",
    "lats": "back",
    "middle back": "back",
    "glutes": "minor",
    "biceps": "minor",
    "triceps": "minor",
    "calves": "minor",
    "abdominals": "minor",
}

MAJOR_MUSCLES = tuple(m for m, tier in TIER.items() if tier in ("major", "back"))


@dataclass(frozen=True)
class GoalRules:
    label: str
    compound_reps: dict[Level, tuple[int, int]]
    isolation_reps: tuple[int, int]
    rest_compound: dict[Level, int]
    rest_isolation: int
    # Séries "duras" diretas por músculo por semana. Os músculos menores recebem
    # parte do estímulo nos exercícios compostos, por isso a meta direta é menor.
    weekly_sets_major: dict[Level, int]
    weekly_sets_minor: dict[Level, int]
    effort_cue: str
    rationale: tuple[str, ...]
    references: tuple[str, ...]


GOALS: dict[Goal, GoalRules] = {
    "hypertrophy": GoalRules(
        label="Hipertrofia",
        compound_reps={"beginner": (8, 12), "intermediate": (6, 10), "expert": (6, 10)},
        isolation_reps=(10, 15),
        rest_compound={"beginner": 120, "intermediate": 150, "expert": 150},
        rest_isolation=75,
        weekly_sets_major={"beginner": 8, "intermediate": 12, "expert": 16},
        weekly_sets_minor={"beginner": 4, "intermediate": 6, "expert": 8},
        effort_cue=(
            "1 a 3 repetições em reserva (perto da falha, sem chegar nela em todas as séries)"
        ),
        rationale=(
            "Para hipertrofia, o volume semanal de séries por músculo é o principal "
            "determinante dos ganhos: a meta cresce com o seu nível, indo de cerca de "
            "8 a 16 séries por grupo principal [R1][R7].",
            "A hipertrofia ocorre numa faixa ampla de cargas, desde que as séries sejam "
            "levadas perto da falha; por isso usamos faixas moderadas de repetições, mais "
            "baixas nos compostos e mais altas nos isoladores [R4][R8].",
            "Descansos mais longos (2 a 2,5 min) nos compostos favorecem mais volume "
            "efetivo e melhores resultados [R5].",
        ),
        references=("R1", "R4", "R5", "R7", "R8"),
    ),
    "strength": GoalRules(
        label="Força",
        compound_reps={"beginner": (6, 10), "intermediate": (4, 8), "expert": (3, 6)},
        isolation_reps=(8, 12),
        rest_compound={"beginner": 120, "intermediate": 180, "expert": 240},
        rest_isolation=90,
        weekly_sets_major={"beginner": 6, "intermediate": 9, "expert": 12},
        weekly_sets_minor={"beginner": 3, "intermediate": 4, "expert": 6},
        effort_cue="1 a 3 repetições em reserva, com técnica sempre limpa",
        rationale=(
            "Para força, cargas mais altas e menos repetições nos compostos aumentam a "
            "especificidade; as faixas diminuem conforme o nível, de 6-10 a 3-6 [R3][R4].",
            "Descansos longos (2 a 4 min) nos compostos preservam a qualidade das séries "
            "pesadas [R3][R5].",
        ),
        references=("R3", "R4", "R5", "R7"),
    ),
    "fat_loss": GoalRules(
        label="Emagrecimento",
        compound_reps={"beginner": (8, 12), "intermediate": (8, 12), "expert": (8, 12)},
        isolation_reps=(12, 15),
        rest_compound={"beginner": 90, "intermediate": 90, "expert": 90},
        rest_isolation=60,
        weekly_sets_major={"beginner": 8, "intermediate": 10, "expert": 12},
        weekly_sets_minor={"beginner": 4, "intermediate": 5, "expert": 6},
        effort_cue="1 a 3 repetições em reserva",
        rationale=(
            "Manter o treino de força durante a perda de peso ajuda a preservar a massa "
            "magra. Usamos volume moderado, repetições médias e descansos mais curtos, "
            "para um treino eficiente em tempo [R3][R7].",
            "A perda de gordura depende principalmente de alimentação e do gasto "
            "energético total; este app prescreve apenas o treino de força.",
        ),
        references=("R1", "R3", "R7"),
    ),
    "general_health": GoalRules(
        label="Saúde e bem-estar",
        compound_reps={"beginner": (8, 12), "intermediate": (8, 12), "expert": (8, 12)},
        isolation_reps=(10, 15),
        rest_compound={"beginner": 90, "intermediate": 90, "expert": 90},
        rest_isolation=60,
        weekly_sets_major={"beginner": 6, "intermediate": 8, "expert": 10},
        weekly_sets_minor={"beginner": 3, "intermediate": 4, "expert": 4},
        effort_cue="2 a 4 repetições em reserva",
        rationale=(
            "A OMS recomenda fortalecimento muscular dos principais grupos em pelo menos "
            "2 dias por semana; o treino cobre o corpo todo com volume moderado e "
            "esforço confortável [R6][R3].",
        ),
        references=("R3", "R6"),
    ),
}

# Fatores de método (gerais, valem para todos os objetivos)
FREQUENCY_NOTE = (
    "cada grupo muscular principal é treinado pelo menos 2 vezes por semana, o que "
    "tende a distribuir melhor o volume e favorecer a hipertrofia [R2]."
)
FREQUENCY_ONE_NOTE = (
    "nesta divisão cada grupo muscular principal é treinado cerca de 1 vez por semana, e as "
    "séries ficam concentradas em uma sessão. Com o mesmo volume semanal, as revisões "
    "indicam resultados parecidos em hipertrofia, embora 2 ou mais vezes por semana tenham "
    "se saído melhor quando o volume não é controlado [R2][R9]."
)
SPLIT_CHOICE_NOTE = (
    "Não há evidência de que um estilo de divisão supere os outros quando o volume semanal é "
    "o mesmo: a composição dos dias é uma convenção de treino, e a escolha serve à sua rotina "
    "e preferência [R9]."
)
PROGRESSION_NOTE = (
    "Progressão: quando completar todas as séries no topo da faixa de repetições, aumente "
    "a carga em cerca de 2% a 10% no treino seguinte (dupla progressão) [R3]."
)
SAFETY_NOTE = (
    "Este treino é uma sugestão geral para adultos saudáveis e não substitui avaliação "
    "médica ou de um profissional de educação física. Dor aguda ou fora do normal é "
    "sinal para parar e buscar orientação."
)
WARMUP_NOTE = (
    "Aquecimento: 5 a 8 minutos leves e 1 a 2 séries de aproximação no primeiro exercício."
)

# Estimativas de tempo (premissas, não literatura)
WARMUP_MINUTES = 8
SECONDS_PER_SET = 40
SETUP_SECONDS_PER_EXERCISE = 60

MIN_SETS_PER_EXERCISE = 2
MAX_SETS_PER_EXERCISE = 5
FOCUS_EXTRA_FRACTION = 0.25
VOLUME_WARNING_RATIO = 0.75


def weekly_target(muscle: str, goal: Goal, level: Level, focus: bool = False) -> int:
    rules = GOALS[goal]
    tier = TIER[muscle]
    major = rules.weekly_sets_major[level]
    if tier == "major":
        target = major
    elif tier == "back":
        target = max(3, round(major / 2))
    else:
        target = rules.weekly_sets_minor[level]
    if focus:
        target += max(2, round(target * FOCUS_EXTRA_FRACTION))
    return min(target, 20)
