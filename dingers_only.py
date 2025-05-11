# Updated Streamlit Fantasy HR Tracker with Monthly Filters

import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
from collections import defaultdict
import unicodedata
import re

# --- Normalize names ---
def normalize_name(name):
    name = unicodedata.normalize('NFD', name)
    name = name.encode('ascii', 'ignore').decode('utf-8')
    name = re.sub(r'[^\w\s]', '', name)
    return name.lower().strip()

# --- Fantasy Teams ---
fantasy_teams = {
    "JIM": [
        "Shohei Ohtani", "Matt Olson", "Eugenio Suarez", "Kyle Tucker",
        "Jackson Chourio", "Spencer Torkelson", "Matt McLain", "Cal Raleigh", "Heliot Ramos"
    ],
    # Add other teams here...
}

# --- Build lookup tables ---
player_team_lookup = {}
original_name_lookup = {}
for team, players in fantasy_teams.items():
    for player in players:
        norm = normalize_name(player)
        player_team_lookup[norm] = team
        original_name_lookup[norm] = player

# --- Streamlit UI ---
st.set_page_config(page_title="Fantasy HR Tracker", layout="wide")
st.title("Fantasy Baseball Home Run Tracker")

# --- Select Month ---
month_options = pd.date_range("2025-04-01", datetime.today(), freq='MS').strftime('%B %Y').tolist()
selected_month_str = st.selectbox("Select a Month", month_options[::-1])  # Most recent first
selected_month = datetime.strptime(selected_month_str, "%B %Y")

# --- Date range ---
start_date = max(selected_month, datetime(2025, 4, 4))  # April starts on the 4th
end_date = (selected_month + pd.offsets.MonthEnd(0)).to_pydatetime()

@st.cache_data(show_spinner=True)
def fetch_hr_data(start_date, end_date):
    player_hr_totals = defaultdict(int)
    current_date = start_date

    while current_date <= end_date:
        date_str = current_date.strftime('%Y-%m-%d')
        schedule_url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={date_str}"
        try:
            schedule = requests.get(schedule_url).json()
            games = schedule.get('dates', [])
            if games:
                for game in games[0]['games']:
                    game_pk = game['gamePk']
                    box_url = f"https://statsapi.mlb.com/api/v1/game/{game_pk}/boxscore"
                    box = requests.get(box_url).json()

                    for team_key in ['home', 'away']:
                        players = box['teams'][team_key]['players']
                        for pid, player_data in players.items():
                            raw_name = player_data['person']['fullName']
                            norm_name = normalize_name(raw_name)
                            stats = player_data.get('stats', {}).get('batting', {})
                            home_runs = stats.get('homeRuns', 0)
                            if home_runs > 0 and norm_name in player_team_lookup:
                                player_hr_totals[norm_name] += home_runs
        except Exception as e:
            print(f"Error on {date_str}: {e}")
        current_date += timedelta(days=1)

    # Build DataFrame
    results = []
    for norm_name, team in player_team_lookup.items():
        hrs = player_hr_totals.get(norm_name, 0)
        results.append({
            'Player': original_name_lookup[norm_name],
            'Team': team,
            'HRs': hrs
        })

    return pd.DataFrame(results)

if st.button("Refresh Home Run Data"):
    st.cache_data.clear()

# --- Fetch and process data ---
df = fetch_hr_data(start_date, end_date)

# --- Top 6 per team ---
top_6_per_team = (
    df.sort_values(by='HRs', ascending=False)
      .groupby('Team')
      .head(6)
      .reset_index(drop=True)
)

# --- Leaderboard ---
leaderboard = top_6_per_team.groupby('Team')['HRs'].sum().sort_values(ascending=False)

st.subheader(f"Fantasy Leaderboard for {selected_month_str} (Top 6 Players Per Team)")
st.bar_chart(leaderboard)

# --- Team breakdown ---
selected_team = st.selectbox("Select a Team to View Player Stats", sorted(fantasy_teams.keys()))
team_df = df[df['Team'] == selected_team].sort_values(by='HRs', ascending=False)

st.subheader(f"{selected_team}'s Player Stats")
st.dataframe(team_df, use_container_width=True)

