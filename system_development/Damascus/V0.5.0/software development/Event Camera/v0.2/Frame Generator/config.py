# ============================================================
# Camera 
# ============================================================

#event camera
SERIAL_NUMBER = 250200198
#SERIAL_NUMBER = 253000176

# ============================================================
# Recording Settings
# ============================================================

POSITIVE_EVENT_BIAS = 5    
NEGATIVE_EVENT_BIAS = 5

LOW_PASS_CUTOFF = 20
REFRACTORY_PERIOD = -20

ERC_ENABLE = False
ERC_RATE_LIMIT = None

# ============================================================
# Reconstruction Settings
# ============================================================

# Time window used to accumulate events (microseconds)
WINDOW_US = 100000     
STEP_US = 10000

# Do 'none' to use the entire recording, otherwise specify start and end times in seconds
START_TIME_S = 5.641000
END_TIME_S = 6.297000

