import os

import pandas as pd

# constants for cost calculations
# capex and opex https://atb.nrel.gov/electricity/2022/index
# eu carbon pricing 86 EUR/TCO2e Jan 02 '23 https://www.statista.com/statistics/1322214/carbon-prices-european-union-emission-trading-scheme/
# norway carbon tax from page 55 of https://www.norskindustri.no/siteassets/dokumenter/rapporter-og-brosjyrer/energy-transition-norway/2023/energy-transition-norway-2023.pdf
USD_KWY = 10.42 / (1e3 * 365.25 * 24 * 3600)
USD_KW = 10.42 / (1e3)
GRAM_MWH = 0.001 / (1e6 * 3600)
CARBON_TAX = 11.34 * (86 + 100) / 1000

# load time series dataset
# https://www.rte-france.com/en/eco2mix/power-generation-energy-source
# https://www.kaggle.com/datasets/robikscube/hourly-energy-consumption
# https://www.agora-energiewende.org/data-tools/agorameter
POWER_DATA = (
    pd.read_csv(
        os.path.join(
            os.path.dirname(os.path.realpath(__file__)),
            "power_generation_and_consumption.csv",
        ),
        index_col="datetime",
    )
    * 1e9
)
POWER_DATA.index = pd.DatetimeIndex(POWER_DATA.index)
POWER_DATA.sort_index(inplace=True)
WEEK_MAP = (
    POWER_DATA.index.isocalendar()
    .reset_index()
    .groupby(by="week")
    .min()[["datetime"]]
    .reset_index()
)


def get_demand_curve(week):
    # extract timestamp of start of week
    week_start = WEEK_MAP.loc[WEEK_MAP["week"] == week, "datetime"].values[0]

    # extract demand data for chosen week and scale to given population
    demand = POWER_DATA.loc[
        week_start : week_start + pd.Timedelta(days=7), "demand"
    ].to_dict()

    return demand
