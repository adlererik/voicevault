"""Synthetic negative controls for the evidence checker, not MCU test results."""
import copy
import unittest
from trace_contract import observation_errors, qualify


class TraceContractTests(unittest.TestCase):
    def setUp(self):
        samples = [((index * 257) % 65536) - 32768 for index in range(320)]
        self.trace = {
            'target':'STM32U5G9ZJT6Q', 'revision':'Z', 'rev_id':'0x1001',
            'timed_out':False, 'unexpected_register_accesses':[], 'emulator_warnings':[],
            'image_sha256':'0' * 64, 'qualified_profile':'synthetic-checker-fixture',
            'audio':{'tx_samples':samples, 'rx_samples':samples.copy(), 'dma_irqs':[29,30,29,30],
                     'guard_words_intact':True, 'underrun_recovered':True},
            'isolation':{'cpu_denied':True,'dma_denied':True,'trusted_memory_unchanged':True,
                         'allowed_transfer_completed':True,'fault_irq':8}}

    def test_fixture_observations_are_well_formed(self):
        self.assertEqual(observation_errors(self.trace), [])

    def test_synthetic_success_cannot_qualify_a_model(self):
        self.assertEqual(qualify(self.trace)['status'], 'fail')

    def test_all_required_fields_fail_when_missing(self):
        paths = [(key,) for key in ('target','revision','rev_id','timed_out',
                 'unexpected_register_accesses','emulator_warnings','image_sha256')]
        paths += [('audio',key) for key in self.trace['audio']]
        paths += [('isolation',key) for key in self.trace['isolation']]
        for path in paths:
            with self.subTest(path=path):
                changed = copy.deepcopy(self.trace)
                parent = changed if len(path) == 1 else changed[path[0]]
                del parent[path[-1]]
                self.assertTrue(observation_errors(changed))

    def test_corrupted_sample_rejected(self):
        self.trace['audio']['rx_samples'][319] ^= 1
        self.assertTrue(observation_errors(self.trace))

    def test_unmapped_access_rejected(self):
        self.trace['unexpected_register_accesses'] = ['0x40015800']
        self.assertTrue(observation_errors(self.trace))

    def test_missing_dma_irq_rejected(self):
        self.trace['audio']['dma_irqs'].pop()
        self.assertTrue(observation_errors(self.trace))

    def test_malformed_json_shapes_rejected(self):
        for value in (None, [], 12, 'success'):
            with self.subTest(value=value):
                self.assertEqual(qualify(value)['status'], 'fail')
        for field in ('audio','isolation'):
            self.trace[field] = []
        self.assertTrue(observation_errors(self.trace))

    def test_timeout_rejected(self):
        self.trace['timed_out'] = True
        self.assertTrue(observation_errors(self.trace))

    def test_allowed_access_must_also_work(self):
        self.trace['isolation']['allowed_transfer_completed'] = False
        self.assertTrue(observation_errors(self.trace))


if __name__ == '__main__':
    unittest.main(verbosity=2)
