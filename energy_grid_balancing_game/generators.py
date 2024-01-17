import numpy as np
import pandas as pd

import utils

from icecream import ic


class BaseGenerator:
    def __init__(
        self,
        installed_capacity,
        min_output,
        co2_opex,
        nok_opex,
        nok_capex,
        carbon_tax,
        time_steps,
    ):
        """
        Initialise values for sinusoidal generator
            Parameters:
                installed_capacity (float, int): Installed capacity [W]
                min_output (float): Proportion of available power that must be generated [-]
                co2_opex (float, int): CO2e per unit energy [kg/J]
                nok_opex (float, int): NOK per unit energy [NOK/J]
                nok_capex (float, int): NOK per installed capacity [NOK/W/WEEK]
                carbon_tax (bool): Whether or not subject to carbon tax
                time_steps (list[float]): Time range [hours]
        """
        # cost rates
        self.co2_opex = co2_opex
        self.nok_opex = nok_opex
        self.nok_capex = nok_capex
        self.carbon_tax = carbon_tax

        # time constants
        self.time_steps = time_steps

        # capcity constraints
        self.min_output = min_output
        if installed_capacity is not None:
            self.installed_capacity = installed_capacity

    @property
    def installed_capacity(self):
        return (
            self._installed_capacity if hasattr(self, "_installed_capacity") else None
        )

    @installed_capacity.setter
    def installed_capacity(self, value):
        "Set installed capacity and calculate min and max power profiles"
        self._installed_capacity = value
        self.calculate_max_power_profile()
        self.calculate_min_power_profile()

    def calculate_max_power_profile(self):
        "Calculate maximum power profile"
        self.max_power = {k: self.installed_capacity for k in self.time_steps}

    def calculate_min_power_profile(self):
        "Calculate minimum power profile"
        self.min_power = {k: v * self.min_output for k, v in self.max_power.items()}

    def calculate_dispatch(self, request) -> tuple[dict]:
        """
        Calculate dispatched energy
            Parameters:
                request (dict): requested energy dispatch at each timestamp
            Returns:
                dispatch power (dict): dispatched power at each timestamp
                spare power (dict): spare power at each timestamp
                co2 (float): total CO2e generated [kg]
                nok (float): total NOK spent [NOK]
        """
        dispatch_power = {
            k: np.clip(req, min_, max_)
            for min_, max_, (k, req) in zip(
                self.min_power.values(), self.max_power.values(), request.items()
            )
        }
        spare_power = {
            k: np.clip(max_ - dispatch, 0, None)
            for dispatch, (k, max_) in zip(
                dispatch_power.values(), self.max_power.items()
            )
        }

        # total power dispatched
        power_arr = np.array(list(dispatch_power.values()))
        mean_power = np.array([power_arr[:-1], power_arr[1:]]).mean(axis=0)
        time_diff = np.array([i.total_seconds() for i in np.diff(self.time_steps)])
        energy = (mean_power * time_diff).sum()

        # total costs
        co2 = energy * self.co2_opex
        nok = (
            energy * self.nok_opex
            + self.installed_capacity * self.nok_capex
            + (co2 * utils.CARBON_TAX if self.carbon_tax else 0)
        )

        return dispatch_power, spare_power, energy, co2, nok


class DataGenerator(BaseGenerator):
    def __init__(
        self,
        time_steps,
        installed_capacity,
        week,
        co2_opex,
        nok_opex,
        nok_capex,
        carbon_tax,
        min_output,
        col,
    ):
        """
        Initialise technology specific values
        """
        # load normalised power profile
        week_start = utils.WEEK_MAP.loc[
            utils.WEEK_MAP["week"] == week, "datetime"
        ].values[0]
        self.power_profile_norm = (
            utils.POWER_DATA.loc[week_start : week_start + pd.Timedelta(days=7), col]
            / utils.POWER_DATA[col].max()
        )
        assert all([x == y for x, y in zip(self.power_profile_norm.index, time_steps)])

        super().__init__(
            installed_capacity=installed_capacity,
            min_output=min_output,
            co2_opex=co2_opex,
            nok_opex=nok_opex,
            nok_capex=nok_capex,
            carbon_tax=carbon_tax,
            time_steps=time_steps,
        )

    def calculate_max_power_profile(self):
        # calculate daily power profile
        self.max_power = (self.power_profile_norm * self.installed_capacity).to_dict()


class SolarGenerator(DataGenerator):
    def __init__(
        self,
        time_steps,
        week,
        installed_capacity=None,
        co2_opex=41000 * utils.GRAM_MWH,
        nok_opex=19 * utils.USD_KWY,
        nok_capex=1784 * utils.USD_KW / 30 / 52,
        carbon_tax=False,
        min_output=1.0,
        col="solar",
    ):
        super().__init__(
            installed_capacity=installed_capacity,
            week=week,
            min_output=min_output,
            co2_opex=co2_opex,
            nok_opex=nok_opex,
            nok_capex=nok_capex,
            carbon_tax=carbon_tax,
            time_steps=time_steps,
            col=col,
        )


class WindGenerator(DataGenerator):
    def __init__(
        self,
        time_steps,
        week,
        installed_capacity=None,
        co2_opex=11000 * utils.GRAM_MWH,
        nok_opex=(116 + 75) / 2 * utils.USD_KWY,
        nok_capex=(5908 + 3285) / 2 * utils.USD_KW / 25 / 52,
        carbon_tax=False,
        min_output=1.0,
        col="wind",
    ):
        super().__init__(
            installed_capacity=installed_capacity,
            week=week,
            min_output=min_output,
            co2_opex=co2_opex,
            nok_opex=nok_opex,
            nok_capex=nok_capex,
            carbon_tax=carbon_tax,
            time_steps=time_steps,
            col=col,
        )


class NuclearGenerator(BaseGenerator):
    def __init__(
        self,
        time_steps,
        installed_capacity=None,
        co2_opex=24000 * utils.GRAM_MWH,
        nok_opex=(146 + 114) / 2 * utils.USD_KWY,
        nok_capex=(7989 + 7442) / 2 * utils.USD_KW / 50 / 52,
        carbon_tax=False,
        min_output=1.0,
    ):
        super().__init__(
            installed_capacity=installed_capacity,
            min_output=min_output,
            co2_opex=co2_opex,
            nok_opex=nok_opex,
            nok_capex=nok_capex,
            carbon_tax=carbon_tax,
            time_steps=time_steps,
        )
        """
        Initialise technology specific values
        """


class CoalGenerator(BaseGenerator):
    def __init__(
        self,
        time_steps,
        installed_capacity=None,
        co2_opex=980_000 * utils.GRAM_MWH,
        nok_opex=(141 + 74) / 2 * utils.USD_KWY,
        nok_capex=(5327 + 3075) / 2 * utils.USD_KW / 40 / 52,
        carbon_tax=True,
        min_output=0.32,
    ):
        super().__init__(
            installed_capacity=installed_capacity,
            min_output=min_output,
            co2_opex=co2_opex,
            nok_opex=nok_opex,
            nok_capex=nok_capex,
            carbon_tax=carbon_tax,
            time_steps=time_steps,
        )
        """
        Initialise technology specific values
        """


class GasGenerator(BaseGenerator):
    def __init__(
        self,
        time_steps,
        installed_capacity=None,
        co2_opex=430_000 * utils.GRAM_MWH,
        nok_opex=(59 + 21) / 2 * utils.USD_KWY,
        nok_capex=(2324 + 922) / 2 * utils.USD_KW / 30 / 52,
        carbon_tax=True,
        min_output=0.35,
    ):
        super().__init__(
            installed_capacity=installed_capacity,
            min_output=min_output,
            co2_opex=co2_opex,
            nok_opex=nok_opex,
            nok_capex=nok_capex,
            carbon_tax=carbon_tax,
            time_steps=time_steps,
        )
        """
        Initialise technology specific values
        """
