from dataclasses import dataclass

from app.schemas.experiment import GeneticAlgorithmParameters


@dataclass(frozen=True)
class ExperimentPreset:
    label: str
    seed: int
    parameters: GeneticAlgorithmParameters


def ga_mandatory_presets() -> list[ExperimentPreset]:
    seeds = (42, 123, 2026)
    return [
        ExperimentPreset(
            "generations",
            seed,
            GeneticAlgorithmParameters(population_size=50, generations=generations),
        )
        for generations in (50, 100, 200)
        for seed in seeds
    ] + [
        ExperimentPreset(
            "population_size",
            seed,
            GeneticAlgorithmParameters(population_size=size, generations=100),
        )
        for size in (20, 50, 100)
        for seed in seeds
    ]
