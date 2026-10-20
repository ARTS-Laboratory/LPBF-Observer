"""Behavioral tests independent of the native camera SDK."""
import json
from pathlib import Path
import tempfile
import unittest

import cv2
import h5py
import numpy as np

from event_optical.reconstruction import EVENT_DTYPE, Reconstruction, reconstruct


class ReconstructionTests(unittest.TestCase):
    def run_chunks(self, chunks, **settings):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        output = Path(temp.name)
        worker = Reconstruction(output, **settings)
        self.addCleanup(worker.close)
        worker.begin(3, 2, {'original': 'preserved'})
        for chunk in chunks:
            worker.feed(np.array(chunk, dtype=EVENT_DTYPE))
        info = worker.finish()
        worker.close()
        return output, info

    def test_trim_window_boundaries_and_final_clip(self):
        chunks = [[(0, 0, 1, 100), (1, 0, 0, 109), (2, 0, 1, 110)],
                  [(0, 1, 1, 119), (1, 1, 0, 120), (2, 1, 1, 124), (0, 0, 0, 125)]]
        output, info = self.run_chunks(chunks, window_us=10, start_s=.000010, end_s=.000025)
        with h5py.File(output / 'curated.h5') as h5:
            self.assertEqual(h5['events']['t'].tolist(), [110, 119, 120, 124])
            self.assertEqual(json.loads(h5['source_metadata_json'][()]), {'original': 'preserved'})
            self.assertTrue(h5.attrs['reconstruction_complete'])
        frames = [json.loads(line) for line in (output / 'frames.jsonl').read_text().splitlines()]
        self.assertEqual([(f['start_us'], f['end_us_exclusive'], f['events']) for f in frames],
                         [(110, 120, 2), (120, 125, 2)])
        self.assertEqual(info['total_events'], 4)

    def test_chunk_partition_independent_images_and_last_polarity(self):
        events = [(0, 0, 1, 0), (0, 0, 0, 1), (1, 0, 1, 2),
                  (0, 1, 0, 25), (0, 1, 1, 26)]
        first, _ = self.run_chunks([events], window_us=10)
        second, _ = self.run_chunks([events[:1], events[1:3], events[3:]], window_us=10)
        for path in first.glob('*/*.png'):
            self.assertEqual(path.read_bytes(), (second / path.relative_to(first)).read_bytes())
        frame = cv2.imread(str(sorted((first / 'binary').glob('*.png'))[0]))
        self.assertEqual(frame[0, 0].tolist(), [255, 0, 0])
        self.assertEqual(frame[1, 2].tolist(), [40, 40, 40])
        blank = cv2.imread(str(sorted((first / 'signed_linear').glob('*.png'))[1]))
        self.assertTrue(np.all(blank == 40))

    def test_signed_log_changes_intensity_and_cancellation_is_neutral(self):
        events = [(0, 0, 1, 0)] * 4 + [(1, 0, 1, 1), (2, 0, 1, 2), (2, 0, 0, 3)]
        output, _ = self.run_chunks([events])
        linear = cv2.imread(str(next((output / 'signed_linear').glob('*.png'))))
        log = cv2.imread(str(next((output / 'signed_log').glob('*.png'))))
        self.assertEqual(linear[0, 0].tolist(), [0, 0, 255])
        self.assertGreater(int(log[0, 1, 2]), int(linear[0, 1, 2]))
        self.assertEqual(log[0, 2].tolist(), [40, 40, 40])

    def test_last_timestamp_included_and_legacy_metadata_copied(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / 'original.h5'
            with h5py.File(source, 'w') as h5:
                h5.attrs.update(width=3, height=2, camera_model='TRT009', custom=42)
                data = h5.create_dataset('events', data=np.array([(0, 0, 1, 100), (1, 1, 0, 110)], dtype=EVENT_DTYPE))
                data.attrs['units'] = 'sensor ticks'
            output = reconstruct(source, root / 'output', window_us=10, modes=['binary'])
            with h5py.File(output / 'curated.h5') as h5:
                self.assertEqual(h5['events']['t'].tolist(), [100, 110])
                self.assertEqual(h5.attrs['custom'], 42)
                self.assertEqual(h5['events'].attrs['units'], 'sensor ticks')
                self.assertEqual(h5.attrs['selection_end_us_exclusive'], 111)
            self.assertEqual(json.loads((output / 'metadata.json').read_text())['state'], 'complete')

    def test_timestamp_reversal_marks_output_incomplete(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / 'bad.h5'
            with h5py.File(source, 'w') as h5:
                h5.attrs.update(width=3, height=2)
                h5.create_dataset('events', data=np.array([(0, 0, 1, 10), (0, 0, 0, 9)], dtype=EVENT_DTYPE))
            with self.assertRaisesRegex(ValueError, 'Timestamp reversal'):
                reconstruct(source, root / 'output')
            output = next((root / 'output').iterdir())
            self.assertEqual(json.loads((output / 'metadata.json').read_text())['state'], 'incomplete')
            with h5py.File(output / 'curated.h5') as h5:
                self.assertFalse(h5.attrs['reconstruction_complete'])

    def test_empty_selection_rejected(self):
        with self.assertRaisesRegex(ValueError, 'no CD events'):
            self.run_chunks([[(0, 0, 1, 0)]], start_s=1)

    def test_configuration_rejected_before_output(self):
        for settings in ({'window_us': 0}, {'start_s': -1}, {'end_s': float('nan')},
                         {'start_s': 2, 'end_s': 1}, {'modes': ['unknown']}):
            with self.subTest(settings=settings), self.assertRaises(ValueError):
                Reconstruction(Path('unused'), **settings)


if __name__ == '__main__':
    unittest.main()
