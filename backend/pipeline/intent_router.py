import json
from openai import AzureOpenAI
from config import AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_KEY, AZURE_OPENAI_DEPLOYMENT, AZURE_OPENAI_API_VERSION

def classify_intent(chat_history: list, has_video: bool, forced_mode: str = None, 
                    known_match: str = None, known_year: str = None, known_player: str = None) -> dict:
    """
    Analyzes the conversation history to determine the user's intent.
    """
    client = AzureOpenAI(
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        api_key=AZURE_OPENAI_KEY,
        api_version=AZURE_OPENAI_API_VERSION
    )
    
    mode_instruction = ""
    if forced_mode == "general":
        mode_instruction = "The user has explicitly selected GENERAL_HIGHLIGHT mode. You MUST classify the intent as GENERAL_HIGHLIGHT (or CONVERSATION if match/year is missing). Do not use PLAYER_FOCUS."
    elif forced_mode == "player":
        mode_instruction = "The user has explicitly selected PLAYER_FOCUS mode. You MUST classify the intent as PLAYER_FOCUS (or CONVERSATION if match, year, or player name is missing). Do not use GENERAL_HIGHLIGHT."
    
    system_prompt = f"""
    You are the "Intent Router" for an AI sports video editor.
    Your job is to read the user's conversation history and determine if you have enough information to start processing a video, or if you just need to reply conversationally.
    
    Currently Known Information (Do NOT ask for these again):
    - Video Uploaded: {has_video}
    - Match Name: {known_match or "Missing"}
    - Year: {known_year or "Missing"}
    - Player Name: {known_player or "Missing"}
    
    {mode_instruction}
    
    To process a video, we MUST have:
    1. A video uploaded (HAS_UPLOADED_A_VIDEO must be True).
    2. The full match details (BOTH teams).
    3. The year of the match.
    4. If they want a player focus, the specific player's name.
    
    CRITICAL REASONING: Use your common sense and general knowledge of football. If the user provides a format like "X vs Y", intelligently evaluate whether X and Y are both actual football teams. If one of them is clearly a person's name, extract it as the player_name and realize you only have ONE team! Do not blindly assume anything in an "X vs Y" format is a complete match name.

    Categorize the intent as one of the following:
    - "CONVERSATION": Use this if you are just chatting, OR if you still need more information from the user (like the match name, year, player name, or video upload).
    - "EDIT_COMMAND": The user explicitly wants to tweak/modify an ALREADY EXISTING timeline (e.g., "make the first clip shorter", "remove the second goal"). Do NOT use this for starting a new match.
    - "GENERAL_HIGHLIGHT": You have ALL required information (Video, Teams, Year) AND the user wants standard match highlights.
    - "PLAYER_FOCUS": You have ALL required information (Video, Teams, Year, Player Name) AND the user wants highlights for that specific player.
      
    You must return a raw JSON object with the following structure:
    {{
        "thought_process": "Analyze the conversation using football common sense. Do we have the video, both actual teams, year, and player? If not, the intent is CONVERSATION and I will ask for what's missing.",
        "intent": "CONVERSATION" | "EDIT_COMMAND" | "GENERAL_HIGHLIGHT" | "PLAYER_FOCUS",
        "match_name": "The full Match Name (BOTH teams). Combine the Currently Known Information with any new info from the user. Return null if completely unknown or if only ONE team is known.",
        "year": "The match year. Combine Currently Known Information with any new info. Return null if completely unknown.",
        "player_name": "The target player. Combine Currently Known Information with any new info. Return null if completely unknown.",
        "chat_response": "If intent is CONVERSATION, provide a SINGLE short, natural sentence. E.g., 'What year was that match?' or 'Hi! What match are we editing today?'. Do NOT provide multiple disconnected greetings. If intent is NOT CONVERSATION, set this to null."
    }}
    
    IMPORTANT: Be a smart conversationalist! If the user provides info across multiple messages, read the whole history to piece it together. Once you see ALL the required info in the history, change the intent to GENERAL_HIGHLIGHT or PLAYER_FOCUS. Until then, keep the intent as CONVERSATION.
    """
    
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(chat_history)
    
    try:
        response = client.chat.completions.create(
            model=AZURE_OPENAI_DEPLOYMENT,
            messages=messages,
            max_tokens=300,
            temperature=0.0
        )
        content = response.choices[0].message.content.strip()
        
        # Remove any markdown JSON wrappers just in case
        if content.startswith("```json"):
            content = content[7:]
        if content.endswith("```"):
            content = content[:-3]
            
        return json.loads(content.strip())
        
    except Exception as e:
        print(f"Error classifying intent: {e}")
        # Safe fallback — default to conversation
        return {
            "intent": "CONVERSATION",
            "match_name": None,
            "year": None,
            "player_name": None,
            "chat_response": "Hey! How can I help you with your video editing today?"
        }
