import inspect
from statistics import mean

import pandas as pd
from scipy.optimize import minimize

from src.generators import DataGenerator
from src.utils import get_demand_curve, total_energy


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

            # define objectives and constraints
            def obj(x):
                self.set_installed_capacity(
                    {k: v * scale for k, v in zip(self.generators.keys(), x)}
                )
                dispatch, _, _, _, _, totals = self.calculate_dispatch()
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

            def cons_shortfall(x):
                self.set_installed_capacity(
                    {k: v * scale for k, v in zip(self.generators.keys(), x)}
                )
                _, _, shortfall, _, _, _ = self.calculate_dispatch()
                return -1 * mean(shortfall.values())

            def cons_oversupply(x):
                self.set_installed_capacity(
                    {k: v * scale for k, v in zip(self.generators.keys(), x)}
                )
                _, _, _, oversupply, _, _ = self.calculate_dispatch()
                return -1 * mean(oversupply.values())

            # minimise
            res = minimize(
                fun=obj,
                x0=[1 / len(self.generators)] * len(self.generators),
                bounds=[(0, None)] * len(self.generators),
                constraints=[
                    {"type": "ineq", "fun": cons_shortfall},
                    {"type": "ineq", "fun": cons_oversupply},
                ],
            )
            if res.success:
                self._optimum = {
                    k: v * scale for k, v in zip(self.generators.keys(), res.x)
                }
            else:
                print(res)
                raise ValueError(
                    f"Optimiser failed - status:{res.status} message:{res.message}"
                )

            # return to original installed capacity
            self.set_installed_capacity(original_installed_capacity)

        return self._optimum

    def calculate_dispatch(self):
        "calculate dispatch and spare capacity of each generator"
        # initially dispatch levels at minimum for each generator
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
        shortfall = (
            (pd.Series(self.demand) - pd.DataFrame(dispatch).sum(axis=1))
            .clip(lower=0)
            .to_dict()
        )
        oversupply = (
            (pd.DataFrame(dispatch).sum(axis=1) - pd.Series(self.demand))
            .clip(lower=0)
            .to_dict()
        )

        # calculate blackouts
        blackouts_start = []
        blackouts_end = []
        blackouts = []
        for i, (time_steps_pre, time_steps_post) in enumerate(
            zip(self.time_steps[:-1], self.time_steps[1:])
        ):
            shortfall_pre = shortfall[time_steps_pre]
            shortfall_post = shortfall[time_steps_post]
            if (shortfall_pre == 0 and shortfall_post > 0) or (
                i == 0 and shortfall_pre > 0
            ):
                blackouts_start.append(time_steps_pre)
            if (shortfall_pre > 0 and shortfall_post == 0) or (
                i == len(self.time_steps) - 2 and shortfall_post > 0
            ):
                blackouts_end.append(time_steps_post)
        assert len(blackouts_start) == len(blackouts_end)
        for start, end in zip(blackouts_start, blackouts_end):
            assert start < end
            blackouts.append((start, end))

        return dispatch, spare, shortfall, oversupply, blackouts, totals
