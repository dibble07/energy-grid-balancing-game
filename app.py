# imports
import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

from src.grid import Grid
from src.generators import (
    CoalGenerator,
    GasGenerator,
    NuclearGenerator,
    SolarGenerator,
    WindGenerator,
    BatteryGenerator,
)
from src.utils import (
    WEEK_MAP,
    total_energy,
    get_windows_range,
    get_game_description,
    titlify,
)

# initialise app
st.set_page_config(page_title="Energy Grid Game", layout="wide")
hide_streamlit_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            </style>
            """
st.markdown(hide_streamlit_style, unsafe_allow_html=True)
st.header("Energy Grid Game")
sidebar = st.sidebar
with st.container():
    user_score_col, opt_score_col = st.columns(2)
main_chart_cont = st.empty()
cost_tab, spare_tab = st.tabs(["Cost breakdown", "Spare capacity"])
with cost_tab:
    cost_chart_cont = st.empty()
with spare_tab:
    spare_chart_cont = st.empty()

# initialise values and state parameters
cost_order = ["capex", "opex", "carbon_tax", "social_carbon_cost"]
display_order = ["nuclear", "solar", "wind", "gas", "coal", "battery"]
week_map = WEEK_MAP.copy()
week_map["date"] = week_map["datetime"].dt.date
if "week_ind" not in st.session_state:
    st.session_state["week_ind"] = int(week_map.sample(1).index[0])
if "grid_optimum" not in st.session_state:
    st.session_state["grid_optimum"] = {}

# get user inputs
with sidebar:
    with st.expander("Gameplay", expanded=False):
        st.markdown(get_game_description())
    with st.expander("Generation sources", expanded=True):
        installed_capacity = {}
        installed_capacity["coal"] = (
            st.number_input("Coal (MW)", min_value=0, value=0) * 1e6
        )
        if installed_capacity["coal"] > 0:
            st.markdown(
                f"{installed_capacity['coal']/1e6/1650:,.0f} Coal Power Stations"
            )
        installed_capacity["gas"] = (
            st.number_input("Gas (MW)", min_value=0, value=0) * 1e6
        )
        if installed_capacity["gas"] > 0:
            st.markdown(f"{installed_capacity['gas']/1e6/650:,.0f} Gas Power Stations")
        installed_capacity["nuclear"] = (
            st.number_input("Nuclear (MW)", min_value=0, value=0) * 1e6
        )
        if installed_capacity["nuclear"] > 0:
            st.markdown(
                f"{installed_capacity['nuclear']/1e6/1150:,.0f} Nuclear Power Stations"
            )
        installed_capacity["solar"] = (
            st.number_input("Solar (MW)", min_value=0, value=0) * 1e6
        )
        if installed_capacity["solar"] > 0:
            st.markdown(
                f"{installed_capacity['solar']/1e6/(1/1000)/7300:,.0f} Football pitches"
            )
        installed_capacity["wind"] = (
            st.number_input("Wind (MW)", min_value=0, value=0) * 1e6
        )
        if installed_capacity["wind"] > 0:
            st.markdown(
                f"{installed_capacity['wind']/1e6/6.8:,.0f} Offshore Wind Turbines"
            )
        installed_capacity["battery"] = (
            st.number_input("Battery (MW)", min_value=0, value=0) * 1e6
        )
        if installed_capacity["battery"] > 0:
            st.markdown(f"{installed_capacity['battery']/1e6/50:,.0f} Battery units")
    with st.expander("Week commencing", expanded=True):
        week_dt = st.selectbox(
            " ", week_map["date"].values, index=st.session_state["week_ind"]
        )
st.session_state["week_ind"] = int(week_map.loc[week_map["date"] == week_dt].index[0])
week_no = week_map.loc[st.session_state["week_ind"], "week"]

# run simulation
grid = Grid(
    generators={
        "nuclear": NuclearGenerator,
        "solar": SolarGenerator,
        "wind": WindGenerator,
        "battery": BatteryGenerator,
        "gas": GasGenerator,
        "coal": CoalGenerator,
    },
    week=week_no,
)
grid.set_installed_capacity(installed_capacity=installed_capacity)
grid.calculate_dispatch()

# display user score
with user_score_col:
    if sum(installed_capacity.values()) > 0:
        useful_energy = total_energy(
            pd.concat([grid.dispatch.sum(axis=1), pd.Series(grid.demand)], axis=1).min(
                axis=1
            ),
            grid.time_steps,
        )
        oversupply = total_energy(grid.oversupply.values, grid.time_steps)
        cost = (
            grid.totals.loc[["capex", "opex", "carbon_tax", "social_carbon_cost"]]
            .sum()
            .sum()
        )
        financial_cost = grid.totals.loc[["capex", "opex", "carbon_tax"]].sum().sum()
        social_carbon_cost = grid.totals.loc["social_carbon_cost"].sum()
        co2 = grid.totals.loc["co2"].sum()
        user_score_colour = (
            "red" if grid.shortfall_windows or grid.oversupply_windows else "green"
        )
        st.markdown(
            f"""
            Cost: :{user_score_colour}[{cost/(useful_energy/1e6/3600):,.2f}] EUR/MWh
            - Financial: :{user_score_colour}[{financial_cost/(useful_energy/1e6/3600):,.2f}] EUR/MWh
            - Emissions: :{user_score_colour}[{co2/(useful_energy/1e6/3600):,.2f}] kgCO2e/MWh
            - Social: :{user_score_colour}[{social_carbon_cost/(useful_energy/1e6/3600):,.2f}] EUR/MWh
            """
        )

# calculate dispatch display data
dispatch_disp = pd.melt(
    (grid.dispatch.clip(lower=0) / 1e6).reset_index(), id_vars=["index"]
)
dispatch_disp["order"] = dispatch_disp["variable"].map(
    {k: i for i, k in enumerate(display_order)}
)
dispatch_disp["variable"] = dispatch_disp["variable"].map(titlify)

# calculate demand display data
demand_disp = pd.melt((grid.demand / 1e6).reset_index(), id_vars=["index"])
demand_disp["variable"] = demand_disp["variable"].map(titlify)

# calculate icon display data
icon_gap = np.timedelta64(12, "h")
demand_met = {"index": [], "value": [], "icon": []}
if grid.shortfall_windows:
    shortfall_idx = get_windows_range(grid.shortfall_windows, grid.time_steps, icon_gap)
    demand_met["index"].extend(shortfall_idx)
    demand_met["value"].extend(
        [grid.demand[pd.Timestamp(i)] / 1e6 for i in shortfall_idx]
    )
    demand_met["icon"].extend(["⚠️"] * len(shortfall_idx))
if grid.oversupply_windows:
    oversupply_idx = get_windows_range(
        grid.oversupply_windows, grid.time_steps, icon_gap
    )
    demand_met["index"].extend(oversupply_idx)
    demand_met["value"].extend(
        [grid.dispatch.sum(axis=1)[pd.Timestamp(i)] / 1e6 for i in oversupply_idx]
    )
    demand_met["icon"].extend(["⚡"] * len(oversupply_idx))
demand_met = pd.DataFrame(demand_met)

# calculate cost breakdown data
costs_disp = grid.totals.loc[["capex", "opex", "carbon_tax", "social_carbon_cost"]] / (
    grid.totals.loc["dispatch_energy"] / 1e6 / 3600
).fillna(0).rename(index={"capex": "installation", "opex": "operation"})
costs_disp = pd.melt(costs_disp.reset_index(), id_vars=["index"])
costs_disp["order"] = costs_disp["index"].map({k: i for i, k in enumerate(cost_order)})
costs_disp[["index", "variable"]] = costs_disp[["index", "variable"]].map(titlify)

# data to plot
spare_disp = pd.melt((grid.spare / 1e6).reset_index(), id_vars=["index"])
spare_disp["order"] = spare_disp["variable"].map(
    {k: i for i, k in enumerate(display_order)}
)
spare_disp["variable"] = spare_disp["variable"].map(titlify)

# display main chart
with main_chart_cont:
    for i in range(0, len(grid.dispatch), 4):
        # obscure future data
        dispatch_disp_ = dispatch_disp.copy()
        dispatch_disp_.loc[
            dispatch_disp_["index"] > grid.time_steps[i], "value"
        ] = np.nan
        demand_disp_ = demand_disp.copy()
        demand_disp_.loc[demand_disp_["index"] > grid.time_steps[i], "value"] = np.nan
        if not demand_met.empty:
            demand_met_ = demand_met.loc[demand_met["index"] <= grid.time_steps[i]]
        else:
            demand_met_ = pd.DataFrame()

        # dispatch chart
        dispatch_chart = (
            alt.Chart(dispatch_disp_)
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

        # demand chart
        demand_chart = (
            alt.Chart(demand_disp_)
            .mark_line()
            .encode(
                alt.X("index"),
                alt.Y("value"),
                alt.Color("variable"),
                opacity={"value": 0.7},
                tooltip=alt.value(None),
            )
        )

        # demand met chart
        if not demand_met_.empty:
            demand_met_chart = (
                alt.Chart(demand_met_)
                .mark_text(size=18, baseline="middle")
                .encode(
                    alt.X("index"),
                    alt.Y("value"),
                    alt.Text("icon"),
                    tooltip=alt.value(None),
                )
            )
        else:
            demand_met_chart = None

        # render layered chart
        layers = (
            dispatch_chart,
            demand_chart,
        ) + ((demand_met_chart,) if demand_met_chart else tuple())
        st.altair_chart(
            alt.layer(*layers).encode(
                color=alt.Color(sort=[titlify(x) for x in display_order + ["demand"]])
            ),
            use_container_width=True,
        )

# display cost breakdown chart
with cost_chart_cont:
    if sum(installed_capacity.values()) > 0:
        st.altair_chart(
            alt.Chart(costs_disp)
            .mark_bar()
            .encode(
                alt.Y("variable", axis=alt.Axis(labelAngle=0)),
                alt.X("value", title="Cost [EUR/MWh]", stack=True),
                alt.Color("index"),
                alt.Order("order"),
                opacity={"value": 0.7},
                tooltip=alt.value(None),
            ),
            use_container_width=True,
        )

# display spare capacity chart
with spare_chart_cont:
    if grid.spare.max().max() > 0:
        st.altair_chart(
            alt.Chart(spare_disp)
            .mark_area()
            .encode(
                alt.X("index", axis=alt.Axis(tickCount="day")),
                alt.Y("value", title="Power [MW]"),
                alt.Color("variable", sort=[titlify(x) for x in display_order]),
                alt.Order("order"),
                opacity={"value": 0.7},
                tooltip=alt.value(None),
            ),
            use_container_width=True,
        )

# display optimum score
if week_no not in st.session_state["grid_optimum"]:
    st.session_state["grid_optimum"][week_no] = grid.optimum
with opt_score_col:
    if st.session_state["grid_optimum"][week_no] is not None:
        if sum(installed_capacity.values()) > 0:
            diff = (
                cost / (useful_energy / 1e6 / 3600)
                - st.session_state["grid_optimum"][week_no]["score"]
            )
            perc = 100 * diff / st.session_state["grid_optimum"][week_no]["score"]
            if perc > 25 or grid.shortfall_windows or grid.oversupply_windows:
                opt_string_colour = "red"
            elif perc > 10:
                opt_string_colour = "orange"
            else:
                opt_string_colour = "green"
            st.markdown(
                f"""
                Optimum cost: :{opt_string_colour}[{st.session_state['grid_optimum'][week_no]['score']:,.2f}] EUR/MWh
                - Difference: :{opt_string_colour}[{diff:,.2f}] EUR/MWh
                - Percentage: :{opt_string_colour}[{perc:,.2f}] %
                """
            )
            with st.expander("Generators", expanded=False):
                for k, v in st.session_state["grid_optimum"][week_no][
                    "installed_capacity"
                ].items():
                    st.write(f"{k.title()}: {v/1e6:,.0f} MW")
        else:
            st.markdown(
                f"Optimum cost: {st.session_state['grid_optimum'][week_no]['score']:,.2f} EUR/MWh"
            )
