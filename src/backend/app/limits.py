"""Execution limits shared by request validation, the runner, and the UI.

The frontend reads these through GET /api/limits instead of copying them.
"""

MAX_PACKAGES = 100
MAX_TRUCKS = 20
MAX_ID_LENGTH = 128
MAX_TOTAL_TRUCK_VOLUME = 100_000
MAX_SAFE_SEED = 2**53 - 1
MAX_REQUEST_BYTES = 256 * 1024

HC_MAX_ITERATIONS = 2_000
HC_MAX_CANDIDATES = 50
HC_MAX_RESTARTS = 20
SA_MAX_ITERATIONS = 5_000
GA_MAX_POPULATION = 100
GA_MAX_GENERATIONS = 200

# Per-algorithm parameter caps enforced by the runner on top of schema bounds.
PARAMETER_BUDGETS: dict[str, dict[str, int]] = {
    "hill_climbing": {
        "max_iterations": HC_MAX_ITERATIONS,
        "candidates_per_iteration": HC_MAX_CANDIDATES,
        "max_restarts": HC_MAX_RESTARTS,
    },
    "simulated_annealing": {"max_iterations": SA_MAX_ITERATIONS},
    "genetic_algorithm": {
        "population_size": GA_MAX_POPULATION,
        "generations": GA_MAX_GENERATIONS,
    },
}
