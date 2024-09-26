from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs
import json
import requests
from datetime import datetime
from typing import List, Dict
import math
import os

class Odds:
    def __init__(self, odds_data: Dict):
        self.sportsbook_id = odds_data.get('SportsbookID')
        self.away_line = odds_data.get('AwayLine')
        self.home_line = odds_data.get('HomeLine')
        self.away_points = odds_data.get('AwayPoints')
        self.home_points = odds_data.get('HomePoints')
        self.away_points_line = odds_data.get('AwayPointsLine')
        self.home_points_line = odds_data.get('HomePointsLine')
        self.over_under = odds_data.get('OverUnder')
        self.over_line = odds_data.get('OverLine')
        self.under_line = odds_data.get('UnderLine')

class Team:
    def __init__(self, team_data: Dict, prefix: str):
        self.id = team_data.get(f'{prefix}TeamID')
        self.name = team_data.get(f'{prefix}TeamName')
        self.abbrev = team_data.get(f'{prefix}TeamAbbrev')
        self.full_name = team_data.get(f'{prefix}TeamFullName', self.name)
        self.wins = team_data.get(f'{prefix}TeamWins', 0)
        self.losses = team_data.get(f'{prefix}TeamLosses', 0)
        self.color = team_data.get(f'{prefix}TeamColor')
        self.color_light = team_data.get(f'{prefix}TeamColorLight')
        self.rank = team_data.get(f'{prefix}TeamRank')

class Event:
    def __init__(self, event_data: Dict):
        self.game_id = event_data.get('GameID')
        self.start_time = datetime.strptime(event_data.get('StartTimeStr', ''), '%m/%d/%Y %H:%M')
        self.status = event_data.get('Status')
        self.away_team = Team(event_data, 'Away')
        self.home_team = Team(event_data, 'Home')
        self.away_score = event_data.get('AwayScore')
        self.home_score = event_data.get('HomeScore')
        self.period = event_data.get('Period', '')
        self.period_number = event_data.get('PeriodNumber', 0)
        self.venue = event_data.get('Venue', '')
        self.location = event_data.get('Location', '')
        self.tv_stations = event_data.get('TVStations', '')
        self.odds = [Odds(odd) for odd in event_data.get('Odds', []) if odd.get('LineType') == 1]

class CFBEvent(Event):
    pass

class NFLEvent(Event):
    def __init__(self, event_data: Dict):
        super().__init__(event_data)
        self.season_type = event_data.get('SeasonType')
        self.week = event_data.get('Week')

class Events:
    def __init__(self):
        self.events: List[Event] = []

    def add_event(self, event_data: Dict):
        self.events.append(Event(event_data))

    def get_event_by_id(self, game_id: int) -> Event:
        return next((event for event in self.events if event.game_id == game_id), None)

    def get_events_by_status(self, status: int) -> List[Event]:
        return [event for event in self.events if event.status == status]

    def get_events_by_date(self, date: datetime) -> List[Event]:
        return [event for event in self.events if event.start_time.date() == date.date()]

class CFBEvents(Events):
    def add_event(self, event_data: Dict):
        self.events.append(CFBEvent(event_data))

class NFLEvents(Events):
    def add_event(self, event_data: Dict):
        self.events.append(NFLEvent(event_data))

def fetch_sports_data(url: str, event_class: type) -> Events:
    response = requests.get(url)
    data = json.loads(response.text)
    
    events = event_class()
    for event_data in data:
        events.add_event(event_data)
    
    return events


class MLBEvent(Event):
    def __init__(self, event_data: Dict):
        super().__init__(event_data)
        self.season_type = event_data.get('SeasonType')
        self.inning = event_data.get('Period')
        self.inning_number = event_data.get('PeriodNumber')

class MLBEvents(Events):
    def add_event(self, event_data: Dict):
        self.events.append(MLBEvent(event_data))

def fetch_sports_data(url: str, event_class: type) -> Events:
    response = requests.get(url)
    data = json.loads(response.text)
    
    events = event_class()
    for event_data in data:
        events.add_event(event_data)
    
    return events

sportsbook_names = {
    1: 'Pinnacle',
    5: 'BookMaker',
    89: 'FanDuel',
    83: 'DraftKings',
    28: 'Caesars',
    87: 'BetMGM',
    85: 'BetRivers'
}


def calculate_ev_percentage(odds: float, fair_odds: float) -> float:
    if odds > 0:
        implied_probability = 100 / (odds + 100)
    else:
        implied_probability = abs(odds) / (abs(odds) + 100)
    
    if fair_odds > 0:
        fair_probability = 100 / (fair_odds + 100)
    else:
        fair_probability = abs(fair_odds) / (abs(fair_odds) + 100)
    
    ev = (fair_probability * (odds / 100 + 1) - 1) * 100
    return round(ev, 2)

def generate_html(sports_data: Dict[str, Events]) -> str:
    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Sports Odds</title>
        <style>
            .highlight-green { background-color: #d4f4d7; }
            body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f0f0f0; }
            .container { max-width: 1200px; margin: 0 auto; background-color: white; border-radius: 10px; box-shadow: 0 0 10px rgba(0,0,0,0.1); overflow: hidden; }
            h1, h2 { text-align: center; padding: 20px 0; margin: 0; background-color: #f0f0f0; }
            .tabs { display: flex; background-color: #e0e0e0; }
            .tab { padding: 15px 20px; cursor: pointer; flex-grow: 1; text-align: center; transition: background-color 0.3s; }
            .tab:hover { background-color: #d0d0d0; }
            .tab.active { background-color: #c0c0c0; font-weight: bold; }
            .content { display: none; padding: 20px; }
            .content.active { display: block; }
            table { width: 100%; border-collapse: collapse; margin-bottom: 20px; }
            th, td { border: 1px solid #ddd; padding: 12px; text-align: center; }
            th { background-color: #f2f2f2; font-weight: bold; }
            tr:nth-child(even) { background-color: #f9f9f9; }
            tr:hover { background-color: #f5f5f5; }
            .best-odds { font-weight: bold; }
            td.team-name { width: 150px; text-align: left;}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Sports Odds</h1>
            <div class="tabs" id="sportTabs">
    """

    for sport in sports_data.keys():
        html += f'<div class="tab" data-sport="{sport}" onclick="showSport(\'{sport}\')">{sport}</div>'

    html += '</div>'

    for sport, events in sports_data.items():
        html += f"""
        <div id="{sport}" class="content">
            <h2>{sport} Odds</h2>
            <div class="tabs">
                <div class="tab active" data-bet-type="moneyline" onclick="showBetType('{sport}', 'moneyline')">Moneyline</div>
                <div class="tab" data-bet-type="spread" onclick="showBetType('{sport}', 'spread')">Spread</div>
                <div class="tab" data-bet-type="total" onclick="showBetType('{sport}', 'total')">Total</div>
            </div>
            <div id="{sport}-moneyline" class="content active">
                {create_table(events, 'moneyline')}
            </div>
            <div id="{sport}-spread" class="content">
                {create_table(events, 'spread')}
            </div>
            <div id="{sport}-total" class="content">
                {create_table(events, 'total')}
            </div>
        </div>
        """

    html += """
        </div>
        <script>
            function showSport(sport) {
                document.querySelectorAll('.content').forEach(content => content.classList.remove('active'));
                document.getElementById(sport).classList.add('active');
                document.querySelectorAll('#sportTabs .tab').forEach(tab => tab.classList.remove('active'));
                document.querySelector(`#sportTabs .tab[data-sport="${sport}"]`).classList.add('active');
            }

            function showBetType(sport, betType) {
                document.querySelectorAll(`#${sport} > div:not(.tabs)`).forEach(content => content.classList.remove('active'));
                document.getElementById(`${sport}-${betType}`).classList.add('active');
                document.querySelectorAll(`#${sport} .tab`).forEach(tab => tab.classList.remove('active'));
                document.querySelector(`#${sport} .tab[data-bet-type="${betType}"]`).classList.add('active');
            }

            function highlightBestOdds() {
                document.querySelectorAll('table').forEach(table => {
                    const rows = table.querySelectorAll('tr');
                    for (let i = 1; i < rows.length; i += 2) {
                        let bestOdds = -Infinity;
                        let bestCell = null;
                        const cells = rows[i].querySelectorAll('td');
                        cells.forEach(cell => {
                            const odds = parseFloat(cell.textContent);
                            if (!isNaN(odds) && odds > bestOdds) {
                                bestOdds = odds;
                                bestCell = cell;
                            }
                        });
                        if (bestCell) {
                            bestCell.classList.add('best-odds');
                        }
                    }
                });
            }

            // Show the first sport by default
            showSport(Object.keys(sports_data)[0]);
            highlightBestOdds();
        </script>
    </body>
    </html>
    """
    html += """
        </div>

        <div id="PlusEV" class="tabcontent">
            <h2>Plus EV Bets</h2>
            <table>
                <tr>
                    <th>Date</th>
                    <th>Teams</th>
                    <th>Bet Type</th>
                    <th>Sportsbook</th>
                    <th>Odds</th>
                    <th>Fair Odds</th>
                </tr>
    """

    for event in plus_ev:
        date = event.start_time.strftime('%Y-%m-%d %H:%M')
        teams = f"{event.away_team.name} @ {event.home_team.name}"
        
        for odd in event.odds:
            sportsbook = sportsbook_names.get(odd.sportsbook_id, 'Unknown')
            
            # Away team moneyline
            if isinstance(odd.away_line, int) and isinstance(calculate_fair_odds("away", event, 1), int):
                if odd.away_line > calculate_fair_odds("away", event, 1):
                    html += f"""
                    <tr>
                        <td>{date}</td>
                        <td>{teams}</td>
                        <td>Moneyline (Away)</td>
                        <td>{sportsbook}</td>
                        <td>{odd.away_line}</td>
                        <td>{calculate_fair_odds("away", event, 1)}</td>
                    </tr>
                    """
            
            # Home team moneyline
            if isinstance(odd.home_line, int) and isinstance(calculate_fair_odds("home", event, 1), int):
                if odd.home_line > calculate_fair_odds("home", event, 1):
                    html += f"""
                    <tr>
                        <td>{date}</td>
                        <td>{teams}</td>
                        <td>Moneyline (Home)</td>
                        <td>{sportsbook}</td>
                        <td>{odd.home_line}</td>
                        <td>{calculate_fair_odds("home", event, 1)}</td>
                    </tr>
                    """

    html += """
            </table>
        </div>

        <script>
            document.getElementById("defaultOpen").click();
        </script>
    </body>
    </html>
    """
    return html


plus_ev = []
def create_table(events: Events, bet_type: str) -> str:
    all_tables = ""
    for event in events.events:
        date = event.start_time.strftime('%Y-%m-%d %H:%M')
        away_team = event.away_team.name
        home_team = event.home_team.name
        location = event.location
        
        table = f'<p>Date: {date} @{location}</p>'
        table += '<table><tr><th class="team-name">Team</th>'
        table += '<th>Fair Odds</th>'
        for name in sportsbook_names.values():
            table += f'<th>{name}</th>'
        table += '</tr>'

        # Away team row
        table += f'<tr><td class="team-name">{away_team}</td>'
        fair_odds_away = calculate_fair_odds("away", event, 1)
        table += f'<td>{fair_odds_away}</td>'
        for sportsbook_id in sportsbook_names.keys():
            odds = next((odd for odd in event.odds if odd.sportsbook_id == sportsbook_id), None)
            if odds:
                if bet_type == 'moneyline':
                    cell_class = "highlight-green" if (isinstance(fair_odds_away, int) and isinstance(odds.away_line, int) and odds.away_line > fair_odds_away) else ""
                    table += f"<td class='{cell_class}'>{odds.away_line}</td>"
                    if cell_class != "":
                        plus_ev.append(event)
                elif bet_type == 'spread':
                    table += f'<td>{odds.away_points} ({odds.away_points_line})</td>'
                elif bet_type == 'total':
                    table += f'<td>O {odds.over_under} ({odds.over_line})</td>'
            else:
                table += '<td>N/A</td>'
                
        table += '</tr>'

        # Home team row
        table += f'<tr><td class="team-name">{home_team}</td>'
        fair_odds_home = calculate_fair_odds("home", event, 1)
        table += f'<td>{fair_odds_home}</td>'
        for sportsbook_id in sportsbook_names.keys():
            odds = next((odd for odd in event.odds if odd.sportsbook_id == sportsbook_id), None)
            if odds:
                if bet_type == 'moneyline':
                    cell_class = "highlight-green" if (isinstance(fair_odds_home, int) and isinstance(odds.home_line, int) and odds.home_line > fair_odds_home) else ""
                    table += f"<td class='{cell_class}'>{odds.home_line}</td>"
                    if cell_class != "":
                        plus_ev.append(event)
                elif bet_type == 'spread':
                    table += f'<td>{odds.home_points} ({odds.home_points_line})</td>'
                elif bet_type == 'total':
                    table += f'<td>U {odds.over_under} ({odds.under_line})</td>'
            else:
                table += '<td>N/A</td>'
        table += '</tr></table>'
        
        all_tables += table + '<hr>'  # Add a horizontal line between tables

    return all_tables

def calculate_fair_odds(team, event: Event, pinnacle_id: int) -> tuple:
    def american_to_decimal(american_odds):
        if american_odds > 0:
            return (american_odds / 100) + 1
        else:
            return (100 / abs(american_odds)) + 1

    def decimal_to_american(decimal_odds):
        if decimal_odds >= 2:
            return round((decimal_odds - 1) * 100)
        else:
            return round(-100 / (decimal_odds - 1))

    # Retrieve odds for the event
    away_odds = next((odd.away_line for odd in event.odds if odd.sportsbook_id == pinnacle_id), None)
    home_odds = next((odd.home_line for odd in event.odds if odd.sportsbook_id == pinnacle_id), None)

    # Handle cases where odds are not available
    if away_odds is None or home_odds is None:
        return 'N/A', 'N/A'

    return calculate_no_vig_odds(team, away_odds, home_odds)

def calculate_no_vig_odds(team, away_odds, home_odds):
    def american_to_decimal(american_odds):
        if american_odds > 0:
            return (american_odds / 100) + 1
        else:
            return (100 / abs(american_odds)) + 1

    def decimal_to_american(decimal_odds):
        if decimal_odds >= 2:
            return round((decimal_odds - 1) * 100)
        else:
            return round(-100 / (decimal_odds - 1))

    if away_odds == 'N/A' or home_odds == 'N/A':
        return 'N/A', 'N/A'

    away_decimal = american_to_decimal(int(away_odds))
    home_decimal = american_to_decimal(int(home_odds))

    total_probability = (1 / away_decimal) + (1 / home_decimal)
    fair_away_decimal = 1 / ((1 / away_decimal) / total_probability)
    fair_home_decimal = 1 / ((1 / home_decimal) / total_probability)

    if team == 'away':
        return decimal_to_american(fair_away_decimal)
    else:
        return decimal_to_american(fair_home_decimal)






def create_tables(events: Events) -> str:
    tables = ''
    for event in events.events:
        tables += create_event_table(event)
    return tables

def create_event_table(event: Event) -> str:
    date = event.start_time.strftime('%Y-%m-%d %H:%M')
    away_team = event.away_team.name
    home_team = event.home_team.name

    table = f'<h3>{away_team} vs {home_team}</h3>'
    table += f'<p>Date: {date}</p>'
    table += '<table><tr><th>Sportsbook</th><th>Moneyline</th><th>Spread</th><th>Total</th></tr>'

    for sportsbook_id, sportsbook_name in sportsbook_names.items():
        odds = next((odd for odd in event.odds if odd.sportsbook_id == sportsbook_id), None)
        table += f'<tr><td>{sportsbook_name}</td>'
        if odds:
            table += f'<td>{odds.away_line} / {odds.home_line}</td>'
            table += f'<td>{odds.away_points} ({odds.away_points_line}) / {odds.home_points} ({odds.home_points_line})</td>'
            table += f'<td>O/U {odds.over_under} ({odds.over_line} / {odds.under_line})</td>'
        else:
            table += '<td>N/A</td><td>N/A</td><td>N/A</td>'
        table += '</tr>'

    table += '</table>'
    return table

    for sport in sports_data.keys():
        html += f'<div class="tab" data-sport="{sport}" >{sport}</div>'

    html += '</div>'

    for sport, events in sports_data.items():
        html += f"""
        <div id="{sport}" class="content">
            <div class="tabs">
                <div class="tab active" data-bet-type="moneyline" onclick="showBetType('{sport}', 'moneyline')">Moneyline</div>
                <div class="tab" data-bet-type="spread" onclick="showBetType('{sport}', 'spread')">Spread</div>
                <div class="tab" data-bet-type="total" onclick="showBetType('{sport}', 'total')">Total</div>
            </div>
            <div id="{sport}-moneyline" class="content active">
                {create_table(events, 'moneyline')}
            </div>
            <div id="{sport}-spread" class="content">
                {create_table(events, 'spread')}
            </div>
            <div id="{sport}-total" class="content">
                {create_table(events, 'total')}
            </div>
        </div>
        """

    html += """
        </div>
        <script>
            function showSport(sport) {
                document.querySelectorAll('.content').forEach(content => content.classList.remove('active'));
                document.getElementById(sport).classList.add('active');
                document.querySelectorAll('#sportTabs .tab').forEach(tab => tab.classList.remove('active'));
                document.querySelector(`#sportTabs .tab[data-sport="${sport}"]`).classList.add('active');
            }

            function showBetType(sport, betType) {
                document.querySelectorAll(`#${sport} > div:not(.tabs)`).forEach(content => content.classList.remove('active'));
                document.getElementById(`${sport}-${betType}`).classList.add('active');
                document.querySelectorAll(`#${sport} .tab`).forEach(tab => tab.classList.remove('active'));
                document.querySelector(`#${sport} .tab[data-bet-type="${betType}"]`).classList.add('active');
            }

            function highlightBestOdds() {
                document.querySelectorAll('table').forEach(table => {
                    const rows = table.querySelectorAll('tr');
                    rows.forEach(row => {
                        const cells = row.querySelectorAll('td');
                        let bestOdds = -Infinity;
                        let bestCell = null;
                        cells.forEach(cell => {
                            const odds = parseFloat(cell.textContent);
                            if (!isNaN(odds) && odds > bestOdds) {
                                bestOdds = odds;
                                bestCell = cell;
                            }
                        });
                        if (bestCell) {
                            bestCell.classList.add('best-odds');
                        }
                    });
                });
            }

            // Show the first sport by default
            showSport(Object.keys(sports_data)[0]);
            highlightBestOdds();
        </script>
    </body>
    </html>
    """

    return html

   
class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        cfb_url = "https://www.lunosoftware.com/sportsdata/SportsDataService.svc/gamesOddsForDateWeek/3?&sportsbookIDList=1,5,89,83,28,87,85"
        nfl_url = "https://www.lunosoftware.com/sportsdata/SportsDataService.svc/gamesOddsForDateWeek/2?&sportsbookIDList=1,5,89,83,28,87,85"
        mlb_url = "https://www.lunosoftware.com/sportsdata/SportsDataService.svc/gamesOddsForDateWeek/1?&sportsbookIDList=1,5,89,83,28,87,85"

        sports_data = {
            'CFB': fetch_sports_data(cfb_url, CFBEvents),
            'NFL': fetch_sports_data(nfl_url, NFLEvents),
            'MLB': fetch_sports_data(mlb_url, MLBEvents)
        }

        html_content = generate_html(sports_data)

        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(html_content.encode())
        return