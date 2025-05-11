# Updated Streamlit Fantasy HR Tracker with Monthly Filters and Winnings Summary

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

# --- Date Helpers ---
first_month = datetime(2025, 4, 1)
latest_month = datetime.today().replace(day=1)

# --- UI Layout ---
st.set_page_config(page_title="Fantasy HR Tracker", layout="wide")
st.title("Fantasy Baseball Home Run Tracker")

page = st.sidebar.radio("Choose View", ["Monthly Leaderboard", "Winnings Summary"])

# --- Month Selection ---
month_options = pd.date_range(first_month, latest_month, freq='MS').strftime('%B %Y').tolist()
selected_month_str = st.sidebar.selectbox("Select a Month", month_options[::-1])
selected_month = datetime.strptime(selected_month_str, "%B %Y")
start_date = max(selected_month, datetime(2025, 4, 4))
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

    results = []
    for norm_name, team in player_team_lookup.items():
        hrs = player_hr_totals.get(norm_name, 0)
        results.append({
            'Player': original_name_lookup[norm_name],
            'Team': team,
            'HRs': hrs
        })

    return pd.DataFrame(results)

# --- Fetch data ---
def get_monthly_results():
    month_data = {}
    months = pd.date_range(first_month, latest_month, freq='MS')
    for month in months:
        s = max(month, datetime(2025, 4, 4))
        e = (month + pd.offsets.MonthEnd(0)).to_pydatetime()
        df = fetch_hr_data(s, e)
        top_6 = df.sort_values(by='HRs', ascending=False).groupby('Team').head(6)
        leaderboard = top_6.groupby('Team')['HRs'].sum().sort_values(ascending=False)
        month_data[month.strftime('%B %Y')] = leaderboard
    return month_data

# --- Monthly Leaderboard ---
if page == "Monthly Leaderboard":
    df = fetch_hr_data(start_date, end_date)
    top_6_per_team = df.sort_values(by='HRs', ascending=False).groupby('Team').head(6).reset_index(drop=True)
    leaderboard = top_6_per_team.groupby('Team')['HRs'].sum().sort_values(ascending=False)

    st.subheader(f"Leaderboard for {selected_month_str} (Top 6 Players Per Team)")
    st.bar_chart(leaderboard)

    selected_team = st.selectbox("Select a Team to View Player Stats", sorted(fantasy_teams.keys()))
    team_df = df[df['Team'] == selected_team].sort_values(by='HRs', ascending=False)

    st.subheader(f"{selected_team}'s Player Stats")
    st.dataframe(team_df, use_container_width=True)

# --- Winnings Summary ---
eligible_months = pd.date_range(first_month, latest_month, freq='MS').strftime('%B %Y').tolist()
results = get_monthly_results()
team_names = fantasy_teams.keys()

winnings = pd.DataFrame(index=team_names, columns=['Paid', 'Won'])
winnings.fillna(0, inplace=True)

for month, leaderboard in results.items():
    if leaderboard.empty: continue
    if len(leaderboard) >= 1:
        first = leaderboard.index[0]
        winnings.at[first, 'Won'] += 35
    if len(leaderboard) >= 2:
        second = leaderboard.index[1]
        winnings.at[second, 'Won'] += 15
    for team in leaderboard.index:
        winnings.at[team, 'Paid'] += 10

winnings['Net'] = winnings['Won'] - winnings['Paid']

if page == "Winnings Summary":
    st.subheader("Fantasy Team Financials Summary")
    st.dataframe(winnings.sort_values(by='Net', ascending=False), use_container_width=True)
    st.bar_chart(winnings['Net'].sort_values(ascending=False))
