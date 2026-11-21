"""Bounded Windows message pipe. No receiver authority on its own."""
import math
import time
import _winapi as win

MAX_FRAME = 4 * 1024 * 1024


def settle(ov, deadline, owner=None):
    """Cancel AND settle pending IO on timeout, owner exit or exception."""
    try:
        if owner is not None and win.WaitForSingleObject(owner, 0) != win.WAIT_TIMEOUT:
            raise TimeoutError('broker owner exited')
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError('broker deadline')
        handles = [ov.event] + ([owner] if owner is not None else [])
        status = win.WaitForMultipleObjects(handles, False, max(1, math.ceil(remaining * 1000)))
        if status != 0:
            raise TimeoutError('broker deadline or owner exit')
        result = ov.GetOverlappedResult(True)
        if owner is not None and win.WaitForSingleObject(owner, 0) != win.WAIT_TIMEOUT:
            raise TimeoutError('broker owner exited')
        return result
    except BaseException as primary:
        # Settlement is mandatory even when CancelIoEx itself reports an error.
        # Kernel settlement is not a separate user-space hard time guarantee.
        for operation in (ov.cancel, lambda: ov.GetOverlappedResult(True)):
            try:
                operation()
            except BaseException as cleanup:
                primary.add_note('IO cleanup failure: ' + repr(cleanup))
        raise


class Connection:
    def __init__(self, handle, deadline, owner):
        self.handle, self.deadline, self.owner = handle, deadline, owner

    def fileno(self):
        return self.handle

    def recv_bytes(self, maxlength=MAX_FRAME):
        if not 0 < maxlength <= MAX_FRAME:
            raise ValueError('frame bound')
        ov, _ = win.ReadFile(self.handle, maxlength, overlapped=True)
        _, error = settle(ov, self.deadline, self.owner)
        if error == win.ERROR_MORE_DATA:
            raise ValueError('oversized broker frame')
        if error:
            raise OSError(error, 'broker read failed')
        return bytes(ov.getbuffer())

    def send_bytes(self, data):
        if len(data) > MAX_FRAME:
            raise ValueError('oversized broker response')
        ov, _ = win.WriteFile(self.handle, data, overlapped=True)
        count, error = settle(ov, self.deadline, self.owner)
        if error or count != len(data):
            raise OSError(error, 'broker write incomplete')

    def close(self):
        if self.handle is not None:
            win.CloseHandle(self.handle)
            self.handle = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class Broker:
    def __init__(self, address, *, deadline, owner=None):
        self.address, self.deadline, self.owner = address, deadline, owner
        self.handle = self._new(first=True)

    def _new(self, first=False):
        return win.CreateNamedPipe(self.address,
            win.PIPE_ACCESS_DUPLEX | win.FILE_FLAG_OVERLAPPED |
            (win.FILE_FLAG_FIRST_PIPE_INSTANCE if first else 0),
            win.PIPE_TYPE_MESSAGE | win.PIPE_READMODE_MESSAGE | win.PIPE_WAIT,
            2, 65536, 65536, 0, win.NULL)

    def accept(self):
        handle = self.handle
        # Keep an instance available while this connection is processed.
        self.handle = self._new()
        try:
            ov = win.ConnectNamedPipe(handle, overlapped=True)
            _, error = settle(ov, self.deadline, self.owner)
            if error:
                raise OSError(error, 'broker connect failed')
            return Connection(handle, self.deadline, self.owner)
        except BaseException:
            win.CloseHandle(handle)
            raise

    def close(self):
        if self.handle is not None:
            win.CloseHandle(self.handle)
            self.handle = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
