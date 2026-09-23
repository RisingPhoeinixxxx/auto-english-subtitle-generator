"""
Auto English Subtitles — runs 100% locally, no API key needed.

Uses OpenAI's open-source Whisper model (downloaded once, then runs offline)
to transcribe speech in ANY language and translate it directly to English
text, with timestamps, producing a standard .srt subtitle file.

Setup:
    pip install -r requirements.txt
    (also install ffmpeg — see README.md)

Run:
    python app.py

Then open http://localhost:5000 in your browser, drop in your downloaded
.mp4 (or .m4v/.m4a), wait for it to process, and download the .srt file.
Save the .srt next to your video with the SAME filename (e.g.
movie.mp4 + movie.srt) and VLC will load it automatically.
"""

import os
import sys
import tempfile
import threading
import time
from pathlib import Path

from flask import Flask, render_template_string, request, send_file, jsonify

try:
    import whisper
except ImportError:
    print("Missing dependency. Run: pip install -r requirements.txt")
    sys.exit(1)

app = Flask(__name__)

UPLOAD_DIR = Path(tempfile.gettempdir()) / "auto_subtitles"
UPLOAD_DIR.mkdir(exist_ok=True)

# Model size vs speed/accuracy tradeoff. Options: tiny, base, small, medium, large
# 'small' is a good default on a normal laptop CPU. Use 'base' for faster/rougher,
# 'medium' or 'large' for much better accuracy if you have a decent GPU.
MODEL_SIZE = os.environ.get("WHISPER_MODEL", "small")

print(f"Loading Whisper model '{MODEL_SIZE}' (first run downloads it once, then it's offline)...")
model = whisper.load_model(MODEL_SIZE)
print("Model loaded. Server ready.")

jobs = {}  # job_id -> status dict

INDEX_HTML = """
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Auto English Subtitles (Local)</title>
<style>
  body { font-family: -apple-system, Segoe UI, Roboto, sans-serif; max-width: 640px;
         margin: 60px auto; padding: 0 20px; color: #1a1a1a; }
  h1 { font-size: 1.4rem; }
  .drop { border: 2px dashed #999; border-radius: 12px; padding: 40px 20px;
          text-align: center; cursor: pointer; transition: 0.2s; }
  .drop.drag { border-color: #333; background: #f5f5f5; }
  .drop input { display: none; }
  #status { margin-top: 20px; font-size: 0.95rem; }
  progress { width: 100%; height: 10px; margin-top: 10px; }
  #dl { display: none; margin-top: 16px; padding: 10px 18px; background: #1a1a1a;
        color: #fff; border: none; border-radius: 8px; cursor: pointer; text-decoration: none; }
  .hint { color: #666; font-size: 0.85rem; margin-top: 30px; line-height: 1.5; }
</style>
</head>
<body>
  <h1>🎬 Auto English Subtitles</h1>
  <p>Drop any movie/series file (any spoken language) — get an English .srt back. Runs fully locally.</p>

  <div class="drop" id="drop">
    <p id="dropText">Click or drag a video file here (.mp4, .m4v, .m4a, .mkv, .avi...)</p>
    <input type="file" id="fileInput" accept="video/*,audio/*">
  </div>

  <div id="status"></div>
  <a id="dl" href="#">⬇ Download .srt</a>

  <div class="hint">
    Save the downloaded .srt in the <b>same folder</b> as your video, with the
    <b>same filename</b> (e.g. <code>movie.mp4</code> + <code>movie.srt</code>) —
    VLC will pick it up automatically.
  </div>

<script>
const drop = document.getElementById('drop');
const fileInput = document.getElementById('fileInput');
const statusEl = document.getElementById('status');
const dlBtn = document.getElementById('dl');

drop.onclick = () => fileInput.click();
drop.ondragover = e => { e.preventDefault(); drop.classList.add('drag'); };
drop.ondragleave = () => drop.classList.remove('drag');
drop.ondrop = e => {
  e.preventDefault();
  drop.classList.remove('drag');
  if (e.dataTransfer.files.length) handleFile(e.dataTransfer.files[0]);
};
fileInput.onchange = () => { if (fileInput.files.length) handleFile(fileInput.files[0]); };

function handleFile(file) {
  dlBtn.style.display = 'none';
  statusEl.innerHTML = 'Uploading "' + file.name + '"...';
  const form = new FormData();
  form.append('video', file);
  fetch('/upload', { method: 'POST', body: form })
    .then(r => r.json())
    .then(data => {
      if (data.error) { statusEl.textContent = 'Error: ' + data.error; return; }
      poll(data.job_id);
    })
    .catch(err => statusEl.textContent = 'Upload failed: ' + err);
}

function poll(jobId) {
  statusEl.innerHTML = 'Transcribing + translating... (this can take a few minutes depending on video length and model size) <progress></progress>';
  const iv = setInterval(() => {
    fetch('/status/' + jobId).then(r => r.json()).then(job => {
      if (job.status === 'done') {
        clearInterval(iv);
        statusEl.textContent = 'Done! Detected source language: ' + (job.detected_language || 'unknown');
        dlBtn.href = '/download/' + jobId;
        dlBtn.style.display = 'inline-block';
      } else if (job.status === 'error') {
        clearInterval(iv);
        statusEl.textContent = 'Error: ' + job.error;
      }
    });
  }, 3000);
}
</script>
</body>
</html>
"""


def format_timestamp(seconds: float) -> str:
    ms = int(round((seconds - int(seconds)) * 1000))
    s = int(seconds) % 60
    m = (int(seconds) // 60) % 60
    h = int(seconds) // 3600
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def write_srt(segments, path: Path):
    with open(path, "w", encoding="utf-8") as f:
        for i, seg in enumerate(segments, start=1):
            f.write(f"{i}\n")
            f.write(f"{format_timestamp(seg['start'])} --> {format_timestamp(seg['end'])}\n")
            f.write(seg["text"].strip() + "\n\n")


def process_video(job_id: str, video_path: Path, srt_path: Path):
    try:
        jobs[job_id]["status"] = "transcribing"
        # task="translate" makes Whisper translate any spoken language
        # directly into English text (not just transcribe in the original language).
        result = model.transcribe(str(video_path), task="translate", verbose=False)
        write_srt(result["segments"], srt_path)
        jobs[job_id]["status"] = "done"
        jobs[job_id]["detected_language"] = result.get("language", "unknown")
    except Exception as e:
        jobs[job_id]["status"] = "error"
        jobs[job_id]["error"] = str(e)
    finally:
        try:
            video_path.unlink(missing_ok=True)
        except Exception:
            pass


@app.route("/")
def index():
    return render_template_string(INDEX_HTML)


@app.route("/upload", methods=["POST"])
def upload():
    if "video" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    f = request.files["video"]
    job_id = str(int(time.time() * 1000))
    safe_name = f.filename.replace("/", "_").replace("\\", "_")
    video_path = UPLOAD_DIR / f"{job_id}_{safe_name}"
    f.save(video_path)
    srt_path = UPLOAD_DIR / f"{job_id}.srt"
    jobs[job_id] = {"status": "queued", "srt_path": str(srt_path), "video_name": safe_name}
    threading.Thread(target=process_video, args=(job_id, video_path, srt_path), daemon=True).start()
    return jsonify({"job_id": job_id})


@app.route("/status/<job_id>")
def status(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    return jsonify(job)


@app.route("/download/<job_id>")
def download(job_id):
    job = jobs.get(job_id)
    if not job or job.get("status") != "done":
        return jsonify({"error": "Not ready"}), 400
    srt_name = Path(job["video_name"]).stem + ".srt"
    return send_file(job["srt_path"], as_attachment=True, download_name=srt_name)


if __name__ == "__main__":
    app.run(debug=False, host="127.0.0.1", port=5000)