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

# set header
st.header("Energy Grid Game")

# initialise gameplay components
week = np.random.randint(low=1, high=53)
grid = EnergyMixer(
    generators={
        "solar": SolarGenerator,
        "wind": WindGenerator,
        "nuclear": NuclearGenerator,
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
    st.subheader("Installed capcity")
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
    col1, col2, col3 = st.columns(3)
    with col1:
        st.write(f"Cost [NOK/MWh]: {nok/energy:,.2f}")
    with col2:
        st.write(f"Emissions [kgCO2e/MWh]: {co2/energy:,.2f}")
    with col3:
        st.write(f"Stability score: {100}")

# display graph
with st.empty():
    for i in range(len(dispatch)):
        # data to plot
        dispatch_disp = dispatch.copy()
        dispatch_disp.iloc[i:] = np.nan
        demand_disp = pd.Series(grid.demand).rename("demand").copy()
        demand_disp.iloc[i:] = np.nan

        # chart layers
        dispatch_chart = (
            alt.Chart(pd.melt(dispatch_disp.reset_index(), id_vars=["index"]))
            .mark_area()
            .encode(
                alt.X("index", title=""),
                alt.Y("value", title="", stack=True),
                alt.Color("variable", title="", type="nominal"),
                opacity={"value": 0.7},
            )
            .interactive()
        )
        demand_chart = (
            alt.Chart(pd.melt(demand_disp.reset_index(), id_vars=["index"]))
            .mark_line()
            .encode(
                alt.X("index", title=""),
                alt.Y("value", title="", stack=True),
                alt.Color("variable", title="", type="nominal"),
                opacity={"value": 0.7},
            )
            .interactive()
        )

        # layered chart
        st.altair_chart(
            alt.layer(
                dispatch_chart,
                demand_chart,
            )
        )
