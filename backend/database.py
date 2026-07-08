import os
import requests
import datetime
from google.cloud import firestore
from google.oauth2 import service_account

# Supabase Credentials loaded from config
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

# Initialize Firestore
def get_firestore_client():
    sa_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gcp-credentials.json")
    if os.path.exists(sa_path):
        credentials = service_account.Credentials.from_service_account_file(sa_path)
        return firestore.Client(credentials=credentials, project="tuc-ai-prod")
    return firestore.Client(project="tuc-ai-prod")

db = get_firestore_client()

def get_headers(token: str = None):
    """Generates standard Supabase request headers."""
    return {
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {token if token else SUPABASE_ANON_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
        "Connection": "close"
    }

# ─────────────────────────────────────────────────────────────
# 1. CHAT SESSIONS PERSISTENCE (FIRESTORE)
# ─────────────────────────────────────────────────────────────

def get_user_sessions(user_id: str, token: str = None) -> list:
    """Retrieves all chat sessions (metadata only) for a user from Firestore."""
    sessions_ref = db.collection('sessions').where('user_id', '==', user_id).stream()
    sessions = []
    for doc in sessions_ref:
        s = doc.to_dict()
        s['id'] = doc.id
        sessions.append(s)
    return sessions

def create_session(session_id: str, user_id: str, data: dict):
    """Creates a new session document."""
    data['user_id'] = user_id
    if 'created_at' not in data:
        data['created_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    data['updated_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    db.collection('sessions').document(session_id).set(data)

def update_session_metadata(session_id: str, data: dict):
    """Updates session metadata."""
    data['updated_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    db.collection('sessions').document(session_id).update(data)

def add_message(session_id: str, message: dict):
    """Appends a single message to a session's messages subcollection."""
    if 'timestamp' not in message:
        message['timestamp'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    db.collection('sessions').document(session_id).collection('messages').add(message)

def get_session_details(session_id: str) -> dict:
    """Retrieves a session and all its messages."""
    session_doc = db.collection('sessions').document(session_id).get()
    if not session_doc.exists:
        return None
    session_data = session_doc.to_dict()
    session_data['id'] = session_doc.id

    messages_ref = db.collection('sessions').document(session_id).collection('messages').order_by('timestamp').stream()
    messages = []
    for m in messages_ref:
        m_dict = m.to_dict()
        m_dict['id'] = m.id
        messages.append(m_dict)
    
    session_data['messages'] = messages
    return session_data

def delete_session(session_id: str):
    """Deletes a session and its messages."""
    session_ref = db.collection('sessions').document(session_id)
    # Delete messages subcollection
    messages = session_ref.collection('messages').stream()
    for m in messages:
        m.reference.delete()
    # Delete the session document
    session_ref.delete()

# ─────────────────────────────────────────────────────────────
# 2. HIGHLIGHT PROJECTS & TIMELINE STATE (FIRESTORE)
# ─────────────────────────────────────────────────────────────

def get_highlight_project(project_id: str, token: str = None) -> dict:
    """Fetches a project status, offsets, index, and timeline state from Firestore."""
    doc = db.collection('projects').document(project_id).get()
    if doc.exists:
        data = doc.to_dict()
        data['id'] = doc.id
        return data
    return None

def save_highlight_project(
    project_id: str,
    user_id: str,
    match_name: str,
    video_storage_path: str,
    timeline_state: list,
    status: str = 'processing',
    current_moment_index: int = 0,
    total_moments: int = None,
    stage_message: str = None,
    video_url: str = None,
    video_offset_half_1: int = None,
    video_offset_half_2: int = None,
    last_error_log: str = None,
    token: str = None
):
    """Saves or updates a project's editing session and AI checkpoints in Firestore."""
    body = {
        "user_id": user_id,
        "match_name": match_name,
        "video_storage_path": video_storage_path,
        "timeline_state": timeline_state,
        "status": status,
        "current_moment_index": current_moment_index,
        "total_moments": total_moments,
        "stage_message": stage_message,
        "video_url": video_url,
        "video_offset_half_1": video_offset_half_1,
        "video_offset_half_2": video_offset_half_2,
        "last_error_log": last_error_log,
        "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
    }
    # Remove None values so we don't overwrite with nulls unnecessarily if we're merging
    body = {k: v for k, v in body.items() if v is not None}
    
    db.collection('projects').document(project_id).set(body, merge=True)
    return True

def update_project_status(project_id: str, status: str, current_moment_index: int = None, 
                          total_moments: int = None, stage_message: str = None,
                          timeline_state: list = None, video_url: str = None,
                           last_error_log: str = None, token: str = None):
    """Lightweight status update for real-time progress tracking in Firestore."""
    body = {"status": status, "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat()}
    if current_moment_index is not None:
        body["current_moment_index"] = current_moment_index
    if total_moments is not None:
        body["total_moments"] = total_moments  
    if stage_message is not None:
        body["stage_message"] = stage_message
    if timeline_state is not None:
        body["timeline_state"] = timeline_state
    if video_url is not None:
        body["video_url"] = video_url
    if last_error_log is not None:
        body["last_error_log"] = last_error_log

    # Firestore handles updates efficiently without token/service_role complexity
    db.collection('projects').document(project_id).update(body)
    return True

def delete_highlight_project(project_id: str, token: str = None) -> bool:
    """Deletes a highlight project from Firestore."""
    db.collection('projects').document(project_id).delete()
    return True

def get_projects_by_ids(project_ids: list):
    """Batch fetches projects by IDs."""
    if not project_ids:
        return []
    # Firestore 'in' query supports up to 30 items
    projects = []
    # Chunk by 30 if needed
    for i in range(0, len(project_ids), 30):
        chunk = project_ids[i:i+30]
        docs = db.collection('projects').where('__name__', 'in', chunk).stream()
        for doc in docs:
            p = doc.to_dict()
            p['id'] = doc.id
            projects.append(p)
    return projects

# ─────────────────────────────────────────────────────────────
# 3. CALIBRATION OFFSETS CACHE (FIRESTORE)
# ─────────────────────────────────────────────────────────────

def get_cached_offsets(user_id: str, video_filename: str) -> dict:
    """Retrieves cached Half 1 & Half 2 offsets from Firestore."""
    doc_id = f"{user_id}_{video_filename}".replace("/", "_")
    doc = db.collection('calibration_offsets').document(doc_id).get()
    if doc.exists:
        return doc.to_dict()
    return None

def cache_calibration_offsets(user_id: str, video_filename: str, half_1_offset: int, half_2_offset: int):
    """Caches calculated offsets in Firestore to prevent redundant scoreboard parsing."""
    doc_id = f"{user_id}_{video_filename}".replace("/", "_")
    body = {
        "user_id": user_id,
        "video_filename": video_filename,
        "half_1_offset": half_1_offset,
        "half_2_offset": half_2_offset
    }
    db.collection('calibration_offsets').document(doc_id).set(body)

# ─────────────────────────────────────────────────────────────
# 4. SUBSCRIPTIONS & BILLING (SUPABASE - UNCHANGED)
# ─────────────────────────────────────────────────────────────

def get_user_subscription(user_id: str, token: str = None) -> dict:
    """Fetches user subscription tier and usage limits."""
    if not SUPABASE_URL:
        return {"plan_tier": "PRO", "player_highlights_used": 0, "free_videos_used": 0}
        
    url = f"{SUPABASE_URL}/rest/v1/user_subscriptions?user_id=eq.{user_id}"
    try:
        response = requests.get(url, headers=get_headers(token))
        if response.status_code == 200:
            data = response.json()
            if data:
                return data[0]
    except Exception as e:
        print(f"Error fetching subscription: {e}")
        
    return {"plan_tier": "FREE", "player_highlights_used": 0, "free_videos_used": 0}

def update_subscription_usage(user_id: str, updates: dict, token: str = None):
    """Updates user usage metrics (e.g., player_highlights_used + 1)."""
    if not SUPABASE_URL:
        return
        
    url = f"{SUPABASE_URL}/rest/v1/user_subscriptions?user_id=eq.{user_id}"
    try:
        requests.patch(url, headers=get_headers(token), json=updates)
    except Exception as e:
        print(f"Error updating subscription usage: {e}")

def update_subscription_tier_admin(user_id: str, plan_tier: str, provider: str = None, external_id: str = None):
    """Updates user subscription tier from a webhook (requires service role key)."""
    SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not SUPABASE_URL or not SERVICE_ROLE_KEY:
        print("Missing SUPABASE_SERVICE_ROLE_KEY for webhook updates.")
        return False
        
    url = f"{SUPABASE_URL}/rest/v1/user_subscriptions?user_id=eq.{user_id}"
    headers = {
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }
    
    updates = {
        "plan_tier": plan_tier,
        "provider": provider,
        "external_subscription_id": external_id
    }
    
    try:
        response = requests.patch(url, headers=headers, json=updates)
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"Error updating subscription tier via admin: {e}")
        return False
