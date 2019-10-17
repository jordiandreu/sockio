import asyncio
import inspect
import functools


def ensure_connection(f):
    if asyncio.iscoroutinefunction(f):
        async def wrapper(self, *args, **kwargs):
            async with self._lock:
                if self.auto_reconnect and not self.connected:
                    await self.open()
                return await f(self, *args, **kwargs)
    elif inspect.isasyncgenfunction(f):
        async def wrapper(self, *args, **kwargs):
            async with self._lock:
                if self.auto_reconnect and not self.connected:
                    await self.open()
                async_gen = f(self, *args, **kwargs)
            async for line in async_gen:
                yield line
    return functools.wraps(f)(wrapper)


class Socket:

    def __init__(self, host, port, auto_reconnect=True):
        self.host = host
        self.port = port
        self.auto_reconnect = auto_reconnect
        self.connection_counter = 0
        self._reader = None
        self._writer = None
        self._lock = asyncio.Lock()

    async def open(self):
        if self.connected:
            raise ConnectionError('socket already open. must close it first')
        self._reader, self._writer = await asyncio.open_connection(
            self.host, self.port)
        self.connection_counter += 1

    async def close(self):
        if self._writer is not None:
            self._writer.close()
            await self._writer.wait_closed()
        self._reader = None
        self._writer = None

    @property
    def connected(self):
        if self._reader is None:
            return False
        eof = self._reader.at_eof()
        return not eof

    @ensure_connection
    async def read(self, n=-1):
        return await self._reader.read(n)

    @ensure_connection
    async def readline(self):
        return await self._reader.readline()

    @ensure_connection
    async def readlines(self, n):
        for i in range(n):
            yield await self._reader.readline()

    @ensure_connection
    async def readexactly(self, n):
        return await self._reader.readexactly(n)

    @ensure_connection
    async def readuntil(self, separator=b'\n'):
        return await self._reader.readuntil(separator)

    @ensure_connection
    async def write(self, data):
        self._writer.write(data)
        await self._writer.drain()

    @ensure_connection
    async def writelines(self, lines):
        self._writer.writelines(lines)
        await self._writer.drain()

    @ensure_connection
    async def write_readline(self, data):
        self._writer.write(data)
        await self._writer.drain()
        return await self._reader.readline()

    @ensure_connection
    async def write_readlines(self, data, n):
        self._writer.write(data)
        await self._writer.drain()
        for i in range(n):
            yield await self._reader.readline()

    @ensure_connection
    async def writelines_readlines(self, lines, n=None):
        if n is None:
            n = len(lines)
        self._writer.writelines(lines)
        await self._writer.drain()
        for i in range(n):
            yield await self._reader.readline()


def app(options):
    async def run():
        sock = Socket(options.host, options.port)
        print(await sock.write_readline(options.request.encode()))
    asyncio.run(run())


def main(cb, args=None):
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='0',
                        help='SCPI device host name / IP')
    parser.add_argument('-p', '--port', type=int, help='SCPI device port')
    parser.add_argument('-r', '--request', default='*IDN?\n',
                        help='SCPI request [%(default)s]')

    options = parser.parse_args(args)
    cb(options)


if __name__ == '__main__':
    main(app)
