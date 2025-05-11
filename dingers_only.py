# app.py
import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
from collections import defaultdict
import unicodedata
import re
import os

# --- Normalize player names ---
def normalize_name(name):
    name = unicodedata.normalize('NFD', name)
    name = name.encode('ascii', 'ignore').decode('utf-8')
    name = re.sub(r'[^\w\s]', '', name)
    return name.lower().strip()

# --- Fantasy Teams ---
fantasy_teams = {
    "JIM": ["Shohei Ohtani", "Matt Olson", "Eugenio Suarez", "Kyle Tucker", "Jackson Chourio", "Spencer Torkelson", "Matt McLain", "Cal Raleigh", "Heliot Ramos"],
    "DAN": ["Jose Ramirez", "Pete Alonso", "Josh Naylor", "Yordan Alvarez", "Mike Trout", "Jorge Soler", "Giancarlo Stanton", "Jonathan India", "Taylor Ward"],
    "ALEX": ["Aaron Judge", "Gunnar Henderson", "Juan Soto", "Austin Riley", "Vladimir Guerrero Jr.", "Marcell Ozuna", "Cody Bellinger", "Elly De La Cruz", "Anthony Santander"],
    "BOB": ["Mookie Betts", "Bryce Harper", "Freddie Freeman", "Corey Seager", "Kyle Schwarber", "Will Smith", "Wander Franco", "Randy Arozarena", "Francisco Lindor"]
}

# --- Lookup Tables ---
player_team_lookup = {}
original_name_lookup = {}
for team, players in fantasy_teams.items():
    for player in players:
        norm = normalize_name(player)
        player_team_lookup[norm] = team
        original_name_lookup[norm] = player

# --- Cache per month ---
def get_month_date_range(year, month):
    start = datetime(year, month, 1)
    if month == 12:
        end = datetime(year + 1, 1, 1) - timedelta(days=1)
    else:
        end = datetime(year, month + 1, 1) - timedelta(days=1)
    return start, min(end, datetime.today())

# --- Fetch data with caching ---
def scrape_month(year, month):
    filename = f"hr_data_{year}_{month:02d}.csv"
    if os.path.exists(filename):
        return pd.read_csv(filename)

    start_date, end_date = get_month_date_range(year, month)
    player_hr_totals = defaultdict(int)

    current_date = start_date
    while current_date <= end_date:
        date_str = current_date.strftime('%Y-%m-%d')
        url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={date_str}"
        schedule = requests.get(url).json()

        for game_date in schedule.get('dates', []):
            for game in game_date['games']:
                game_pk = game['gamePk']
                box_url = f"https://statsapi.mlb.com/api/v1/game/{game_pk}/boxscore"
                box = requests.get(box_url).json()

                for team_key in ['home', 'away']:
                    players = box['teams'][team_key]['players']
                    for player_data in players.values():
                        raw_name = player_data['person']['fullName']
                        norm_name = normalize_name(raw_name)
                        stats = player_data.get('stats', {}).get('batting', {})
                        home_runs = stats.get('homeRuns', 0)
                        if home_runs > 0 and norm_name in player_team_lookup:
                            player_hr_totals[norm_name] += home_runs

        current_date += timedelta(days=1)

    results = []
    for norm_name, team in player_team_lookup.items():
        hrs = player_hr_totals.get(norm_name, 0)
        results.append({
            'Player': original_name_lookup[norm_name],
            'Team': team,
            'HRs': hrs
        })

    df = pd.DataFrame(results)
    df.to_csv(filename, index=False)
    return df

# --- Streamlit UI ---
st.set_page_config(page_title="Fantasy HR Tracker", layout="wide")
st.title("Fantasy Baseball Home Run Tracker")

month_options = ["April", "May", "June", "July", "August", "September"]
month_num_map = {name: idx+4 for idx, name in enumerate(month_options)}
selected_month = st.selectbox("Choose a month", month_options)
month = month_num_map[selected_month]

# --- Load HR Data ---
year = 2025
df = scrape_month(year, month)

# --- Chart of all HRs ---
st.subheader(f"Total Home Runs - {selected_month}")
total_hrs = df['HRs'].sum()
st.markdown(f"### Total HRs: {total_hrs}")
st.bar_chart(df.groupby("Player")["HRs"].sum().sort_values(ascending=False))

# --- Top 6 per team ---
top_6 = df.sort_values(by='HRs', ascending=False).groupby('Team').head(6)
leaderboard = top_6.groupby('Team')['HRs'].sum().sort_values(ascending=False)

st.subheader("Fantasy Leaderboard (Top 6 Players per Team)")
st.bar_chart(leaderboard)

# --- Financial Summary ---
if month != 4:  # Skip April payouts
    pot = len(fantasy_teams) * 10
    payouts = {"1st": 35, "2nd": 15}
    first, second = leaderboard.index[:2]
    financials = []
    for team in fantasy_teams:
        paid = 10
        won = 35 if team == first else 15 if team == second else 0
        net = won - paid
        financials.append({"Team": team, "Paid": paid, "Won": won, "Net": net})
    fin_df = pd.DataFrame(financials)
    st.subheader("💰 Monthly Financial Summary")
    st.dataframe(fin_df, use_container_width=True)

# --- Team Viewer ---
selected_team = st.selectbox("Select a Team to View Player Stats", sorted(fantasy_teams.keys()))
st.subheader(f"{selected_team} - Player HR Stats")
st.dataframe(df[df['Team'] == selected_team].sort_values(by='HRs', ascending=False))
