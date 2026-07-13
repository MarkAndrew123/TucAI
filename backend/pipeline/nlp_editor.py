import json
import os
from openai import AzureOpenAI
from config import AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_KEY, AZURE_OPENAI_DEPLOYMENT, AZURE_OPENAI_API_VERSION, OUTPUT_DIR

def process_edit_command(prompt: str, timeline_data: list = None) -> tuple[str, list]:
    """
    Passes the timeline data to the LLM with the user's prompt,
    and returns a tuple of (success_message, updated_timeline).
    """
    timeline_path = os.path.join(OUTPUT_DIR, "timeline.json")
    
    if timeline_data is None:
        if not os.path.exists(timeline_path):
            raise FileNotFoundError("timeline.json not found. You must generate a highlight reel first before editing it.")
            
        with open(timeline_path, "r") as f:
            timeline_data = json.load(f)
            
    # Calculate the rendered timestamps for the LLM to understand relative edits
    enriched_timeline = []
    current_render_time = 0.0
    for clip in timeline_data:
        # Create a copy so we don't accidentally mutate the original data permanently if the LLM messes up
        enriched_clip = dict(clip)
        clip_duration = clip['end'] - clip['start']
        enriched_clip['rendered_start_time'] = round(current_render_time, 2)
        enriched_clip['rendered_end_time'] = round(current_render_time + clip_duration, 2)
        enriched_timeline.append(enriched_clip)
        current_render_time += clip_duration
            
    client = AzureOpenAI(
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        api_key=AZURE_OPENAI_KEY,
        api_version=AZURE_OPENAI_API_VERSION
    )
    
    system_prompt = """
    You are an expert video editor AI managing a football highlight reel.
    You will receive the current `timeline.json` representing the video clips, and a user's natural language edit command.
    
    The timeline JSON contains blocks with `id`, `start` (timestamp in the ORIGINAL full match video), `end` (in the ORIGINAL full match), and `vision_analysis`.
    CRITICALLY: It also contains `rendered_start_time` and `rendered_end_time`. These represent exactly where this clip appears in the FINAL EXPORTED HIGHLIGHT REEL that the user is currently watching.
    
    Your job is to translate the user's request into a list of specific mutations to apply to the timeline.
    
    If the user says "remove the first 3 minutes of the video", they mean the rendered highlight reel! You must find ALL clips where `rendered_start_time` < 180.0, and issue a "remove" action for each of their IDs.
    If they say "add 30 seconds to the beginning of the first goal", you find the clip representing the goal, and issue an "update" action with a new `start` value that is 30 seconds EARLIER than its current `start` (e.g., if start is 429, new_start is 399).
    
    You must output ONLY a valid JSON object containing a "mutations" array. Do not output anything else.
    Format:
    {
      "mutations": [
        {"action": "remove", "id": "moment_0_clip_0"},
        {"action": "update", "id": "moment_3_clip_0", "new_start": 399, "new_end": 444}
      ]
    }
    """
    
    user_content = f"""
    CURRENT TIMELINE JSON:
    {json.dumps(enriched_timeline, indent=2)}
    
    USER EDIT COMMAND:
    "{prompt}"
    """
    
    try:
        response = client.chat.completions.create(
            model=AZURE_OPENAI_DEPLOYMENT,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            temperature=0.0
        )
        
        response_text = response.choices[0].message.content.strip()
        
        # Try to extract JSON object
        import re
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            response_text = json_match.group(0)
            
        try:
            mutations_data = json.loads(response_text)
            mutations = mutations_data.get("mutations", [])
        except json.JSONDecodeError:
            return "Sorry, I couldn't understand how to apply that edit. Could you be more specific?", timeline_data
            
        # Apply mutations deterministically
        updated_timeline = []
        for clip in timeline_data:
            clip_id = clip['id']
            # Check if this clip has a mutation
            mutation = next((m for m in mutations if m['id'] == clip_id), None)
            
            if mutation:
                if mutation['action'] == 'remove':
                    continue # Skip adding it to the new timeline
                elif mutation['action'] == 'update':
                    clip['start'] = mutation.get('new_start', clip['start'])
                    clip['end'] = mutation.get('new_end', clip['end'])
                    updated_timeline.append(clip)
            else:
                updated_timeline.append(clip)
        
        # Save it locally for dev fallback
        try:
            os.makedirs(OUTPUT_DIR, exist_ok=True)
            with open(timeline_path, "w") as f:
                json.dump(updated_timeline, f, indent=2)
        except Exception:
            pass
            
        return f"Successfully processed edit: '{prompt}'.", updated_timeline
        
    except Exception as e:
        print(f"NLP Editor Error: {e}")
        return "I encountered an error trying to edit the timeline. Please try again.", timeline_data
