"""Register all domain models so cross-domain relationships resolve consistently."""

from src.workouts.biomechanics import models as biomechanical_models  # noqa: F401
from src.workouts.exercises import models as exercise_models  # noqa: F401
from src.workouts.plans import models as plan_models  # noqa: F401
from src.workouts.sessions import models as session_models  # noqa: F401
