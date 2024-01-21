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
from utils import WEEK_MAP

# set config
st.set_page_config(page_title="Energy Grid Game", layout="wide")
hide_streamlit_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            </style>
            """
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

# set header
st.header("Energy Grid Game")

# get user inputs
week_map = WEEK_MAP.copy()
week_map["date"] = week_map["datetime"].dt.date
with st.sidebar:
    st.subheader("Week commencing")
    week_dt = st.selectbox("", week_map["date"].values, index=None)
    st.subheader("Installed capacity")
    coal = st.number_input("Coal (MW)", min_value=0, value=0)
    gas = st.number_input("Gas (MW)", min_value=0, value=0)
    nuclear = st.number_input("Nuclear (MW)", min_value=0, value=0)
    solar = st.number_input("Solar (MW)", min_value=0, value=0)
    wind = st.number_input("Wind (MW)", min_value=0, value=0)

# continue only if date selected
if week_dt:
    week_no = week_map.loc[week_map["date"] == week_dt, "week"].values[0]

    # initialise gameplay components
    grid = EnergyMixer(
        generators={
            "nuclear": NuclearGenerator,
            "solar": SolarGenerator,
            "wind": WindGenerator,
            "gas": GasGenerator,
            "coal": CoalGenerator,
        },
        week=week_no,
    )
    max_demand = max(grid.demand.values())

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
    dispatch, _, _, blackouts, totals = grid.calculate_dispatch()
    dispatch = pd.DataFrame(dispatch)
    totals = pd.DataFrame(totals)

    # display score(s)
    if sum([g.installed_capacity for g in grid.generators.values()]) > 0:
        energy = totals.loc["dispatch_energy"].sum() / 1e6 / 3600
        cost = (
            totals.loc[["capex", "opex", "carbon_tax", "social_carbon_cost"]]
            .sum()
            .sum()
        )
        financial_cost = totals.loc[["capex", "opex", "carbon_tax"]].sum().sum()
        social_carbon_cost = totals.loc["social_carbon_cost"].sum()
        co2 = totals.loc["co2"].sum()
        string_colour = "red" if blackouts else "green"
        with st.container():
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(
                    f"""
                    Cost: :{string_colour}[{cost/energy:,.2f}] EUR/MWh
                    - Financial: :{string_colour}[{financial_cost/energy:,.2f}] EUR/MWh
                    - Emissions: :{string_colour}[{social_carbon_cost/energy:,.2f}] EUR/MWh (:{string_colour}[{co2/energy:,.2f}] kgCO2e/MWh)
                    """
                )
            with col2:
                if blackouts:
                    blackout_duration = (
                        np.diff(np.array(blackouts)).sum() / 7
                    ).components
                    st.write(
                        f"Blackout duration: :{string_colour}[{(blackout_duration.hours+blackout_duration.days*24):02d}:{blackout_duration.minutes:02d}:{blackout_duration.seconds:02d}] /day"
                    )
                else:
                    st.write(f"Blackout duration: :{string_colour}[00:00:00] /day")

    # display dispatch and demand
    with st.empty():
        for i in range(len(dispatch)):
            # data to plot
            dispatch_disp = dispatch.copy() / 1e6
            dispatch_disp.iloc[i:] = np.nan
            dispatch_disp = pd.melt(dispatch_disp.reset_index(), id_vars=["index"])
            dispatch_disp["order"] = dispatch_disp["variable"].map(
                {"solar": 1, "wind": 2, "nuclear": 0, "gas": 3, "coal": 4}
            )
            dispatch_disp["variable"] = dispatch_disp["variable"].map(
                lambda x: x.replace("_", " ").title()
            )
            demand_disp = pd.Series(grid.demand).rename("Demand").copy() / 1e6
            demand_disp.iloc[i:] = np.nan
            demand_disp = pd.melt(demand_disp.reset_index(), id_vars=["index"])

            # chart layers
            dispatch_chart = (
                alt.Chart(dispatch_disp)
                .mark_area()
                .encode(
                    alt.X("index", title="", axis=alt.Axis(tickCount="day")),
                    alt.Y("value", title="Power [MW]", stack=True),
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
                    alt.X("index", title="", axis=alt.Axis(tickCount="day")),
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

    # display cost breakdown graph
    if sum([g.installed_capacity for g in grid.generators.values()]) > 0:
        with st.empty():
            # data to plot
            costs_disp = (
                totals.loc[["capex", "opex", "carbon_tax", "social_carbon_cost"]]
                / (totals.loc["dispatch_energy"] / 1e6 / 3600)
            ).fillna(0)
            costs_text = costs_disp.sum().to_frame("total_cost")
            costs_text["percent"] = (
                totals.loc["dispatch_energy"]
                / totals.loc["dispatch_energy"].sum()
                * 100
            )
            costs_text.reset_index(inplace=True)
            costs_text["index"] = costs_text["index"].map(
                lambda x: x.replace("_", " ").title()
            )
            costs_disp.rename(
                index={"capex": "installation", "opex": "operation"}, inplace=True
            )
            costs_disp = pd.melt(costs_disp.reset_index(), id_vars=["index"])
            cost_order = ["capex", "opex", "carbon_tax", "social_carbon_cost"]
            costs_disp["order"] = costs_disp["index"].map(
                {k: v for v, k in enumerate(cost_order)}
            )
            costs_disp[["index", "variable"]] = costs_disp[["index", "variable"]].map(
                lambda x: x.replace("_", " ").title()
            )

            # costs chart
            costs_chart = (
                alt.Chart(costs_disp)
                .mark_bar()
                .encode(
                    alt.X("variable", title="", axis=alt.Axis(labelAngle=0)),
                    alt.Y("value", title="Cost [EUR/MWh]", stack=True),
                    alt.Color("index", title="", type="nominal", sort=cost_order),
                    alt.Order(field="order"),
                    opacity={"value": 0.7},
                )
            )

            # annotation chart
            annotate_chart = (
                alt.Chart(costs_text)
                .mark_text(baseline="bottom", color="white")
                .encode(
                    alt.X("index", title=""),
                    alt.Y("total_cost", title=""),
                    alt.Text("percent", format=".1f"),
                )
            )

            # layered chart
            st.altair_chart(
                alt.layer(
                    costs_chart,
                    annotate_chart,
                ),
                use_container_width=True,
            )
