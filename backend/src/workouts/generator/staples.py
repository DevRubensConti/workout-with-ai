"""
Exercícios-base curados por músculo. Cada "vaga" (slot) lista candidatos em ordem de
preferência, pelo `source_id` do catálogo free-exercise-db.

Por que uma lista curada? A classificação `mechanic` do catálogo é ruidosa (crucifixos
e giros de kettlebell aparecem como "compound"), então a seleção não pode depender só
dela. O gerador só escolhe entre estes IDs; os filtros de nível e de áreas a evitar
usam os metadados do catálogo.

A ordem dos candidatos é uma escolha prática (movimentos básicos e seguros primeiro),
não uma regra científica, e deve passar por revisão profissional.
"""

from dataclasses import dataclass
from typing import Literal

Role = Literal["compound", "isolation"]


@dataclass(frozen=True)
class Slot:
    name: str
    role: Role
    candidates: tuple[str, ...]
    # Ordem alternativa para iniciantes (movimentos mais guiados/simples primeiro)
    beginner_candidates: tuple[str, ...] | None = None

    def ordered_for(self, level: str) -> tuple[str, ...]:
        if level == "beginner" and self.beginner_candidates:
            return self.beginner_candidates
        return self.candidates


SLOTS: dict[str, tuple[Slot, ...]] = {
    "chest": (
        Slot(
            "press",
            "compound",
            (
                "Barbell_Bench_Press_-_Medium_Grip",
                "Dumbbell_Bench_Press",
                "Machine_Bench_Press",
                "Leverage_Chest_Press",
                "Smith_Machine_Bench_Press",
                "Pushups",
            ),
            beginner_candidates=(
                "Machine_Bench_Press",
                "Dumbbell_Bench_Press",
                "Leverage_Chest_Press",
                "Pushups",
                "Smith_Machine_Bench_Press",
                "Barbell_Bench_Press_-_Medium_Grip",
            ),
        ),
        Slot(
            "incline",
            "compound",
            (
                "Incline_Dumbbell_Press",
                "Barbell_Incline_Bench_Press_-_Medium_Grip",
                "Leverage_Incline_Chest_Press",
                "Incline_Cable_Chest_Press",
            ),
        ),
        Slot(
            "fly",
            "isolation",
            ("Cable_Crossover", "Butterfly", "Dumbbell_Flyes", "Incline_Dumbbell_Flyes"),
        ),
    ),
    "lats": (
        Slot(
            "pull",
            "compound",
            (
                "Wide-Grip_Lat_Pulldown",
                "Close-Grip_Front_Lat_Pulldown",
                "Underhand_Cable_Pulldowns",
                "Pullups",
                "Chin-Up",
            ),
        ),
        Slot("straight_arm", "isolation", ("Straight-Arm_Pulldown", "Rope_Straight-Arm_Pulldown")),
    ),
    "middle back": (
        Slot(
            "row",
            "compound",
            (
                "Seated_Cable_Rows",
                "Bent_Over_Barbell_Row",
                "One-Arm_Dumbbell_Row",
                "Leverage_High_Row",
                "T-Bar_Row_with_Handle",
            ),
        ),
        Slot(
            "row_alt",
            "compound",
            (
                "One-Arm_Dumbbell_Row",
                "Dumbbell_Incline_Row",
                "Bent_Over_Two-Dumbbell_Row",
                "Leverage_High_Row",
                "Seated_Cable_Rows",
            ),
        ),
    ),
    "shoulders": (
        Slot(
            "press",
            "compound",
            (
                "Seated_Dumbbell_Press",
                "Machine_Shoulder_Military_Press",
                "Standing_Military_Press",
                "Dumbbell_Shoulder_Press",
                "Smith_Machine_Overhead_Shoulder_Press",
                "Barbell_Shoulder_Press",
            ),
            beginner_candidates=(
                "Machine_Shoulder_Military_Press",
                "Seated_Dumbbell_Press",
                "Smith_Machine_Overhead_Shoulder_Press",
                "Standing_Military_Press",
            ),
        ),
        Slot(
            "lateral",
            "isolation",
            (
                "Side_Lateral_Raise",
                "Cable_Seated_Lateral_Raise",
                "Seated_Side_Lateral_Raise",
                "One-Arm_Side_Laterals",
            ),
        ),
        Slot(
            "rear",
            "isolation",
            (
                "Reverse_Flyes",
                "Cable_Rear_Delt_Fly",
                "Bent_Over_Dumbbell_Rear_Delt_Raise_With_Head_On_Bench",
                "Face_Pull",
            ),
        ),
    ),
    "quadriceps": (
        Slot(
            "squat",
            "compound",
            ("Barbell_Squat", "Goblet_Squat", "Dumbbell_Squat", "Hack_Squat"),
            beginner_candidates=("Dumbbell_Squat", "Goblet_Squat", "Hack_Squat", "Barbell_Squat"),
        ),
        Slot("leg_press", "compound", ("Leg_Press", "Hack_Squat")),
        Slot("extension", "isolation", ("Leg_Extensions",)),
        Slot(
            "lunge",
            "compound",
            ("Dumbbell_Lunges", "Barbell_Walking_Lunge", "Barbell_Side_Split_Squat"),
        ),
    ),
    "hamstrings": (
        Slot(
            "hinge",
            "compound",
            (
                "Romanian_Deadlift",
                "Stiff-Legged_Dumbbell_Deadlift",
                "Stiff-Legged_Barbell_Deadlift",
                "Smith_Machine_Stiff-Legged_Deadlift",
            ),
            beginner_candidates=(
                "Stiff-Legged_Dumbbell_Deadlift",
                "Smith_Machine_Stiff-Legged_Deadlift",
            ),
        ),
        Slot("curl", "isolation", ("Lying_Leg_Curls", "Seated_Leg_Curl", "Standing_Leg_Curl")),
    ),
    "glutes": (
        Slot(
            "bridge",
            "compound",
            ("Barbell_Hip_Thrust", "Butt_Lift_Bridge", "Single_Leg_Glute_Bridge"),
        ),
        Slot(
            "kickback",
            "isolation",
            ("Pull_Through", "Glute_Kickback", "One-Legged_Cable_Kickback"),
        ),
    ),
    "biceps": (
        Slot(
            "curl",
            "isolation",
            (
                "Dumbbell_Bicep_Curl",
                "Barbell_Curl",
                "EZ-Bar_Curl",
                "Alternate_Incline_Dumbbell_Curl",
            ),
        ),
        Slot(
            "hammer",
            "isolation",
            (
                "Hammer_Curls",
                "Alternate_Hammer_Curl",
                "Cable_Hammer_Curls_-_Rope_Attachment",
                "Cable_Preacher_Curl",
            ),
        ),
    ),
    "triceps": (
        Slot(
            "pushdown",
            "isolation",
            (
                "Triceps_Pushdown",
                "Triceps_Pushdown_-_Rope_Attachment",
                "Low_Cable_Triceps_Extension",
            ),
        ),
        Slot(
            "overhead",
            "isolation",
            (
                "Cable_Rope_Overhead_Triceps_Extension",
                "EZ-Bar_Skullcrusher",
                "Dumbbell_Tricep_Extension_-Pronated_Grip",
                "Lying_Triceps_Press",
            ),
        ),
    ),
    "calves": (
        Slot(
            "standing",
            "isolation",
            (
                "Standing_Calf_Raises",
                "Standing_Barbell_Calf_Raise",
                "Smith_Machine_Calf_Raise",
                "Calf_Press",
            ),
        ),
        Slot("seated", "isolation", ("Seated_Calf_Raise", "Calf_Press_On_The_Leg_Press_Machine")),
    ),
    "abdominals": (
        Slot("crunch", "isolation", ("Cable_Crunch", "Crunches", "Crunch_-_Hands_Overhead")),
        Slot(
            "leg_raise",
            "isolation",
            ("Hanging_Leg_Raise", "Flat_Bench_Lying_Leg_Raise", "Decline_Reverse_Crunch"),
        ),
    ),
}


def all_source_ids() -> set[str]:
    return {
        source_id
        for slots in SLOTS.values()
        for slot in slots
        for source_id in (*slot.candidates, *(slot.beginner_candidates or ()))
    }
