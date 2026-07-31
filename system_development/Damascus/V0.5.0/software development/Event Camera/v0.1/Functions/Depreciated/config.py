from pathlib import Path

current_dir = Path(__file__).resolve().parent
OUTPUT_FOLDER = Path(
    current_dir / "Recordings"
)

OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)
VIDEO_FPS = 30.0
RECORD_SECONDS: float | None = None
VIDEO_CODEC = "MJPG"
STREAM_BUFFER_COUNT = 50