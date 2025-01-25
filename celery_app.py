from celery import Celery, states
import os
import subprocess
from video_processing import get_video_dimensions
import shutil

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

def process_video(input_path, output_path, orientation='vertical'):
    """Process video and ensure it's saved to the correct location"""
    try:
        # Base FFmpeg command
        cmd = [
            'ffmpeg', '-y',
            '-i', input_path,
            '-c:v', 'libx264',
            '-preset', 'medium',
            '-profile:v', 'high',
            '-crf', '20',
        ]

        # Add orientation-specific parameters
        if orientation == 'vertical':
            cmd.extend(['-vf', 'scale=1080:1920'])
        else:
            cmd.extend(['-vf', 'scale=1920:1080'])

        # Add remaining parameters
        cmd.extend([
            '-pix_fmt', 'yuv420p',
            '-c:a', 'aac',
            '-b:a', '256k',
            output_path
        ])

        # Run FFmpeg process
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )

        # Wait for process to complete
        stdout, stderr = process.communicate()

        # Check if process was successful
        if process.returncode != 0:
            print(f"FFmpeg stderr: {stderr}")
            raise Exception("FFmpeg processing failed")

        # Verify the output file exists and has size > 0
        if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
            raise Exception("Output file was not created or is empty")

        return output_path

    except Exception as e:
        raise Exception(f"Video processing failed: {str(e)}")

@celery.task(bind=True)
def process_video_task(self, session_input_dir, session_output_dir, copies, orientation):
    try:
        self.update_state(
            state='PROCESSING',
            meta={'status': 'Starting video processing...'}
        )
        
        # Get input video file
        input_files = [f for f in os.listdir(session_input_dir) 
                      if f.lower().endswith(('.mp4', '.mov'))]
        if not input_files:
            raise Exception("No input video files found")
        
        input_path = os.path.join(session_input_dir, input_files[0])
        processed_files = []

        # Process each copy
        for i in range(copies):
            self.update_state(
                state='PROCESSING',
                meta={'status': f'Processing copy {i+1} of {copies}'}
            )
            
            output_path = os.path.join(session_output_dir, f'{i+1}.mp4')
            process_video(input_path, output_path, orientation)
            
            # Verify the file was created
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                processed_files.append(f'{i+1}.mp4')
            else:
                raise Exception(f"Failed to create output file {i+1}.mp4")

        if not processed_files:
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
            'files': processed_files
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