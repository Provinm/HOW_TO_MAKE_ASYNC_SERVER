import typing
import asyncio
import logging
import h11
from urllib.parse import unquote

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(filename)s [line:%(lineno)d] %(levelname)s %(message)s",
    datefmt="%a, %d %b %Y %H:%M:%S",
    filemode="w",
)

logger = logging.getLogger()


# server
class Server:
    def __init__(
        self, app: typing.Callable, host: str = "127.0.0.1", port: int = 5000
    ) -> None:
        self.app = app
        self.host = host
        self.port = port

    async def handler(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):

        conn = h11.Connection(h11.SERVER)
        data = await reader.read(1000)
        conn.receive_data(data)

        default_headers = None
        resp = None
        while True:
            event = conn.next_event()
            event_type = type(event)

            if event_type is h11.Request:
                default_headers = event.headers
                resp = await self.app(event)

            elif event_type is h11.EndOfMessage:
                continue

            else:
                break

        # start resp
        event = h11.Response(
            status_code=200,
            headers=default_headers,
            reason="OK",
        )
        output = conn.send(event)
        writer.write(output)

        # write resp
        body = resp.encode() if resp else b""
        event = h11.Data(data=body)
        output = conn.send(event)
        writer.write(output)

        # write endofmsg
        endevent = h11.EndOfMessage()
        output = conn.send(endevent)
        writer.write(output)

        # close
        closeevent = h11.ConnectionClosed()
        output = conn.send(closeevent)

        # start response
        await writer.drain()
        writer.close()

    async def serve(self):

        await asyncio.start_server(self.handler, self.host, self.port)
        while True:
            await asyncio.sleep(0.1)


# business
async def app(request: h11.Request) -> str:
    target = request.target.decode()

    if target == "/":
        return "hello,world"
    return f"hello, {target}"


if __name__ == "__main__":
    server = Server(app)
    asyncio.run(server.serve())
