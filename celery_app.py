from celery import Celery, states
import os
import shutil
from video_processing import main_modified
import logging
import traceback
import sys

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
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
             retry_backoff=True,
             name='video_processing.process_video_task')
def process_video_task(self, session_input_dir, session_output_dir, copies, orientation):
    try:
        logger.info(f"[TASK {self.request.id}] Starting video processing task")
        logger.debug(f"Parameters: input_dir={session_input_dir}, output_dir={session_output_dir}, copies={copies}, orientation={orientation}")
        
        # Initial state update
        self.update_state(state='PROCESSING', meta={'status': 'Starting video processing...'})
        
        # Ensure output directory exists and is empty
        if os.path.exists(session_output_dir):
            shutil.rmtree(session_output_dir)
        os.makedirs(session_output_dir)
        logger.info(f"[TASK {self.request.id}] Created output directory: {session_output_dir}")
        
        # Process video using original logic
        logger.info(f"[TASK {self.request.id}] Calling main_modified")
        main_modified(session_input_dir, session_output_dir, copies, orientation)
        logger.info(f"[TASK {self.request.id}] Finished main_modified")
        
        # Wait a moment to ensure all files are written
        import time
        time.sleep(2)
        
        # Verify the output files
        output_files = [f for f in os.listdir(session_output_dir) 
                       if os.path.isfile(os.path.join(session_output_dir, f))]
        
        logger.info(f"[TASK {self.request.id}] Found output files: {output_files}")
        logger.debug(f"[TASK {self.request.id}] Output directory contents: {os.listdir(session_output_dir)}")
        
        if not output_files:
            error_msg = "No output files were generated"
            logger.error(f"[TASK {self.request.id}] {error_msg}")
            self.update_state(
                state=states.FAILURE,
                meta={
                    'status': error_msg,
                    'error': error_msg
                }
            )
            return {
                'status': 'error',
                'error': error_msg
            }

        # Return success with the list of generated files
        result = {
            'status': 'success',
            'files': output_files
        }
        logger.info(f"[TASK {self.request.id}] Task completed successfully with result: {result}")
        self.update_state(
            state=states.SUCCESS,
            meta=result
        )
        return result
        
    except Exception as e:
        error_msg = f"Error in process_video_task: {str(e)}"
        logger.error(f"[TASK {self.request.id}] {error_msg}")
        logger.error(f"[TASK {self.request.id}] Traceback: {traceback.format_exc()}")
        
        self.update_state(
            state=states.FAILURE,
            meta={
                'status': error_msg,
                'error': error_msg
            }
        )
        # Let the autoretry_for handle the retry if needed
        raise 