import logging

from app.config.settings import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


logger.info("OpenTelemetry trace/span exports are disabled")
