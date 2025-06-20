import streamlit as st
import pandas as pd
from elo import EloRating

@st.cache_data(show_spinner=True)
def init_elo_ratings(games_df):
    elo = EloRating()
    for _, game in games_df.iterrows():
        home = game["Home Team"]
        away = game["Away Team"]
        home_score = game["Home Score"]
        away_score = game["Away Score"]

        if pd.isna(home_score) or pd.isna(away_score):
            continue

        if home_score > away_score:
            result = 1
        elif home_score < away_score:
            result = 0
        else:
            result = 0.5

        elo.update_ratings(home, away, result)
    return elo

def forecast_win_probs(elo, upcoming_games):
    forecasts = []
    for _, game in upcoming_games.iterrows():
        home = game["Home Team"]
        away = game["Away Team"]
        prob = elo.win_probability(home, away)
        forecasts.append({
            "Home Team": home,
            "Away Team": away,
            "Elo Home Win Prob": prob
        })
    return pd.DataFrame(forecasts)

def calculate_betting_edges(forecasts, betting_df):
    edges = []
    for _, row in forecasts.iterrows():
        home = row["Home Team"]
        away = row["Away Team"]
        elo_prob = row["Elo Home Win Prob"]

        match = betting_df[
            (betting_df["Home Team"] == home) & (betting_df["Away Team"] == away)
        ]
        if not match.empty:
            bookmaker_prob = match.iloc[0]["Bookmaker Home Win Prob"]
            edge = elo_prob - bookmaker_prob
            edges.append({
                "Home Team": home,
                "Away Team": away,
                "Elo Prob": elo_prob,
                "Bookmaker Prob": bookmaker_prob,
                "Edge": edge
            })

    return pd.DataFrame(edges)

st.title("MLB Elo Ratings Live Dashboard")

@st.cache_data
def load_data():
    return pd.read_csv("historical_mlb_games_3seasons.csv")

historical_games = load_data()

# Initialize Elo ratings once, cached
elo = init_elo_ratings(historical_games)

st.sidebar.header("Controls")
tab = st.sidebar.radio("Select View", ["Power Rankings", "Input Game Results", "Forecast Upcoming Games", "Betting Edges"])

if tab == "Power Rankings":
    st.subheader("Current Power Rankings")
    ratings = elo.get_all_ratings()
    ratings_df = pd.DataFrame(ratings.items(), columns=["Team", "Elo Rating"])
    ratings_df = ratings_df.sort_values(by="Elo Rating", ascending=False)
    st.dataframe(ratings_df.style.format({"Elo Rating": "{:.1f}"}))

elif tab == "Input Game Results":
    st.subheader("Enter Finished Game Result")
    home_team = st.text_input("Home Team")
    away_team = st.text_input("Away Team")
    home_score = st.number_input("Home Score", min_value=0, step=1)
    away_score = st.number_input("Away Score", min_value=0, step=1)
    add_game = st.button("Add Game Result & Update Elo")

    if add_game:
        if home_team and away_team:
            result = 1 if home_score > away_score else 0 if home_score < away_score else 0.5
            elo.update_ratings(home_team, away_team, result)
            st.success(f"Updated Elo after {home_team} {home_score} - {away_score} {away_team}")
        else:
            st.error("Please enter both teams")

elif tab == "Forecast Upcoming Games":
    st.subheader("Enter Upcoming Games")
    upcoming_games_data = []
    n_games = st.number_input("Number of upcoming games to forecast", min_value=1, max_value=20, value=3)
    for i in range(n_games):
        cols = st.columns(2)
        home = cols[0].text_input(f"Game {i+1} Home Team", key=f"home_{i}")
        away = cols[1].text_input(f"Game {i+1} Away Team", key=f"away_{i}")
        upcoming_games_data.append({"Home Team": home, "Away Team": away})

    if st.button("Get Forecasts"):
        upcoming_df = pd.DataFrame(upcoming_games_data)
        upcoming_df = upcoming_df[(upcoming_df["Home Team"] != "") & (upcoming_df["Away Team"] != "")]
        if upcoming_df.empty:
            st.warning("Enter at least one upcoming game with both teams.")
        else:
            forecasts_df = forecast_win_probs(elo, upcoming_df)
            st.dataframe(forecasts_df.style.format({"Elo Home Win Prob": "{:.2%}"}))

elif tab == "Betting Edges":
    st.subheader("Calculate Betting Edges")
    st.markdown("""
    Enter upcoming games with bookmaker odds for home team winning.
    Elo probability will be compared against bookmaker probability to show edges.
    """)

    n_bet_games = st.number_input("Number of games to enter odds for", min_value=1, max_value=20, value=3)
    betting_data = []
    for i in range(n_bet_games):
        cols = st.columns(3)
        home = cols[0].text_input(f"Game {i+1} Home Team (Betting)", key=f"bet_home_{i}")
        away = cols[1].text_input(f"Game {i+1} Away Team (Betting)", key=f"bet_away_{i}")
        odds = cols[2].number_input(f"Bookmaker Home Win Probability (0-1)", min_value=0.0, max_value=1.0, step=0.01, key=f"bet_odds_{i}")
        betting_data.append({"Home Team": home, "Away Team": away, "Bookmaker Home Win Prob": odds})

    if st.button("Calculate Edges"):
        betting_df = pd.DataFrame(betting_data)
        betting_df = betting_df[
            (betting_df["Home Team"] != "") &
            (betting_df["Away Team"] != "") &
            (betting_df["Bookmaker Home Win Prob"] > 0)
        ]
        if betting_df.empty:
            st.warning("Enter valid betting odds data.")
        else:
            upcoming_games = betting_df[["Home Team", "Away Team"]]
            forecasts_df = forecast_win_probs(elo, upcoming_games)
            edges_df = calculate_betting_edges(forecasts_df, betting_df)
            if edges_df.empty:
                st.info("No matching games found between Elo forecasts and betting odds.")
            else:
                edges_df["Edge"] = edges_df["Edge"].map("{:.2%}".format)
                st.dataframe(edges_df)
