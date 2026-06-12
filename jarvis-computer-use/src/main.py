import os
import sys
import uuid
import time
from dotenv import load_dotenv

# Load API keys (e.g. GEMINI_API_KEY, ANTHROPIC_API_KEY, etc.)
load_dotenv()

import sys
import asyncio
import structlog
from src.daemon import main as daemon_main

logger = structlog.get_logger()

def main():
    logger.info("launching_jarvis_computer_use_daemon")
    try:
        asyncio.run(daemon_main())
    except KeyboardInterrupt:
        logger.info("daemon_terminated_by_user")
    except Exception as e:
        logger.error("daemon_crashed", error=str(e))
        sys.exit(1)

if __name__ == "__main__":
    main()
