"""Regression for the observed zero-exit-code numerical-abort failure mode."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from spice_results import measurements_from_log


class SimulatorResults(unittest.TestCase):
    def test_complete_finite_measurement(self):
        self.assertEqual(measurements_from_log('normal_v = 3.29335e+00\n', ['normal_v']), {'normal_v': 3.29335})

    def test_zero_exit_after_partial_measurement_is_still_abort(self):
        log = 'normal_v = 3.29335e+00\ndoAnalyses: TRAN: Timestep too small\nrun simulation(s) aborted\n'
        with self.assertRaises(RuntimeError):
            measurements_from_log(log, ['normal_v'], exit_code=0)

    def test_nonzero_exit_rejected_even_with_measurements(self):
        with self.assertRaises(RuntimeError):
            measurements_from_log('normal_v = 3.29335\n', ['normal_v'], exit_code=1)

    def test_missing_measurement_rejected(self):
        with self.assertRaises(RuntimeError):
            measurements_from_log('No. of Data Rows : 20\n', ['normal_v'])

    def test_nonfinite_results_rejected(self):
        for value in ['nan', 'inf', '1e999']:
            with self.subTest(value=value), self.assertRaises(RuntimeError):
                measurements_from_log('normal_v = '+value+'\n', ['normal_v'])

    def test_error_rejected_even_with_measurements(self):
        with self.assertRaises(RuntimeError):
            measurements_from_log('normal_v = 3.29335\n  Error: source failed\n', ['normal_v'])


if __name__ == '__main__':
    unittest.main()
