import asyncio
import os
import sys

from app.agent.manus import Manus
from app.logger import logger


async def process_prompt(prompt: str) -> str:
    """Processes the prompt and returns the result"""
    agent = await Manus.create()
    try:
        if not prompt.strip():
            logger.warning("Empty prompt provided.")
            return "Empty prompt provided"

        logger.warning("Processing your request...")
        result = await agent.run(prompt)
        logger.info("Request processing completed.")
        return result
    except Exception as e:
        logger.error(f"Error processing prompt: {str(e)}")
        return f"Error processing prompt: {str(e)}"
    finally:
        await agent.cleanup()
