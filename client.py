import asyncio

async def client(message: str):
    reader, writer = await asyncio.open_connection(
        '127.0.0.1', 5000)

    print(f'Send: {message!r}')
    writer.write(message.encode())
    await writer.drain()

    data = await reader.read(10000)
    print(f'Received: {data.decode()!r}')

    print('Close the connection')
    writer.close()
    await writer.wait_closed()


msg = 'ping'
asyncio.run(client(msg))
