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
    - Display breakdown
        - Split by cost type
        - Split by source
        - Normalise by source generation
    - Fail if not all energy need is met
        - Fun animation and stats about blackouts
    - Ethical carbon tax to reduce to single value
- More info on user values
    - Context: 2GW per nuclear plant, 5.4MW per wind turbine onshore, 8.6MW per wind turbine offshore
    - Tips on good/bad of each resource
- Choose/set day
- Describe methodology
    - Assume perfect ramping
    - Ignore ability to turn off gas/coal intermittently
- Calculate optimum score
    - Cache value in streamlit
    - With and without storage
- Add storage entity
    - Hydro, hyrogen or battery
    - Green energy only?
    - Display surplus energy