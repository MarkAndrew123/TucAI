import re
import json
import time
import os
import unicodedata
from curl_cffi import requests as cffi_requests

from pipeline.espn import HighlightMoment, AmbiguousMatchError

class PlayerNotFoundError(Exception):
    def __init__(self, message, candidates=None):
        super().__init__(message)
        self.message = message
        self.candidates = candidates or []

def normalize_name(s):
    s = ''.join(c for c in unicodedata.normalize('NFD', str(s)) if unicodedata.category(c) != 'Mn').lower()
    s = re.sub(r'[^\w\s]', ' ', s)
    return ' '.join(s.split())

def search_and_extract_whoscored(match_name: str, year: str, player_target: str) -> list[HighlightMoment]:
    query = f"{match_name} {year}" if year else match_name
    
    cache_file = "match_url_cache.json"
    whoscored_url = None
    
    url_match = re.search(r'id:?\s*(https?://[^\s\)]+)', query, re.IGNORECASE)
    if url_match:
        whoscored_url = url_match.group(1)
        print(f"\n[DIRECT URL] User provided explicit WhoScored URL: {whoscored_url}")
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                cache = json.load(f)
                if query in cache:
                    whoscored_url = cache[query]
                    print(f"\n[CACHE HIT] Skipped Google. Found URL for '{query}': {whoscored_url}")
        except:
            pass

    moments = []
    
    proxies = {
        "http": "http://wbceapdy:87497syjdt71@82.23.72.77:5835",
        "https": "http://wbceapdy:87497syjdt71@82.23.72.77:5835"
    }


    if not whoscored_url:
        import requests
        api_key = os.getenv("BRAVE_SEARCH_API_KEY")
        print("\n[1] Calling Brave Search API to find match URL...")
        try:
            res = requests.get(
                "https://api.search.brave.com/res/v1/web/search",
                headers={"Accept": "application/json", "X-Subscription-Token": api_key},
                params={"q": f"site:whoscored.com {query}", "count": 10},
                timeout=15
            )
            if res.status_code == 200:
                results = res.json().get("web", {}).get("results", [])
                candidates = []
                seen_match_ids = set()
                
                for r in results:
                    href = r.get("url", "")
                    if "whoscored.com/Matches/" in href or "whoscored.com/matches/" in href.lower():
                        match_id_search = re.search(r'/[Mm]atches/(\d+)', href)
                        if not match_id_search:
                            continue
                        match_id = match_id_search.group(1)
                        if match_id in seen_match_ids:
                            continue
                        seen_match_ids.add(match_id)
                        
                        title = r.get("title", f"Match {match_id}")
                        live_url = f"https://www.whoscored.com/Matches/{match_id}/Live/"
                        candidates.append({"title": title, "url": live_url, "match_id": match_id})
                        print(f"  - Found Candidate: {title} ({live_url})")
            else:
                print(f"  ✗ Brave API Error: {res.status_code} - {res.text}")
                candidates = []
        except Exception as e:
            print(f"  ✗ Brave API Exception: {e}")
            candidates = []
            
        if not candidates:
            print("  ✗ Could not find any WhoScored match URLs via Brave API.")
            return []

        # 2. VALIDATION
        if len(candidates) == 1:
            whoscored_url = candidates[0]["url"]
            print(f"\n  ✓ Only one match found. Using: {candidates[0]['title']}")
        else:
            normalized_query = normalize_name(query)
            exact_matches = []
            for c in candidates:
                normalized_title = normalize_name(c["title"])
                query_words = normalized_query.split()
                if all(word in normalized_title for word in query_words if len(word) > 2):
                    exact_matches.append(c)
            
            if len(exact_matches) == 1:
                whoscored_url = exact_matches[0]["url"]
                print(f"\n  ✓ Auto-matched: {exact_matches[0]['title']}")
            else:
                options_to_show = exact_matches if len(exact_matches) > 1 else candidates
                print(f"\n  ⚠ Found {len(options_to_show)} matches that fit '{query}'.")
                candidate_list = [{"name": c["title"], "id": c["url"]} for c in options_to_show]
                raise AmbiguousMatchError(
                    f"Found {len(options_to_show)} matches for '{query}'. Which one did you mean?",
                    candidate_list
                )
        
        # Save to cache
        try:
            cache = {}
            if os.path.exists(cache_file):
                with open(cache_file, "r", encoding="utf-8") as f:
                    cache = json.load(f)
            
            cache[query] = whoscored_url
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(cache, f)
        except:
            pass

    # 2. Scrape WhoScored Page
    print(f"\n[2] Navigating to WhoScored via curl_cffi (Chrome TLS): {whoscored_url}")
    html = None
    for attempt in range(3):
        try:
            response = cffi_requests.get(
                whoscored_url, 
                proxies=proxies, 
                timeout=20,
                impersonate="chrome"
            )
            html = response.text
            print(f"  [DEBUG] Attempt {attempt+1} - Status: {response.status_code}, HTML length: {len(html)}")
            if response.status_code == 200 and 'matchCentreData' in html:
                break
            if response.status_code == 403:
                print(f"  [DEBUG] 403 blocked on attempt {attempt+1}, retrying...")
                time.sleep(2)
                html = None
                continue
        except Exception as e:
            print(f"  ✗ curl_cffi Error (attempt {attempt+1}): {e}")
            time.sleep(2)
    
    if not html:
        print("  ✗ All attempts to fetch WhoScored failed.")
        return []
        
    match = re.search(r'matchCentreData:\s*({.*?}),\s*matchCentreEventTypeJson', html, re.DOTALL)
    if not match:
        print("  ✗ Could not find 'matchCentreData' in the HTML.")
        title_match = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE)
        if title_match:
            print(f"  [DEBUG] Page title: {title_match.group(1)}")
        print(f"  [DEBUG] First 500 chars: {html[:500]}")
        return []
        
    data = json.loads(match.group(1))
    
    # 2.5 STRICT MATCH VALIDATION
    home_team = data.get('home', {}).get('name', '')
    away_team = data.get('away', {}).get('name', '')
    
    home_norm = normalize_name(home_team)
    away_norm = normalize_name(away_team)
    match_str = f"{home_norm} {away_norm}"
    
    query_words = normalize_name(match_name).split()
    for word in query_words:
        if word == 'vs' or len(word) <= 2: continue
        if word not in match_str:
            print(f"  ✗ MATCH VALIDATION FAILED: You asked for '{match_name}', but WhoScored only had '{home_team} vs {away_team}'.")
            print("  ✗ This means WhoScored does NOT have data for this specific match. Falling back...")
            return []
    
    # 3. Find Player (Robust Tokenized Matching with Initials Support)
    name_dict = data.get('playerIdNameDictionary', {})
    normalized_target = normalize_name(player_target)
    target_tokens = set(normalized_target.split())
    
    matched_players = []
    for pid, name in name_dict.items():
        norm_name = normalize_name(name)
        name_tokens = set(norm_name.split())
        
        # Check if all target tokens match a name token (handling initials)
        is_match = True
        for t_token in target_tokens:
            token_matched = False
            for n_token in name_tokens:
                if t_token == n_token or (len(t_token) == 1 and n_token.startswith(t_token)):
                    token_matched = True
                    break
            if not token_matched:
                is_match = False
                break
                
        if is_match or normalized_target in norm_name:
            matched_players.append((int(pid), name))
            
    if not matched_players:
        raise PlayerNotFoundError(f"I couldn't find anyone named '{player_target}' in this match.")
    elif len(matched_players) > 1:
        names = [m[1] for m in matched_players]
        names_str = " or ".join([f"'{n}'" for n in names])
        raise PlayerNotFoundError(f"I found multiple players matching '{player_target}' ({names_str}). Could you specify which one you meant?", candidates=names)
    else:
        player_id, player_name = matched_players[0]
        print(f"\n[3] Found Player: {player_name} (ID: {player_id})")
        
    # 3.5 Find Jersey Number
    jersey_number = None
    for team in ['home', 'away']:
        players = data.get(team, {}).get('players', [])
        for p in players:
            if p.get('playerId') == player_id:
                jersey_number = p.get('shirtNo')
                break
        if jersey_number:
            break
            
    if jersey_number:
        print(f"  ✓ Automatically detected Jersey Number: #{jersey_number}")
        
    # 4. Extract Touches
    events = data.get('events', [])
    for event in events:
        if event.get('playerId') == player_id:
            raw_minute = event.get('minute', 0)
            second = event.get('second', 0)
            period = event.get('period', {}).get('value', 1)
            event_type = event.get('type', {}).get('displayName', 'Unknown')
            
            minute = raw_minute
            added_time = 0
            
            # Handle injury time logic cleanly based on period
            if period == 1:
                if minute >= 45:
                    added_time = minute - 45
                    minute = 45
            elif period == 2:
                if minute < 46:
                    minute = 46  # Second half starts at 46' to avoid overlap with 1st half
                    added_time = 0
                elif minute >= 90:
                    added_time = minute - 90
                    minute = 90
            elif period == 3:
                if minute < 91:
                    minute = 91
                elif minute >= 105:
                    added_time = minute - 105
                    minute = 105
            elif period == 4:
                if minute < 106:
                    minute = 106
                elif minute >= 120:
                    added_time = minute - 120
                    minute = 120
            
            moment_type = event_type
            if 'Goal' in event_type:
                moment_type = "Goal"
            elif 'Shot' in event_type:
                moment_type = "Big Chance"
                
            details = f"Exact Second: {(raw_minute * 60) + second}. Event: {event_type}"
            if jersey_number:
                details += f". Jersey Number: {jersey_number}"
                
            m = HighlightMoment(
                minute=minute,
                added_time=added_time,
                moment_type=moment_type,
                player=player_target,
                details=details,
                expected_score_before="Unknown"
            )
            # sort_key must ensure 2nd half comes AFTER 1st half for sorting
            # We add an artificial bump for period to guarantee chronological sort
            m.absolute_seconds = (raw_minute * 60) + second
            m.sort_key = (period * 10000) + m.absolute_seconds
            m.match_seconds = (minute * 60) + (added_time * 60) + second # True match time for offset math
            moments.append(m)
            
    if not moments:
        raise PlayerNotFoundError(f"I found '{player_name}', but they didn't have any recorded touches.")
        
    return moments

def _gcs_cache_key(match_name, year, player_target):
    """Generate a GCS cache key for player touch data."""
    safe = re.sub(r'[^\w\-]', '_', f"{match_name}_{year}_{player_target}").lower()
    return f"whoscored/{safe}"

def _serialize_moments(moments):
    """Serialize moments to a list of dicts for caching."""
    data = []
    for m in moments:
        data.append({
            "minute": m.minute,
            "added_time": m.added_time,
            "moment_type": m.moment_type,
            "player": m.player,
            "details": m.details,
            "expected_score_before": m.expected_score_before,
            "absolute_seconds": getattr(m, 'absolute_seconds', m.minute * 60),
            "sort_key": getattr(m, 'sort_key', getattr(m, 'absolute_seconds', m.minute * 60))
        })
    return data

def _deserialize_moments(data):
    """Load moments from cached dicts."""
    moments = []
    for d in data:
        m = HighlightMoment(
            minute=d["minute"],
            added_time=d["added_time"],
            moment_type=d["moment_type"],
            player=d["player"],
            details=d["details"],
            expected_score_before=d["expected_score_before"]
        )
        raw_abs = d.get("absolute_seconds", m.minute * 60)
        # Sanitize poisoned caches where absolute_seconds was artificially bloated by period * 10000
        m.absolute_seconds = raw_abs % 10000 if raw_abs >= 10000 else raw_abs
        m.sort_key = d.get("sort_key", raw_abs)
        moments.append(m)
    return moments

def fetch_player_touches(match_name: str, year: str, player_target: str) -> list[HighlightMoment]:
    """Public function to wrap the subprocess lifecycle. Uses GCS cache when available."""
    from pipeline.caching import get_cache, set_cache
    
    cache_key = _gcs_cache_key(match_name, year, player_target)
    cached = get_cache(cache_key)
    if cached:
        print(f"\n  ⚡ GCS CACHE HIT — Loading {len(cached['moments'])} touches from cloud cache")
        return _deserialize_moments(cached["moments"])

    moments = []
    try:
        moments = search_and_extract_whoscored(match_name, year, player_target)
        if moments:
            set_cache(cache_key, {"moments": _serialize_moments(moments)})
    except (AmbiguousMatchError, PlayerNotFoundError) as e:
        print(f"Conversational pushback: {e}")
        raise
    except Exception as e:
        print(f"Error extracting WhoScored data: {e}")
            
    return moments
