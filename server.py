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


def is_ssl(transport: asyncio.Transport) -> bool:
    return bool(transport.get_extra_info("sslcontext"))


class H11Protocol(asyncio.BaseProtocol):
    def __init__(self, app: typing.Callable, on_response: typing.Callable) -> None:
        self.app = app
        self.conn = h11.Connection(h11.SERVER)
        self.loop = asyncio.get_event_loop()
        self.on_response = on_response

        # per-conn
        self.transport = None
        self.server = None
        self.client = None

        # per-request
        self.scope = None
        self.headers = None
        self.cycle = None

    def data_received(self, buffer: bytes):
        self.conn.receive_data(buffer)
        self.startup()

    def connection_made(self, transport):

        self.server = transport.get_extra_info("socket").getsockname()[0]
        self.client = transport.get_extra_info("socket").getpeername()[0]
        self.transport = transport

    def eof_received(self):
        pass

    def startup(self):

        while True:
            try:
                event = self.conn.next_event()
            except h11.RemoteProtocolError:
                return

            _type = type(event)
            if _type is h11.NEED_DATA:
                break

            elif _type is h11.PAUSED:
                break

            elif _type is h11.Request:
                raw_path, _, query_string = event.target.partition(b"?")
                self.scope = {
                    "type": "http",
                    "asgi": {
                        "version": "3.0",
                        "spec_version": "2.1",
                    },
                    "http_version": event.http_version.decode("ascii"),
                    "server": self.server,
                    "client": self.client,
                    "method": event.method.decode("ascii"),
                    "path": unquote(raw_path.decode("ascii")),
                    "raw_path": raw_path,
                    "query_string": query_string,
                    "headers": [(key.lower(), value) for key, value in event.headers],
                }

                self.cycle = Cycle(
                    scope=self.scope,
                    conn=self.conn,
                    transport=self.transport,
                    headers=event.headers,
                    message_event=asyncio.Event(),
                    on_response=self.on_response,
                )

                self.loop.create_task(self.cycle(app))

            elif _type is h11.EndOfMessage:
                self.cycle.message_event.set()


class Cycle:
    def __init__(
        self,
        scope,
        conn,
        transport,
        headers,
        message_event,
        on_response,
    ) -> None:
        self.scope = scope
        self.conn = conn
        self.transport = transport
        self.headers = headers
        self.message_event = message_event
        self.on_response = on_response
        self.response_complete = False

    async def __call__(self, app) -> typing.Any:
        await app(self.scope, self.receive, self.send)

    async def send(self, message):
        message_type = message["type"]
        if message_type == "http.response.body":
            body = message.get("body", b"")
            event = h11.Data(data=body)
            output = self.conn.send(event)
            self.transport.write(output)
            self.response_complete = True
            event = h11.EndOfMessage()
            output = self.conn.send(event)
            self.transport.write(output)

        elif message_type == "http.response.start":
            status_code = message["status"]
            headers = self.headers
            reason = b"OK"
            event = h11.Response(
                status_code=status_code, headers=headers, reason=reason
            )
            output = self.conn.send(event)
            self.transport.write(output)

        if self.response_complete:
            event = h11.ConnectionClosed()
            self.conn.send(event)
            self.transport.close()
            self.on_response()

    async def receive(self):

        # if not self.response_complete:
        #     await self.message_event.wait()
        #     self.message_event.clear()

        # if self.response_complete:
        #     message = {"type": "http.disconnect"}

        # else:
        #     message = {
        #         "type": "http.request",
        #         "body": self.body,
        #         "more_body": self.more_body,
        #     }
        #     self.body = b""

        # return message
        pass


# server
class Server:
    def __init__(
        self, app: typing.Callable, host: str = "127.0.0.1", port: int = 5000
    ) -> None:
        self.app = app
        self.host = host
        self.port = port

    async def handler(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):

        # read all data

        loop = asyncio.get_event_loop()
        connection_lost = loop.create_future()

        transport = writer.transport
        protocol = H11Protocol(
            self.app, on_response=lambda: connection_lost.set_result(True)
        )
        transport.set_protocol(protocol)

        protocol.connection_made(transport)
        data = reader._buffer  # type: ignore

        if data:
            protocol.data_received(data)

        await connection_lost

    async def serve(self):

        await asyncio.start_server(self.handler, self.host, self.port)
        while True:
            await asyncio.sleep(0.1)


class Request:
    def __init__(self, scope: dict) -> None:
        self.scope = scope

    @property
    def method(self):
        return self.scope["method"]

    @property
    def scheme(self):
        return self.scope["scheme"]

    @property
    def query_string(self):
        query = self.scope["query_string"].decode()
        return {
            key: value
            for key, value in [
                raw_single_query.split("=") for raw_single_query in query.split("#")
            ]
        }

    @property
    def headers(self):
        return {key.decode(): value.decode() for key, value in self.scope["headers"]}


class Response:
    def __init__(self, content: str, status_code: int) -> None:
        self.body = content.encode()
        self.status_code = status_code

    def __str__(self) -> str:
        return f"Response(content={self.body!r},status_code={self.status_code})"


class Route:
    def __init__(self, path: str, endpoint: typing.Callable) -> None:
        self.path = path
        self.endpoint = endpoint

    async def __call__(
        self,
        scope: dict,
        receive: typing.Callable,
        send: typing.Callable,
    ) -> None:

        request = Request(scope)
        res: Response = await self.endpoint(request)
        logger.info(f"res = {res}")
        await send(
            {
                "type": "http.response.start",
                "status": res.status_code,
            }
        )

        await send({"type": "http.response.body", "body": res.body})

    def match(self, url: str) -> bool:
        return url == self.path


class Router:
    class NotFound(Exception):
        pass

    def __init__(self, routes: typing.List[Route]) -> None:
        self.routes = routes

    async def __call__(
        self,
        scope: dict,
        receive: typing.Callable,
        send: typing.Callable,
    ) -> None:

        url = scope["path"]
        for r in self.routes:
            if r.match(url):
                return await r(scope, receive, send)

        raise self.NotFound()


class Application:
    def __init__(self, router: Router) -> None:
        self.router = router

    async def __call__(
        self,
        scope: dict,
        receive: typing.Callable,
        send: typing.Callable,
    ) -> None:

        return await self.router(scope, receive, send)


# business
async def hello(request: Request) -> Response:

    name = request.query_string.get("name")
    return Response(f"hello, {name}", 200)


router = Router([Route("/", hello)])
app = Application(router)


if __name__ == "__main__":
    server = Server(app)
    asyncio.run(server.serve())
