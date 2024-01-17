# imports
import math

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st
from icecream import ic

from calculate_production import calculate_cost_score, calculate_production
from sources_and_sinks import (
    CoalGenerator,
    GasGenerator,
    NuclearGenerator,
    SolarGenerator,
    WindGenerator,
    get_demand_curve
)

# initialise app

## set header
st.header("Energy Grid Game")

## initialise gameplay components
week_no = 6
df_demand = get_demand_curve(week_no=week_no).to_frame()/1e6
max_demand = max(df_demand["demand"])
coal = 0
gas = 0
nuclear = 0
solar = 0
wind = 0

## initialise user inputs
with st.sidebar:
    st.subheader("Energy Mix")
    coal = st.number_input("Coal (MW)", value=coal)
    gas = st.number_input("Gas (MW)", value=gas)
    nuclear = st.number_input("Nuclear (MW)", value=nuclear)
    solar = st.number_input("Solar (MW)", value=solar)
    wind = st.number_input("Wind (MW)", value=wind)

    total_production = coal + gas + nuclear + solar + wind
    if total_production < math.ceil(max_demand):
        st.write(f"Installed Capacity: :red[{total_production}]/{max_demand:5.0f}")
    else:
        st.write(f"Installed Capacity: :green[{total_production}]/{max_demand:5.0f}")

    button_display = st.button("Run Simulation")

## run simulation
demand = df_demand["demand"]
t = np.arange(0,7*24+1,1)
df_prod = pd.DataFrame({"t": t})

ENERGY_PRODUCERS = {
    "solar": SolarGenerator(time_steps=t, installed_capacity=solar),
    "wind": WindGenerator(time_steps=t, installed_capacity=wind, week_no=week_no),
    "gas": GasGenerator(time_steps=t, installed_capacity=gas),
    "coal": CoalGenerator(time_steps=t, installed_capacity=coal),
    "nuclear": NuclearGenerator(time_steps=t, installed_capacity=nuclear),
}

PRIORITY_LIST = ["nuclear", "solar", "wind", "gas", "coal"]

df_demand.index.name = "t"
df_prod = calculate_production(ENERGY_PRODUCERS, df_demand, PRIORITY_LIST)
co2, nok = calculate_cost_score(df_prod=df_prod, ENERGY_PRODUCERS=ENERGY_PRODUCERS)

## display score(s)
cont1 = st.container()
with cont1:
    col1, col2, col3 = st.columns(3)
cont2 = st.container()

with col1:
    st.write(f"Price score: {nok:9.0f}")
with col2:
    st.write(f"CO2 score: {co2:9.0f}")
with col3:
    st.write(f"Stability score: {100}")

## display graph
with st.empty():
    df_demand["demand"] = np.nan
    output = df_prod.copy()

    output["wind"] = np.nan
    output["solar"] = np.nan
    for hour in range(0, len(demand), 3):
        df_demand["demand"].iloc[0:hour] = list(demand)[0:hour]
        output["solar"].iloc[0:hour] = df_prod["solar"].iloc[0:hour]
        output["wind"].iloc[0:hour] = df_prod["wind"].iloc[0:hour]

        st.altair_chart(
            alt.layer(
                alt.Chart(
                    pd.melt(output.reset_index(), id_vars=["t"]),
                    width=640,
                    height=480,
                )
                .mark_area()
                .encode(
                    alt.X("t", title=""),
                    alt.Y("value", title="", stack=True),
                    alt.Color("variable", title="", type="nominal"),
                    opacity={"value": 0.7},
                )
                .interactive(),
                alt.Chart(pd.melt(df_demand.reset_index(), id_vars=["t"]))
                .mark_line()
                .encode(
                    alt.X("t", title=""),
                    alt.Y("value", title="", stack=True),
                    alt.Color("variable", title="", type="nominal"),
                    opacity={"value": 0.7},
                )
                .interactive(),
            )
        )
