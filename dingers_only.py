import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
from collections import defaultdict
import unicodedata
import re

# --- Normalize names to match regardless of accents, punctuation, or casing ---
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

# --- Create normalized name lookup ---
player_team_lookup = {}
original_name_lookup = {}
for team, players in fantasy_teams.items():
    for player in players:
        norm = normalize_name(player)
        player_team_lookup[norm] = team
        original_name_lookup[norm] = player

# --- HR Tally Function ---
@st.cache_data(show_spinner=True)
def fetch_hr_data(month):
    player_hr_totals = defaultdict(int)
    today = datetime.today()

    start_date = datetime(today.year, month, 1)
    if month == 4:
        start_date = datetime(today.year, 4, 4)  # League started April 4th

    if month == today.month:
        end_date = today
    else:
        next_month = datetime(today.year if month < 12 else today.year + 1, month % 12 + 1, 1)
        end_date = next_month - timedelta(days=1)

    current_date = start_date

    while current_date <= end_date:
        try:
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
        except:
            pass

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

# --- Streamlit UI ---
st.set_page_config(page_title="Fantasy HR Tracker", layout="wide")
st.title("Fantasy Baseball Home Run Tracker")

month_names = {
    4: "April", 5: "May", 6: "June", 7: "July",
    8: "August", 9: "September"
}

month = st.selectbox("Select Month", options=list(month_names.keys()), format_func=lambda x: month_names[x])
if st.button("Refresh Data"):
    st.cache_data.clear()

df = fetch_hr_data(month)

# --- Show leaderboard using top 6 HR hitters per team ---
top_6_per_team = (
    df.sort_values(by='HRs', ascending=False)
      .groupby('Team')
      .head(6)
      .reset_index(drop=True)
)

team_leaderboard = top_6_per_team.groupby('Team')['HRs'].sum().sort_values(ascending=False)

# --- Determine payouts ---
first_place = team_leaderboard.index[0]
second_place = team_leaderboard.index[1]

payouts = {team: 0 for team in fantasy_teams.keys()}
payouts[first_place] = 35
payouts[second_place] = 15

# --- Display Leaderboard ---
st.subheader(f"{month_names[month]} Leaderboard (Top 6 Players Per Team)")
st.bar_chart(team_leaderboard)

# --- Show payouts ---
payout_df = pd.DataFrame({
    'Team': payouts.keys(),
    'HRs': [team_leaderboard.get(team, 0) for team in payouts.keys()],
    'Payout ($)': payouts.values()
}).sort_values(by='HRs', ascending=False)

st.subheader("Monthly Payouts")
st.dataframe(payout_df, use_container_width=True)

# --- Team Viewer ---
selected_team = st.selectbox("Select a Team to View Player Stats", sorted(fantasy_teams.keys()))
team_df = df[df['Team'] == selected_team].sort_values(by='HRs', ascending=False)
st.subheader(f"{selected_team.title()}'s Player Stats")
st.dataframe(team_df, use_container_width=True)
