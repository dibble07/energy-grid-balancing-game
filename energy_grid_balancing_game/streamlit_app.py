# imports
import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

from gameplay import EnergyMixer
from generators import (
    CoalGenerator,
    GasGenerator,
    NuclearGenerator,
    SolarGenerator,
    WindGenerator,
)

# set config
st.set_page_config(page_title="Energy Grid Game", layout="wide")

# set header
st.header("Energy Grid Game")

# initialise gameplay components
week = np.random.randint(low=1, high=53)
grid = EnergyMixer(
    generators={
        "nuclear": NuclearGenerator,
        "solar": SolarGenerator,
        "wind": WindGenerator,
        "gas": GasGenerator,
        "coal": CoalGenerator,
    },
    week=week,
)
max_demand = max(grid.demand.values())

# get user inputs
coal = 0
gas = 0
nuclear = 0
solar = 0
wind = 0
with st.sidebar:
    st.subheader("Installed capacity")
    coal = st.number_input("Coal (MW)", value=coal)
    gas = st.number_input("Gas (MW)", value=gas)
    nuclear = st.number_input("Nuclear (MW)", value=nuclear)
    solar = st.number_input("Solar (MW)", value=solar)
    wind = st.number_input("Wind (MW)", value=wind)

# run simulation
grid.set_installed_capacity(
    installed_capacity={
        "solar": solar * 1e6,
        "wind": wind * 1e6,
        "gas": gas * 1e6,
        "coal": coal * 1e6,
        "nuclear": nuclear * 1e6,
    }
)
dispatch, _, energy, co2, nok = grid.calculate_dispatch()
dispatch = pd.DataFrame(dispatch)

# display score(s)
energy = sum(energy.values()) / 1e6 / 3600
co2 = sum(co2.values())
nok = sum(nok.values())
with st.container():
    col1, col2 = st.columns(2)
    with col1:
        st.write(f"Cost [NOK/MWh]: {nok/energy:,.2f}")
    with col2:
        st.write(f"Emissions [kgCO2e/MWh]: {co2/energy:,.2f}")

# display graph
with st.empty():
    for i in range(len(dispatch)):
        # data to plot
        dispatch_disp = dispatch.copy()
        dispatch_disp.iloc[i:] = np.nan
        dispatch_disp = pd.melt(dispatch_disp.reset_index(), id_vars=["index"])
        dispatch_disp["order"] = dispatch_disp["variable"].map(
            {v: i for i, v in enumerate(grid.generators.keys())}
        )
        demand_disp = pd.Series(grid.demand).rename("demand").copy()
        demand_disp.iloc[i:] = np.nan
        demand_disp = pd.melt(demand_disp.reset_index(), id_vars=["index"])

        # chart layers
        dispatch_chart = (
            alt.Chart(dispatch_disp)
            .mark_area()
            .encode(
                alt.X("index", title=""),
                alt.Y("value", title="", stack=True),
                alt.Color(
                    "variable",
                    title="",
                    type="nominal",
                    sort=list(grid.generators.keys()),
                ),
                alt.Order(field="order"),
                opacity={"value": 0.7},
            )
        )
        demand_chart = (
            alt.Chart(demand_disp)
            .mark_line()
            .encode(
                alt.X("index", title=""),
                alt.Y("value", title="", stack=True),
                alt.Color("variable", title="", type="nominal"),
                opacity={"value": 0.7},
            )
        )

        # layered chart
        st.altair_chart(
            alt.layer(
                dispatch_chart,
                demand_chart,
            ),
            use_container_width=True,
        )
