"""
Motor determinístico de geração de treinos (sem IA, sem acesso a banco).

Fluxo: divisão por dias -> metas semanais por músculo -> séries por dia -> escolha dos
exercícios entre os candidatos curados -> ajuste ao tempo -> volume semanal resultante.
"""

import math
import re
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field
from uuid import UUID

from src.workouts.generator import rules
from src.workouts.generator.rules import GOALS, LEVELS, MUSCLE_LABELS, TIER, Goal, Level
from src.workouts.generator.splits import Item, get_split
from src.workouts.generator.staples import SLOTS, Slot

LEVEL_LABELS = {"beginner": "iniciante", "intermediate": "intermediário", "expert": "avançado"}


@dataclass(frozen=True)
class ExerciseInfo:
    id: UUID
    source_id: str
    name: str
    muscle_group: str
    equipment: str | None
    level: str
    images: tuple[str, ...]
    primary_muscles: tuple[str, ...]
    secondary_muscles: tuple[str, ...]


@dataclass(frozen=True)
class GenerationInput:
    goal: Goal
    level: Level
    days_per_week: int
    session_minutes: int
    focus_muscles: tuple[str, ...] = ()
    avoid_muscles: tuple[str, ...] = ()
    split_style: str = "auto"


@dataclass
class PlannedExercise:
    info: ExerciseInfo
    muscle: str
    slot: str
    role: str
    sets: int
    reps_min: int
    reps_max: int
    rest_seconds: int
    keep_score: int


@dataclass
class PlannedDay:
    name: str
    exercises: list[PlannedExercise]
    minutes: int


@dataclass(frozen=True)
class WeeklyVolume:
    muscle: str
    achieved: int
    target: int


@dataclass
class GenerationResult:
    name: str
    description: str
    split_name: str
    days: list[PlannedDay]
    weekly: list[WeeklyVolume]
    rationale: list[str]
    warnings: list[str]
    reference_ids: list[str] = field(default_factory=list)


def _level_index(level: str) -> int:
    return LEVELS.index(level) if level in LEVELS else 0


def _estimate_minutes(exercises: list[PlannedExercise]) -> int:
    seconds = sum(
        rules.SETUP_SECONDS_PER_EXERCISE + e.sets * (rules.SECONDS_PER_SET + e.rest_seconds)
        for e in exercises
    )
    return rules.WARMUP_MINUTES + math.ceil(seconds / 60)


def _candidates(
    slot: Slot,
    level: Level,
    catalog: Mapping[str, ExerciseInfo],
    used: set[str],
) -> list[ExerciseInfo]:
    candidates: list[ExerciseInfo] = []
    for source_id in slot.ordered_for(level):
        info = catalog.get(source_id)
        if info is None or source_id in used:
            continue
        if _level_index(info.level) > _level_index(level):
            continue
        candidates.append(info)
    return candidates


def _pick(
    slot: Slot,
    occurrence: int,
    level: Level,
    catalog: Mapping[str, ExerciseInfo],
    used: set[str],
) -> ExerciseInfo | None:
    pool = _candidates(slot, level, catalog, used)
    if not pool:
        return None
    # Iniciantes repetem os mesmos movimentos (prática); os demais alternam variações.
    index = 0 if level == "beginner" else occurrence % len(pool)
    return pool[index]


def _split_sets(total: int, count: int) -> list[int]:
    base, extra = divmod(total, count)
    sizes = [base + (1 if i < extra else 0) for i in range(count)]
    return [min(rules.MAX_SETS_PER_EXERCISE, max(rules.MIN_SETS_PER_EXERCISE, s)) for s in sizes]


def _plan_muscle(
    item: Item,
    day_sets: int,
    occurrence: int,
    params: GenerationInput,
    catalog: Mapping[str, ExerciseInfo],
    used: set[str],
    focus: set[str],
) -> list[PlannedExercise]:
    goal = GOALS[params.goal]
    slots = [s for s in SLOTS[item.muscle] if item.slots is None or s.name in item.slots]
    wanted = 1 if day_sets <= 4 else 2 if day_sets <= 8 else 3

    chosen: list[tuple[int, Slot, ExerciseInfo]] = []
    for index, slot in enumerate(slots):
        if len(chosen) == wanted:
            break
        info = _pick(slot, occurrence, params.level, catalog, used)
        if info is None:
            continue
        used.add(info.source_id)
        chosen.append((index, slot, info))

    planned = []
    tier_score = 10 if TIER[item.muscle] == "minor" else 30
    sizes = _split_sets(day_sets, len(chosen)) if chosen else []
    for (index, slot, info), sets in zip(chosen, sizes):
        compound = slot.role == "compound"
        reps = goal.compound_reps[params.level] if compound else goal.isolation_reps
        planned.append(
            PlannedExercise(
                info=info,
                muscle=item.muscle,
                slot=slot.name,
                role=slot.role,
                sets=sets,
                reps_min=reps[0],
                reps_max=reps[1],
                rest_seconds=goal.rest_compound[params.level] if compound else goal.rest_isolation,
                keep_score=(50 if compound else 0)
                + tier_score
                + (15 if item.muscle in focus else 0)
                - index * 3,
            )
        )
    return planned


def _fit_time(days: list[PlannedDay], budget_minutes: int, targets: dict[str, int]) -> bool:
    """
    Ajusta cada dia ao tempo disponível. Corta sempre do músculo mais "sobrando" em relação
    à meta semanal (o que equaliza o déficit entre grupos e protege os mais defasados):
    primeiro reduz séries (até o mínimo), depois remove exercícios. Empates: isoladores e
    exercícios do fim do dia saem antes.
    """
    achieved: Counter[str] = Counter()
    for day in days:
        for exercise in day.exercises:
            achieved[exercise.muscle] += exercise.sets

    def victim(entries: list[tuple[PlannedDay, PlannedExercise]]):
        return min(
            entries,
            key=lambda entry: (
                -achieved[entry[1].muscle] / targets[entry[1].muscle],
                entry[1].keep_score,
                -entry[0].exercises.index(entry[1]),
            ),
        )

    trimmed = False
    while True:
        over = [day for day in days if _estimate_minutes(day.exercises) > budget_minutes]
        entries = [(day, e) for day in over for e in day.exercises]
        reducible = [(day, e) for day, e in entries if e.sets > rules.MIN_SETS_PER_EXERCISE]
        if reducible:
            _, exercise = victim(reducible)
            exercise.sets -= 1
            achieved[exercise.muscle] -= 1
        else:
            removable = [(day, e) for day, e in entries if len(day.exercises) > 1]
            if not removable:
                return trimmed
            day, exercise = victim(removable)
            day.exercises.remove(exercise)
            achieved[exercise.muscle] -= exercise.sets
        trimmed = True


def generate(params: GenerationInput, catalog: Mapping[str, ExerciseInfo]) -> GenerationResult:
    goal_rules = GOALS[params.goal]
    split = get_split(params.split_style, params.days_per_week)
    focus = set(params.focus_muscles)

    frequency: Counter[str] = Counter()
    for template in split.days:
        frequency.update({item.muscle for item in template.items})
    targets = {
        muscle: rules.weekly_target(muscle, params.goal, params.level, muscle in focus)
        for muscle in frequency
    }

    warnings: list[str] = []
    if params.avoid_muscles:
        warnings.append(
            "As queixas informadas não alteraram a seleção de exercícios. Este gerador "
            "usa regras gerais e ainda não realiza avaliação por IA. Revise o treino com "
            "um profissional antes de praticá-lo."
        )
    occurrence: Counter[str] = Counter()
    days: list[PlannedDay] = []

    for template in split.days:
        used: set[str] = set()
        planned: list[PlannedExercise] = []
        for item in template.items:
            muscle = item.muscle
            turn = occurrence[muscle]
            occurrence[muscle] += 1
            day_sets = max(
                rules.MIN_SETS_PER_EXERCISE, math.ceil(targets[muscle] / frequency[muscle])
            )
            planned += _plan_muscle(
                item, day_sets, turn, params, catalog, used, focus
            )
        # Exercícios agrupados por músculo, na ordem de prioridade do dia
        days.append(PlannedDay(template.name, planned, 0))

    if not any(day.exercises for day in days):
        return GenerationResult("", "", split.name, days, [], [], ["Sem exercícios."], [])

    any_trimmed = _fit_time(days, params.session_minutes, targets)
    for day in days:
        day.minutes = _estimate_minutes(day.exercises)

    achieved: Counter[str] = Counter()
    for day in days:
        for exercise in day.exercises:
            achieved[exercise.muscle] += exercise.sets
    weekly = [
        WeeklyVolume(muscle, achieved[muscle], targets[muscle])
        for muscle in targets
    ]

    if any_trimmed:
        warnings.append(
            f"Para caber em {params.session_minutes} min por sessão, reduzimos séries e "
            "exercícios menos prioritários. Com mais tempo ou dias, o treino fica mais completo."
        )
    short = [
        entry
        for entry in weekly
        if entry.achieved < rules.VOLUME_WARNING_RATIO * entry.target
    ]
    if short:
        details = ", ".join(
            f"{MUSCLE_LABELS[entry.muscle]} ({entry.achieved}/{entry.target})" for entry in short
        )
        warnings.append(f"Séries por semana abaixo da meta em: {details}.")

    rationale = _rationale(params, split.name, frequency, targets, focus)
    references = sorted(
        {ref for text in rationale for ref in re.findall(r"\[(R\d+)\]", text)},
        key=lambda r: int(r[1:]),
    )

    return GenerationResult(
        name=f"{goal_rules.label} · {params.days_per_week} dias ({split.name})",
        description=_description(params, split.name),
        split_name=split.name,
        days=days,
        weekly=weekly,
        rationale=rationale,
        warnings=warnings,
        reference_ids=references,
    )


def _description(params: GenerationInput, split_name: str) -> str:
    goal_rules = GOALS[params.goal]
    return (
        f"Treino gerado por regras baseadas em evidências (versão {rules.RULES_VERSION}). "
        f"Objetivo: {goal_rules.label.lower()}. Nível: {LEVEL_LABELS[params.level]}. "
        f"{params.days_per_week} dias por semana, divisão {split_name.lower()}.\n\n"
        f"Esforço: termine as séries com {goal_rules.effort_cue}.\n"
        f"{rules.PROGRESSION_NOTE}\n\n{rules.SAFETY_NOTE}"
    )


def _rationale(
    params: GenerationInput,
    split_name: str,
    frequency: Counter[str],
    targets: dict[str, int],
    focus: set[str],
) -> list[str]:
    goal_rules = GOALS[params.goal]
    lines = list(goal_rules.rationale)

    majors = [m for m in rules.MAJOR_MUSCLES if m in frequency]
    if majors and min(frequency[m] for m in majors) >= 2:
        lines.append(f"Divisão {split_name.lower()}: {rules.FREQUENCY_NOTE}")
    else:
        lines.append(f"Divisão {split_name.lower()}: {rules.FREQUENCY_ONE_NOTE}")
    lines.append(rules.SPLIT_CHOICE_NOTE)

    major = goal_rules.weekly_sets_major[params.level]
    minor = goal_rules.weekly_sets_minor[params.level]
    compound_low, compound_high = goal_rules.compound_reps[params.level]
    iso_low, iso_high = goal_rules.isolation_reps
    lines.append(
        f"Neste plano: compostos com {compound_low}-{compound_high} repetições e descanso de "
        f"{goal_rules.rest_compound[params.level]} s; isoladores com {iso_low}-{iso_high} "
        f"repetições e {goal_rules.rest_isolation} s."
    )
    lines.append(
        f"Metas semanais para o nível {LEVEL_LABELS[params.level]}: cerca de {major} séries "
        f"por grupo principal e {minor} por grupo menor (que também trabalham nos compostos)."
    )
    if params.level == "beginner":
        lines.append(
            "Como iniciante, priorizamos movimentos guiados e mais simples, repetidos entre "
            "os treinos para ganhar técnica, com volume menor [R3]."
        )
    else:
        lines.append(
            "Quando um músculo é treinado mais de uma vez na semana, usamos variações "
            "diferentes do exercício para variar o estímulo [R3]."
        )
    if focus:
        names = ", ".join(MUSCLE_LABELS[m] for m in sorted(focus) if m in MUSCLE_LABELS)
        if names:
            lines.append(f"Músculos em foco ({names}) receberam cerca de 25% mais séries.")
    lines.append(f"Esforço: termine as séries com {goal_rules.effort_cue}.")
    lines.append(rules.PROGRESSION_NOTE)
    lines.append(rules.WARMUP_NOTE)
    lines.append(rules.SAFETY_NOTE)
    return lines
