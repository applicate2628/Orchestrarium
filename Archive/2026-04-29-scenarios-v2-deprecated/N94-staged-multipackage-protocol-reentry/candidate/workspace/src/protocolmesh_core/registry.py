class HandlerRegistry:
    def __init__(self, handlers=None):
        self.handlers = dict(handlers or {})

    def register(self, action, handler):
        self.handlers[action] = handler

    def lookup(self, action):
        return self.handlers.get(action)
