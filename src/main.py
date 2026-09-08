from vesper.assisstant import run_assistant
import asyncio

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop=loop)
loop.run_until_complete(run_assistant())