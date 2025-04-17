import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
from collections import defaultdict
import unicodedata
import re

# --- Normalize player names ---
def normalize_name(name):
    name = unicodedata.normalize('NFD', name)
    name = name.encode('ascii', 'ignore').decode('utf-8')
    name = re.sub(r'[^\w\s]', '', name)
    return name.lower().strip()

# --- Fantasy Teams ---
fantasy_teams = {
    'jim': [
        "Shohei Ohtani", "Matt Olson", "Eugenio Suarez", "Kyle Tucker", "Jackson Chourio",
        "Spencer Torkelson", "Matt McLain", "Cal Raleigh", "Heliot Ramos"
    ],
    'miles': [
        "Aaron Judge", "Jose Ramirez", "Francisco Lindor", "Gunnar Henderson", "Bobby Witt Jr.",
        "Elly De La Cruz", "Shea Langeliers", "Adolis Garcia", "Jazz Chisholm Jr."
    ],
    'ben': [
        "Bryce Harper", "Yordan Alvarez", "Marcell Ozuna", "Rafael Devers", "Wilmer Flores",
        "Freddie Freeman", "Adley Rutschman", "Mark Vientos", "Oneil Cruz"
    ],
    'rich': [
        "Mookie Betts", "Manny Machado", "Teoscar Hernandez", "Alex Bregman", "Anthony Santander",
        "Julio Rodriguez", "Max Muncy", "Matt Chapman", "Will Smith"
    ],
    'jaren': [
        "Juan Soto", "Kyle Schwarber", "Brent Rooker", "Fernando Tatis Jr.", "Austin Riley",
        "Jake Burger", "Ronald Acuna Jr.", "Lars Nootbaar", "Byron Buxton"
    ],
    'simon': [
        "Vladimir Guerrero Jr.", "Pete Alonso", "Mike Trout", "Corey Seager", "Ketel Marte",
        "Willy Adames", "Bo Bichette", "Tyler O'Neill", "Jorge Soler"
    ]
}

# --- Build lookup tables ---
player_team_lookup = {}
original_name_lookup = {}
for team, players in fantasy_teams.items():
    for player in players:
        norm = normalize_name(player)
        player_team_lookup[norm] = team
        original_name_lookup[norm] = player

# --- HR Tally Function ---
@st.cache_data(show_spinner=True)
def fetch_hr_data():
    player_hr_totals = defaultdict(int)
    start_date = datetime(2025, 4, 3)
    end_date = datetime.today()
    current_date = start_date

    while current_date <= end_date:
        date_str = current_date.strftime('%Y-%m-%d')
        schedule_url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={date_str}"
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

        current_date += timedelta(days=1)

    # Build DataFrame
    results = []
    for norm_name, team in player_team_lookup.items():
        hrs = player_hr_totals.get(norm_name, 0)
        results.append({
            'Player': original_name_lookup[norm_name],
            'Team': team,
            'HRs Since April 3': hrs
        })

    return pd.DataFrame(results)

# --- Streamlit UI ---
st.set_page_config(page_title="Fantasy HR Tracker", layout="wide")
st.title("Fantasy Baseball Home Run Tracker")
st.markdown("**Since April 3, 2025**")

if st.button("Refresh Home Run Data"):
    st.cache_data.clear()

df = fetch_hr_data()

# --- Show leaderboard using top 6 HR hitters per team ---
top_6_per_team = (
    df.sort_values(by='HRs Since April 3', ascending=False)
      .groupby('Team')
      .head(6)
      .reset_index(drop=True)
)

leaderboard = top_6_per_team.groupby('Team')['HRs Since April 3'].sum().sort_values(ascending=False)

st.subheader("Fantasy Leaderboard (Top 6 Players Per Team)")
st.bar_chart(leaderboard)

# --- Team Viewer ---
selected_team = st.selectbox("Select a Team to View Player Stats", sorted(fantasy_teams.keys()))
team_df = df[df['Team'] == selected_team].sort_values(by='HRs Since April 3', ascending=False)

st.subheader(f"{selected_team.title()}'s Player Stats")
st.dataframe(team_df, use_container_width=True)
