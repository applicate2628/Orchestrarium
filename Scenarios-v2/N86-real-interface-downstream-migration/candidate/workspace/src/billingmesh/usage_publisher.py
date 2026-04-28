class UsagePublisher:
    def __init__(self, transport):
        self.transport = transport

    def publish(self, event):
        return bool(self.transport.send(event))
