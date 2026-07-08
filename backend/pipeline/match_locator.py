import json
import datetime
from openai import AzureOpenAI
from config import AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_KEY, AZURE_OPENAI_DEPLOYMENT, AZURE_OPENAI_API_VERSION
from . import espn
from .espn import AmbiguousMatchError

def extract_match_params(prompt: str) -> dict:
    if not AZURE_OPENAI_ENDPOINT:
        print("Azure OpenAI endpoint not configured.")
        return {}
        
    client = AzureOpenAI(
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        api_key=AZURE_OPENAI_KEY,
        api_version=AZURE_OPENAI_API_VERSION
    )
    
    system_prompt = """
    Extract the football match details from the user's prompt. 
    Return a JSON object with the following keys exactly:
    - home_team (string or null)
    - away_team (string or null)
    - year (string or null)
    - exact_date (string or null, format YYYYMMDD if a specific month/day is mentioned, else null)
    - score (string or null, e.g. "2-2")
    """
    
    try:
        response = client.chat.completions.create(
            model=AZURE_OPENAI_DEPLOYMENT,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ]
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"Error extracting params: {e}")
        return {}

def locate_exact_match(prompt: str) -> str:
    """Returns the exact ESPN game ID based on the prompt or URL."""
    # 1. Check if the user just pasted an ID directly (e.g. "id:740779" from disambiguation)
    import re
    id_match = re.search(r'id[:=]?(\d+)', prompt.lower())
    if id_match:
        game_id = id_match.group(1)
        print(f"Match locked via raw ID: {game_id}")
        return str(game_id)
        
    # 2. Check if the user pasted an ESPN URL
    # e.g., https://www.espn.com/soccer/match/_/gameId/740779/afc-bournemouth-chelsea
    url_match = re.search(r'gameId[=:/]+(\d+)', prompt)
    if url_match:
        print(f"Match locked via URL Game ID: {url_match.group(1)}")
        return str(url_match.group(1))
        
    # 3. Use LLM extraction to find the match parameters
    params = extract_match_params(prompt)
    if not params:
        raise ValueError("Could not extract match parameters from prompt")
        
    home = params.get('home_team') or ''
    away = params.get('away_team') or ''
    query = f"{home} {away}".strip()
    
    if not query:
        raise ValueError("Could not determine team names from prompt")
        
    team_tokens = [t for t in [home, away] if t]
    target_score = params.get('score')
    target_year = params.get('year')
    exact_date = params.get('exact_date')
    
    print(f"Extracted Params -> Teams: {team_tokens}, Score: {target_score}, Year: {target_year}, Exact Date: {exact_date}")
    
    # 4. Search Strategy 1: Brave Search API Locator (primary)
    game_id = espn.search_google_locator(query, target_score, target_year, team_tokens)
    if game_id:
        return str(game_id)

    # 5. Search Strategy 2: ESPN Scoreboard API (if exact date is known)
    if exact_date:
        game_id = espn.search_espn_scoreboard(exact_date, team_tokens)
        if game_id:
            return str(game_id)
    
    # 6. Search Strategy 3: ESPN Team Schedule API (last resort)
    game_id = espn.search_team_schedule(team_tokens, target_score, target_year)
    if game_id:
        return str(game_id)
        
    raise ValueError("Match not found via ESPN or Google Locator")
