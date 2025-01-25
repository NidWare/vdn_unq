from celery import Celery, states
import os
import shutil
from video_processing import main_modified
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

celery = Celery('tasks', 
                broker='redis://redis:6379/0', 
                backend='redis://redis:6379/0',
                broker_connection_retry_on_startup=True)

celery.conf.update(
    task_track_started=True,
    task_time_limit=3600,  # 1 hour max
    task_soft_time_limit=3600,
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1,
    broker_connection_retry=True,
    broker_connection_max_retries=None,
    task_acks_late=True,  # Only acknowledge after the task is completed
    task_reject_on_worker_lost=True,  # Reject tasks if worker is killed
    worker_max_memory_per_child=1000000,  # Restart worker after 1GB memory used
    task_serializer='json',
    result_serializer='json',
    accept_content=['json']
)

@celery.task(bind=True, 
             max_retries=3,
             default_retry_delay=5,
             autoretry_for=(Exception,),
             retry_backoff=True)
def process_video_task(self, session_input_dir, session_output_dir, copies, orientation):
    try:
        logger.info("[TASK] Starting video processing task")
        # Initial state update
        self.update_state(state='PROCESSING', meta={'status': 'Starting video processing...'})
        
        # Ensure output directory exists and is empty
        if os.path.exists(session_output_dir):
            shutil.rmtree(session_output_dir)
        os.makedirs(session_output_dir)
        logger.info(f"[TASK] Created output directory: {session_output_dir}")
        
        # Process video using original logic
        logger.info("[TASK] Calling main_modified")
        main_modified(session_input_dir, session_output_dir, copies, orientation)
        logger.info("[TASK] Finished main_modified")
        
        # Wait a moment to ensure all files are written
        import time
        time.sleep(2)
        
        # Verify the output files
        output_files = [f for f in os.listdir(session_output_dir) 
                       if os.path.isfile(os.path.join(session_output_dir, f))]
        
        logger.info(f"[TASK] Found output files: {output_files}")
        logger.info(f"[TASK] Output directory contents: {os.listdir(session_output_dir)}")
        
        if not output_files:
            logger.error("[TASK] No output files found - failing task")
            self.update_state(
                state=states.FAILURE,
                meta={
                    'status': 'No output files were generated',
                    'error': 'No output files were generated'
                }
            )
            return {
                'status': 'error',
                'error': 'No output files were generated'
            }

        # Return success with the list of generated files
        result = {
            'status': 'success',
            'files': output_files
        }
        logger.info(f"[TASK] Task completed successfully with result: {result}")
        self.update_state(
            state=states.SUCCESS,
            meta=result
        )
        return result
        
    except Exception as e:
        logger.exception(f"[TASK] Error in process_video_task: {str(e)}")
        error_msg = str(e)
        self.update_state(
            state=states.FAILURE,
            meta={
                'status': error_msg,
                'error': error_msg
            }
        )
        # Let the autoretry_for handle the retry if needed
        raise 