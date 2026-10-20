import csv
from pathlib import Path
import tempfile
import unittest
import numpy as np
from event_optical.event_analysis import EventAnalysis
from event_optical.reconstruction import EVENT_DTYPE


class AnalysisTests(unittest.TestCase):
    def run_analysis(self, chunks, bin_us=10):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        output = Path(temp.name)
        worker = EventAnalysis(output, bin_us)
        self.addCleanup(worker.close)
        worker.begin(3, 2, {'recorder_metadata': {'elapsed_seconds': 5}})
        for chunk in chunks:
            worker.feed(np.array(chunk, dtype=EVENT_DTYPE))
        summary = worker.finish()
        worker.close()
        with (output / 'event_rate.csv').open() as handle:
            return list(csv.DictReader(handle)), summary

    def test_boundaries_empty_bins_and_partial_denominator(self):
        rows, report = self.run_analysis([[(0,0,1,100),(1,0,0,109),(0,0,1,110),(0,1,0,135)]])
        self.assertEqual([int(r['cd_events']) for r in rows], [2,1,0,1])
        self.assertEqual([int(r['duration_us']) for r in rows], [10,10,10,6])
        self.assertEqual(float(rows[-1]['cd_event_rate_ev_s']), 1e6/6)
        self.assertEqual(report['decoded_cd_events'], 4)
        self.assertEqual(report['cd_event_span_seconds'], 36/1e6)
        self.assertEqual(report['host_capture_elapsed_seconds'], 5)
        self.assertFalse(report['losslessness_verified'])

    def test_chunk_independence_and_polarity_totals(self):
        data = [(0,0,1,10),(0,0,0,10),(1,0,1,20),(0,1,0,49)]
        a, stats = self.run_analysis([data])
        b, _ = self.run_analysis([data[:1], data[1:3], data[3:]])
        self.assertEqual(a,b)
        self.assertEqual(stats['positive_events'],2)
        self.assertEqual(stats['negative_events'],2)
        self.assertEqual(sum(int(r['cd_events']) for r in a),4)

    def test_single_event_included(self):
        rows, report = self.run_analysis([[(0,0,1,100)]])
        self.assertEqual(int(rows[0]['duration_us']),1)
        self.assertEqual(report['decoded_cd_events'],1)

    def test_reversal_across_callbacks_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            worker=EventAnalysis(temp,10)
            worker.begin(3,2,{})
            try:
                worker.feed(np.array([(0,0,1,10)],dtype=EVENT_DTYPE))
                with self.assertRaisesRegex(ValueError,'Timestamp reversal'):
                    worker.feed(np.array([(0,0,1,9)],dtype=EVENT_DTYPE))
                self.assertEqual(worker.negative_transitions,1)
            finally: worker.close()

    def test_bad_coordinate_rejected(self):
        with self.assertRaisesRegex(ValueError,'Invalid CD'):
            self.run_analysis([[(3,0,1,10)]])

    def test_empty_input_rejected(self):
        with self.assertRaisesRegex(ValueError,'no decoded CD'):
            self.run_analysis([[]])

    def test_invalid_bin_rejected(self):
        for value in (0,-1,True,1.5):
            with self.subTest(value=value),self.assertRaises(ValueError):
                EventAnalysis('.',value)


if __name__ == '__main__': unittest.main()
