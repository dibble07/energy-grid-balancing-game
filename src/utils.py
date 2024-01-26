import json
import os
import warnings

import numpy as np
import pandas as pd

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


def total_energy(power, time):
    # calculate average power in each time interval
    power_arr = np.array(list(power))
    power_arr = np.array([power_arr[:-1], power_arr[1:]]).mean(axis=0)

    # calculate time span of each interval
    time_diff = np.array([i.total_seconds() for i in np.diff(time)])

    # calculate total energy
    energy = (power_arr * time_diff).sum()

    return energy


def get_windows(values, time_steps):
    # initialise lists
    windows_start = []
    windows_end = []
    windows = []

    # identify boundaries
    atol = 1
    for i, (time_steps_pre, time_steps_post) in enumerate(
        zip(time_steps[:-1], time_steps[1:])
    ):
        values_pre = values[time_steps_pre]
        values_post = values[time_steps_post]
        if (
            np.isclose(values_pre, 0, atol=atol)
            and not np.isclose(values_post, 0, atol=atol)
        ) or (i == 0 and not np.isclose(values_pre, 0, atol=atol)):
            windows_start.append(time_steps_pre)
        if (
            not np.isclose(values_pre, 0, atol=atol)
            and np.isclose(values_post, 0, atol=atol)
        ) or (i == len(time_steps) - 2 and not np.isclose(values_post, 0, atol=atol)):
            windows_end.append(time_steps_post)
    assert len(windows_start) == len(windows_end)

    # group boundaries
    for start, end in zip(windows_start, windows_end):
        assert start < end
        windows.append((start, end))

    return windows


def get_windows_range(windows, time_steps, icon_gap):
    # initialise indexes
    window_idx = []

    # loop over all windows
    for window in windows:
        # identify window midpoint
        window = np.array(window, dtype="datetime64")
        midpoint_exact = (window[1] - window[0]) / 2 + window[0]
        midpoint = time_steps[
            np.argmin(abs(np.array(time_steps, dtype="datetime64") - midpoint_exact))
        ]

        # calculate indexes
        n_icon = max(1, int(np.floor(np.diff(window) / icon_gap)[0]))
        window_idx.extend(
            np.arange(
                midpoint - (n_icon - 1) / 2 * icon_gap,
                midpoint + (n_icon - 1) / 2 * icon_gap + icon_gap,
                icon_gap,
            )
        )

    return window_idx


def get_game_description():
    return """
## Aim of the game 
You are in charge of deciding how much of each source of energy generation method to install in the grid. You must make sure that throughout the week, there is always enough energy being generated by the grid to meet the demand. Any times where demand is not met will cause blackouts which are not allowed. Any times where there is an oversupply of energy will damage the grid and is not allowed.
## Scoring
Your score is determined by the cost per unit of energy produced. The cost comprises of both the financial cost (installation, operation and carbon tax) as well as the indirect cost to society due to the impact of the carbon emissions.
## Generators
### Coal
- Dispatchable (i.e. can increase or decrease output to dynamically match demand)
- Large carbon output
### Gas
- Similarly dispatchable as coal
- Lower carbon emissions than coal
### Nuclear
- No dispatchability
- Consistent output 
- Low carbon emissions
### Solar
- Dispatchable but curtailment doesn't save money
- Consistent peak timings but limited output in mornings and evenings
-Low carbon emissions
### Wind
- Dispatchable but curtailment doesn't save money
- Erratic power profile
- Low carbon emissions
## Assumptions
- Generators can ramp up and down infinitely quickly
- Coal, gas and nuclear generators can't be turned off completely
"""


def titlify(x):
    return x.replace("_", " ").title()


f_path = os.path.join(
    os.path.dirname(os.path.realpath(__file__)),
    "weekly_optimum.json",
)
if os.path.isfile(f_path):
    with open(f_path, "r") as f:
        OPT_INIT_WEEKLY = json.loads(f.read())
        OPT_INIT_WEEKLY = {int(k): v for k, v in OPT_INIT_WEEKLY.items()}
else:
    warnings.warn(f"No initial optimum file available in {f_path}")
    OPT_INIT_WEEKLY = {}


def get_optimum_init_params(week):
    if week in OPT_INIT_WEEKLY:
        out = OPT_INIT_WEEKLY[week]
    else:
        warnings.warn(f"No initial optimum available for week {week}")
        out = {
            "solar": 0.32,
            "wind": 1.01,
            "nuclear": 0.52,
            "gas": 0.46,
            "coal": 0.00,
        }
    return out
