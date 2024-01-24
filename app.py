# imports
import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

from src.gameplay import EnergyMixer
from src.generators import (
    CoalGenerator,
    GasGenerator,
    NuclearGenerator,
    SolarGenerator,
    WindGenerator,
)
from src.utils import WEEK_MAP, total_energy, get_windows_range

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

# initialise random week selection
week_map = WEEK_MAP.copy()
week_map["date"] = week_map["datetime"].dt.date
if "week_ind" not in st.session_state:
    st.session_state["week_ind"] = int(week_map.sample(1).index[0])

# get user inputs
with st.sidebar:
    with st.expander("Gameplay", expanded=False):
        st.markdown(
            """
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
        )
    with st.expander("Generation sources", expanded=True):
        coal = st.number_input("Coal (MW)", min_value=0, value=0)
        if coal > 0:
            st.markdown(f"{coal/1650:,.0f} Coal Power Stations")
        gas = st.number_input("Gas (MW)", min_value=0, value=0)
        if gas > 0:
            st.markdown(f"{gas/650:,.0f} Gas Power Stations")
        nuclear = st.number_input("Nuclear (MW)", min_value=0, value=0)
        if nuclear > 0:
            st.markdown(f"{nuclear/1150:,.0f} Nuclear Power Stations")
        solar = st.number_input("Solar (MW)", min_value=0, value=0)
        if solar > 0:
            st.markdown(f"{solar/(1/1000)/7300:,.0f} Football pitches")
        wind = st.number_input("Wind (MW)", min_value=0, value=0)
        if wind > 0:
            st.markdown(f"{wind/6.8:,.0f} Offshore Wind Turbines")
    with st.expander("Week commencing", expanded=True):
        week_dt = st.selectbox(
            " ", week_map["date"].values, index=st.session_state["week_ind"]
        )
st.session_state["week_ind"] = int(week_map.loc[week_map["date"] == week_dt].index[0])
week_no = week_map.loc[st.session_state["week_ind"], "week"]

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

# initialise optimum score
if "grid_optimum" not in st.session_state:
    st.session_state["grid_optimum"] = {}
if week_no not in st.session_state["grid_optimum"]:
    st.session_state["grid_optimum"][week_no] = grid.optimum

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
(
    dispatch,
    spare,
    shortfall,
    oversupply,
    shortfall_windows,
    oversupply_windows,
    totals,
) = grid.calculate_dispatch()
dispatch = pd.DataFrame(dispatch)
spare = pd.DataFrame(spare)
totals = pd.DataFrame(totals)

# display score(s)
if sum([g.installed_capacity for g in grid.generators.values()]) > 0:
    energy = (
        total_energy(
            pd.concat(
                [pd.DataFrame(dispatch).sum(axis=1), pd.Series(grid.demand)], axis=1
            )
            .min(axis=1)
            .values,
            grid.time_steps,
        )
        / 1e6
        / 3600
    )
    oversupply = total_energy(oversupply.values(), grid.time_steps) / 1e6 / 3600
    cost = totals.loc[["capex", "opex", "carbon_tax", "social_carbon_cost"]].sum().sum()
    financial_cost = totals.loc[["capex", "opex", "carbon_tax"]].sum().sum()
    social_carbon_cost = totals.loc["social_carbon_cost"].sum()
    co2 = totals.loc["co2"].sum()
    string_colour = (
        "red" if shortfall_windows or not np.isclose(oversupply, 0) else "green"
    )
    with st.container():
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(
                f"""
                Cost: :{string_colour}[{cost/energy:,.2f}] EUR/MWh
                - Financial: :{string_colour}[{financial_cost/energy:,.2f}] EUR/MWh
                - Emissions: :{string_colour}[{co2/energy:,.2f}] kgCO2e/MWh
                - Social: :{string_colour}[{social_carbon_cost/energy:,.2f}] EUR/MWh
                """
            )
        with col2:
            diff = cost / energy - st.session_state["grid_optimum"][week_no]["score"]
            perc = 100 * diff / st.session_state["grid_optimum"][week_no]["score"]
            if perc > 25:
                opt_string_colour = "red"
            elif perc > 10:
                opt_string_colour = "orange"
            else:
                opt_string_colour = "green"
            st.markdown(
                f"""
                Optimum cost: :{opt_string_colour}[{st.session_state["grid_optimum"][week_no]["score"]:,.2f}] EUR/MWh
                - Difference: :{opt_string_colour}[{diff:,.2f}] EUR/MWh
                - Percentage: :{opt_string_colour}[{perc:,.2f}] %
                """
            )
            with st.expander("Generators", expanded=False):
                for k, v in st.session_state["grid_optimum"][week_no][
                    "installed_capacity"
                ].items():
                    st.write(f"{k.title()}: {v/1e6:,.0f} MW")

# display dispatch and demand
icon_gap = np.timedelta64(12, "h")
shortfall_windows_idx = get_windows_range(shortfall_windows, grid.time_steps, icon_gap)
oversupply_windows_idx = get_windows_range(
    oversupply_windows, grid.time_steps, icon_gap
)
shortfall_windows_disp = (
    pd.DataFrame(
        data={
            "time": shortfall_windows_idx,
            "demand": [
                grid.demand[pd.Timestamp(i)] / 1e6 for i in shortfall_windows_idx
            ],
            "icon": ["⚠️"] * len(shortfall_windows_idx),
        }
    )
    if shortfall_windows
    else pd.DataFrame()
)
oversupply_windows_disp = (
    pd.DataFrame(
        data={
            "time": oversupply_windows_idx,
            "demand": [
                dispatch.sum(axis=1).loc[pd.Timestamp(i)] / 1e6
                for i in oversupply_windows_idx
            ],
            "icon": ["⚡"] * len(oversupply_windows_idx),
        }
    )
    if oversupply_windows
    else pd.DataFrame()
)
windows_disp = pd.concat([shortfall_windows_disp, oversupply_windows_disp])
disp_order = {"nuclear": 0, "solar": 1, "wind": 2, "gas": 3, "coal": 4}
with st.empty():
    for i in range(0, len(dispatch), 4):
        # data to plot
        dispatch_disp = dispatch.copy() / 1e6
        dispatch_disp.iloc[i:] = np.nan
        dispatch_disp = pd.melt(dispatch_disp.reset_index(), id_vars=["index"])
        dispatch_disp["order"] = dispatch_disp["variable"].map(disp_order)
        dispatch_disp["variable"] = dispatch_disp["variable"].map(
            lambda x: x.replace("_", " ").title()
        )
        demand_disp = pd.Series(grid.demand).rename("Demand").copy() / 1e6
        demand_disp.iloc[i:] = np.nan
        demand_disp = pd.melt(demand_disp.reset_index(), id_vars=["index"])
        if not windows_disp.empty:
            shortfall_windows_disp = windows_disp.loc[
                windows_disp["time"] <= grid.time_steps[i]
            ]

        # chart layers
        if not windows_disp.empty:
            shortfall_windows_chart = (
                alt.Chart(windows_disp)
                .mark_text(size=18, baseline="middle")
                .encode(
                    alt.X("time"),
                    alt.Y("demand"),
                    alt.Text("icon"),
                    tooltip=alt.value(None),
                )
            )
        dispatch_chart = (
            alt.Chart(dispatch_disp)
            .mark_area()
            .encode(
                alt.X("index", axis=alt.Axis(tickCount="day")),
                alt.Y("value", title="Power [MW]", stack=True),
                alt.Color("variable"),
                alt.Order("order"),
                opacity={"value": 0.7},
                tooltip=alt.value(None),
            )
        )
        demand_chart = (
            alt.Chart(demand_disp)
            .mark_line()
            .encode(
                alt.X("index"),
                alt.Y("value"),
                alt.Color("variable"),
                opacity={"value": 0.7},
                tooltip=alt.value(None),
            )
        )

        # layered chart
        if not windows_disp.empty:
            layer_chart = alt.layer(
                dispatch_chart,
                demand_chart,
                shortfall_windows_chart,
            )
        else:
            layer_chart = alt.layer(
                dispatch_chart,
                demand_chart,
            )
        st.altair_chart(
            layer_chart.encode(
                color=alt.Color(
                    sort=[x.replace("_", " ").title() for x in disp_order.keys()]
                    + ["Demand"]
                )
            ),
            use_container_width=True,
        )

# display cost breakdown graph
tab1, tab2 = st.tabs(["Cost breakdown", "Spare capacity"])
with tab1:
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
                    alt.Y("variable", axis=alt.Axis(labelAngle=0)),
                    alt.X("value", title="Cost [EUR/MWh]", stack=True),
                    alt.Color("index"),
                    alt.Order("order"),
                    opacity={"value": 0.7},
                    tooltip=alt.value(None),
                )
            )

            # layered chart
            st.altair_chart(costs_chart, use_container_width=True)
with tab2:
    if spare.max().max() > 0:
        with st.empty():
            # data to plot
            spare_disp = spare.copy() / 1e6
            spare_disp = pd.melt(spare_disp.reset_index(), id_vars=["index"])
            spare_disp["order"] = spare_disp["variable"].map(
                {"solar": 1, "wind": 2, "nuclear": 0, "gas": 3, "coal": 4}
            )
            spare_disp["variable"] = spare_disp["variable"].map(
                lambda x: x.replace("_", " ").title()
            )

            # chart
            spare_chart = (
                alt.Chart(spare_disp)
                .mark_area()
                .encode(
                    alt.X("index", axis=alt.Axis(tickCount="day")),
                    alt.Y("value", title="Power [MW]"),
                    alt.Color(
                        "variable",
                        sort=[x.replace("_", " ").title() for x in disp_order.keys()],
                    ),
                    alt.Order("order"),
                    opacity={"value": 0.7},
                    tooltip=alt.value(None),
                )
            )
            st.altair_chart(
                spare_chart,
                use_container_width=True,
            )
