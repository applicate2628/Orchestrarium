class SessionStore:
    def __init__(self, records, now=50):
        self.records = records
        self.now = now

    def get(self, session_id):
        record = self.records.get(session_id)
        if not record:
            return None
        return dict(record)
