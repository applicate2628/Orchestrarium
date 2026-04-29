class HttpAdapter:
    def __init__(self, transport):
        self.transport = transport

    def publish(self, payload):
        return self.transport.send(payload)
