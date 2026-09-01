class TransientError(Exception):
    pass


class RetryWorker:
    def __init__(self, max_retries):
        self.max_retries = max_retries

    def run(self, job):
        attempts = 0
        while attempts < self.max_retries:
            try:
                return job()
            except TransientError:
                if job.calls > self.max_retries:
                    raise AssertionError(
                        f"observed {job.calls} job calls with max_retries={self.max_retries}"
                    )
            else:
                attempts += 1
        raise RuntimeError("retry budget exhausted")


class AlwaysTransient:
    def __init__(self):
        self.calls = 0

    def __call__(self):
        self.calls += 1
        raise TransientError("temporary")


def test_transient_errors_stop_at_budget():
    RetryWorker(max_retries=3).run(AlwaysTransient())


if __name__ == "__main__":
    test_transient_errors_stop_at_budget()
