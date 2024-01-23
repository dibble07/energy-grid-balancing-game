# Energy Grid Balancing Game
Game to balance energy generators in the electricity grid

![](energy_grid_balancing_game/gameplay.gif)

## Purpose
To create an engaging way to educate people about the challenges of balancing the energy grid at out reach programmes and events.

## Gameplay
The user is able to select energy generators from a range of sources (both renewables and hydrocarbon based) and is tasked to select a balance that reduce cost and emissions whilst ensuring that demand is always met.

## Setup and launch game
1. Clone this repository
1. Open repository in Python tool of choice
1. Create virtual environment
1. Run the following commands:
    - `pip install -U pip`
    - `pip install poetry`
    - `poetry install`
    - `streamlit run app.py`

## To do
- Deploy to streamlit and refactor path references
- More context on user values: "equivalant to 14000 wind turbines"
- Calculate optimum score
    - Cache value in streamlit
    - With and without storage
    - Optimum over entire year
- More graphs
    - Distribution of dispatched/spare/installed energy
    - Distribution of dispatched energy per source
    - Tab separated graphs
    - Shrink and/or make horizontal
- Add storage entity
    - Hydro, hyrogen or battery
    - Green energy only?
    - Display surplus energy
- Update screencast gif to README
- Share on Slack