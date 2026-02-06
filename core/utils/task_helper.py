import logging
import threading
from django.conf import settings
from celery.exceptions import OperationalError

logger = logging.getLogger(__name__)

def run_task_safe(task_func, sync_func, *args, **kwargs):
    """
    Safely execute a task, falling back to synchronous/threaded execution
    if Celery is disabled or unavailable.
    
    Args:
        task_func: The Celery task function (should have .delay method)
        sync_func: The standalone function to run if fallback is needed
        *args: Arguments for the task
        **kwargs: Keyword arguments for the task
    """
    enable_celery = getattr(settings, 'ENABLE_CELERY', True)
    
    if enable_celery:
        try:
            # Attempt to queue the task
            result = task_func.delay(*args, **kwargs)
            logger.debug(f"Task {task_func.__name__} queued via Celery: {result.id}")
            return True
        except (OperationalError, Exception) as e:
            logger.warning(f"Failed to queue task {task_func.__name__} via Celery: {e}. Falling back to thread.")
            # Fall through to fallback logic
    else:
        logger.debug(f"Celery disabled. Running {sync_func.__name__} via fallback.")

    # Fallback: Run in a separate thread to avoid blocking the request
    try:
        thread = threading.Thread(
            target=sync_func,
            args=args,
            kwargs=kwargs,
            daemon=True
        )
        thread.start()
        logger.info(f"Started fallback thread for {sync_func.__name__}")
        return True
    except Exception as e:
        logger.error(f"Failed to start fallback thread for {sync_func.__name__}: {e}")
        # Last resort: Try running synchronously (risky for long tasks, but ensures execution)
        try:
            sync_func(*args, **kwargs)
            logger.info(f"Executed {sync_func.__name__} synchronously as last resort")
            return True
        except Exception as e2:
             logger.error(f"Failed to execute {sync_func.__name__} synchronously: {e2}")
             return False
