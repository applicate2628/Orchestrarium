class EventRouter:
    def __init__(self, transport):
        self.transport = transport

    def dispatch(self, event):
        return bool(self.transport.send(event))
