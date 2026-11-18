import copy
import unittest
from audit_cuda_resize_v1 import validate


def records():
    pinned = dict(library='/frozen/libresize.so', sha256='ab' * 32)
    metadata = dict(**pinned, kind='cuda-two-pass-exact-v1', cpu_resize_threads=0,
                    host_wait='cudaEventBlockingSync', calls=3, failures=0,
                    closed=True, owner_thread_id=22, owner_native_tid=23)
    owner = dict(preparation_thread_overrides=dict(cv=4, resize=0),
                 preparation_calls=[dict(owner_thread_id=22)] * 3, model_calls=[],
                 cuda_resize=copy.deepcopy(metadata))
    renderer = dict(host_pipeline=dict(cv_threads=4, resize_threads=0, thread_id=23),
                    preparation=[{}] * 3, inference=[], cuda_resize=copy.deepcopy(metadata))
    return dict(cuda_resize=pinned), owner, renderer


class CudaResizeAuditTests(unittest.TestCase):
    def test_both_owners_original_counts_and_exact_library(self):
        self.assertEqual(validate(*records())['status'], 'PASS_EXPLICIT_CUDA_RESIZE_ONLY')

    def test_missing_or_substituted_lifetime_cannot_pass(self):
        for field, value in [('sha256', 'cd' * 32), ('calls', 2), ('failures', 1),
                             ('closed', False), ('cpu_resize_threads', 4),
                             ('host_wait', 'spin'), ('owner_thread_id', 99)]:
            with self.subTest(field=field):
                server, owner, renderer = records()
                owner['cuda_resize'][field] = value
                with self.assertRaises(ValueError): validate(server, owner, renderer)

    def test_worker_handoff_and_failed_inference(self):
        server, owner, renderer = records()
        renderer['host_pipeline']['thread_id'] += 1
        with self.assertRaises(ValueError): validate(server, owner, renderer)
        server, owner, renderer = records()
        renderer['inference'].append(dict(error='failed model'))
        renderer['cuda_resize']['calls'] += 1
        with self.assertRaises(ValueError): validate(server, owner, renderer)


if __name__ == '__main__': unittest.main()
