import base64
import os

import pandas as pd

# constants for cost calculations
# capex and opex https://atb.nrel.gov/electricity/2022/index
# eu carbon pricing 86 EUR/TCO2e Jan 02 '23 https://www.statista.com/statistics/1322214/carbon-prices-european-union-emission-trading-scheme/
# social carbon cost - https://www.rff.org/news/press-releases/social-cost-of-carbon-more-than-triple-the-current-federal-estimate-new-study-finds/
USD_KWY = 0.92 / (1e3 * 365.25 * 24 * 3600)
USD_KW = 0.92 / (1e3)
GRAM_MWH = 0.001 / (1e6 * 3600)
CARBON_TAX = 86 / 1000
SOCIAL_CARBON_COST = 0.92 * 185 / 1000

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


# get demand power profile
def get_demand_curve(week):
    # extract timestamp of start of week
    week_start = WEEK_MAP.loc[WEEK_MAP["week"] == week, "datetime"].values[0]

    # extract demand data for chosen week and scale to given population
    demand = POWER_DATA.loc[
        week_start : week_start + pd.Timedelta(days=7), "demand"
    ].to_dict()

    return demand


# get blackout icon
def get_blackout_icon():
    image_path = "/Users/RDIB/Documents/GitHub/energy-grid-balancing-game/energy_grid_balancing_game/electricity.png"
    print(
        os.path.join(
            os.path.dirname(os.path.realpath(__file__)),
            "electricity.png",
        )
    )
    with open(image_path, "rb") as f:
        encoded_image = base64.b64encode(f.read()).decode()
    return encoded_image
