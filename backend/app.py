from fastapi import FastAPI, UploadFile, File, Form, Request, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import json
import uuid
import requests

from config import UPLOAD_DIR, OUTPUT_DIR

app = FastAPI(title="Football Highlights API")

# Setup CORS for the React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow frontend origin in production
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

from fastapi.staticfiles import StaticFiles
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/outputs", StaticFiles(directory=OUTPUT_DIR), name="outputs")
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


import shutil
from pipeline.orchestrator import HighlightPipeline
from pipeline import espn
from pipeline.whoscored import PlayerNotFoundError

pipeline = HighlightPipeline(OUTPUT_DIR)

import database

import database
import uuid
import datetime

def get_or_create_session(user_id: str, token: str = None, session_id: str = None, default_title: str = "New Session", match_name: str = None, player_name: str = None, year: str = None, video_path: str = None):
    if session_id:
        existing = database.get_session_details(session_id)
        if existing:
            return session_id
            
    session_id = session_id or str(uuid.uuid4())
    data = {
        "title": default_title,
        "project_ids": [],
    }
    if match_name: data["match_name"] = match_name
    if player_name: data["player_name"] = player_name
    if year: data["year"] = year
    if video_path: data["video_path"] = video_path
        
    database.create_session(session_id, user_id, data)
    return session_id


def verify_supabase_token(token: str) -> dict:
    from config import SUPABASE_URL, SUPABASE_ANON_KEY
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        return None
    url = f"{SUPABASE_URL}/auth/v1/user"
    headers = {
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {token}"
    }
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.json()
    except:
        pass
    return None

class SignupPayload(BaseModel):
    name: str
    email: str
    password: str

class LoginPayload(BaseModel):
    email: str
    password: str

@app.post("/auth/signup")
async def auth_signup(payload: SignupPayload):
    # Strict validation to block disposable/temporary emails
    disposable_domains = [
        "mailinator.com", "yopmail.com", "tempmail.com", "guerrillamail.com",
        "dispostable.com", "sharklasers.com", "getairmail.com", "maildrop.cc",
        "temp-mail.org", "fakeinbox.com", "throwawaymail.com", "mailnesia.com"
    ]
    email_domain = payload.email.split("@")[-1].lower().strip()
    if email_domain in disposable_domains:
        raise HTTPException(
            status_code=400,
            detail="Disposable/temporary email addresses are not allowed. Please use a verified, permanent email provider."
        )

    from config import SUPABASE_URL, SUPABASE_ANON_KEY
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        raise HTTPException(status_code=500, detail="Supabase connection not configured on backend.")
    
    url = f"{SUPABASE_URL}/auth/v1/signup"
    headers = {
        "apikey": SUPABASE_ANON_KEY,
        "Content-Type": "application/json"
    }
    body = {
        "email": payload.email,
        "password": payload.password,
        "data": {
            "name": payload.name
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=body)
        res_data = response.json()
        
        if response.status_code != 200:
            err_msg = res_data.get("msg", res_data.get("error_description", "Registration failed."))
            raise HTTPException(status_code=response.status_code, detail=err_msg)
            
        access_token = res_data.get("access_token")
        refresh_token = res_data.get("refresh_token")
        
        # In GoTrue, if auto-confirm is OFF, the user object is at the root level of res_data.
        # If auto-confirm is ON, the user details are inside the "user" key.
        user_obj = res_data.get("user")
        if not user_obj:
            user_obj = res_data
            
        if not access_token:
            # Return verification status indicating registration succeeded but email needs confirmation
            return {
                "status": "verification_required",
                "message": "User registered successfully. Please check your email inbox to verify your account.",
                "user": user_obj
            }
            
        return {
            "status": "success",
            "message": "User registered successfully.",
            "user": user_obj,
            "access_token": access_token,
            "refresh_token": refresh_token
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/auth/login")
async def auth_login(payload: LoginPayload):
    from config import SUPABASE_URL, SUPABASE_ANON_KEY
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        raise HTTPException(status_code=500, detail="Supabase connection not configured on backend.")
        
    url = f"{SUPABASE_URL}/auth/v1/token?grant_type=password"
    headers = {
        "apikey": SUPABASE_ANON_KEY,
        "Content-Type": "application/json"
    }
    body = {
        "email": payload.email,
        "password": payload.password
    }
    
    try:
        response = requests.post(url, headers=headers, json=body)
        res_data = response.json()
        
        if response.status_code != 200:
            err_msg = res_data.get("error_description", res_data.get("msg", "Invalid credentials."))
            raise HTTPException(status_code=response.status_code, detail=err_msg)
            
        user_data = res_data.get("user")
        access_token = res_data.get("access_token")
        
        # Fetch subscription tier
        import billing
        if user_data:
            sub = billing.get_user_subscription(user_data.get("id"), access_token)
            user_data["plan_tier"] = sub.get("plan_tier", "FREE")
            
        return {
            "status": "success",
            "user": user_data,
            "access_token": access_token,
            "refresh_token": res_data.get("refresh_token")
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/auth/me")
async def get_current_user(request: Request):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid token.")
    token = auth_header.split(" ")[1]
    user_data = verify_supabase_token(token)
    if not user_data:
        raise HTTPException(status_code=401, detail="Session expired or invalid.")
    return {"status": "success", "user": user_data}

@app.post("/chat")
async def process_chat(
    request: Request,
    background_tasks: BackgroundTasks,
    prompt: str = Form(...),
    filename: str = Form(None),
    mode: str = Form(None),
    session_id: str = Form(None)
):
    # Secure token verification
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication token missing or invalid.")
        
    token = auth_header.split(" ")[1]
    user_info = verify_supabase_token(token)
    if not user_info:
        raise HTTPException(status_code=401, detail="Authentication session has expired or is invalid.")

    user_id = user_info.get("id")
    print(f"Received prompt: {prompt} (mode: {mode}, token) for user: {user_info.get('email')} (id: {user_id}, token)")
    video_path = None
    
    if filename:
        print(f"Received filename reference: {filename}")
        # Check standard upload dir
        possible_path_1 = os.path.join(UPLOAD_DIR, filename)
        # Check backend root dir
        possible_path_2 = os.path.join(os.path.dirname(UPLOAD_DIR), filename)
        
        if os.path.exists(possible_path_1):
            video_path = possible_path_1
        elif os.path.exists(possible_path_2):
            video_path = possible_path_2
        else:
            # Check if it exists in the GCS bucket
            try:
                from google.cloud import storage
                storage_client = storage.Client()
                bucket = storage_client.bucket("tuc-ai-raw-uploads")
                blob = bucket.blob(filename)
                if blob.exists():
                    video_path = filename  # Set as GCS blob path to be downloaded by worker
                else:
                    return {
                        "status": "error",
                        "message": f"Could not find '{filename}' locally or in cloud storage."
                    }
            except Exception as e:
                # Fallback: if GCS checks fail (e.g. local offline dev), allow path if it looks like a GCS key
                if "/" in filename:
                    video_path = filename
                else:
                    return {
                        "status": "error",
                        "message": f"Could not find '{filename}' locally. Error checking GCS: {e}"
                    }
            
    # --- CHATBOT STATE MANAGER ---
    try:
        from pipeline.intent_router import classify_intent
        
        chat_history = []
        if session_id:
            existing = database.get_session_details(session_id)
            if existing:
                chat_history = existing.get("messages", [])

        formatted_history = []
        for msg in chat_history:
            formatted_history.append({"role": msg.get("role", "user"), "content": msg.get("text") or msg.get("content", "")})
        formatted_history.append({"role": "user", "content": prompt})

        intent_data = classify_intent(formatted_history, has_video=video_path is not None, forced_mode=mode)
        
        if intent_data.get('intent') == 'CONVERSATION':
            active_session_id = get_or_create_session(user_id, token, session_id, default_title=prompt[:30])
            database.add_message(active_session_id, {"role": "user", "content": prompt, "file": filename})
            bot_msg = intent_data.get('conversational_response', "Could you provide more details?")
            database.add_message(active_session_id, {"role": "assistant", "content": bot_msg})
            return {
                "status": "missing_info",
                "message": bot_msg,
                "session_id": active_session_id
            }

        player_name = intent_data.get('player_name')
        year = intent_data.get('year')
        current_match = intent_data.get('match_name')

        if intent_data.get('intent') in ['PLAYER_FOCUS', 'GENERAL_HIGHLIGHT']:
            match_results = espn.get_match_from_description(current_match or prompt, player_name, year)
            if match_results:
                current_match = match_results[0]['name']

        active_session_id = get_or_create_session(user_id, token, session_id, default_title=(current_match or prompt)[:30], match_name=current_match, player_name=player_name, year=year, video_path=video_path)
        database.add_message(active_session_id, {"role": "user", "content": prompt, "file": filename})

        import uuid
        project_id = str(uuid.uuid4())

        import billing
        is_player_focus = intent_data.get('intent') == "PLAYER_FOCUS"
        if not billing.can_generate_highlight(user_id, is_player_focus, token):
            msg = "You have exhausted your generation limits. Please upgrade to Pro!"
            database.add_message(active_session_id, {"role": "assistant", "content": msg, "status": "error"})
            return {"status": "error", "message": msg, "session_id": active_session_id}

        if not IS_LOCAL:
            from google.cloud import run_v2
            import json
            client = run_v2.JobsClient()
            job_name = f"projects/tuc-ai-prod/locations/us-central1/jobs/tuc-highlight-worker"
            try:
                request = run_v2.RunJobRequest(
                    name=job_name,
                    overrides={
                        "container_overrides": [{
                            "env": [
                                {"name": "JOB_PAYLOAD", "value": json.dumps({
                                    "video_path": video_path,
                                    "prompt": prompt,
                                    "intent_data": intent_data,
                                    "user_id": user_id,
                                    "project_id": project_id,
                                    "token": token
                                })}
                            ]
                        }]
                    }
                )
                client.run_job(request=request)
            except Exception as e:
                print(f"Failed to trigger Cloud Run Job: {e}")
                background_tasks.add_task(
                    run_pipeline_with_error_handling,
                    pipeline, video_path, prompt,
                    intent_data=intent_data, user_id=user_id, project_id=project_id, token=token
                )
        else:
            try:
                from celery_worker import process_highlight_job
                process_highlight_job.delay(
                    video_path=video_path, 
                    prompt=prompt, 
                    intent_data=intent_data, 
                    user_id=user_id, 
                    project_id=project_id, 
                    token=token
                )
            except Exception as celery_err:
                background_tasks.add_task(
                    run_pipeline_with_error_handling,
                    pipeline, video_path, prompt,
                    intent_data=intent_data, user_id=user_id, project_id=project_id, token=token
                )
                
        msg = "Processing your highlight reel..."
        database.add_message(active_session_id, {"role": "assistant", "content": msg, "project_id": project_id, "status": "processing"})
        
        session_details = database.get_session_details(active_session_id)
        if session_details:
            p_ids = session_details.get("project_ids", [])
            if project_id not in p_ids:
                p_ids.append(project_id)
                database.update_session_metadata(active_session_id, {"project_ids": p_ids, "title": (current_match or prompt)[:30] + "..."})
                
        return {
            "status": "processing",
            "message": msg,
            "project_id": project_id,
            "session_id": active_session_id
        }

    except espn.AmbiguousMatchError as e:
        active_session_id = get_or_create_session(user_id, token, session_id, default_title=prompt[:30])
        database.add_message(active_session_id, {"role": "assistant", "content": "I found multiple matches that fit that description. Which one did you mean?", "candidates": e.candidates, "status": "multiple_matches"})
        return {
            "status": "multiple_matches",
            "message": "I found multiple matches that fit that description. Which one did you mean?",
            "candidates": e.candidates,
            "session_id": active_session_id
        }
    except PlayerNotFoundError as e:
        active_session_id = get_or_create_session(user_id, token, session_id, default_title=prompt[:30])
        database.add_message(active_session_id, {"role": "assistant", "content": e.message, "status": "missing_info"})
        return {
            "status": "missing_info",
            "message": e.message,
            "session_id": active_session_id
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            "status": "error",
            "message": f"An error occurred: {str(e)}"
        }

def run_pipeline_with_error_handling(pipeline_obj, video_path, prompt, intent_data, user_id, project_id, token):
    try:
        result = pipeline_obj.run(video_path, prompt, intent_data=intent_data, user_id=user_id, project_id=project_id, token=token)
        
        # Only deduct credits if the pipeline actually produced output
        if result is not None:
            import billing
            is_player_focus = intent_data.get('intent') == "PLAYER_FOCUS"
            billing.record_successful_generation(user_id, is_player_focus, token)
        
    except Exception as e:
        import traceback
        import json
        traceback.print_exc()
        if type(e).__name__ == 'PlayerNotFoundError':
            error_data = {
                "message": str(e),
                "candidates": getattr(e, 'candidates', [])
            }
            database.update_project_status(project_id, 'conversational_pushback', last_error_log=json.dumps(error_data), token=token)
        else:
            database.update_project_status(project_id, 'error', last_error_log=str(e), token=token)


def get_signed_video_url(project, user_id, token=None):
    """Dynamically generates a signed GCS URL for projects with old relative video paths."""
    video_url = project.get("video_url")
    if not video_url:
        return None
    if video_url.startswith("http"):
        return video_url
        
    project_id = project.get("id")
    filename = os.path.basename(video_url)
    
    gcs_paths = [
        f"{user_id}/projects/{project_id}/{filename}",
        f"{user_id}/projects/{project_id}/final_highlights.mp4"
    ]
    
    try:
        from google.cloud import storage
        from google.oauth2 import service_account
        import datetime
        
        # Use explicit service account credentials for signing
        # (Cloud Run default credentials lack a private key)
        sa_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gcp-credentials.json")
        if os.path.exists(sa_path):
            credentials = service_account.Credentials.from_service_account_file(sa_path)
            storage_client = storage.Client(credentials=credentials)
        else:
            storage_client = storage.Client()
            
        bucket = storage_client.bucket("tuc-ai-raw-uploads")
        for path in gcs_paths:
            blob = bucket.blob(path)
            if blob.exists():
                url = blob.generate_signed_url(
                    version="v4",
                    expiration=datetime.timedelta(days=7),
                    method="GET"
                )
                print(f"Dynamically signed relative URL for GCS blob: {path}")
                return url
    except Exception as e:
        print(f"Error dynamically signing GCS URL: {e}")
        
    return video_url


@app.get("/projects/{project_id}/status")
async def get_project_status(project_id: str, request: Request):
    auth_header = request.headers.get("Authorization")
    token = None
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        
    project = database.get_highlight_project(project_id, token)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
        
    # Support self-healing signed GCS URLs for completed runs
    if project.get("status") == "complete" and project.get("video_url"):
        user_id = project.get("user_id")
        project["video_url"] = get_signed_video_url(project, user_id, token)
        
    return project


@app.get("/api/videos")
async def get_videos(request: Request):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token.")
    token = auth_header.split(" ")[1]
    user_info = verify_supabase_token(token)
    if not user_info:
        raise HTTPException(status_code=401, detail="Invalid token.")

    user_id = user_info.get("id")
    try:
        import datetime
        videos = []
        total_storage_bytes = 0
        
        from google.cloud import storage
        from google.oauth2 import service_account
        import os
        
        sa_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gcp-credentials.json")
        if os.path.exists(sa_path):
            credentials = service_account.Credentials.from_service_account_file(sa_path)
            storage_client = storage.Client(credentials=credentials)
        else:
            storage_client = storage.Client()
            
        bucket = storage_client.bucket("tuc-ai-raw-uploads")
            
        # List all blobs under user's prefix
        blobs = bucket.list_blobs(prefix=f"{user_id}/")
        
        for blob in blobs:
            # Sum up total storage before filtering (to include generated edits)
            total_storage_bytes += blob.size or 0
            
            # Skip any subfolders, stray files (like old thumbnails), or generated outputs
            if "/thumbnails/" in blob.name or blob.name.endswith(".jpg") or "/projects/" in blob.name:
                continue
                
            try:
                url = blob.generate_signed_url(
                    version="v4",
                    expiration=datetime.timedelta(hours=2),
                    method="GET"
                )
            except Exception:
                url = f"https://storage.googleapis.com/tuc-ai-raw-uploads/{blob.name}"
                
            videos.append({
                "name": blob.name,
                "url": url,
                "created_at": blob.time_created,
                "size": blob.size
            })
            
        return {"videos": videos, "total_storage_bytes": total_storage_bytes}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/chat/sessions")
async def get_sessions(request: Request):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token.")
    token = auth_header.split(" ")[1]
    user_info = verify_supabase_token(token)
    if not user_info:
        raise HTTPException(status_code=401, detail="Invalid token.")
    
    user_id = user_info.get("id")
    sessions = database.get_user_sessions(user_id, token)
    
    # Collect all project ids
    all_project_ids = []
    for s in sessions:
        all_project_ids.extend(s.get("project_ids", []))
        
    projects = database.get_projects_by_ids(all_project_ids)
    project_map = {p["id"]: p for p in projects}
    
    session_list = []
    
    for s in sessions:
        s_id = s["id"]
        p_ids = s.get("project_ids", [])
        
        if not p_ids:
            # Empty chat without any generated videos
            continue
            
        for pid in p_ids:
            proj = project_map.get(pid, {})
            vid_url = proj.get("video_url")
            if vid_url and not vid_url.startswith("http"):
                vid_url = get_signed_video_url(proj, user_id, token)
                
            session_list.append({
                "id": s_id,
                "project_id": pid,
                "title": proj.get("match_name") or s.get("title", "New Session"),
                "updated_at": proj.get("updated_at") or s.get("updated_at"),
                "created_at": proj.get("created_at") or s.get("created_at"),
                "status": proj.get("status", "draft"),
                "videoUrl": vid_url
            })
            
    session_list.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
    return {"sessions": session_list}

@app.get("/chat/sessions/{session_id}")
async def get_session_details(session_id: str, request: Request):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token.")
    token = auth_header.split(" ")[1]
    user_info = verify_supabase_token(token)
    if not user_info:
        raise HTTPException(status_code=401, detail="Invalid token.")
    
    user_id = user_info.get("id")
    session_data = database.get_session_details(session_id)
    if not session_data or session_data.get("user_id") != user_id:
        raise HTTPException(status_code=404, detail="Session not found")
        
    # Sync project statuses and dynamically generate signed URLs
    for msg in session_data.get("messages", []):
        proj_id = msg.get("project_id")
        if not proj_id:
            continue
            
        project = database.get_highlight_project(proj_id, token)
        if not project:
            continue
            
        # 1. Update stale processing statuses in Firestore
        if msg.get("status") in ["processing", "queued", "analyzing", "rendering", "calibrating"]:
            if project["status"] == "complete":
                msg["status"] = "success"
                msg["content"] = "Your highlight reel is ready!"
                msg["text"] = "Your highlight reel is ready!"
                # Save status update to DB (without videoUrl)
                update_payload = {
                    "status": "success", 
                    "content": msg["content"], 
                    "text": msg["text"]
                }
                database.db.collection("sessions").document(session_id).collection("messages").document(msg["id"]).update(update_payload)
            elif project["status"] in ["error", "failed"]:
                msg["status"] = "error"
                msg["content"] = f"Processing failed: {project.get('last_error_log', 'Unknown error')}"
                msg["text"] = msg["content"]
                database.db.collection("sessions").document(session_id).collection("messages").document(msg["id"]).update(msg)
            elif project["status"] == "conversational_pushback":
                import json
                msg["status"] = "error"
                try:
                    err_data = json.loads(project.get("last_error_log", "{}"))
                    msg["content"] = err_data.get("message", "I need clarification.")
                    msg["candidates"] = [{"id": c, "label": c} for c in err_data.get("candidates", [])]
                except:
                    msg["content"] = project.get("last_error_log", "I need clarification.")
                msg["text"] = msg["content"]
                database.db.collection("sessions").document(session_id).collection("messages").document(msg["id"]).update(msg)

        # 2. Inject fresh signed URLs into the response for ANY completed project
        if msg.get("status") == "success" or project["status"] == "complete":
            msg["videoUrl"] = get_signed_video_url(project, user_id, token)
            msg["timeline"] = project.get("timeline_state")
            
    # Format correctly for frontend
    # the frontend expects "chat_history", we pass "messages" as "chat_history" for compatibility
    session_data["chat_history"] = session_data.pop("messages", [])
    
    return {"session": session_data}

@app.delete("/chat/sessions/{session_id}")
async def delete_session(session_id: str, request: Request):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token.")
    token = auth_header.split(" ")[1]
    user_info = verify_supabase_token(token)
    if not user_info:
        raise HTTPException(status_code=401, detail="Invalid token.")
    
    user_id = user_info.get("id")
    session = database.get_session_details(session_id)
    
    if session and session.get("user_id") == user_id:
        project_ids = set(session.get("project_ids", []))
        for msg in session.get("messages", []):
            if msg.get("project_id"):
                project_ids.add(msg["project_id"])
                
        # Delete from GCS
        if project_ids:
            try:
                from google.cloud import storage
                # Use credentials
                from google.oauth2 import service_account
                import os
                sa_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gcp-credentials.json")
                if os.path.exists(sa_path):
                    creds = service_account.Credentials.from_service_account_file(sa_path)
                    storage_client = storage.Client(credentials=creds)
                else:
                    storage_client = storage.Client()
                    
                bucket = storage_client.bucket("tuc-ai-raw-uploads")
                for pid in project_ids:
                    try:
                        prefix = f"{user_id}/projects/{pid}/"
                        print(f"[SESSION_DELETE] Scanning GCS prefix for deletion: {prefix}")
                        blobs = bucket.list_blobs(prefix=prefix)
                        deleted_count = 0
                        for blob in blobs:
                            print(f"[SESSION_DELETE] Deleting {blob.name}")
                            blob.delete()
                            deleted_count += 1
                        print(f"[SESSION_DELETE] Successfully deleted {deleted_count} video objects for project {pid}")
                        # Delete from Firestore
                        database.delete_highlight_project(pid, token)
                        print(f"[SESSION_DELETE] Successfully wiped project metadata {pid}")
                    except Exception as e:
                        print(f"Error wiping project {pid}: {e}")
            except Exception as e:
                print(f"Error connecting to GCS for wipe: {e}")
                
        # Delete session
        database.delete_session(session_id)
        
    return {"status": "success"}

#
# ─────────────────────────────────────────────────────────────
# 6. CLOUD STORAGE UPLOADS (GCP)
# ─────────────────────────────────────────────────────────────
import datetime

@app.post("/api/videos/upload-url")
async def generate_upload_url(request: Request):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token.")
    token = auth_header.split(" ")[1]
    user_info = verify_supabase_token(token)
    if not user_info:
        raise HTTPException(status_code=401, detail="Invalid token.")

    data = await request.json()
    filename = data.get("filename")
    content_type = data.get("contentType", "video/mp4")
    
    if not filename:
        raise HTTPException(status_code=400, detail="Missing filename")
        
    bucket_name = "tuc-ai-raw-uploads"
    safe_filename = filename.replace(" ", "_")
    blob_name = f"{user_info.get('id')}/{int(datetime.datetime.now().timestamp())}_{safe_filename}"

    try:
        from google.cloud import storage
        from google.oauth2 import service_account
        
        sa_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gcp-credentials.json")
        if os.path.exists(sa_path):
            credentials = service_account.Credentials.from_service_account_file(sa_path)
            storage_client = storage.Client(credentials=credentials)
        else:
            storage_client = storage.Client()
            
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_name)

        kwargs = {
            "version": "v4",
            "expiration": datetime.timedelta(hours=2),
            "method": "PUT",
            "content_type": content_type,
        }
        
        # If in Cloud Run, we must explicitly provide the service account email so it uses IAM to sign
        if not os.path.exists(sa_path):
            kwargs["service_account_email"] = "530507298858-compute@developer.gserviceaccount.com"

        # Generate a v4 signed URL for PUT upload
        url = blob.generate_signed_url(**kwargs)
        return {"uploadUrl": url, "blobName": blob_name, "provider": "gcp"}
    except Exception as e:
        print(f"Error generating GCS signed URL (Missing GCP Config?): {e}")
        # Fallback to local
        return {
            "uploadUrl": f"http://localhost:8000/api/videos/upload-local",
            "blobName": blob_name,
            "provider": "local"
        }

@app.post("/api/videos/upload-local")
async def upload_local_video(request: Request, file: UploadFile = File(...)):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token.")
    token = auth_header.split(" ")[1]
    user_info = verify_supabase_token(token)
    if not user_info:
        raise HTTPException(status_code=401, detail="Invalid token.")
        
    user_id = user_info.get("id")
    user_upload_dir = os.path.join(UPLOAD_DIR, user_id)
    os.makedirs(user_upload_dir, exist_ok=True)
    
    safe_filename = file.filename.replace(" ", "_")
    blob_name = f"{int(datetime.datetime.now().timestamp())}_{safe_filename}"
    file_path = os.path.join(user_upload_dir, blob_name)
    
    with open(file_path, "wb") as buffer:
        import shutil
        shutil.copyfileobj(file.file, buffer)
        
    return {"status": "success", "blobName": f"{user_id}/{blob_name}"}

@app.post("/api/videos/finalize")
async def finalize_upload(request: Request):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token.")
    token = auth_header.split(" ")[1]
    if not verify_supabase_token(token):
        raise HTTPException(status_code=401, detail="Invalid token.")
        
    data = await request.json()
    return {"status": "success", "message": "Video registered successfully", "blobName": data.get("blobName")}

# ─────────────────────────────────────────────────────────────
# 7. PAYMENT WEBHOOKS (Dual Gateway)
# ─────────────────────────────────────────────────────────────
import hmac
import hashlib

@app.post("/webhook/lemonsqueezy")
async def lemonsqueezy_webhook(request: Request):
    from config import LEMON_SQUEEZY_WEBHOOK_SECRET
    signature = request.headers.get("x-signature")
    if not signature:
        raise HTTPException(status_code=400, detail="Missing signature")
        
    payload = await request.body()
    if not LEMON_SQUEEZY_WEBHOOK_SECRET:
        return {"status": "ignored", "reason": "No webhook secret configured"}
        
    computed_signature = hmac.new(
        LEMON_SQUEEZY_WEBHOOK_SECRET.encode('utf-8'),
        payload,
        hashlib.sha256
    ).hexdigest()
    
    if not hmac.compare_digest(signature, computed_signature):
        raise HTTPException(status_code=400, detail="Invalid signature")
        
    data = json.loads(payload)
    event_name = data.get("meta", {}).get("event_name")
    custom_data = data.get("meta", {}).get("custom_data", {})
    user_id = custom_data.get("user_id")
    
    if not user_id:
        return {"status": "ignored", "reason": "No user_id in custom_data"}
        
    import database
    if event_name in ["subscription_created", "subscription_updated", "subscription_resumed", "subscription_plan_changed"]:
        plan_tier = custom_data.get("plan_tier", "BASIC")
        sub_id = data.get("data", {}).get("id")
        database.update_subscription_tier_admin(user_id, plan_tier, "lemonsqueezy", sub_id)
    elif event_name in ["subscription_expired", "subscription_payment_refunded"]:
        database.update_subscription_tier_admin(user_id, "FREE", "lemonsqueezy", None)
        
    return {"status": "success"}

@app.post("/webhook/paystack")
async def paystack_webhook(request: Request):
    from config import PAYSTACK_SECRET_KEY
    signature = request.headers.get("x-paystack-signature")
    if not signature:
        raise HTTPException(status_code=400, detail="Missing signature")
        
    payload = await request.body()
    if not PAYSTACK_SECRET_KEY:
        return {"status": "ignored", "reason": "No paystack secret configured"}
        
    computed_signature = hmac.new(
        PAYSTACK_SECRET_KEY.encode('utf-8'),
        payload,
        hashlib.sha512
    ).hexdigest()
    
    if not hmac.compare_digest(signature, computed_signature):
        raise HTTPException(status_code=400, detail="Invalid signature")
        
    data = json.loads(payload)
    event = data.get("event")
    
    import database
    if event == "charge.success":
        metadata = data.get("data", {}).get("metadata", {})
        user_id = metadata.get("user_id")
        plan_tier = metadata.get("plan_tier", "BASIC")
        
        if user_id:
            ref = str(data.get("data", {}).get("reference"))
            database.update_subscription_tier_admin(user_id, plan_tier, "paystack", ref)
            
    elif event == "subscription.disable":
        # Handle cancellations if applicable
        pass
        
    return {"status": "success"}

# --- INTERNAL WORKER SERVICE ENDPOINT ---
class WorkerPayload(BaseModel):
    project_id: str
    user_id: str
    video_path: str
    mode: str
    token: str = None
    intent_data: dict = None
    prompt: str = None

@app.post("/internal/worker")
async def internal_worker(request: Request, payload: WorkerPayload, background_tasks: BackgroundTasks):
    secret = request.headers.get("X-Worker-Secret")
    expected_secret = os.getenv("INTERNAL_WORKER_SECRET", "dev-secret")
    if secret != expected_secret:
        raise HTTPException(status_code=403, detail="Forbidden: Invalid internal worker secret")
        
    def run_worker_task(data: WorkerPayload):
        try:
            print(f"\n\n{'='*50}")
            print(f"=== [DEDICATED WORKER] TASK FOR {data.project_id} ===")
            print(f"{'='*50}\n")
            
            import database
            from pipeline.orchestrator import HighlightPipeline
            import json
            
            pipeline = HighlightPipeline(OUTPUT_DIR)
            intent_data_parsed = data.intent_data or {}
            
            local_video_path = data.video_path
            # Download if it's a GCS blob name
            if not os.path.exists(local_video_path):
                temp_path = f"/tmp/{os.path.basename(local_video_path)}"
                try:
                    from google.cloud import storage
                    storage_client = storage.Client()
                    bucket = storage_client.bucket("tuc-ai-raw-uploads")
                    blob = bucket.blob(data.video_path)
                    blob.download_to_filename(temp_path)
                    local_video_path = temp_path
                except Exception as e:
                    print(f"Failed to download video from GCS: {e}")
                    database.update_project_status(data.project_id, 'error', last_error_log=f"Failed to download video from cloud storage: {e}", token=data.token)
                    return
            
            project_state = database.get_highlight_project(data.project_id, data.token)
            
            if data.mode == "edit":
                print("  [Mode: Edit] Bypassing AI intent and jumping straight to render_from_timeline.")
                timeline_state = project_state.get('timeline_state') if project_state else None
                if not timeline_state:
                    raise Exception("Cannot render edit: timeline_state not found in database.")
                    
                pipeline.render_from_timeline(
                    video_path=local_video_path,
                    user_id=data.user_id,
                    project_id=data.project_id,
                    token=data.token,
                    timeline_state=timeline_state
                )
            else:
                # Normal Generation Mode
                print("  [Mode: Generate] Running full AI pipeline.")
                pipeline.run(
                    video_path=local_video_path,
                    prompt=data.prompt or "",
                    user_id=data.user_id, 
                    project_id=data.project_id, 
                    token=data.token,
                    intent_data=intent_data_parsed
                )
        except Exception as e:
            import traceback
            traceback.print_exc()
            import database
            database.update_project_status(data.project_id, 'error', last_error_log=str(e), token=data.token)

    background_tasks.add_task(run_worker_task, payload)
    return {"status": "accepted", "message": "Background worker started."}

if __name__ == "__main__":
    import uvicorn
    import signal
    import sys

    def force_exit(sig, frame):
        print("\n[Server] Shutting down (Ctrl+C)...")
        # Kill the entire process tree so zombie subprocesses (Chrome, etc.) also die
        os._exit(0)

    signal.signal(signal.SIGINT, force_exit)
    # Windows also sends SIGBREAK for Ctrl+Break
    if hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, force_exit)

    uvicorn.run(app, host="0.0.0.0", port=8000)
