from os import write
import typing
import asyncio
import logging

logging.basicConfig(
                level=logging.DEBUG,
                format='%(asctime)s %(filename)s [line:%(lineno)d] %(levelname)s %(message)s',
                datefmt='%a, %d %b %Y %H:%M:%S',
                filemode='w')

logger = logging.getLogger()

# server
# async def serve(callback: typing.Callable, host: str="127.0.0.1", port: int=5000):

#     await asyncio.start_server(callback, host, port)
#     while True:
#         await asyncio.sleep(0.1)

# # application
# async def handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):

#     data = await reader.read(1000)
#     msg = data.decode()

#     logger.info(f"Received data:")
#     logger.info(f"begin -----------------------------")
#     logger.info(f"\n{msg}")
#     logger.info(f"end -----------------------------")

#     send_data = "pong"
#     writer.write(send_data.encode())
#     await writer.drain()
#     logger.info(f"Send: {send_data}")
#     logger.info(f"Connection close")
#     writer.close()


class Request:

    def __init__(self, method: str, router: str, headers: dict = {}):

        self.method = method
        self.router = router
        self.headers = headers

    def __str__(self) -> str:
        
        return f"method = {self.method}, router = {self.router}, headers = {self.headers}"

# server
class Server:

    def __init__(self, app: typing.Callable) -> None:
        self.app = app
        self.host = "127.0.0.1"
        self.port = 5000

    async def handler(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):

        data = await reader.read(100)
        msg = data.decode()


        logger.info(f"Received data:")
        logger.info(f"begin -----------------------------")
        logger.info(f"\n{msg}")
        logger.info(f"end -----------------------------")

        req = self.parse_http_request(msg)
        logger.info(f"parsed request = {req}")
        res = await self.app(req)
        writer.write(res.encode())
        await writer.drain()
        logger.info(f"Send: {res}")
        logger.info(f"Connection close")
        writer.close()

    def parse_http_request(self, msg: str):

        lines = msg.split("\n")
        head = lines[0]
        method, uri, _ = head.split(" ")
        headers = {}
        for line in lines[1:]:
            if not line:
                continue
            if ": " not in line:
                continue
            key, value = line.split(": ")
            headers[key] = value

        return Request(method, uri, headers)

    async def serve(self):

        await asyncio.start_server(self.handler, self.host, self.port)
        while True:
            await asyncio.sleep(0.1)


# application
async def app(req: Request) -> str:


    if req.router == "/":
        return "root router"

    elif req.router == "/abc":
        return "handling abc"
    elif req.router == "/ping":
        msg = (
            "HTTP/1.1 200 OK\r\n"
            "date: Wed, 18 Aug 2021 15:17:41 GMT\r\n"
            "server: uvicorn\r\n"
            "content-length: 14\r\n"
            "\r\n"
            "hello, world"
            "\r\n"
        )
        return msg
    else:
        return "handleing others"


if __name__ == "__main__":
    server = Server(app)
    asyncio.run(server.serve())

