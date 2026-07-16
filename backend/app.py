from flask import Flask, request, jsonify
from flask_cors import CORS
from database import engine, SessionLocal, Base
import models

# Create database tables
Base.metadata.create_all(bind=engine)

app = Flask(__name__)
# Allow CORS for local HTML testing
CORS(app)

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
                "diagnostics": r.diagnostics
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
            pipeline_state["data"]["image_url"] = f"http://127.0.0.1:5000/api/images/{image_filename}"
            
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
        pipeline_state["status"] = "running"
        stages = pipeline_state["stages"]
        
        # Complete validation
        stages[4]["status"] = "done"
        
        # Stage 5: Upload
        pipeline_state["current_stage_index"] = 5
        stages[5]["status"] = "progress"
        
        def simulate_upload():
            # TODO: Integrate actual upload agent when ready
            time.sleep(2)
            stages[5]["status"] = "done"
            pipeline_state["status"] = "complete"
            
        thread = threading.Thread(target=simulate_upload)
        thread.daemon = True
        thread.start()
        
        return jsonify({"message": "Publishing sequence initiated"})
    return jsonify({"message": "Invalid state"}), 400

@app.route('/api/pipeline/reject', methods=['POST'])
def reject_pipeline():
    global pipeline_state
    if pipeline_state["status"] == "waiting_validation":
        # Reset back to idle
        pipeline_state["status"] = "idle"
        for stage in pipeline_state["stages"]:
            stage["status"] = "wait"
        pipeline_state["current_stage_index"] = -1
        return jsonify({"message": "Pipeline rejected and reset"})
    return jsonify({"message": "Invalid state"}), 400


if __name__ == '__main__':
    app.run(port=5000, debug=True)
