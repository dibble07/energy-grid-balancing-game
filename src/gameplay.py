import inspect

import pandas as pd

from src.generators import DataGenerator
from src.utils import get_demand_curve


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

        # calculate shortfall
        shortfall = (
            (pd.Series(self.demand) - pd.DataFrame(dispatch).sum(axis=1))
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

        return dispatch, spare, shortfall, blackouts, totals
