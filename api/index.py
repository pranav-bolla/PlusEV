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
        self.line_type = odds_data.get('LineType')
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
        self.odds = [Odds(odd) for odd in event_data.get('Odds', [])]

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

class CFBEvent(Event):
    pass

class NFLEvent(Event):
    def __init__(self, event_data: Dict):
        super().__init__(event_data)
        self.season_type = event_data.get('SeasonType')
        self.week = event_data.get('Week')

class MLBEvent(Event):
    def __init__(self, event_data: Dict):
        super().__init__(event_data)
        self.season_type = event_data.get('SeasonType')
        self.inning = event_data.get('Period')
        self.inning_number = event_data.get('PeriodNumber')

class CFBEvents(Events):
    def add_event(self, event_data: Dict):
        self.events.append(CFBEvent(event_data))

class NFLEvents(Events):
    def add_event(self, event_data: Dict):
        self.events.append(NFLEvent(event_data))

class MLBEvents(Events):
    def add_event(self, event_data: Dict):
        self.events.append(MLBEvent(event_data))
        
class NHLEvent(Event):
    def __init__(self, event_data: Dict):
        super().__init__(event_data)
        self.period1_score = event_data.get('Period1Score')
        self.period2_score = event_data.get('Period2Score')
        self.period3_score = event_data.get('Period3Score')

class NHLEvents(Events):
    def add_event(self, event_data: Dict):
        self.events.append(NHLEvent(event_data))

def fetch_sports_data(url: str, event_class: type) -> Events:
    response = requests.get(url)
    data = json.loads(response.text)
    
    events = event_class()
    for event_data in data:
        events.add_event(event_data)
    
    return events

# BookMaker is 5
sportsbook_names = {
    1: 'Pinnacle',
    89: 'FanDuel',
    83: 'DraftKings',
    28: 'Caesars',
    87: 'BetMGM',
    85: 'BetRivers',
    8: 'bet365',
    86: 'PointsBet',
    98: 'Bet99',
    100: 'BetVictor',
    101: 'Betano',
    139: 'theScore'
}

def find_plus_ev_bets(sports_data: Dict[str, Events]) -> List[Dict]:
    plus_ev_bets = []
    for sport, events in sports_data.items():
        for event in events.events:
            for odd in event.odds:
                line_type_name = get_line_type_name(odd.line_type)
                fair_away_odds = calculate_fair_odds("away", event, 1, odd.line_type)
                fair_home_odds = calculate_fair_odds("home", event, 1, odd.line_type)
                
                if isinstance(odd.away_line, (int, float)) and isinstance(fair_away_odds, (int, float)):
                    ev_away = calculate_ev_percentage(odd.away_line, fair_away_odds)
                    if ev_away > 0:
                        plus_ev_bets.append({
                            'sport': sport,
                            'line_type': line_type_name,
                            'game': f"{event.away_team.name} @ {event.home_team.name}",
                            'team': event.away_team.name,
                            'book': sportsbook_names.get(odd.sportsbook_id, 'Unknown'),
                            'odds': odd.away_line,
                            'fair_odds': fair_away_odds,
                            'ev': ev_away
                        })
                
                if isinstance(odd.home_line, (int, float)) and isinstance(fair_home_odds, (int, float)):
                    ev_home = calculate_ev_percentage(odd.home_line, fair_home_odds)
                    if ev_home > 0:
                        plus_ev_bets.append({
                            'sport': sport,
                            'line_type': line_type_name,
                            'game': f"{event.away_team.name} @ {event.home_team.name}",
                            'team': event.home_team.name,
                            'book': sportsbook_names.get(odd.sportsbook_id, 'Unknown'),
                            'odds': odd.home_line,
                            'fair_odds': fair_home_odds,
                            'ev': ev_home
                        })
    
    return sorted(plus_ev_bets, key=lambda x: x['ev'], reverse=True)


def find_arbitrage_opportunities(sports_data: Dict[str, Events]) -> List[Dict]:
    arbitrage_opportunities = []
    for sport, events in sports_data.items():
        for event in events.events:
            for line_type in set(odd.line_type for odd in event.odds):
                moneyline_odds = [odd for odd in event.odds if odd.line_type == line_type]
                
                for i in range(len(moneyline_odds)):
                    for j in range(i + 1, len(moneyline_odds)):
                        arb = calculate_arbitrage(moneyline_odds[i], moneyline_odds[j], event, sport)
                        if arb:
                            arbitrage_opportunities.append(arb)
    
    return sorted(arbitrage_opportunities, key=lambda x: x['profit'], reverse=True)


def calculate_ev_percentage(odds: float, fair_odds: float) -> float:
    def odds_to_probability(odds):
        if odds > 0:
            return 100 / (odds + 100)
        else:
            return abs(odds) / (abs(odds) + 100)

    implied_probability = odds_to_probability(odds)
    fair_probability = odds_to_probability(fair_odds)

    ev = (fair_probability * (1 / implied_probability) - 1) * 100
    return round(ev, 2)

def create_table(events: Events, bet_type: str) -> str:
    all_tables = ""
    for event in events.events:
        date = event.start_time.strftime('%Y-%m-%d %H:%M')
        away_team = event.away_team.name
        home_team = event.home_team.name
        location = event.location
        
        all_tables += f'<h3>{away_team} vs {home_team}</h3>'
        all_tables += f'<p>Date: {date} @{location}</p>'
        
        if isinstance(event, NHLEvent):
            all_tables += create_odds_table(event, bet_type, 1, "NHL Game")
        else:
            # Full Game Table
            all_tables += create_odds_table(event, bet_type, 1, "Full Game")
            
            # First Half Table
            all_tables += create_odds_table(event, bet_type, 2, "First Half")
        
        all_tables += '<hr>'  # Add a horizontal line between events
    
    return all_tables

def calculate_arbitrage(odds1: Odds, odds2: Odds, event: Event, sport: str) -> Dict:
    def implied_probability(odds):
        if odds is None:
            return None
        try:
            return 1 / (1 + (odds / 100)) if odds > 0 else abs(odds) / (abs(odds) + 100)
        except Exception as e:
            print(f"Error calculating implied probability for odds {odds}: {e}")
            return None

    book1 = sportsbook_names.get(odds1.sportsbook_id, 'Unknown')
    book2 = sportsbook_names.get(odds2.sportsbook_id, 'Unknown')
    
    prob1_away = implied_probability(odds1.away_line)
    prob1_home = implied_probability(odds1.home_line)
    prob2_away = implied_probability(odds2.away_line)
    prob2_home = implied_probability(odds2.home_line)

    if None in (prob1_away, prob1_home, prob2_away, prob2_home):
        return None

    line_type_name = get_line_type_name(odds1.line_type)

    if (prob1_away + prob2_home < 1) or (prob1_home + prob2_away < 1):
        stake = 100  # Assume $100 total stake
        if prob1_away + prob2_home < 1:
            stake1 = stake * prob2_home / (prob1_away + prob2_home)
            stake2 = stake - stake1
            return {
                'sport': sport,
                'game': f"{event.away_team.name} @ {event.home_team.name}",
                'market': 'Moneyline',
                'book1': book1,
                'odds1': odds1.away_line,
                'stake1': round(stake1, 2),
                'team1': event.away_team.name,
                'book2': book2,
                'odds2': odds2.home_line,
                'stake2': round(stake2, 2),
                'team2': event.home_team.name,
                'profit': round(stake / (prob1_away + prob2_home) - stake, 2),
                'line_type': line_type_name
            }
        else:
            stake1 = stake * prob2_away / (prob1_home + prob2_away)
            stake2 = stake - stake1
            return {
                'sport': sport,
                'game': f"{event.away_team.name} @ {event.home_team.name}",
                'market': 'Moneyline',
                'book1': book1,
                'odds1': odds1.home_line,
                'stake1': round(stake1, 2),
                'team1': event.home_team.name,
                'book2': book2,
                'odds2': odds2.away_line,
                'stake2': round(stake2, 2),
                'team2': event.away_team.name,
                'profit': round(stake / (prob1_home + prob2_away) - stake, 2),
                'line_type': line_type_name
            }
    
    return None

def get_line_type_name(line_type: int) -> str:
    line_type_map = {
        1: "Full Game",
        2: "First Half",
        3: "Second Half",
        4: "First Period",
        5: "Second Period",
        6: "Third Period"
    }
    return line_type_map.get(line_type, f"Unknown ({line_type})")

def create_odds_table(event: Event, bet_type: str, line_type: int, table_title: str) -> str:
    table = f'<h4>{table_title}</h4>'
    table += '<table><tr><th class="team-name">Team</th>'
    table += '<th>Fair Odds</th>'
    for name in sportsbook_names.values():
        table += f'<th>{name}</th>'
    table += '</tr>'

    table += create_team_row(event, "away", bet_type, line_type)
    table += create_team_row(event, "home", bet_type, line_type)

    if isinstance(event, NHLEvent):
        table += create_nhl_period_rows(event, bet_type)

    table += '</table>'
    return table

def create_nhl_period_rows(event: NHLEvent, bet_type: str) -> str:
    rows = ""
    for period in range(1, 4):
        rows += f'<tr><td colspan="{len(sportsbook_names) + 2}" style="text-align: center; font-weight: bold; background-color: #f0f0f0;">Period {period}</td></tr>'
        rows += create_team_row(event, "away", bet_type, period + 3)
        rows += create_team_row(event, "home", bet_type, period + 3)
    return rows

def create_team_row(event: Event, team: str, bet_type: str, line_type: int) -> str:
    team_name = event.away_team.name if team == "away" else event.home_team.name
    row = f'<tr><td class="team-name">{team_name}</td>'
    fair_odds = calculate_fair_odds(team, event, 1, line_type)
    row += f'<td>{fair_odds}</td>'
    
    for sportsbook_id in sportsbook_names.keys():
        odds = next((odd for odd in event.odds if odd.sportsbook_id == sportsbook_id and odd.line_type == line_type), None)
        
        if bet_type == 'moneyline':
            row += add_cell(odds, f'{team}_line', fair_odds)
        elif bet_type == 'spread':
            row += add_spread_cell(odds, team)
        elif bet_type == 'total':
            row += add_total_cell(odds, 'over' if team == 'away' else 'under')
    
    row += '</tr>'
    return row

def add_cell(odds, attr, fair_odds):
    if odds:
        value = getattr(odds, attr)
        cell_class = "highlight-green" if (isinstance(fair_odds, int) and isinstance(value, int) and value > fair_odds) else ""
        return f"<td class='{cell_class}'>{value}</td>"
    else:
        return '<td>N/A</td>'

def add_spread_cell(odds, team):
    if odds:
        points = getattr(odds, f'{team}_points')
        points_line = getattr(odds, f'{team}_points_line')
        return f'<td>{points} ({points_line})</td>'
    else:
        return '<td>N/A</td>'

def add_total_cell(odds, over_under):
    if odds:
        if over_under == 'over':
            return f'<td>O {odds.over_under} ({odds.over_line})</td>'
        else:
            return f'<td>U {odds.over_under} ({odds.under_line})</td>'
    else:
        return '<td>N/A</td>'

def calculate_fair_odds(team, event: Event, pinnacle_id: int, line_type: int) -> str:
    odds = next((odd for odd in event.odds if odd.sportsbook_id == pinnacle_id and odd.line_type == line_type), None)
    
    if odds is None:
        return 'N/A'

    away_odds = odds.away_line
    home_odds = odds.home_line

    if away_odds is None or home_odds is None:
        return 'N/A'

    return calculate_no_vig_odds(team, away_odds, home_odds)


def calculate_no_vig_odds(team, away_odds, home_odds):
    def american_to_decimal(american_odds):
        if american_odds is None:
            return None
        if american_odds > 0:
            return (american_odds / 100) + 1
        else:
            return (100 / abs(american_odds)) + 1

    def decimal_to_american(decimal_odds):
        if decimal_odds is None:
            return None
        if decimal_odds >= 2:
            return round((decimal_odds - 1) * 100)
        else:
            return round(-100 / (decimal_odds - 1))

    if away_odds == 'N/A' or home_odds == 'N/A' or away_odds is None or home_odds is None:
        return 'N/A'

    away_decimal = american_to_decimal(away_odds)
    home_decimal = american_to_decimal(home_odds)

    if away_decimal is None or home_decimal is None:
        return 'N/A'

    total_probability = (1 / away_decimal) + (1 / home_decimal)
    fair_away_decimal = 1 / ((1 / away_decimal) / total_probability)
    fair_home_decimal = 1 / ((1 / home_decimal) / total_probability)

    if team == 'away':
        return decimal_to_american(fair_away_decimal)
    else:
        return decimal_to_american(fair_home_decimal)

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
            .container { max-width: 95%; margin: 0 auto; background-color: white; border-radius: 10px; box-shadow: 0 0 10px rgba(0,0,0,0.1); overflow: hidden; }
            table { width: 100%; border-collapse: collapse; margin-bottom: 20px; font-size: 14px; }
            h1, h2, h3, h4 { text-align: center; padding: 10px 0; margin: 0; background-color: #f0f0f0; }
            .tabs { display: flex; background-color: #e0e0e0; }
            .tab { padding: 15px 20px; cursor: pointer; flex-grow: 1; text-align: center; transition: background-color 0.3s; }
            .tab:hover { background-color: #d0d0d0; }
            .tab.active { background-color: #c0c0c0; font-weight: bold; }
            .content { display: none; padding: 20px; }
            .content.active { display: block; }
            th, td { border: 1px solid #ddd; padding: 12px; text-align: center; }
            th { background-color: #f2f2f2; font-weight: bold; }
            tr:nth-child(even) { background-color: #f9f9f9; }
            tr:hover { background-color: #f5f5f5; }
            .best-odds { font-weight: bold; }
            td.team-name { width: 150px; text-align: left;}
            .bottom-tables { margin-top: 20px; }
            .bottom-tables table { margin-bottom: 40px; }
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
        <div class="bottom-tables">
            <h2>Plus EV Bets</h2>
            <table>
                <tr>
                    <th>Sport</th>
                    <th>Line Type</th>
                    <th>Game</th>
                    <th>Team</th>
                    <th>Book</th>
                    <th>Odds</th>
                    <th>Fair Odds</th>
                    <th>EV%</th>
                </tr>
    """
    
    all_plus_ev_bets = find_plus_ev_bets(sports_data)
    
    for bet in all_plus_ev_bets:
        html += f"""
            <tr>
                <td>{bet['sport']}</td>
                <td>{bet['line_type']}</td>
                <td>{bet['game']}</td>
                <td>{bet['team']}</td>
                <td>{bet['book']}</td>
                <td>{bet['odds']}</td>
                <td>{bet['fair_odds']}</td>
                <td>{bet['ev']}%</td>               
            </tr>
        """
    
    html += """
            </table>
            
            <h2>Arbitrage Opportunities</h2>
            <table>
                <tr>
                    <th>Sport</th>
                    <th>Line Type</th>
                    <th>Game</th>
                    <th>Market</th>
                    <th>Book 1</th>
                    <th>Team 1</th>
                    <th>Odds 1</th>
                    <th>Stake 1</th>
                    <th>Book 2</th>
                    <th>Team 2</th>
                    <th>Odds 2</th>
                    <th>Stake 2</th>
                    <th>Profit</th>                    
                </tr>
    """
    
    all_arbitrage_opportunities = find_arbitrage_opportunities(sports_data)
    
    for arb in all_arbitrage_opportunities:
        html += f"""
            <tr>
                <td>{arb['sport']}</td>
                <td>{arb['line_type']}</td>
                <td>{arb['game']}</td>
                <td>{arb['market']}</td>
                <td>{arb['book1']}</td>
                <td>{arb['team1']}</td>
                <td>{arb['odds1']}</td>
                <td>${arb['stake1']}</td>
                <td>{arb['book2']}</td>
                <td>{arb['team2']}</td>
                <td>{arb['odds2']}</td>
                <td>${arb['stake2']}</td>
                <td>${arb['profit']}</td>                
            </tr>
        """

    html += """
            </table>
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
        nhl_url = "https://www.lunosoftware.com/sportsdata/SportsDataService.svc/gamesOddsForDateWeek/6?&sportsbookIDList=1,89,83,28,87,85,8,86,98,100,101,139"

        sports_data = {
            # 'CFB': fetch_sports_data(cfb_url, CFBEvents),
            'NFL': fetch_sports_data(nfl_url, NFLEvents),
            'MLB': fetch_sports_data(mlb_url, MLBEvents),
            'NHL': fetch_sports_data(nhl_url, NHLEvents)
        }

        html_content = generate_html(sports_data)

        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(html_content.encode())
        return