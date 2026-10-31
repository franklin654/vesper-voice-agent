from vesper.assisstant import run_assistant
import asyncio
import warnings
from langchain_core.api.deprecation import LangChainBetaWarning

# Suppress LangChain-specific beta/experimental warnings
warnings.filterwarnings("ignore", category=LangChainBetaWarning)

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop=loop)
loop.run_until_complete(run_assistant())