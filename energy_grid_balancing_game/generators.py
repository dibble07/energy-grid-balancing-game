import numpy as np
import pandas as pd

import utils


class BaseGenerator:
    def __init__(
        self,
        installed_capacity,
        min_output,
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
                cost (float): total cost [EUR]
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

        # total energy
        dispatch_power_arr = np.array(list(dispatch_power.values()))
        dispatch_power_arr = np.array(
            [dispatch_power_arr[:-1], dispatch_power_arr[1:]]
        ).mean(axis=0)
        spare_power_arr = np.array(list(spare_power.values()))
        spare_power_arr = np.array([spare_power_arr[:-1], spare_power_arr[1:]]).mean(
            axis=0
        )
        time_diff = np.array([i.total_seconds() for i in np.diff(self.time_steps)])
        dispatch_energy = (dispatch_power_arr * time_diff).sum()
        spare_energy = (spare_power_arr * time_diff).sum()

        # emissions and costs
        co2 = dispatch_energy * self.co2_oper
        capex = self.installed_capacity * self.cost_inst
        opex = dispatch_energy * self.cost_oper
        carbon_tax = co2 * utils.CARBON_TAX if self.carbon_tax else 0
        social_carbon_cost = co2 * utils.SOCIAL_CARBON_COST

        return (
            dispatch_power,
            spare_power,
            {
                "dispatch_energy": dispatch_energy,
                "spare_energy": spare_energy,
                "co2": co2,
                "capex": capex,
                "opex": opex,
                "carbon_tax": carbon_tax,
                "social_carbon_cost": social_carbon_cost,
            },
        )


class DataGenerator(BaseGenerator):
    def __init__(
        self,
        time_steps,
        installed_capacity,
        week,
        co2_oper,
        cost_oper,
        cost_inst,
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
            co2_oper=co2_oper,
            cost_oper=cost_oper,
            cost_inst=cost_inst,
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
        co2_oper=41000 * utils.GRAM_MWH,
        cost_oper=19 * utils.USD_KWY,
        cost_inst=1784 * utils.USD_KW / 30 / 52,
        carbon_tax=False,
        min_output=0,
        col="solar",
    ):
        super().__init__(
            installed_capacity=installed_capacity,
            week=week,
            min_output=min_output,
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
        co2_oper=11000 * utils.GRAM_MWH,
        cost_oper=(116 + 75) / 2 * utils.USD_KWY,
        cost_inst=(5908 + 3285) / 2 * utils.USD_KW / 25 / 52,
        carbon_tax=False,
        min_output=0,
        col="wind",
    ):
        super().__init__(
            installed_capacity=installed_capacity,
            week=week,
            min_output=min_output,
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
        co2_oper=24000 * utils.GRAM_MWH,
        cost_oper=(146 + 114) / 2 * utils.USD_KWY,
        cost_inst=(7989 + 7442) / 2 * utils.USD_KW / 50 / 52,
        carbon_tax=False,
        min_output=1.0,
    ):
        super().__init__(
            installed_capacity=installed_capacity,
            min_output=min_output,
            co2_oper=co2_oper,
            cost_oper=cost_oper,
            cost_inst=cost_inst,
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
        co2_oper=980_000 * utils.GRAM_MWH,
        cost_oper=(141 + 74) / 2 * utils.USD_KWY,
        cost_inst=(5327 + 3075) / 2 * utils.USD_KW / 40 / 52,
        carbon_tax=True,
        min_output=0.32,
    ):
        super().__init__(
            installed_capacity=installed_capacity,
            min_output=min_output,
            co2_oper=co2_oper,
            cost_oper=cost_oper,
            cost_inst=cost_inst,
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
        co2_oper=430_000 * utils.GRAM_MWH,
        cost_oper=(59 + 21) / 2 * utils.USD_KWY,
        cost_inst=(2324 + 922) / 2 * utils.USD_KW / 30 / 52,
        carbon_tax=True,
        min_output=0.35,
    ):
        super().__init__(
            installed_capacity=installed_capacity,
            min_output=min_output,
            co2_oper=co2_oper,
            cost_oper=cost_oper,
            cost_inst=cost_inst,
            carbon_tax=carbon_tax,
            time_steps=time_steps,
        )
        """
        Initialise technology specific values
        """
