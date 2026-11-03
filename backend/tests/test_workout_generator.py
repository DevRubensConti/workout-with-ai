import itertools
import uuid

import pytest

from src.workouts.generator import rules
from src.workouts.generator.engine import ExerciseInfo, GenerationInput, generate
from src.workouts.generator.rules import GOALS, LEVELS, TIER
from src.workouts.generator.splits import (
    AUTO_STYLE,
    DAYS,
    SPLITS,
    InvalidSplitError,
    get_split,
    styles_for,
)
from src.workouts.generator.staples import SLOTS, all_source_ids

INTERMEDIATE = {
    "Romanian_Deadlift",
    "Stiff-Legged_Barbell_Deadlift",
    "Barbell_Hip_Thrust",
    "Dumbbell_Shoulder_Press",
    "Barbell_Shoulder_Press",
    "Flat_Bench_Cable_Flyes",
    "Face_Pull",
    "One-Legged_Cable_Kickback",
    "Lying_Triceps_Press",
}
EXPERT = {"Hanging_Leg_Raise"}


def build_catalog() -> dict[str, ExerciseInfo]:
    muscle_of = {
        source_id: muscle
        for muscle, slots in SLOTS.items()
        for slot in slots
        for source_id in (*slot.candidates, *(slot.beginner_candidates or ()))
    }
    catalog = {}
    for source_id in all_source_ids():
        level = (
            "expert"
            if source_id in EXPERT
            else "intermediate"
            if source_id in INTERMEDIATE
            else "beginner"
        )
        muscle = muscle_of[source_id]
        catalog[source_id] = ExerciseInfo(
            id=uuid.uuid4(),
            source_id=source_id,
            name=source_id.replace("_", " "),
            muscle_group=muscle,
            equipment="barbell",
            level=level,
            images=(f"{source_id}/0.jpg",),
        )
    return catalog


@pytest.fixture(scope="module")
def catalog():
    return build_catalog()


def params(**overrides):
    base = dict(goal="hypertrophy", level="intermediate", days_per_week=4, session_minutes=90)
    return GenerationInput(**{**base, **overrides})


def test_knowledge_base_is_consistent():
    for split in SPLITS.values():
        for day in split.days:
            for item in day.items:
                assert item.muscle in SLOTS and item.muscle in TIER
                names = {slot.name for slot in SLOTS[item.muscle]}
                assert set(item.slots or ()) <= names
    assert DAYS == (2, 3, 4, 5, 6)
    for days, style in AUTO_STYLE.items():
        assert (style, days) in SPLITS
    for days in DAYS:
        assert get_split("auto", days).days
        assert styles_for(days)
    for goal in GOALS.values():
        for level in LEVELS:
            low, high = goal.compound_reps[level]
            assert 0 < low <= high
            assert goal.rest_compound[level] > goal.rest_isolation > 0
    for goal in GOALS.values():
        assert set(goal.references) <= set(rules.REFERENCES)
    for slots in SLOTS.values():
        for slot in slots:
            assert len(set(slot.candidates)) == len(slot.candidates)


@pytest.mark.parametrize(
    ("goal", "level", "days", "minutes"),
    list(itertools.product(GOALS, LEVELS, range(2, 7), (45, 90))),
)
def test_every_combination_produces_a_valid_plan(catalog, goal, level, days, minutes):
    result = generate(
        GenerationInput(goal, level, days, minutes), catalog
    )
    rule = GOALS[goal]

    assert len(result.days) == days
    for day in result.days:
        assert day.exercises
        source_ids = [e.info.source_id for e in day.exercises]
        assert len(source_ids) == len(set(source_ids))
        assert day.minutes <= minutes or len(day.exercises) == 1
        for e in day.exercises:
            assert rules.MIN_SETS_PER_EXERCISE <= e.sets <= rules.MAX_SETS_PER_EXERCISE
            expected = rule.compound_reps[level] if e.role == "compound" else rule.isolation_reps
            assert (e.reps_min, e.reps_max) == expected
            assert e.rest_seconds > 0
        # exercícios do mesmo músculo ficam juntos (sem voltar a um músculo já treinado)
        muscles = [e.muscle for e in day.exercises]
        blocks = [m for i, m in enumerate(muscles) if i == 0 or m != muscles[i - 1]]
        assert len(blocks) == len(set(blocks))
    total = {w.muscle: w.achieved for w in result.weekly}
    for day in result.days:
        for e in day.exercises:
            total[e.muscle] -= e.sets
    assert all(value == 0 for value in total.values())
    assert result.rationale and result.reference_ids
    assert set(result.reference_ids) <= set(rules.REFERENCES)


def test_with_enough_time_every_weekly_target_is_met(catalog):
    result = generate(params(days_per_week=5, session_minutes=120), catalog)

    assert all(entry.achieved >= entry.target for entry in result.weekly)
    assert not result.warnings


def test_tight_time_trims_equally_and_warns(catalog):
    relaxed = generate(params(session_minutes=120), catalog)
    tight = generate(params(session_minutes=45), catalog)

    assert sum(e.sets for d in tight.days for e in d.exercises) < sum(
        e.sets for d in relaxed.days for e in d.exercises
    )
    assert any("Para caber em 45 min" in warning for warning in tight.warnings)
    assert all(day.minutes <= 45 for day in tight.days)


def test_major_muscles_are_trained_at_least_twice_a_week(catalog):
    for days in range(3, 7):
        result = generate(params(days_per_week=days, session_minutes=120), catalog)
        for muscle in rules.MAJOR_MUSCLES:
            frequency = sum(
                any(e.muscle == muscle for e in day.exercises) for day in result.days
            )
            assert frequency >= 2, (days, muscle)


def test_beginner_only_gets_beginner_exercises_and_repeats_movements(catalog):
    result = generate(params(level="beginner", days_per_week=3), catalog)

    for day in result.days:
        assert all(e.info.level == "beginner" for e in day.exercises)
    chest_days = [
        {e.info.source_id for e in day.exercises if e.muscle == "chest" and e.slot == "press"}
        for day in result.days
    ]
    chest_days = [ids for ids in chest_days if ids]
    assert len(chest_days) >= 2 and all(ids == chest_days[0] for ids in chest_days)


def test_intermediate_rotates_variations_for_repeated_muscles(catalog):
    result = generate(params(level="intermediate", days_per_week=4), catalog)
    press = [
        next(e.info.source_id for e in day.exercises if e.muscle == "chest" and e.slot == "press")
        for day in result.days
        if any(e.muscle == "chest" and e.slot == "press" for e in day.exercises)
    ]

    assert len(press) == 2 and press[0] != press[1]


@pytest.mark.parametrize("level", LEVELS)
@pytest.mark.parametrize(
    "complaints",
    [("shoulders",), ("lower back",), tuple(TIER)],
)
def test_complaints_do_not_filter_or_deprioritise_exercises(catalog, level, complaints):
    baseline = generate(params(level=level), catalog)
    result = generate(params(level=level, avoid_muscles=complaints), catalog)

    assert result.days == baseline.days
    assert result.weekly == baseline.weekly
    assert result.rationale == baseline.rationale
    assert any("não alteraram" in warning for warning in result.warnings)


def test_focus_muscle_gets_more_weekly_sets(catalog):
    base = generate(params(days_per_week=5, session_minutes=120), catalog)
    focused = generate(
        params(days_per_week=5, session_minutes=120, focus_muscles=("biceps",)), catalog
    )

    def sets(result, muscle):
        return next(w.achieved for w in result.weekly if w.muscle == muscle)

    assert sets(focused, "biceps") > sets(base, "biceps")
    assert any("foco" in line for line in focused.rationale)


def test_missing_exercises_are_skipped_and_empty_catalog_yields_empty_result(catalog):
    assert generate(params(), {}).name == ""

    partial = {k: v for k, v in catalog.items() if v.muscle_group != "chest"}
    result = generate(params(), partial)
    assert result.name
    assert all(e.muscle != "chest" for day in result.days for e in day.exercises)


STYLE_COMBINATIONS = sorted(SPLITS)


@pytest.mark.parametrize(("style", "days"), STYLE_COMBINATIONS)
def test_every_split_style_produces_a_valid_plan(catalog, style, days):
    result = generate(params(split_style=style, days_per_week=days, session_minutes=120), catalog)

    assert len(result.days) == days
    assert result.split_name == SPLITS[(style, days)].name
    assert all(day.exercises for day in result.days)
    trained = {e.muscle for day in result.days for e in day.exercises}
    assert trained == set(TIER)


def test_auto_style_matches_the_documented_default(catalog):
    for days, style in AUTO_STYLE.items():
        auto = generate(params(days_per_week=days), catalog)
        explicit = generate(params(days_per_week=days, split_style=style), catalog)
        assert [d.name for d in auto.days] == [d.name for d in explicit.days]


def test_body_part_split_trains_each_muscle_once_and_explains_the_trade_off(catalog):
    result = generate(
        params(split_style="body_part", days_per_week=5, session_minutes=120), catalog
    )

    for muscle in rules.MAJOR_MUSCLES:
        days_with_muscle = sum(any(e.muscle == muscle for e in d.exercises) for d in result.days)
        assert days_with_muscle == 1
    assert any("1 vez por semana" in line for line in result.rationale)
    assert {"R2", "R9"} <= set(result.reference_ids)
    chest_day = next(d for d in result.days if d.name == "Peito")
    assert {e.muscle for e in chest_day.exercises} == {"chest"}


def test_frequency_two_splits_cite_frequency_evidence_only_when_true(catalog):
    twice = generate(params(split_style="upper_lower", days_per_week=4), catalog)
    once = generate(params(split_style="push_pull_legs", days_per_week=3), catalog)

    assert any("pelo menos 2 vezes" in line for line in twice.rationale)
    assert not any("pelo menos 2 vezes" in line for line in once.rationale)
    assert any("convenção" in line for line in twice.rationale)


def test_unavailable_style_for_the_number_of_days_is_rejected():
    assert "body_part" not in styles_for(2)
    with pytest.raises(InvalidSplitError):
        get_split("body_part", 2)
    with pytest.raises(InvalidSplitError):
        get_split("upper_lower", 5)
