from celery import Celery, states
import os
from video_processing import main_modified

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
    broker_connection_max_retries=None
)

@celery.task(bind=True)
def process_video_task(self, session_input_dir, session_output_dir, copies, orientation):
    try:
        self.update_state(state='PROCESSING', meta={'status': 'Processing video...'})
        
        # Process video
        main_modified(session_input_dir, session_output_dir, copies, orientation)
        
        # Get list of processed files
        output_files = [f for f in os.listdir(session_output_dir) 
                       if os.path.isfile(os.path.join(session_output_dir, f))]
        
        if not output_files:
            self.update_state(
                state=states.FAILURE,
                meta={'status': 'No output files were generated'}
            )
            return {
                'status': 'error',
                'error': 'No output files were generated'
            }
        
        return {
            'status': 'success',
            'files': output_files
        }
    except Exception as e:
        self.update_state(
            state=states.FAILURE,
            meta={'status': str(e)}
        )
        return {
            'status': 'error',
            'error': str(e)
        } 