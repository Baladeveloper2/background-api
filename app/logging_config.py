import logging
import json
import sys
import re
from datetime import datetime
from typing import Any

class JsonFormatter(logging.Formatter):
    """
    Custom formatter to output logs in JSON format for production observability.
    """
    def format(self, record: logging.LogRecord) -> str:
        # PII Masking logic
        message = record.getMessage()
        # Mask emails
        message = re.sub(r'[\w\.-]+@[\w\.-]+\.\w+', '[MASKED_EMAIL]', message)
        # Mask phone numbers (simple pattern for 10 digits)
        message = re.sub(r'\b\d{10}\b', '[MASKED_PHONE]', message)

        log_record = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "message": message,
            "module": record.module,
            "funcName": record.funcName,
            "line": record.lineno,
        }
        
        # Add extra fields if present
        # Standard attributes to exclude
        standard_attrs = {
            'args', 'asctime', 'created', 'exc_info', 'filename', 'funcName',
            'levelname', 'levelno', 'lineno', 'module', 'msecs', 'message',
            'msg', 'name', 'pathname', 'process', 'processName',
            'relativeCreated', 'stack_info', 'thread', 'threadName', 'extra'
        }
        for key, value in record.__dict__.items():
            if key not in standard_attrs and not key.startswith('_'):
                log_record[key] = value
            
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)
            
        return json.dumps(log_record)

def setup_logging(level: int = logging.INFO):
    """
    Configure global logging to use the JSON formatter for stdout.
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Remove existing handlers to avoid duplicates
    for h in root_logger.handlers[:]:
        root_logger.removeHandler(h)
        
    root_logger.addHandler(handler)
    
    # Optional: Suppress noisy third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

def instrument_sqlalchemy(engine):
    """
    Adds performance tracking to the SQLAlchemy engine to log slow queries.
    """
    from sqlalchemy import event
    import time

    @event.listens_for(engine, "before_cursor_execute")
    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        context._query_start_time = time.time()

    @event.listens_for(engine, "after_cursor_execute")
    def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        total = time.time() - context._query_start_time
        if total > 0.2: # Log queries slower than 200ms
            logger.warning("Slow Query Detected", extra={
                "duration": f"{total:.4f}s",
                "statement": statement,
                "parameters": str(parameters)[:200]
            })

logger = logging.getLogger("bgvms")
