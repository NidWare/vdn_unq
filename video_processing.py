import os
import subprocess
import random
import math
import json
import tempfile

# Функции для работы с видеофайлами

def get_video_dimensions(filepath):
    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height",
        "-of", "json",
        filepath
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe error on {filepath}\n{result.stderr}")
    info = json.loads(result.stdout)
    w = info["streams"][0]["width"]
    h = info["streams"][0]["height"]
    return w, h

def remove_all_metadata(input_video, output_video):
    cmd = [
        "ffmpeg", "-y", "-nostdin",
        "-i", input_video,
        "-map_metadata", "-1",
        "-c", "copy",
        output_video
    ]
    subprocess.run(cmd, check=True)

# Неразрушающие преобразования
def container_rewrap(input_video, output_video):
    exts = [".mp4", ".mkv"]
    chosen = random.choice(exts)
    base, _ = os.path.splitext(output_video)
    new_out = base + chosen
    cmd = [
        "ffmpeg", "-y", "-nostdin",
        "-i", input_video,
        "-c:v", "copy",
        "-c:a", "copy",
        new_out
    ]
    subprocess.run(cmd, check=True)

def add_silent_subtitle(input_video, output_video):
    try:
        get_video_dimensions(input_video)
    except:
        cmd = [
            "ffmpeg", "-y", "-nostdin",
            "-i", input_video,
            "-c", "copy",
            output_video
        ]
        subprocess.run(cmd, check=True)
        return

    with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False, encoding='utf-8') as f:
        srt_content = (
            "1\n"
            "00:00:00,000 --> 00:00:01,000\n\n"
        )
        f.write(srt_content)
        dummy_srt = f.name

    try:
        cmd = [
            "ffmpeg", "-y", "-nostdin",
            "-i", input_video,
            "-i", dummy_srt,
            "-c:v", "copy",
            "-c:a", "copy",
            "-c:s", "mov_text",
            "-map", "0",
            "-map", "1",
            "-f", "mp4",
            output_video
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            cmd = [
                "ffmpeg", "-y", "-nostdin",
                "-i", input_video,
                "-c", "copy",
                output_video
            ]
            subprocess.run(cmd, check=True)
    finally:
        if os.path.exists(dummy_srt):
            os.remove(dummy_srt)

def add_dummy_chapter(input_video, output_video):
    try:
        get_video_dimensions(input_video)
    except:
        cmd = [
            "ffmpeg", "-y", "-nostdin",
            "-i", input_video,
            "-c", "copy",
            output_video
        ]
        subprocess.run(cmd, check=True)
        return

    start_time = random.randint(0, 30)
    end_time = start_time + 10
    chapter_str = f"""
[CHAPTER]
TIMEBASE=1/1
START={start_time}
END={end_time}
title=RandomChapter{random.randint(100,999)}
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
        f.write(chapter_str.strip())
        chap_file = f.name

    try:
        cmd = [
            "ffmpeg", "-y", "-nostdin",
            "-i", input_video,
            "-i", chap_file,
            "-map_metadata", "1",
            "-map", "0",
            "-c:v", "copy",
            "-c:a", "copy",
            "-f", "mp4",
            output_video
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            cmd = [
                "ffmpeg", "-y", "-nostdin",
                "-i", input_video,
                "-c", "copy",
                output_video
            ]
            subprocess.run(cmd, check=True)
    finally:
        if os.path.exists(chap_file):
            os.remove(chap_file)

def apply_random_metadata(input_video, output_video):
    tval = f"UniqueID_{random.randint(100000,999999)}"
    cval = f"Comment_{random.randint(1000,9999)}"
    aval = f"Artist_{random.randint(100,999)}"
    cmd = [
        "ffmpeg","-y","-nostdin",
        "-i", input_video,
        "-c:v","copy",
        "-c:a","copy",
        "-metadata", f"title={tval}",
        "-metadata", f"comment={cval}",
        "-metadata", f"artist={aval}",
        output_video
    ]
    subprocess.run(cmd, check=True)

# Разрушающие (re-encode) преобразования
def apply_random_noise(input_video, output_video):
    noise_val = round(random.uniform(0.05, 0.15), 2)
    nf = f"noise=alls={noise_val}:allf=t+u"
    cmd = [
        "ffmpeg","-y","-nostdin",
        "-i", input_video,
        "-filter:v", nf,
        "-c:v","libx264","-preset","veryfast","-profile:v","high",
        "-crf","26",
        "-pix_fmt","yuv420p",
        "-c:a","aac","-b:a","128k",
        output_video
    ]
    print(f"[Random Noise] => alls={noise_val}")
    subprocess.run(cmd, check=True)

def apply_small_speed_change(input_video, output_video):
    sp = round(random.uniform(0.95, 1.05), 3)
    f_str = f"[0:v]setpts=PTS/{sp}[v];[0:a]atempo={sp}[a]"
    cmd = [
        "ffmpeg","-y","-nostdin",
        "-i", input_video,
        "-filter_complex", f_str,
        "-map","[v]","-map","[a]",
        "-c:v","libx264","-preset","veryfast","-profile:v","high",
        "-crf","26",
        "-pix_fmt","yuv420p",
        "-c:a","aac","-b:a","128k",
        output_video
    ]
    print(f"[Small Speed Change] => {sp}")
    subprocess.run(cmd, check=True)

def apply_resolution_change(input_video, output_video, orientation='horizontal'):
    if orientation == 'vertical':
        w, h = (1080, 1920)
    else:
        w, h = (1920, 1080)

    vf_str = f"scale={w}:{h}"
    cmd = [
        "ffmpeg","-y","-nostdin",
        "-i", input_video,
        "-vf", vf_str,
        "-c:v","libx264","-preset","veryfast","-profile:v","high",
        "-crf","26",
        "-pix_fmt","yuv420p",
        "-c:a","aac","-b:a","128k",
        output_video
    ]
    subprocess.run(cmd, check=True)

def apply_frame_rate_change(input_video, output_video):
    fr = random.choice([24,25,30,60])
    cmd = [
        "ffmpeg","-y","-nostdin",
        "-i", input_video,
        "-r", str(fr),
        "-c:v","libx264","-preset","veryfast","-profile:v","high",
        "-crf","26",
        "-pix_fmt","yuv420p",
        "-c:a","aac","-b:a","128k",
        output_video
    ]
    subprocess.run(cmd, check=True)

def apply_audio_codec_change(input_video, output_video):
    ac = random.choice(["aac","libmp3lame"])
    cmd = [
        "ffmpeg","-y","-nostdin",
        "-i", input_video,
        "-c:v","libx264","-preset","veryfast","-profile:v","high",
        "-crf","26",
        "-pix_fmt","yuv420p",
        "-c:a", ac,
        "-b:a","128k","-ac","2","-ar","44100",
        output_video
    ]
    subprocess.run(cmd, check=True)

def apply_audio_sample_rate_change(input_video, output_video):
    sr = random.choice([44100,48000])
    cmd = [
        "ffmpeg","-y","-nostdin",
        "-i", input_video,
        "-c:v","libx264","-preset","veryfast","-profile:v","high",
        "-crf","26",
        "-pix_fmt","yuv420p",
        "-c:a","aac","-ar", str(sr),
        "-b:a","128k","-ac","2",
        output_video
    ]
    subprocess.run(cmd, check=True)

def apply_small_rotation(input_video, output_video):
    angle_deg = random.uniform(-2,2)
    angle_rad = angle_deg*math.pi/180
    vf = f"rotate={angle_rad}:fillcolor=black"
    cmd = [
        "ffmpeg","-y","-nostdin",
        "-i", input_video,
        "-vf", vf,
        "-c:v","libx264","-preset","veryfast","-profile:v","high",
        "-crf","26",
        "-pix_fmt","yuv420p",
        "-c:a","aac","-b:a","128k",
        output_video
    ]
    subprocess.run(cmd, check=True)

def apply_flip(input_video, output_video):
    flip_type = random.choice(["hflip","vflip"])
    cmd = [
        "ffmpeg","-y","-nostdin",
        "-i", input_video,
        "-vf", flip_type,
        "-c:v","libx264","-preset","veryfast","-profile:v","high",
        "-crf","26",
        "-pix_fmt","yuv420p",
        "-c:a","aac","-b:a","128k",
        output_video
    ]
    subprocess.run(cmd, check=True)

def apply_mirror(input_video, output_video):
    cmd = [
        "ffmpeg","-y","-nostdin",
        "-i", input_video,
        "-vf","hflip",
        "-c:v","libx264","-preset","veryfast","-profile:v","high",
        "-crf","26",
        "-pix_fmt","yuv420p",
        "-c:a","aac","-b:a","128k",
        output_video
    ]
    subprocess.run(cmd, check=True)

def apply_padding(input_video, output_video, orientation='horizontal'):
    if orientation == 'vertical':
        tw, th = (1080, 1920)
    else:
        tw, th = (1920, 1080)

    w,h = get_video_dimensions(input_video)
    if w >= tw or h >= th:
        cmd = [
            "ffmpeg","-y","-nostdin",
            "-i", input_video,
            "-c:v","copy","-c:a","copy",
            output_video
        ]
        subprocess.run(cmd, check=True)
        return

    vf_str = f"pad={tw}:{th}:(ow-iw)/2:(oh-ih)/2"
    cmd = [
        "ffmpeg","-y","-nostdin",
        "-i", input_video,
        "-vf", vf_str,
        "-c:v","libx264","-preset","veryfast","-profile:v","high",
        "-crf","26",
        "-pix_fmt","yuv420p",
        "-c:a","aac","-b:a","128k",
        output_video
    ]
    subprocess.run(cmd, check=True)

def apply_text_overlay(input_video, output_video):
    text_str = "Follow me and check my link in bio"
    x = random.randint(10,100)
    y = random.randint(10,100)
    draw = f"drawtext=text='{text_str}':x={x}:y={y}:fontcolor=white:fontsize=20:shadowcolor=black:shadowx=2:shadowy=2"
    cmd = [
        "ffmpeg","-y","-nostdin",
        "-i", input_video,
        "-vf", draw,
        "-c:v","libx264","-preset","veryfast","-profile:v","high",
        "-crf","26",
        "-pix_fmt","yuv420p",
        "-c:a","aac","-b:a","128k",
        output_video
    ]
    subprocess.run(cmd, check=True)

def apply_pixelate(input_video, output_video):
    factor = random.choice([1.1,1.2,1.3])
    pf = (
        f"scale=iw/{factor}:ih/{factor}:flags=lanczos,"
        f"scale=iw*{factor}:ih*{factor}:flags=neighbor"
    )
    cmd = [
        "ffmpeg","-y","-nostdin",
        "-i", input_video,
        "-vf", pf,
        "-c:v","libx264","-preset","veryfast","-profile:v","high",
        "-crf","26",
        "-pix_fmt","yuv420p",
        "-c:a","aac","-b:a","128k",
        output_video
    ]
    subprocess.run(cmd, check=True)

def apply_small_color_filter(input_video, output_video):
    bval = round(random.uniform(-0.05,0.05),3)
    cval = round(random.uniform(0.95,1.05),3)
    sval = round(random.uniform(0.95,1.05),3)
    eq_str = f"eq=brightness={bval}:contrast={cval}:saturation={sval}"
    cmd = [
        "ffmpeg","-y","-nostdin",
        "-i", input_video,
        "-vf", eq_str,
        "-c:v","libx264","-preset","veryfast","-profile:v","high",
        "-crf","26",
        "-pix_fmt","yuv420p",
        "-c:a","aac","-b:a","128k",
        output_video
    ]
    subprocess.run(cmd, check=True)

def apply_fade_in_50frames(input_video, output_video):
    fade_filter = "fade=t=in:st=0:d=2"
    cmd = [
        "ffmpeg","-y","-nostdin",
        "-i", input_video,
        "-vf", fade_filter,
        "-c:v","libx264","-preset","veryfast","-profile:v","high",
        "-crf","26",
        "-pix_fmt","yuv420p",
        "-c:a","aac","-b:a","128k",
        output_video
    ]
    subprocess.run(cmd, check=True)

def check_and_fix_even(input_video, output_video):
    w,h = get_video_dimensions(input_video)
    if (w % 2 == 0) and (h % 2 == 0):
        print(f"[CheckEven] {w}x{h} уже чётное. Пропускаем.")
        cmd = [
            "ffmpeg","-y","-nostdin",
            "-i", input_video,
            "-c","copy",
            output_video
        ]
        subprocess.run(cmd, check=True)
    else:
        print(f"[CheckEven] => исправляем {w}x{h}")
        scale_str = "scale='2*ceil(iw/2)':'2*ceil(ih/2)':force_original_aspect_ratio=decrease"
        cmd = [
            "ffmpeg","-y","-nostdin",
            "-i", input_video,
            "-vf", scale_str,
            "-c:v","libx264","-preset","medium","-profile:v","high",
            "-crf","20",
            "-pix_fmt","yuv420p",
            "-c:a","aac","-b:a","256k",
            output_video
        ]
        subprocess.run(cmd, check=True)

def generate_unique_video(input_video, output_video, orientation='horizontal', task=None):
    try:
        if task:
            task.update_state(state='PROCESSING', meta={'status': 'Starting video speed change...'})
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
            tmp_speed = tmp.name
        apply_small_speed_change(input_video, tmp_speed)

        current_input = tmp_speed

        if random.random() < 0.5:
            if task:
                task.update_state(state='PROCESSING', meta={'status': 'Applying random noise...'})
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
                tmp_noise = tmp.name
            apply_random_noise(current_input, tmp_noise)
            current_input = tmp_noise

        transformations = [
            container_rewrap,
            add_silent_subtitle,
            add_dummy_chapter,
            apply_random_metadata,
            lambda inp, out: apply_resolution_change(inp, out, orientation),
            apply_frame_rate_change,
            apply_audio_codec_change,
            apply_audio_sample_rate_change,
            apply_small_rotation,
            apply_mirror,
            lambda inp, out: apply_padding(inp, out, orientation),
            apply_text_overlay,
            apply_pixelate,
            apply_small_color_filter,
            apply_fade_in_50frames
        ]
        num = random.choice([3,4])
        selected = random.sample(transformations, num)

        for i, transform in enumerate(selected, start=1):
            if task:
                task.update_state(state='PROCESSING', 
                                meta={'status': f'Applying transformation {i}/{num}: {transform.__name__ if hasattr(transform,"__name__") else "custom"}...'})
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
                tmp_out = tmp.name

            print(f"\n--- Transformation {i}/{num}: {transform.__name__ if hasattr(transform,'__name__') else 'custom'} ---")
            transform(current_input, tmp_out)
            current_input = tmp_out

        if task:
            task.update_state(state='PROCESSING', meta={'status': 'Finalizing video...'})
            
        print("\n--- Final Step: check_and_fix_even ---")
        check_and_fix_even(current_input, output_video)
        print(f"[DONE] => {output_video}")
        
        # Verify the output file exists and is not empty
        if not os.path.exists(output_video) or os.path.getsize(output_video) == 0:
            raise RuntimeError("Generated file is missing or empty")
            
    except Exception as e:
        print(f"Error in generate_unique_video: {str(e)}")
        if task:
            task.update_state(state='FAILURE', meta={'status': str(e), 'error': str(e)})
        raise

def main_modified(input_dir, output_dir, num_variants=1, orientation='horizontal', task=None):
    print(f"\nStarting main_modified with parameters:")
    print(f"input_dir: {input_dir}")
    print(f"output_dir: {output_dir}")
    print(f"num_variants: {num_variants}")
    print(f"orientation: {orientation}")

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"Created output directory: {output_dir}")

    largest_number = 0
    for fn in os.listdir(output_dir):
        lower = fn.lower()
        if lower.endswith(".mp4") or lower.endswith(".mov"):
            base, _ = os.path.splitext(fn)
            try:
                val = int(base)
                if val > largest_number:
                    largest_number = val
            except ValueError:
                pass
    print(f"Starting with largest_number: {largest_number}")

    input_files = [f for f in os.listdir(input_dir) 
                  if f.lower().endswith(('.mp4', '.mov'))]
    
    if not input_files:
        print("No valid input files found")
        if task:
            task.update_state(state='FAILURE', meta={'status': 'No valid input files found', 'error': 'No valid input files found'})
        return

    print(f"Found input files: {input_files}")
    successful_outputs = []

    for fname in input_files:
        in_path = os.path.join(input_dir, fname)
        print(f"\nProcessing file: {in_path}")
        
        try:
            get_video_dimensions(in_path)
            print("Successfully got video dimensions")
        except Exception as e:
            print(f"Error getting video dimensions: {str(e)}")
            print(f"Skipping invalid file: {fname}")
            if task:
                task.update_state(state='FAILURE', meta={'status': f'Invalid video file: {str(e)}', 'error': str(e)})
            continue

        with tempfile.TemporaryDirectory() as temp_dir:
            print(f"Created temporary directory: {temp_dir}")
            clean_input = os.path.join(temp_dir, "clean_input.mp4")
            try:
                remove_all_metadata(in_path, clean_input)
                print("Successfully removed metadata")
            except Exception as e:
                print(f"Error cleaning metadata: {str(e)}")
                print(f"Using original file: {fname}")
                clean_input = in_path

            try:
                get_video_dimensions(clean_input)
                print("Successfully verified cleaned file")
            except Exception as e:
                print(f"Error with cleaned file: {str(e)}")
                print(f"Using original file: {fname}")
                clean_input = in_path

            for variant in range(num_variants):
                largest_number += 1
                out_name = f"{largest_number}.mp4"
                out_path = os.path.join(output_dir, out_name)

                print(f"\n[PROCESS] Variant {variant + 1}/{num_variants}: {fname} => {out_name}")
                try:
                    generate_unique_video(clean_input, out_path, orientation, task)
                    if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
                        print(f"Successfully generated => {out_path}")
                        successful_outputs.append(out_path)
                    else:
                        print(f"Generated file is missing or empty: {out_path}")
                        try:
                            print("Attempting to save copy of original...")
                            cmd = [
                                "ffmpeg", "-y", "-nostdin",
                                "-i", in_path,
                                "-c", "copy",
                                out_path
                            ]
                            subprocess.run(cmd, check=True)
                            if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
                                print(f"Successfully saved copy of original => {out_path}")
                                successful_outputs.append(out_path)
                            else:
                                print(f"Failed to save copy: file is missing or empty")
                                if task:
                                    task.update_state(state='FAILURE', meta={'status': 'Failed to save video', 'error': 'Generated file is missing or empty'})
                        except Exception as e:
                            print(f"Failed to save copy: {str(e)}")
                            if task:
                                task.update_state(state='FAILURE', meta={'status': f'Failed to save video: {str(e)}', 'error': str(e)})
                except Exception as e:
                    print(f"Error processing variant: {str(e)}")
                    try:
                        print("Attempting to save copy of original...")
                        cmd = [
                            "ffmpeg", "-y", "-nostdin",
                            "-i", in_path,
                            "-c", "copy",
                            out_path
                        ]
                        subprocess.run(cmd, check=True)
                        if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
                            print(f"Successfully saved copy of original => {out_path}")
                            successful_outputs.append(out_path)
                        else:
                            print(f"Failed to save copy: file is missing or empty")
                            if task:
                                task.update_state(state='FAILURE', meta={'status': 'Failed to save video', 'error': 'Generated file is missing or empty'})
                    except Exception as e:
                        print(f"Failed to save copy: {str(e)}")
                        if task:
                            task.update_state(state='FAILURE', meta={'status': f'Failed to save video: {str(e)}', 'error': str(e)})

    print("\nFinished main_modified processing")
    print(f"Successfully processed {len(successful_outputs)} files")
    print(f"Final contents of output directory: {os.listdir(output_dir)}")
    
    # Verify all output files
    for out_path in successful_outputs:
        if not os.path.exists(out_path) or os.path.getsize(out_path) == 0:
            print(f"Warning: Output file {out_path} is missing or empty")
            if task:
                task.update_state(state='FAILURE', meta={'status': 'Some output files are missing or empty', 'error': 'Generated files are missing or empty'})
            return
            
    if not successful_outputs:
        if task:
            task.update_state(state='FAILURE', meta={'status': 'No files were successfully processed', 'error': 'No files were successfully processed'})
    else:
        if task:
            task.update_state(state='SUCCESS', meta={'status': 'success', 'files': [os.path.basename(p) for p in successful_outputs]})
