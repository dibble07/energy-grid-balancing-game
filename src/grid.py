import inspect
import warnings
from functools import cache
from statistics import mean

import pandas as pd
from scipy.optimize import minimize

from src.generators import DataGenerator
from src.utils import get_demand_curve, total_energy, get_windows


class EnergyMixer:
    def __init__(self, generators, week) -> None:
        """
        Initialise energy mixer
            Parameters:
                generators (dict): Generator classes in energy mix in order of preference,
                week(int): week of year in consideration,
        """
        # get demand curve
        self.demand = get_demand_curve(week=week)
        self.time_steps = list(self.demand.keys())

        # initialise generators
        self.generators = {
            k: g(time_steps=self.time_steps, week=week)
            if DataGenerator in inspect.getmro(g)
            else g(time_steps=self.time_steps)
            for k, g in generators.items()
        }

    def set_installed_capacity(self, installed_capacity) -> None:
        """
        Set installed capacity for each generator
            Parameters:
                installed_capacity (dict): generator name and installed capacity,
        """
        self.reset_dispatch()
        for k, v in installed_capacity.items():
            self.generators[k].installed_capacity = v

    @property
    def min_power_profiles(self) -> dict:
        return {k: g.min_power for k, g in self.generators.items()}

    @property
    def optimum(self) -> dict:
        # calculate optimum if not already stored
        if not hasattr(self, "_optimum"):

            # save current install capacity
            original_installed_capacity = {
                k: g.installed_capacity for k, g in self.generators.items()
            }

            # set scaling factor
            scale = mean(self.demand.values())

            # define dispatch calculation
            @cache
            def dispatch_calculation(x):
                self.set_installed_capacity(
                    {k: v * scale for k, v in zip(self.generators.keys(), x)}
                )
                self.calculate_dispatch()
                return self.dispatch, self.shortfall, self.oversupply, self.totals

            # define objectives
            def obj(x):
                dispatch, _, _, totals = dispatch_calculation(tuple(x))
                cost = (
                    pd.DataFrame(totals)
                    .loc[["capex", "opex", "carbon_tax", "social_carbon_cost"]]
                    .sum()
                    .sum()
                )
                useful_energy = (
                    total_energy(
                        pd.concat(
                            [
                                pd.DataFrame(dispatch).sum(axis=1),
                                pd.Series(self.demand),
                            ],
                            axis=1,
                        )
                        .min(axis=1)
                        .values,
                        self.time_steps,
                    )
                    / 1e6
                    / 3600
                )
                return cost / useful_energy

            # define contraints
            def cons_shortfall(x):
                _, shortfall, _, _ = dispatch_calculation(tuple(x))
                return -1 * shortfall.mean() / 1e6 / 3600 / 7

            def cons_oversupply(x):
                _, _, oversupply, _ = dispatch_calculation(tuple(x))
                return -1 * oversupply.mean() / 1e6 / 3600 / 7

            # initial estimate
            init_values = {
                "solar": 0.32,
                "wind": 1.01,
                "nuclear": 0.52,
                "gas": 0.46,
                "coal": 0.00,
            }
            init_values_backup = {
                "solar": 1,
                "wind": 1,
                "nuclear": 0,
                "gas": 1,
                "coal": 0.00,
            }

            # define minimisation function
            def optimise(init):
                res = minimize(
                    fun=obj,
                    x0=[init[x] for x in self.generators.keys()],
                    bounds=[(0, None)] * len(self.generators),
                    constraints=[
                        {"type": "ineq", "fun": cons_shortfall},
                        {"type": "ineq", "fun": cons_oversupply},
                    ],
                    method="SLSQP",
                    options={"ftol": 10**-4},
                )
                return res

            # perform minimisation
            res = optimise(init_values)
            if not res.success:
                res = optimise(init_values_backup)
            if res.success:
                self._optimum = {
                    "installed_capacity": {
                        k: v * scale for k, v in zip(self.generators.keys(), res.x)
                    },
                    "score": res.fun,
                }
            else:
                warnings.warn(f"Optimiser failed: {res}")
                self._optimum = None

            # return to original installed capacity
            self.set_installed_capacity(original_installed_capacity)

        return self._optimum

    def calculate_dispatch(self):
        "calculate dispatch and spare capacity of each generator"
        # initially dispatch levels at minimum for each generator
        self.reset_dispatch()
        dispatch = self.min_power_profiles.copy()
        spare = {}
        totals = {}

        # loop over generation sources in order of preference
        for name, gen in self.generators.items():
            # calculate shortfall between current dispatch and demand
            shortfall = (
                pd.Series(self.demand) - pd.DataFrame(dispatch).sum(axis=1)
            ).clip(lower=0)

            # request generator provides its minimum plus the shortfall
            request = (shortfall + pd.Series(gen.min_power)).to_dict()
            dispatch[name], spare[name], totals[name] = gen.calculate_dispatch(request)

        # calculate shortfall and oversupply
        shortfall = (pd.Series(self.demand) - pd.DataFrame(dispatch).sum(axis=1)).clip(
            lower=0
        )
        oversupply = (pd.DataFrame(dispatch).sum(axis=1) - pd.Series(self.demand)).clip(
            lower=0
        )
        shortfall_windows = get_windows(shortfall.to_dict(), self.time_steps)
        oversupply_windows = get_windows(oversupply.to_dict(), self.time_steps)

        # store results
        self.dispatch = pd.DataFrame(dispatch)
        self.spare = pd.DataFrame(spare)
        self.shortfall = shortfall
        self.oversupply = oversupply
        self.shortfall_windows = shortfall_windows
        self.oversupply_windows = oversupply_windows
        self.totals = pd.DataFrame(totals)

    def reset_dispatch(self):
        for attr in [
            "dispatch",
            "spare",
            "shortfall",
            "oversupply",
            "shortfall_windows",
            "oversupply_windows",
            "totals",
        ]:
            if hasattr(self, attr):
                delattr(self, attr)