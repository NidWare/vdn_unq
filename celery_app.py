from celery import Celery, states
import os
import shutil
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
        # Initial state update
        self.update_state(state='PROCESSING', meta={'status': 'Starting video processing...'})
        
        # Ensure output directory exists and is empty
        if os.path.exists(session_output_dir):
            shutil.rmtree(session_output_dir)
        os.makedirs(session_output_dir)
        
        # Process video using original logic
        main_modified(session_input_dir, session_output_dir, copies, orientation)
        
        # Wait a moment to ensure all files are written
        import time
        time.sleep(2)
        
        # Verify the output files
        output_files = [f for f in os.listdir(session_output_dir) 
                       if os.path.isfile(os.path.join(session_output_dir, f))]
        
        print(f"Found output files: {output_files}")
        print(f"Output directory contents: {os.listdir(session_output_dir)}")
        
        if not output_files:
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
        self.update_state(
            state=states.SUCCESS,
            meta=result
        )
        return result
        
    except Exception as e:
        print(f"Error in process_video_task: {str(e)}")
        error_msg = str(e)
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