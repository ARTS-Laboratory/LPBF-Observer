# ============================================================
# Recording Settings
# ============================================================

POSITIVE_EVENT_BIAS = 5
NEGATIVE_EVENT_BIAS = 5

LOW_PASS_CUTOFF = 20
REFRACTORY_PERIOD = -20

ERC_ENABLE = True
ERC_RATE_LIMIT = 3000

# ============================================================
# Reconstruction Settings
# ============================================================

# Playback
VIDEO_FPS = 6

# Time window used to accumulate events (microseconds)
WINDOW_US = 1000         # 5 ms

# Video
VIDEO_CODEC = "MJPG"

#event camera
SERIAL_NUMBER = 250200198
#SERIAL_NUMBER = 253000176