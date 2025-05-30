import asyncio
import sys

from app.agent.manus import Manus
from app.logger import logger


async def main():
    # Create and initialize Manus agent
    agent = await Manus.create()
    try:
        print("Enter your prompt: ", end='', flush=True)
        data = sys.stdin.buffer.readline()
        prompt = data.decode('utf-8', errors='replace').rstrip('\n')

        if not prompt.strip():
            logger.warning("Empty prompt provided.")
            return

        logger.warning("Processing your request...")
        await agent.run(prompt)
        logger.info("Request processing completed.")
    except KeyboardInterrupt:
        logger.warning("Operation interrupted.")
    finally:
        # Ensure agent resources are cleaned up before exiting
        await agent.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
