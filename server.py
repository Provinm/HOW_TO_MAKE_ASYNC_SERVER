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

        res = await self.app(msg)
        writer.write(res.encode())
        await writer.drain()
        logger.info(f"Send: {res}")
        logger.info(f"Connection close")
        writer.close()


    async def serve(self):

        await asyncio.start_server(self.handler, self.host, self.port)
        while True:
            await asyncio.sleep(0.1)


# application
async def app(msg) -> str:

    if msg == "ping":
        return "pong"

    return "cannot handle"


if __name__ == "__main__":
    server = Server(app)
    asyncio.run(server.serve())

