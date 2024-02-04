import warnings

from src.grid import Grid
from src.generators import (
    SolarGenerator,
    WindGenerator,
    NuclearGenerator,
    CoalGenerator,
    GasGenerator,
    BatteryGenerator,
)

# define optimisation worker function
def worker(week: int):
    # initialise grid for current week
    grid = Grid(
        generators={
            "solar": SolarGenerator,
            "wind": WindGenerator,
            "nuclear": NuclearGenerator,
            "battery": BatteryGenerator,
            "gas": GasGenerator,
            "coal": CoalGenerator,
        },
        week=week,
    )

    # save successul optimisations and print unsuccessful ones
    if grid.optimum is not None:
        return {
            **{
                k: v / grid.demand.max()
                for k, v in grid.optimum["installed_capacity"].items()
            },
            **{"score": grid.optimum["score"]},
        }
    else:
        warnings.warn(f"No optimum found")
