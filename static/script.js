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
            const response = await fetch(`/task/${taskId}`);
            const data = await response.json();

            // Update progress text for any state
            if (data.status) {
                progressText.textContent = data.status;
            }

            if (data.state === 'SUCCESS') {
                clearInterval(pollInterval);
                hideProgress();
                if (data.result && data.result.status === 'success' && data.result.files) {
                    showResults({
                        session_id: sessionId,
                        files: data.result.files
                    });
                } else {
                    showError(data.result?.error || 'Processing failed');
                }
                submitButton.disabled = false;
            } else if (data.state === 'FAILURE') {
                clearInterval(pollInterval);
                hideProgress();
                showError(data.error || data.status || 'Processing failed');
                submitButton.disabled = false;
            } else if (data.state === 'PROCESSING') {
                // Show progress bar at 90% during processing
                progressBar.style.width = '90%';
            } else if (data.state === 'PENDING') {
                // Show progress bar at 10% while pending
                progressBar.style.width = '10%';
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

        const formData = new FormData();
        formData.append('video', currentFile);
        formData.append('orientation', form.orientation.value);
        formData.append('copies', form.copies.value);

        try {
            submitButton.disabled = true;
            showProgress();
            hideError();

            const response = await fetch('/upload', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || 'An error occurred during upload');
            }

            // Start polling for task status
            pollInterval = setInterval(() => {
                pollTaskStatus(data.task_id, data.session_id);
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