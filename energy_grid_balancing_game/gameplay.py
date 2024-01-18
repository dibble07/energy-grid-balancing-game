import inspect

import pandas as pd

from generators import DataGenerator
from utils import get_demand_curve


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

        # initialise generators
        self.generators = {
            k: g(time_steps=list(self.demand.keys()), week=week)
            if DataGenerator in inspect.getmro(g)
            else g(time_steps=list(self.demand.keys()))
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
        dispatch_all = self.min_power_profiles.copy()
        spare_all = {}
        energy_all = {}
        co2_all = {}
        cost_all = {}

        # loop over generation sources in order of preference
        for col in ["nuclear", "gas", "coal", "solar", "wind"]:
            # calculate shortfall between current dispatch and demand
            shortfall = (
                pd.Series(self.demand) - pd.DataFrame(dispatch_all).sum(axis=1)
            ).clip(lower=0)

            # request generator provides its minimum plus the shortfall
            request = (shortfall + pd.Series(self.generators[col].min_power)).to_dict()
            (
                dispatch_all[col],
                spare_all[col],
                energy_all[col],
                co2_all[col],
                cost_all[col],
            ) = self.generators[col].calculate_dispatch(request)

        return dispatch_all, spare_all, energy_all, co2_all, cost_all
