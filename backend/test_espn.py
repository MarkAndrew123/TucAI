import requests
import json

url = 'https://site.api.espn.com/apis/site/v2/sports/soccer/all/summary?event=760511'
headers = {'User-Agent': 'Mozilla/5.0'}
try:
    res = requests.get(url, headers=headers, timeout=10)
    data = res.json()
    commentary = data.get('commentary', [])
    for item in commentary:
        t = item.get('time', {}).get('displayValue', '')
        text = item.get('text', '')
        if 'goal' in text.lower():
            print(f'[{t}] {text}')
except Exception as e:
    print(f"Error: {e}")
