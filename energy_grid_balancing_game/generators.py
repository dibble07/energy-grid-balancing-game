import numpy as np
import pandas as pd
from scipy.stats import norm

import utils


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
        self.installed_capacity = installed_capacity

    @property
    def installed_capacity(self):
        return self._installed_capacity

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

    def calculate_costs(self, power):
        """
        Calculate finanical and emissions costs
            Parameters:
                power (list[float]): power generated for each time increment [W]
            Returns:
                co2 (float): total CO2e generated [kg]
                nok (float): total NOK spent [NOK]
        """
        # total power generated
        time_step = list(set(np.diff(self.time_steps).round(8)))
        assert len(time_step) == 1
        time_step = time_step[0]
        energy_total = sum(power) * time_step * 3600

        # total costs
        co2 = energy_total * self.co2_opex
        carbon_tax = co2 * utils.CARBON_TAX if self.carbon_tax else 0
        nok = (
            energy_total * self.nok_opex
            + self.installed_capacity * self.nok_capex
            + carbon_tax
        )

        return co2, nok


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
        installed_capacity,
        week,
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
        installed_capacity,
        week,
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
        installed_capacity,
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
        installed_capacity,
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
        installed_capacity,
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
