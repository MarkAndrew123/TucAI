import requests
import re
import json
from datetime import datetime
from openai import AzureOpenAI
from bs4 import BeautifulSoup
import time
import os
from config import AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_KEY, AZURE_OPENAI_DEPLOYMENT, AZURE_OPENAI_API_VERSION

COMPETITION_SLUGS = [
    "fifa.world",           # FIFA World Cup
    "fifa.worldq.concacaf", # World Cup Qualifiers CONCACAF
    "fifa.worldq.conmebol", # World Cup Qualifiers CONMEBOL
    "fifa.worldq.uefa",     # World Cup Qualifiers UEFA
    "eng.1",                # Premier League
    "esp.1",                # La Liga
    "ger.1",                # Bundesliga
    "ita.1",                # Serie A
    "fra.1",                # Ligue 1
    "uefa.champions",       # Champions League
    "uefa.europa",          # Europa League
    "usa.1",                # MLS
    "fifa.friendly",        # International Friendlies
    "conmebol.america",     # Copa America
    "uefa.euro",            # Euros
]

class HighlightMoment:
    def __init__(self, minute: int, added_time: int, moment_type: str, player: str, details: str, expected_score_before: str):
        self.minute = minute
        self.added_time = added_time
        self.moment_type = moment_type
        self.player = player
        self.details = details
        self.expected_score_before = expected_score_before

    def __repr__(self):
        added_str = f"+{self.added_time}" if self.added_time else ""
        return f"HighlightMoment({self.minute}'{added_str} {self.moment_type} {self.player})"

    def to_dict(self):
        return {
            "minute": self.minute,
            "added_time": self.added_time,
            "moment_type": self.moment_type,
            "player": self.player,
            "details": self.details,
            "expected_score_before": self.expected_score_before
        }

    @classmethod
    def from_dict(cls, d):
        return cls(
            minute=d.get("minute", 0),
            added_time=d.get("added_time", 0),
            moment_type=d.get("moment_type", "Unknown"),
            player=d.get("player", "Unknown"),
            details=d.get("details", ""),
            expected_score_before=d.get("expected_score_before", "Unknown")
        )

class AmbiguousMatchError(Exception):
    def __init__(self, message, candidates):
        super().__init__(message)
        self.candidates = candidates

def extract_moments_via_ai(commentary_data: list, key_events: list) -> list:
    """Uses Azure OpenAI to extract all goals, red cards, and up to 2 big chances from play-by-play text."""
    if not AZURE_OPENAI_ENDPOINT:
        return []
        
    client = AzureOpenAI(
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        api_key=AZURE_OPENAI_KEY,
        api_version=AZURE_OPENAI_API_VERSION
    )
    
    compressed = []
    
    if commentary_data:
        for item in commentary_data:
            t = item.get('time', {}).get('displayValue', '')
            text = item.get('text', '')
            if t and text:
                compressed.append(f"[{t}] {text}")
        compressed.reverse()
    elif key_events:
        for event in key_events:
            t = event.get('clock', {}).get('displayValue', '')
            text = event.get('text', '')
            etype = event.get('type', {}).get('text', '')
            if t and text:
                compressed.append(f"[{t}] {etype}: {text}")
                
    if not compressed:
        return []
        
    commentary_str = "\n".join(compressed)
    
    system_prompt = """
    You are an expert football video editor. Read the provided play-by-play text.
    Extract the following moments in chronological order:
    1. ALL Goals
    2. ALL Red Cards
    3. ALL Saved Shots (goalkeeper saves a shot on target)
    4. ALL Shots on Target by any player
    5. A MAXIMUM of 2 'Big Chances' (e.g. hitting the post, missed penalties, near misses).
    
    Return a JSON object containing a "moments" array. Each item must have:
    - minute (integer, e.g. 45)
    - added_time (integer, default 0. e.g. if 45'+3, this is 3)
    - moment_type (string, EXACTLY one of: 'Goal', 'Red Card', 'SavedShot', 'ShotOnPost', 'Big Chance')
    - player (string, name of the main player involved)
    - details (string, a short sentence describing the moment)
    - score_before (string, e.g. "0-0" or "2-1". The score immediately BEFORE this moment happened)
    """
    
    try:
        response = client.chat.completions.create(
            model=AZURE_OPENAI_DEPLOYMENT,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": commentary_str}
            ],
            max_tokens=4000
        )
        content = json.loads(response.choices[0].message.content)
        return content.get('moments', [])
    except Exception as e:
        print(f"Error extracting moments via AI: {e}")
        return []

def fetch_match_details(game_id: str) -> list[HighlightMoment]:
    """
    Fetches the match summary from ESPN API and parses it into HighlightMoment objects.
    Uses GCS caching to avoid redundant API calls and AI extraction on retries.
    """
    # Check GCS cache first
    from pipeline.caching import get_cache, set_cache
    cache_key = f"espn/game_{game_id}"
    cached = get_cache(cache_key)
    if cached:
        print(f"\n  [ESPN Cache] Loaded {len(cached['moments'])} moments from cache for game {game_id}")
        return [HighlightMoment.from_dict(m) for m in cached["moments"]]
    
    url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/all/summary?event={game_id}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()
    data = response.json()
    
    moments = []
    
    commentary_data = data.get('commentary', [])
    key_events = data.get('keyEvents', [])
    
    print("\n  Extracting all moments (Goals, Cards, Shots, Big Chances) via AI from commentary...")
    ai_moments = extract_moments_via_ai(commentary_data, key_events)
    
    for m_dict in ai_moments:
        moment = HighlightMoment(
            minute=m_dict.get('minute', 0),
            added_time=m_dict.get('added_time', 0),
            moment_type=m_dict.get('moment_type', 'Unknown'),
            player=m_dict.get('player', 'Unknown'),
            details=m_dict.get('details', ''),
            expected_score_before=m_dict.get('score_before', 'Unknown')
        )
        moments.append(moment)

    # Sort moments chronologically
    moments.sort(key=lambda x: (x.minute, x.added_time))
    
    # Save to GCS cache for future retries
    set_cache(cache_key, {"moments": [m.to_dict() for m in moments]})
    
    return moments

def validate_match(game_id: str, target_score: str = None, target_year: str = None, team_tokens: list = None) -> tuple[bool, str, str]:
    """Check if a Game ID matches the expected score, year, and teams."""
    url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/all/summary?event={game_id}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    try:
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code != 200:
            return False, None, None
        
        data = response.json()
        header = data.get('header', {}).get('competitions', [{}])[0]
        competitors = header.get('competitors', [])
        match_date = header.get('date', '')
        
        scores = []
        team_names = []
        for team in competitors:
            scores.append(str(team.get('score', 0)))
            team_names.append(team.get('team', {}).get('displayName', ''))
            
        match_name = " vs ".join(team_names)
        
        # Check score matches
        if target_score:
            h_score, a_score = scores[0], scores[1]
            match_score = f"{h_score}-{a_score}"
            match_score_rev = f"{a_score}-{h_score}"
            
            if match_score != target_score and match_score_rev != target_score:
                print(f"    ID {game_id}: {match_name} {scores[0]}-{scores[1]} — score mismatch ✗")
                return False, None, None
            
        # Check teams if provided
        if team_tokens:
            match_name_lower = match_name.lower()
            aliases = {
                "usa": "united states",
                "us": "united states",
                "uk": "england",
                "uae": "united arab emirates"
            }
            for team in team_tokens:
                team_lower = team.lower()
                alias = aliases.get(team_lower, team_lower)
                # Check both the raw token and its alias
                if team_lower not in match_name_lower and alias not in match_name_lower:
                    print(f"    ID {game_id}: {match_name} {scores[0]}-{scores[1]} — team mismatch ('{team}' missing) ✗")
                    return False, None, None
        
        # Check year if provided
        if target_year:
            if match_date and str(target_year) not in match_date:
                print(f"    ID {game_id}: {match_name} {scores[0]}-{scores[1]} — year mismatch ({match_date[:4]} ≠ {target_year}) ✗")
                return False, None, None
        
        return True, match_date, match_name
    except Exception as e:
        print(f"    ID {game_id}: Error during validation: {e}")
        return False, None, None

def search_espn_scoreboard(date_str: str, team_tokens: list) -> str:
    """Strategy 1: Search ESPN scoreboard by exact date."""
    print(f"\n[Strategy 1] Searching ESPN Scoreboards for date: {date_str}")
    url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/all/scoreboard?dates={date_str}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        for event in data.get('events', []):
            name = event.get('name', '').lower()
            
            # Check if all team tokens match
            if all(t.lower() in name for t in team_tokens):
                game_id = event.get('id')
                print(f"  [✓] FOUND: {event.get('name')} (ID: {game_id}) in {event.get('season', {}).get('slug', 'unknown')}")
                return game_id
    except Exception as e:
        print(f"  [!] Scoreboard search error: {e}")
        
    return None

def _normalize(name):
    """Normalize a team name for fuzzy matching."""
    return name.lower().strip().replace(".", "").replace("-", " ")

def search_team_schedule(team_tokens: list, target_score: str = None, target_year: str = None) -> str:
    """Strategy 2.5: Find team on ESPN API, then search their schedule."""
    print("\n[Strategy 2.5] Searching ESPN Team Schedule API...")
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    first_team = team_tokens[0] if team_tokens else ""
    second_team = team_tokens[1] if len(team_tokens) > 1 else ""
    
    for slug in COMPETITION_SLUGS:
        teams_url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{slug}/teams"
        try:
            response = requests.get(teams_url, headers=headers, timeout=5)
            if response.status_code != 200:
                continue
            
            data = response.json()
            teams = data.get('sports', [{}])[0].get('leagues', [{}])[0].get('teams', [])
            
            for team_entry in teams:
                team = team_entry.get('team', {})
                team_name = _normalize(team.get('displayName', ''))
                team_short = _normalize(team.get('shortDisplayName', ''))
                team_abbr = _normalize(team.get('abbreviation', ''))
                
                if _normalize(first_team) in team_name or _normalize(first_team) == team_abbr or _normalize(first_team) in team_short:
                    team_id = team.get('id')
                    print(f"  Found team: {team.get('displayName')} (ID: {team_id}) in {slug}")
                    
                    # Now get their schedule
                    schedule_url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{slug}/teams/{team_id}/schedule"
                    if target_year:
                        # Attempt to query historical season
                        schedule_url += f"?season={target_year}"
                        
                    sched_resp = requests.get(schedule_url, headers=headers, timeout=5)
                    if sched_resp.status_code != 200:
                        continue
                    
                    sched_data = sched_resp.json()
                    events = sched_data.get('events', [])
                    
                    for event in events:
                        event_name = _normalize(event.get('name', ''))
                        event_short = _normalize(event.get('shortName', ''))
                        
                        if second_team and (_normalize(second_team) in event_name or _normalize(second_team) in event_short):
                            game_id = event.get('id')
                            
                            # Validate match before returning!
                            is_valid, m_date, m_name = validate_match(game_id, target_score, target_year, team_tokens)
                            if is_valid:
                                print(f"  [✓] VALIDATED via Schedule: {m_name} on {m_date[:10]} (ID: {game_id})")
                                return game_id
                    
        except:
            continue
    
    print("  [-] Team not found or no matching opponent in schedule.")
    return None

def search_google_locator(query: str, target_score: str = None, target_year: str = None, team_tokens: list = None) -> str:
    """Strategy 2: Search via Brave API and extract Game IDs."""
    import os
    
    search_query = f"site:espn.com {query}"
    api_key = os.getenv("BRAVE_SEARCH_API_KEY")
    url = "https://api.search.brave.com/res/v1/web/search"
    
    print(f"  [Strategy 2] Calling Brave API for: '{search_query}'")
    try:
        res = requests.get(
            url,
            headers={"Accept": "application/json", "X-Subscription-Token": api_key},
            params={"q": search_query, "count": 10},
            timeout=10
        )
        all_ids = []
        if res.status_code == 200:
            results = res.json().get("web", {}).get("results", [])
            for r in results:
                href = r.get("url", "")
                if "espn.com" in href and "gameId" in href:
                    id_match = re.search(r'gameId/(\d+)', href) or re.search(r'gameId=(\d+)', href)
                    if id_match and id_match.group(1) not in all_ids:
                        all_ids.append(id_match.group(1))
        else:
            print(f"  [!] Brave API Error: {res.status_code}")
            
        if not all_ids:
            print("  [-] No ESPN Game IDs found via Brave API.")
            return None
            
        print(f"  Found {len(all_ids)} candidate Game IDs: {all_ids}")
            
        valid_candidates = []
        for gid in all_ids:
            is_valid, match_date, match_name = validate_match(gid, target_score, target_year, team_tokens)
            if is_valid:
                valid_candidates.append({
                    "id": str(gid),
                    "name": match_name,
                    "date": match_date[:10] if match_date else "Unknown"
                })
        
        if not valid_candidates:
            print("  [-] None of the candidates matched the validation criteria.")
            return None
        elif len(valid_candidates) == 1:
            cand = valid_candidates[0]
            print(f"  [✓] VALIDATED: {cand['name']} on {cand['date']} (ID {cand['id']})")
            return cand['id']
        else:
            raise AmbiguousMatchError(
                "Found multiple valid matches. Please select one.",
                candidates=valid_candidates
            )
            
    except AmbiguousMatchError:
        raise
    except Exception as e:
        print(f"  [!] DuckDuckGo Search error: {e}")
        
    return None
