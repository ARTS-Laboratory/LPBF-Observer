"""Change these two values, then press Run for event recording + post-recording photo."""
import sys
from native_experiment import run

NAME = "run_10_welding_glass"
DURATION_SECONDS = 5


if __name__ == '__main__':
    try:
        raise SystemExit(run(NAME, DURATION_SECONDS))
    except Exception as error:
        print(f'Cannot start paired recording: {error}', file=sys.stderr)
        raise SystemExit(1)
