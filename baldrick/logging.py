import logging

from os import environ

from loguru import logger

LOG_LEVEL_TO_NAME = {5: 'TRACE',
                     10: 'DEBUG',
                     20: 'INFO',
                     25: 'SUCCESS',
                     30: 'WARNING',
                     40: 'ERROR',
                     50: 'CRITICAL'}

LOG_NAME_TO_LEVEL = {v: k for k, v in LOG_LEVEL_TO_NAME.items()}

class InterceptHandler(logging.Handler):
    """
    Handler to route stdlib logs to loguru
    """
    def emit(self, record):
        # Retrieve context where the logging call occurred, this happens to be in the 6th frame upward
        logger_opt = logger.opt(depth=6, exception=record.exc_info)

        # Log with name to support formatting if known, otherwise use the level number
        logger_opt.log(LOG_LEVEL_TO_NAME.get(record.levelno, record.levelno), record.getMessage())

# Retrieve default log level from same environment variable as loguru
log_level = LOG_NAME_TO_LEVEL.get(environ.get("BALDRICK_LOG_LEVEL", "INFO"), "INFO")

# Configuration for stdlib logger to route messages to loguru; must be run before other imports
logging.basicConfig(handlers=[InterceptHandler()], level=log_level)
