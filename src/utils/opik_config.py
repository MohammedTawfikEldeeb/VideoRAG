import opik
import os
from src.config import get_settings
from loguru import logger

settings = get_settings()

def configure() -> None:
    """func to configure opik"""
    if settings.OPIK_API_KEY and settings.OPIK_PROJECT and settings.OPIK_WORKSPACE:
        os.environ["OPIK_PROJECT_NAME"] = settings.OPIK_PROJECT
        try:
            opik.configure(
                api_key= settings.OPIK_API_KEY,
                workspace= settings.OPIK_WORKSPACE,
                use_local=False,
                force=True
            )
            logger.info(f"opik configured sucessfully using workspace {settings.OPIK_WORKSPACE}")
        except Exception as e:
            logger.error(e)
            logger.warning("couldn't configure opik")
    
    else:
        logger.warning("OPIK_API_KEY , OPIK_PROJECT , OPIK_WORKSPACE are not set ")
