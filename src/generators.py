import numpy as np
import pandas as pd

import src.utils as utils

# sources for default values
# capex and opex https://atb.nrel.gov/electricity/2023/index
# emissions - https://www.sciencedirect.com/science/article/pii/S0306261921012149#f0045
# eu carbon pricing 86 EUR/TCO2e Jan 02 '23 https://www.statista.com/statistics/1322214/carbon-prices-european-union-emission-trading-scheme/
# social carbon cost - https://www.rff.org/news/press-releases/social-cost-of-carbon-more-than-triple-the-current-federal-estimate-new-study-finds/
# technology lifespans - https://atb.nrel.gov/electricity/2023/definitions#costrecoveryperiod

# constants for cost calculations
USD_KWY = 0.92 / (1e3 * 365.25 * 24 * 3600)
USD_KW = 0.92 / (1e3)
GRAM_MWH = 0.001 / (1e6 * 3600)
CARBON_TAX = 86 / 1000
SOCIAL_CARBON_COST = 0.92 * 185 / 1000


class BaseGenerator:
    def __init__(
        self,
        installed_capacity,
        min_output,
        storage_duration,
        co2_oper,
        cost_oper,
        cost_inst,
        carbon_tax,
        time_steps,
    ):
        """
        Initialise values for sinusoidal generator
            Parameters:
                installed_capacity (float, int): Installed capacity [W]
                min_output (float): Proportion of available power that must be generated [-]
                co2_oper (float, int): CO2e per unit energy [kg/J]
                cost_oper (float, int): EUR per unit energy [EUR/J]
                cost_inst (float, int): EUR per installed capacity [EUR/W/WEEK]
                carbon_tax (bool): Whether or not subject to carbon tax
                time_steps (list[float]): Time range [hours]
        """
        # cost rates
        self.co2_oper = co2_oper
        self.cost_oper = cost_oper
        self.cost_inst = cost_inst
        self.carbon_tax = carbon_tax

        # time constants
        self.time_steps = time_steps

        # storage duration
        self.storage_duration = storage_duration

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
        if self.installed_capacity is not None:
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
                totals (dict): totals across entire time window
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
        totals = self.calculate_dispatch_totals(dispatch_power, spare_power)

        return dispatch_power, spare_power, totals

    def calculate_dispatch_totals(self, dispatch_power, spare_power) -> dict:
        """
        Calculate dispatched energy totals across time window
            Parameters:
                dispatch power (dict): dispatched power at each timestamp
                spare power (dict): spare power at each timestamp
            Returns:
                totals (dict): totals across entire time window
        """
        # total energy
        dispatch_energy = utils.total_energy(dispatch_power.values(), self.time_steps)
        spare_energy = utils.total_energy(spare_power.values(), self.time_steps)

        # emissions and costs
        co2 = dispatch_energy * self.co2_oper
        capex = self.installed_capacity * self.cost_inst
        opex = dispatch_energy * self.cost_oper
        carbon_tax = co2 * CARBON_TAX if self.carbon_tax else 0
        social_carbon_cost = co2 * SOCIAL_CARBON_COST

        # combine into output
        totals = {
            "dispatch_energy": dispatch_energy,
            "spare_energy": spare_energy,
            "co2": co2,
            "capex": capex,
            "opex": opex,
            "carbon_tax": carbon_tax,
            "social_carbon_cost": social_carbon_cost,
        }

        return totals


class DataGenerator(BaseGenerator):
    def __init__(self, week, col, *args, **kwargs):
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
        assert all(
            [
                x == y
                for x, y in zip(self.power_profile_norm.index, kwargs["time_steps"])
            ]
        )

        super().__init__(*args, **kwargs)

    def calculate_max_power_profile(self):
        # calculate daily power profile
        self.max_power = (self.power_profile_norm * self.installed_capacity).to_dict()


class SolarGenerator(DataGenerator):
    def __init__(
        self,
        time_steps,
        week,
        installed_capacity=None,
        storage_duration=None,
        co2_oper=41000 * GRAM_MWH,
        cost_oper=18 * USD_KWY,
        cost_inst=1691 * USD_KW / 30 / 52,
        carbon_tax=False,
        min_output=0,
        col="solar",
    ):
        super().__init__(
            installed_capacity=installed_capacity,
            week=week,
            min_output=min_output,
            storage_duration=storage_duration,
            co2_oper=co2_oper,
            cost_oper=cost_oper,
            cost_inst=cost_inst,
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
        storage_duration=None,
        co2_oper=11000 * GRAM_MWH,
        cost_oper=(116 + 102) / 2 * USD_KWY,
        cost_inst=(2080 + 2769) / 2 * USD_KW / 30 / 52,
        carbon_tax=False,
        min_output=0,
        col="wind",
    ):
        super().__init__(
            installed_capacity=installed_capacity,
            week=week,
            min_output=min_output,
            storage_duration=storage_duration,
            co2_oper=co2_oper,
            cost_oper=cost_oper,
            cost_inst=cost_inst,
            carbon_tax=carbon_tax,
            time_steps=time_steps,
            col=col,
        )


class NuclearGenerator(BaseGenerator):
    def __init__(
        self,
        time_steps,
        installed_capacity=None,
        storage_duration=None,
        co2_oper=24000 * GRAM_MWH,
        cost_oper=152 * USD_KWY,
        cost_inst=7468 * USD_KW / 60 / 52,
        carbon_tax=False,
        min_output=1.0,
    ):
        super().__init__(
            installed_capacity=installed_capacity,
            min_output=min_output,
            storage_duration=storage_duration,
            co2_oper=co2_oper,
            cost_oper=cost_oper,
            cost_inst=cost_inst,
            carbon_tax=carbon_tax,
            time_steps=time_steps,
        )


class CoalGenerator(BaseGenerator):
    def __init__(
        self,
        time_steps,
        installed_capacity=None,
        storage_duration=None,
        co2_oper=980_000 * GRAM_MWH,
        cost_oper=(77 + 150) / 2 * USD_KWY,
        cost_inst=(2857 + 5002) / 2 * USD_KW / 30 / 52,
        carbon_tax=True,
        min_output=0.32,
    ):
        super().__init__(
            installed_capacity=installed_capacity,
            min_output=min_output,
            storage_duration=storage_duration,
            co2_oper=co2_oper,
            cost_oper=cost_oper,
            cost_inst=cost_inst,
            carbon_tax=carbon_tax,
            time_steps=time_steps,
        )


class GasGenerator(BaseGenerator):
    def __init__(
        self,
        time_steps,
        installed_capacity=None,
        storage_duration=None,
        co2_oper=430_000 * GRAM_MWH,
        cost_oper=(24 + 31) / 2 * USD_KWY,
        cost_inst=(1003 + 1148) / 2 * USD_KW / 30 / 52,
        carbon_tax=True,
        min_output=0.35,
    ):
        super().__init__(
            installed_capacity=installed_capacity,
            min_output=min_output,
            storage_duration=storage_duration,
            co2_oper=co2_oper,
            cost_oper=cost_oper,
            cost_inst=cost_inst,
            carbon_tax=carbon_tax,
            time_steps=time_steps,
        )


class BatteryGenerator(BaseGenerator):
    def __init__(
        self,
        time_steps,
        installed_capacity=None,
        storage_duration=4 * 3600,
        co2_oper=78000 * GRAM_MWH,
        cost_oper=(24 + 88) / 2 * USD_KWY,
        cost_inst=(943 + 3520) / 2 * USD_KW / 15 / 52,
        carbon_tax=False,
        min_output=-1,
    ):
        super().__init__(
            installed_capacity=installed_capacity,
            min_output=min_output,
            storage_duration=storage_duration,
            co2_oper=co2_oper,
            cost_oper=cost_oper,
            cost_inst=cost_inst,
            carbon_tax=carbon_tax,
            time_steps=time_steps,
        )
