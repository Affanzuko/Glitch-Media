from flask import Flask, request, jsonify, redirect, url_for, send_from_directory
from flask_cors import CORS
from database import engine, SessionLocal, Base
import models
import os

# Create database tables
Base.metadata.create_all(bind=engine)

from sqlalchemy import text
try:
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE publish_history ADD COLUMN caption_x TEXT"))
        conn.execute(text("ALTER TABLE publish_history ADD COLUMN caption_ig TEXT"))
        conn.execute(text("ALTER TABLE publish_history ADD COLUMN image_url VARCHAR(500)"))
        conn.execute(text("ALTER TABLE publish_history ADD COLUMN news_title VARCHAR(255)"))
except Exception:
    pass

frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'frontend'))
app = Flask(__name__, static_folder=frontend_dir, static_url_path='')
# Allow CORS for local HTML testing
CORS(app)

@app.route('/')
def index():
    return app.send_static_file('dashboard.html')

@app.route('/api/history', methods=['GET'])
def get_history():
    db = SessionLocal()
    try:
        # Get all history, ordered by newest
        history_records = db.query(models.PublishHistory).order_by(models.PublishHistory.created_at.desc()).all()
        result = []
        for r in history_records:
            result.append({
                "id": r.id,
                "created_at": r.created_at.isoformat(),
                "payload_title": r.payload_title,
                "target_platform": r.target_platform,
                "status": r.status,
                "diagnostics": r.diagnostics,
                "caption_x": r.caption_x,
                "caption_ig": r.caption_ig,
                "image_url": r.image_url,
                "news_title": r.news_title
            })
        return jsonify(result)
    finally:
        db.close()

@app.route('/api/history', methods=['POST'])
def add_history():
    data = request.json
    db = SessionLocal()
    try:
        new_record = models.PublishHistory(
            payload_title=data.get('payload_title'),
            target_platform=data.get('target_platform'),
            status=data.get('status'),
            diagnostics=data.get('diagnostics')
        )
        db.add(new_record)
        db.commit()
        db.refresh(new_record)
        return jsonify({"message": "Success", "id": new_record.id}), 201
    finally:
        db.close()

@app.route('/api/settings', methods=['GET'])
def get_settings():
    db = SessionLocal()
    try:
        configs = db.query(models.SystemConfig).all()
        result = {c.key: c.value for c in configs}
        return jsonify(result)
    finally:
        db.close()

@app.route('/api/settings', methods=['POST'])
def update_settings():
    data = request.json
    db = SessionLocal()
    try:
        for key, value in data.items():
            config = db.query(models.SystemConfig).filter(models.SystemConfig.key == key).first()
            if config:
                config.value = value
            else:
                config = models.SystemConfig(key=key, value=value)
                db.add(config)
        db.commit()
        return jsonify({"message": "Settings updated successfully"})
    finally:
        db.close()

# --- OAUTH API ENDPOINTS ---

@app.route('/api/oauth/status', methods=['GET'])
def get_oauth_status():
    """Get connection status for X and IG accounts."""
    try:
        from tools.oauth_manager import get_connection_status
        status = get_connection_status()
        return jsonify(status)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Shared state for tracking OAuth login progress
_oauth_login_state = {}


@app.route('/api/oauth/login/x', methods=['POST'])
def oauth_login_x():
    """Initiate X/Twitter OAuth login — returns auth_url for frontend to open."""
    try:
        from tools.oauth_server import initiate_x_login, complete_x_login

        # Initiate login and get auth URL
        initiation = initiate_x_login()
        if "error" in initiation:
            return jsonify(initiation), 400

        # Start background thread to wait for callback and exchange token
        _oauth_login_state["x"] = "pending"

        def wait_for_x():
            result = complete_x_login(timeout=120)
            _oauth_login_state["x"] = result

        thread = threading.Thread(target=wait_for_x, daemon=True)
        thread.start()

        return jsonify({"auth_url": initiation["auth_url"], "status": "pending"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/oauth/login/ig', methods=['POST'])
def oauth_login_ig():
    """Initiate Instagram OAuth login — returns auth_url for frontend to open."""
    try:
        from tools.oauth_server import initiate_ig_login, complete_ig_login

        # Initiate login and get auth URL
        initiation = initiate_ig_login()
        if "error" in initiation:
            return jsonify(initiation), 400

        # Start background thread to wait for callback and exchange token
        _oauth_login_state["ig"] = "pending"

        def wait_for_ig():
            result = complete_ig_login(timeout=120)
            _oauth_login_state["ig"] = result

        thread = threading.Thread(target=wait_for_ig, daemon=True)
        thread.start()

        return jsonify({"auth_url": initiation["auth_url"], "status": "pending"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/oauth/login/<platform>/poll', methods=['GET'])
def oauth_login_poll(platform):
    """Poll OAuth login status — frontend calls this to check if login is complete."""
    if platform not in ("x", "ig"):
        return jsonify({"error": "Invalid platform"}), 400

    state = _oauth_login_state.get(platform)
    if state is None:
        return jsonify({"status": "none"})
    if state == "pending":
        return jsonify({"status": "pending"})

    # Login completed (state is now the result dict)
    result = state
    _oauth_login_state.pop(platform, None)  # Clear state after reading
    if "error" in result:
        return jsonify({"status": "error", "error": result["error"]})
    return jsonify({"status": "success", **result})


@app.route('/api/oauth/logout/<platform>', methods=['POST'])
def oauth_logout(platform):
    """Disconnect an account — remove stored tokens."""
    if platform not in ("x", "ig"):
        return jsonify({"error": "Invalid platform"}), 400

    try:
        from tools.oauth_manager import remove_tokens
        from tools.x_api_client import reset_client

        remove_tokens(platform)

        # Reset cached client jika X
        if platform == "x":
            reset_client()

        return jsonify({"message": f"{platform} account disconnected"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# --- PIPELINE INTEGRATION ---
import threading
import time
import uuid
import os
import sys

# Ensure backend can import pipeline modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.state import PipelineState
from pipeline.orchestrator import run_stage_1_2, run_stage_3_fork, run_stage_4
from config.settings import DEFAULT_SOURCES, IMAGES_DIR

pipeline_state = {
    "status": "idle", # idle, running, waiting_validation, complete, error
    "stages": [
        {"id": "stage-scraping", "name": "Scraping Data", "status": "wait"},
        {"id": "stage-screening", "name": "Data Screening", "status": "wait"},
        {"id": "stage-caption", "name": "Caption Drafting (X & IG)", "status": "wait"},
        {"id": "stage-image", "name": "Agent Image Gen", "status": "wait"},
        {"id": "stage-validation", "name": "Validation", "status": "wait"},
        {"id": "stage-upload", "name": "Final Upload", "status": "wait"}
    ],
    "current_stage_index": -1,
    "error_message": "",
    "data": {
        "caption_x": "",
        "caption_ig": "",
        "image_url": "",
        "news_title": ""
    }
}

# Add route to serve local generated images
@app.route('/api/images/<path:filename>')
def serve_image(filename):
    return send_from_directory(IMAGES_DIR, filename)

def run_actual_pipeline():
    global pipeline_state
    pipeline_state["status"] = "running"
    pipeline_state["error_message"] = ""
    stages = pipeline_state["stages"]
    
    # Initialize PipelineState
    run_id = f"run_{uuid.uuid4().hex[:8]}"
    state = PipelineState(run_id=run_id)
    
    try:
        # Stage 1 & 2: Scraping & Screening
        pipeline_state["current_stage_index"] = 0
        stages[0]["status"] = "progress"
        stages[1]["status"] = "progress"
        
        state = run_stage_1_2(state, DEFAULT_SOURCES)
        
        stages[0]["status"] = "done"
        stages[1]["status"] = "done"
        
        # Stage 3: Caption X & IG
        pipeline_state["current_stage_index"] = 2
        stages[2]["status"] = "progress"
        
        state = run_stage_3_fork(state)
        
        stages[2]["status"] = "done"
        if state.caption_x and state.caption_ig:
            pipeline_state["data"]["caption_x"] = state.caption_x.caption_long
            pipeline_state["data"]["caption_ig"] = state.caption_ig.caption_short
            pipeline_state["data"]["news_title"] = state.caption_x.news_ref_title
        
        # Stage 4: Image Generation
        pipeline_state["current_stage_index"] = 3
        stages[3]["status"] = "progress"
        
        state = run_stage_4(state)
        
        stages[3]["status"] = "done"
        if state.image_result:
            # We just need the basename of the image to serve it via our API
            image_filename = os.path.basename(state.image_result.image_path)
            pipeline_state["data"]["image_url"] = f"/api/images/{image_filename}"
            
        # Stage 5: Waiting Validation
        pipeline_state["current_stage_index"] = 4
        stages[4]["status"] = "progress"
        pipeline_state["status"] = "waiting_validation"
        
    except Exception as e:
        pipeline_state["status"] = "error"
        pipeline_state["error_message"] = str(e)
        # Mark all in-progress as failed/wait
        for s in stages:
            if s["status"] == "progress":
                s["status"] = "wait"

@app.route('/api/pipeline/status', methods=['GET'])
def get_pipeline_status():
    return jsonify(pipeline_state)

@app.route('/api/pipeline/start', methods=['POST'])
def start_pipeline():
    global pipeline_state
    if pipeline_state["status"] in ["idle", "complete", "error"]:
        # Reset stages
        for stage in pipeline_state["stages"]:
            stage["status"] = "wait"
        pipeline_state["current_stage_index"] = -1
        pipeline_state["data"] = {"caption_x": "", "caption_ig": "", "image_url": "", "news_title": ""}
        
        # Start background thread
        thread = threading.Thread(target=run_actual_pipeline)
        thread.daemon = True
        thread.start()
        return jsonify({"message": "Pipeline started"})
    return jsonify({"message": "Pipeline already running or waiting validation"}), 400

@app.route('/api/pipeline/publish', methods=['POST'])
def publish_pipeline():
    global pipeline_state
    if pipeline_state["status"] == "waiting_validation":
        # ── Cek apakah ada akun yang terkoneksi sebelum lanjut upload ──
        try:
            from tools.oauth_manager import is_token_valid
            x_connected = is_token_valid("x")
            ig_connected = is_token_valid("ig")
        except Exception:
            x_connected = False
            ig_connected = False

        if not x_connected and not ig_connected:
            # Tidak ada akun terkoneksi — pipeline tetap di validasi
            return jsonify({
                "error": "no_account_connected",
                "message": "Tidak ada akun yang terkoneksi. Hubungkan akun X atau Instagram di halaman Settings terlebih dahulu."
            }), 400

        pipeline_state["status"] = "running"
        stages = pipeline_state["stages"]
        
        # Complete validation
        stages[4]["status"] = "done"
        
        # Stage 5: Upload
        pipeline_state["current_stage_index"] = 5
        stages[5]["status"] = "progress"
        
        def real_upload():
            """Upload ke X dan IG menggunakan agent yang sudah terkoneksi via OAuth."""
            try:
                from tools.oauth_manager import is_token_valid
                from agents.agent_upload_x import run as upload_x_run
                from agents.agent_upload_ig import run as upload_ig_run
                from config.schemas import CaptionX, CaptionIG, ImageGenResult

                caption_x_text = pipeline_state["data"].get("caption_x", "")
                caption_ig_text = pipeline_state["data"].get("caption_ig", "")
                news_title = pipeline_state["data"].get("news_title", "")
                image_path = pipeline_state["data"].get("image_url", "")

                errors = []

                # Upload ke X jika token tersedia
                if is_token_valid("x") and caption_x_text:
                    try:
                        caption_x = CaptionX(
                            news_ref_title=news_title,
                            caption_long=caption_x_text,
                        )
                        result_x = upload_x_run(caption_x)
                        if not result_x.success:
                            errors.append(f"X: {result_x.error}")
                    except Exception as e:
                        errors.append(f"X upload error: {str(e)}")
                elif caption_x_text:
                    errors.append("X: Akun belum terkoneksi")

                # Upload ke IG jika token tersedia
                if is_token_valid("ig") and caption_ig_text:
                    try:
                        # Resolve image path dari API URL ke path lokal
                        local_image_path = image_path
                        if image_path.startswith("/api/images/"):
                            image_filename = image_path.replace("/api/images/", "")
                            local_image_path = str(IMAGES_DIR / image_filename)

                        caption_ig = CaptionIG(
                            news_ref_title=news_title,
                            caption_short=caption_ig_text,
                        )
                        image_result = ImageGenResult(image_path=local_image_path)
                        result_ig = upload_ig_run(caption_ig, image_result)
                        if not result_ig.success:
                            errors.append(f"IG: {result_ig.error}")
                    except Exception as e:
                        errors.append(f"IG upload error: {str(e)}")
                elif caption_ig_text:
                    errors.append("IG: Akun belum terkoneksi")

                if errors:
                    stages[5]["status"] = "done"
                    pipeline_state["status"] = "complete"
                    pipeline_state["error_message"] = "; ".join(errors)
                else:
                    stages[5]["status"] = "done"
                    pipeline_state["status"] = "complete"

            except Exception as e:
                stages[5]["status"] = "wait"
                pipeline_state["status"] = "error"
                pipeline_state["error_message"] = f"Upload failed: {str(e)}"
            
        thread = threading.Thread(target=real_upload)
        thread.daemon = True
        thread.start()
        
        return jsonify({"message": "Publishing sequence initiated"})
    return jsonify({"message": "Invalid state"}), 400

@app.route('/api/pipeline/cancel', methods=['POST'])
def cancel_pipeline():
    global pipeline_state
    if pipeline_state["status"] == "waiting_validation":
        # Save current state to history
        db = SessionLocal()
        try:
            new_record = models.PublishHistory(
                payload_title=f"Unpublished_Agent_{uuid.uuid4().hex[:6]}",
                target_platform="Platform X & Instagram",
                status="UNPUBLISHED",
                diagnostics="Cancelled during validation.",
                caption_x=pipeline_state["data"].get("caption_x"),
                caption_ig=pipeline_state["data"].get("caption_ig"),
                image_url=pipeline_state["data"].get("image_url"),
                news_title=pipeline_state["data"].get("news_title")
            )
            db.add(new_record)
            db.commit()
        finally:
            db.close()

        # Reset back to idle
        pipeline_state["status"] = "idle"
        for stage in pipeline_state["stages"]:
            stage["status"] = "wait"
        pipeline_state["current_stage_index"] = -1
        return jsonify({"message": "Pipeline cancelled and saved to history"})
    return jsonify({"message": "Invalid state"}), 400

@app.route('/api/history/publish/<int:record_id>', methods=['POST'])
def publish_from_history(record_id):
    # Cek apakah ada akun yang terkoneksi sebelum lanjut upload
    try:
        from tools.oauth_manager import is_token_valid
        x_connected = is_token_valid("x")
        ig_connected = is_token_valid("ig")
    except Exception:
        x_connected = False
        ig_connected = False

    if not x_connected and not ig_connected:
        return jsonify({
            "error": "no_account_connected",
            "message": "Tidak ada akun yang terkoneksi. Hubungkan akun X atau Instagram di halaman Settings terlebih dahulu."
        }), 400

    req_data = request.json if request.is_json else {}

    db = SessionLocal()
    try:
        record = db.query(models.PublishHistory).filter(models.PublishHistory.id == record_id).first()
        if not record or record.status != "UNPUBLISHED":
            return jsonify({"error": "Invalid record"}), 400
            
        edited_cap_x = req_data.get("caption_x")
        edited_cap_ig = req_data.get("caption_ig")
        if edited_cap_x is not None:
            record.caption_x = edited_cap_x
        if edited_cap_ig is not None:
            record.caption_ig = edited_cap_ig
        db.commit()

        data = {
            "caption_x": record.caption_x,
            "caption_ig": record.caption_ig,
            "news_title": record.news_title,
            "image_url": record.image_url
        }
        
        def real_upload_from_history(data, rec_id):
            try:
                from tools.oauth_manager import is_token_valid
                from agents.agent_upload_x import run as upload_x_run
                from agents.agent_upload_ig import run as upload_ig_run
                from config.schemas import CaptionX, CaptionIG, ImageGenResult
                
                caption_x_text = data.get("caption_x", "")
                caption_ig_text = data.get("caption_ig", "")
                news_title = data.get("news_title", "")
                image_path = data.get("image_url", "")
                
                errors = []
                if is_token_valid("x") and caption_x_text:
                    try:
                        caption_x = CaptionX(news_ref_title=news_title, caption_long=caption_x_text)
                        result_x = upload_x_run(caption_x)
                        if not result_x.success: errors.append(f"X: {result_x.error}")
                    except Exception as e: errors.append(f"X upload error: {str(e)}")
                elif caption_x_text:
                    errors.append("X: Akun belum terkoneksi")

                if is_token_valid("ig") and caption_ig_text:
                    try:
                        local_image_path = image_path
                        if image_path.startswith("/api/images/"):
                            image_filename = image_path.replace("/api/images/", "")
                            local_image_path = str(IMAGES_DIR / image_filename)
                        caption_ig = CaptionIG(news_ref_title=news_title, caption_short=caption_ig_text)
                        image_result = ImageGenResult(image_path=local_image_path)
                        result_ig = upload_ig_run(caption_ig, image_result)
                        if not result_ig.success: errors.append(f"IG: {result_ig.error}")
                    except Exception as e: errors.append(f"IG upload error: {str(e)}")
                elif caption_ig_text:
                    errors.append("IG: Akun belum terkoneksi")
                    
                local_db = SessionLocal()
                try:
                    rec = local_db.query(models.PublishHistory).filter(models.PublishHistory.id == rec_id).first()
                    if errors:
                        rec.status = "FAILED"
                        rec.diagnostics = "; ".join(errors)
                    else:
                        rec.status = "SUCCESS"
                        rec.diagnostics = "Published from History."
                    local_db.commit()
                finally:
                    local_db.close()
            except Exception as e:
                local_db = SessionLocal()
                try:
                    rec = local_db.query(models.PublishHistory).filter(models.PublishHistory.id == rec_id).first()
                    rec.status = "FAILED"
                    rec.diagnostics = f"Upload failed: {str(e)}"
                    local_db.commit()
                finally:
                    local_db.close()

        thread = threading.Thread(target=real_upload_from_history, args=(data, record_id))
        thread.daemon = True
        thread.start()
        
        # update state immediately to progressing
        record.status = "PUBLISHING"
        record.diagnostics = "Upload in progress..."
        db.commit()
        
        return jsonify({"message": "Publishing initiated from history"})
    finally:
        db.close()

@app.route('/api/pipeline/regen-image', methods=['POST'])
def regen_image():
    global pipeline_state
    if pipeline_state["status"] != "waiting_validation":
        return jsonify({"message": "Invalid state"}), 400

    def do_regen():
        try:
            from agents import agent_image_generation
            from config.schemas import CaptionIG
            import uuid
            import os

            caption_ig_text = pipeline_state["data"].get("caption_ig", "")
            news_title = pipeline_state["data"].get("news_title", "")
            
            caption_ig = CaptionIG(
                news_ref_title=news_title,
                caption_short=caption_ig_text
            )
            
            run_id = f"regen_{uuid.uuid4().hex[:8]}"
            
            image_result = agent_image_generation.run(
                caption_ig=caption_ig,
                run_id=run_id
            )
            
            if image_result and image_result.image_path:
                image_filename = os.path.basename(image_result.image_path)
                pipeline_state["data"]["image_url"] = f"/api/images/{image_filename}"
                
        except Exception as e:
            print(f"Regen image error: {e}")

    thread = threading.Thread(target=do_regen)
    thread.daemon = True
    thread.start()
    
    return jsonify({"message": "Regenerating image..."})
@app.route('/api/history/regen-image/<int:record_id>', methods=['POST'])
def regen_image_from_history(record_id):
    req_data = request.json if request.is_json else {}

    db = SessionLocal()
    try:
        record = db.query(models.PublishHistory).filter(models.PublishHistory.id == record_id).first()
        if not record or record.status != "UNPUBLISHED":
            return jsonify({"error": "Invalid record"}), 400
        
        edited_cap_x = req_data.get("caption_x")
        edited_cap_ig = req_data.get("caption_ig")
        if edited_cap_x is not None:
            record.caption_x = edited_cap_x
        if edited_cap_ig is not None:
            record.caption_ig = edited_cap_ig
        db.commit()

        caption_ig_text = record.caption_ig or ""
        news_title = record.news_title or ""
        
        def do_regen_hist(rec_id, cap_ig, title):
            try:
                from agents import agent_image_generation
                from config.schemas import CaptionIG
                import uuid
                import os

                caption_ig = CaptionIG(news_ref_title=title, caption_short=cap_ig)
                run_id = f"regen_hist_{uuid.uuid4().hex[:8]}"
                
                image_result = agent_image_generation.run(caption_ig=caption_ig, run_id=run_id)
                
                if image_result and image_result.image_path:
                    image_filename = os.path.basename(image_result.image_path)
                    new_image_url = f"/api/images/{image_filename}"
                    
                    local_db = SessionLocal()
                    try:
                        rec = local_db.query(models.PublishHistory).filter(models.PublishHistory.id == rec_id).first()
                        if rec:
                            rec.image_url = new_image_url
                            local_db.commit()
                    finally:
                        local_db.close()
            except Exception as e:
                print(f"Regen history image error: {e}")

        thread = threading.Thread(target=do_regen_hist, args=(record_id, caption_ig_text, news_title))
        thread.daemon = True
        thread.start()
        
        return jsonify({"message": "Regenerating image for history record..."})
    finally:
        db.close()

if __name__ == '__main__':
    app.run(port=5001, debug=True)

