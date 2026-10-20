"""Preserve a second incomplete EVT3 item when completing a buffered item.

Applies only to the recognized OpenEB 5.2-era implementation. The original
source is retained next to the header; the patch recipe belongs in this repo.
"""
import argparse
from pathlib import Path

MARKER = "// LPBF Observer: retain chained incomplete EVT3 items."
START = "        if (raw_events_missing_count_ > 0) {"
END = "        raw_events_missing_count_ = is_time_shifting_enabled() ? decode_events_buffer<true>(cur_raw_ev, raw_ev_end) :"
REPLACEMENT = '''        // LPBF Observer: retain chained incomplete EVT3 items.
        while (raw_events_missing_count_ > 0) {
            const auto copied_count =
                std::min(raw_events_missing_count_, std::distance(cur_raw_ev, raw_ev_end));
            incomplete_multiword_raw_event_.insert(incomplete_multiword_raw_event_.end(), cur_raw_ev,
                                                   cur_raw_ev + copied_count);
            cur_raw_ev += copied_count;
            raw_events_missing_count_ -= copied_count;
            if (raw_events_missing_count_ > 0) {
                return;
            }

            const RawEvent *buffered_begin = incomplete_multiword_raw_event_.data();
            const RawEvent *const buffered_end = buffered_begin + incomplete_multiword_raw_event_.size();
            raw_events_missing_count_ = is_time_shifting_enabled() ?
                decode_events_buffer<true>(buffered_begin, buffered_end) :
                decode_events_buffer<false>(buffered_begin, buffered_end);

            // An OTHERS marker can consume fewer words than its maximum length.
            // Its lookahead can therefore end in a second incomplete item.
            const auto consumed_count = std::distance(
                static_cast<const RawEvent *>(incomplete_multiword_raw_event_.data()), buffered_begin);
            incomplete_multiword_raw_event_.erase(incomplete_multiword_raw_event_.begin(),
                                                 incomplete_multiword_raw_event_.begin() + consumed_count);
            if (raw_events_missing_count_ > 0 && cur_raw_ev == raw_ev_end) {
                return;
            }
        }
'''


def patch(source_root):
    path = source_root / "hal/cpp/include/metavision/hal/decoders/evt3/evt3_decoder.h"
    text = path.read_text()
    if MARKER in text:
        print("Boundary patch already applied:", path)
        return
    if text.count(START) != 1 or text.count(END) != 1:
        raise RuntimeError("Unrecognized decoder layout; source left unchanged")
    begin, end = text.index(START), text.index(END)
    old = text[begin:end]
    if end <= begin or "incomplete_multiword_raw_event_.clear();" not in old or \
       "decode_events_buffer<true>(multi_word_raw_ev_begin, multi_word_raw_ev_end)" not in old:
        raise RuntimeError("Expected split-event implementation not found; source left unchanged")
    backup = path.with_name(path.name + ".before_lpbf_boundary_fix")
    if backup.exists():
        raise RuntimeError(f"Backup already exists; inspect it before patching: {backup}")
    with backup.open("x") as handle:
        handle.write(text)
    path.write_text(text[:begin] + REPLACEMENT + text[end:])
    print("Patched:", path)
    print("Original:", backup)
    print("Rebuild the Python OpenEB build, then run the boundary regression.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_root", type=Path, nargs="?", default=Path.home() / "src/openeb-5.2.0")
    patch(parser.parse_args().source_root)
