document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('uploadForm');
    const videoInput = document.getElementById('videoInput');
    const dropZone = document.getElementById('dropZone');
    const fileNameDisplay = document.getElementById('fileNameDisplay');
    const submitButton = document.getElementById('submitButton');
    const progressContainer = document.getElementById('progressContainer');
    const progressBar = document.getElementById('progressBar');
    const progressText = document.getElementById('progressText');
    const results = document.getElementById('results');
    const downloadLinks = document.getElementById('downloadLinks');
    const errorMessage = document.getElementById('errorMessage');

    let pollInterval = null;
    let currentFile = null; // Store the current file

    // Handle drag and drop
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, preventDefaults, false);
        document.body.addEventListener(eventName, preventDefaults, false);
    });

    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, highlight, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, unhighlight, false);
    });

    dropZone.addEventListener('drop', handleDrop, false);

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    function highlight(e) {
        dropZone.classList.add('border-blue-500');
    }

    function unhighlight(e) {
        dropZone.classList.remove('border-blue-500');
    }

    function handleDrop(e) {
        const dt = e.dataTransfer;
        const file = dt.files[0];
        if (file) {
            // Create a new File object from the dropped file
            const newFile = new File([file], file.name, {
                type: file.type,
                lastModified: file.lastModified,
            });

            // Create a new DataTransfer object
            const dataTransfer = new DataTransfer();
            dataTransfer.items.add(newFile);

            // Set the files property of the file input
            videoInput.files = dataTransfer.files;

            handleFile(file);
        }
    }

    // Handle file selection
    videoInput.addEventListener('change', (e) => {
        const file = e.target.files[0];
        handleFile(file);
    });

    function handleFile(file) {
        if (file) {
            // Check file type
            const validTypes = ['video/mp4', 'video/quicktime'];
            if (!validTypes.includes(file.type)) {
                showError('Please upload an MP4 or MOV file.');
                return;
            }

            // Check file size (2GB max)
            if (file.size > 2048 * 1024 * 1024) {
                showError('File size must be less than 2GB.');
                return;
            }

            currentFile = file; // Store the current file
            fileNameDisplay.textContent = file.name;
            submitButton.disabled = false;
            hideError();
        }
    }

    async function pollTaskStatus(taskId, sessionId) {
        try {
            console.log(`Polling task status for task ${taskId}`);
            const response = await fetch(`/task/${taskId}`);
            const data = await response.json();
            console.log('Task status response:', data);

            // Update progress text for any state
            if (data.status) {
                progressText.textContent = data.status;
                console.log('Updated progress text:', data.status);
            }

            if (data.state === 'SUCCESS') {
                console.log('Task succeeded:', data);
                clearInterval(pollInterval);
                hideProgress();
                if (data.result && data.result.status === 'success' && data.result.files) {
                    console.log('Showing results with files:', data.result.files);
                    showResults({
                        session_id: sessionId,
                        files: data.result.files
                    });
                } else {
                    console.log('Task success but no valid result:', data);
                    showError(data.result?.error || 'Processing failed');
                }
                submitButton.disabled = false;
            } else if (data.state === 'FAILURE') {
                console.log('Task failed:', data);
                clearInterval(pollInterval);
                hideProgress();
                showError(data.error || data.status || 'Processing failed');
                submitButton.disabled = false;
            } else if (data.state === 'PROCESSING') {
                console.log('Task processing');
                // Show progress bar at 90% during processing
                progressBar.style.width = '90%';
            } else if (data.state === 'PENDING') {
                console.log('Task pending');
                // Show progress bar at 10% while pending
                progressBar.style.width = '10%';
            } else {
                console.log('Unknown task state:', data.state);
            }
        } catch (error) {
            console.error('Error polling task status:', error);
            // Don't clear interval on network errors, keep trying
            progressText.textContent = 'Checking status...';
        }
    }

    // Handle form submission
    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        if (!currentFile) {
            showError('Please select a video file first.');
            return;
        }

        submitButton.disabled = true;
        showProgress();
        hideError();

        const CHUNK_SIZE = 1024 * 1024; // 1MB chunks
        const totalChunks = Math.ceil(currentFile.size / CHUNK_SIZE);
        let uploadedChunks = 0;

        try {
            // First create a session for this upload
            const sessionResponse = await fetch('/upload/start', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    filename: currentFile.name,
                    filesize: currentFile.size,
                    orientation: form.orientation.value,
                    copies: form.copies.value
                })
            });

            if (!sessionResponse.ok) {
                throw new Error('Failed to start upload session');
            }

            const { session_id } = await sessionResponse.json();

            // Upload file in chunks
            for (let start = 0; start < currentFile.size; start += CHUNK_SIZE) {
                const chunk = currentFile.slice(start, start + CHUNK_SIZE);
                const formData = new FormData();
                formData.append('chunk', chunk);
                formData.append('chunk_number', Math.floor(start / CHUNK_SIZE));
                formData.append('total_chunks', totalChunks);

                const response = await fetch(`/upload/chunk/${session_id}`, {
                    method: 'POST',
                    body: formData
                });

                if (!response.ok) {
                    throw new Error('Failed to upload chunk');
                }

                uploadedChunks++;
                const uploadProgress = (uploadedChunks / totalChunks) * 100;
                progressBar.style.width = `${uploadProgress}%`;
                progressText.textContent = `Uploading: ${Math.round(uploadProgress)}%`;
            }

            // Complete the upload
            const completeResponse = await fetch(`/upload/complete/${session_id}`, {
                method: 'POST'
            });

            if (!completeResponse.ok) {
                throw new Error('Failed to complete upload');
            }

            const data = await completeResponse.json();
            progressText.textContent = 'Processing video...';

            // Start polling for task status
            pollInterval = setInterval(() => {
                pollTaskStatus(data.task_id, session_id);
            }, 2000);

        } catch (error) {
            hideProgress();
            showError(error.message);
            submitButton.disabled = false;
        }
    });

    function showProgress() {
        progressContainer.classList.remove('hidden');
        results.classList.add('hidden');
        progressBar.style.width = '90%';
        progressText.textContent = 'Processing video...';
    }

    function hideProgress() {
        progressContainer.classList.add('hidden');
        progressBar.style.width = '0%';
    }

    function showResults(data) {
        results.classList.remove('hidden');
        downloadLinks.innerHTML = '';

        data.files.forEach(filename => {
            const link = document.createElement('a');
            link.href = `/download/${data.session_id}/${filename}`;
            link.className = 'block w-full text-center py-2 px-4 bg-gray-100 hover:bg-gray-200 rounded transition-colors';
            link.textContent = filename;
            link.download = filename;
            downloadLinks.appendChild(link);
        });
    }

    function showError(message) {
        errorMessage.textContent = message;
        errorMessage.classList.remove('hidden');
    }

    function hideError() {
        errorMessage.textContent = '';
        errorMessage.classList.add('hidden');
    }
}); 