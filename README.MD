# Auto English Subtitles (runs locally, no API key)

Drop in any downloaded video (any spoken language) and get back an English
`.srt` subtitle file, timed to match, that VLC picks up automatically.

It uses OpenAI's open-source **Whisper** model, which runs entirely on your
own machine — nothing is uploaded anywhere, no API key or account needed.
The model weights (a few hundred MB) download once the first time you run it,
then it works fully offline.

## 1. Install Python requirements

```bash
pip install -r requirements.txt
```

This installs Flask and `openai-whisper`. Whisper also needs **PyTorch** —
`pip` usually pulls a CPU-only build automatically. If you have an NVIDIA GPU
and want it to run faster, install a CUDA build of PyTorch first from
https://pytorch.org/get-started/locally/, then run the command above.

## 2. Install ffmpeg

Whisper uses ffmpeg to read audio out of video files.

- **Windows:** `winget install ffmpeg` (or download from ffmpeg.org and add
  it to your PATH)
- **Mac:** `brew install ffmpeg`
- **Linux (Debian/Ubuntu):** `sudo apt install ffmpeg`

## 3. Run it

```bash
python app.py
```

The first run downloads the Whisper model — this can take a few minutes.
Once you see "Server ready", open **http://localhost:5000** in your browser.

## 4. Use it

1. Drag your `.mp4` / `.m4v` / `.m4a` / `.mkv` file onto the page.
2. Wait — processing time is roughly the length of the video, sometimes a
   bit more, depending on your CPU and the model size.
3. Download the `.srt` file.
4. **Rename it to exactly match your video's filename** and put it in the
   same folder, e.g.:
   ```
   MyMovie.mp4
   MyMovie.srt
   ```
   VLC automatically loads a same-named `.srt` sitting next to the video —
   no manual "load subtitle" step needed.

## Choosing model size (speed vs. accuracy)

By default it uses the `small` model, a good balance for a normal laptop.
You can change this by setting an environment variable before running:

```bash
# faster, rougher translation
WHISPER_MODEL=base python app.py

# slower, noticeably more accurate (needs more RAM/CPU or a GPU)
WHISPER_MODEL=medium python app.py
```

Options, roughly fastest→most accurate: `tiny`, `base`, `small`, `medium`, `large`.

## Notes

- Works for movies/series in **any language Whisper supports** (100+
  languages) — it transcribes the original speech and translates it
  directly into English text in one pass.
- Long files (a 2-hour movie) can take a while on CPU-only machines —
  that's normal, just let it run.
- This is a local single-user tool (no login, no cloud) — don't expose
  port 5000 to the internet as-is.