# Energy Grid Balancing Game
Game to balance energy generators in the electricity grid

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
    - `streamlit run energy_grid_balancing_game/streamlit_app.py`

## To do
- Single score value
    - Ethical carbon tax to reduce to single value
    - Normalise by power generated
    - Context for high generation price
    - Display cost components and CO2
        - Split by source
    - Fail if not all energy need is met
        - Fun animation and stats about blackouts
- Give context to slider values
    -2GW per nuclear plant, 5.4MW per wind turbine onshore, 8.6MW per wind turbine offshore
- Describe methodology
- Calculate optimum score
    - Cache value in streamlit
- Add storage entity
    - Hydro, hyrogen or battery
    - Green energy only?