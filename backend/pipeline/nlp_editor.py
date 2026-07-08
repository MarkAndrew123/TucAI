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
    
    When a user says "cut from 0:23 to 1:45" or "remove the clip at 1:10", they are almost always referring to the `rendered_start_time` (the final video they are watching), NOT the original full match!
    
    Your job is to:
    1. Read the user's request.
    2. Figure out if they are referring to the final rendered video timestamps OR the original match.
    3. If they want to REMOVE a clip entirely, DELETE that entire JSON object from the array.
    4. If they want to TRIM/SHORTEN a clip, calculate the new exact original `start` and `end` floats that correspond to their request, and modify them.
    5. Output the UPDATED full timeline JSON. Do not include the `rendered_` helper keys in your output.
    
    Rules:
    1. To remove a clip, completely omit it from the JSON array. Do NOT set its timestamps to 0.0.
    2. To trim a clip, ONLY update the `start` and `end` floats.
    3. Do NOT change IDs, file paths, or the vision_analysis text of the clips you keep.
    4. Return ONLY valid JSON representing the entire updated timeline array. Do not wrap in markdown or backticks.
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
        
        # Try to find JSON array in the response text
        import re
        json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
        if json_match:
            response_text = json_match.group(0)
            
        try:
            updated_timeline = json.loads(response_text)
        except json.JSONDecodeError:
            return "Sorry, I couldn't understand how to apply that edit to the timeline. Could you be more specific about what you want to change?", timeline_data
        
        # Save it locally for dev fallback
        try:
            os.makedirs(OUTPUT_DIR, exist_ok=True)
            with open(timeline_path, "w") as f:
                json.dump(updated_timeline, f, indent=2)
        except Exception:
            pass
            
        return f"Successfully processed edit: '{prompt}'. The timeline has been updated based on your instructions!", updated_timeline
        
    except Exception as e:
        print(f"NLP Editor Error: {e}")
        return "I encountered an error trying to edit the timeline. Please try again.", timeline_data
