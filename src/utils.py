import os

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
    for i, (time_steps_pre, time_steps_post) in enumerate(
        zip(time_steps[:-1], time_steps[1:])
    ):
        values_pre = values[time_steps_pre]
        values_post = values[time_steps_post]
        if (values_pre == 0 and values_post > 0) or (i == 0 and values_pre > 0):
            windows_start.append(time_steps_pre)
        if (values_pre > 0 and values_post == 0) or (
            i == len(time_steps) - 2 and values_post > 0
        ):
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
