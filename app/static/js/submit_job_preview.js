document.addEventListener('DOMContentLoaded', () => {
    const previewBreaksButton = document.getElementById('previewBreaksButton');
    const audioFileInput = document.getElementById('audioFile');
    const detectedBreaksContainer = document.getElementById('detectedBreaksContainer');
    const previewLoading = document.getElementById('previewLoading');
    const previewError = document.getElementById('previewError');

    // Assume these IDs for commercial settings inputs on the form
    const minCommercialDurationInput = document.getElementById('minCommercialDuration');
    const maxCommercialDurationInput = document.getElementById('maxCommercialDuration');
    const commercialWindowStartInput = document.getElementById('commercialWindowStart');
    const commercialWindowEndInput = document.getElementById('commercialWindowEnd');
    const minSilenceDurationInput = document.getElementById('minSilenceDuration'); // Example additional setting
    const silenceThresholdInput = document.getElementById('silenceThreshold');     // Example additional setting

    // Basic check for required elements
    if (!previewBreaksButton || !audioFileInput || !detectedBreaksContainer || !previewLoading || !previewError ||
        !minCommercialDurationInput || !maxCommercialDurationInput || !commercialWindowStartInput || !commercialWindowEndInput ||
        !minSilenceDurationInput || !silenceThresholdInput) {
        console.error("One or more required DOM elements for 'Preview Breaks' are missing. Please ensure all IDs are correct.");
        // Optionally, disable the button or show a user-friendly error on the page
        if (previewBreaksButton) {
            previewBreaksButton.disabled = true;
            previewBreaksButton.textContent = 'Preview (Missing Elements)';
        }
        return;
    }

    // Initialize display states
    previewLoading.style.display = 'none';
    previewError.style.display = 'none';

    previewBreaksButton.addEventListener('click', async (event) => {
        event.preventDefault(); // Prevent default form submission behavior

        // Clear previous results and errors
        detectedBreaksContainer.innerHTML = '';
        previewError.textContent = '';
        previewError.style.display = 'none';
        previewLoading.style.display = 'block'; // Show loading indicator

        const audioFile = audioFileInput.files[0];
        if (!audioFile) {
            previewError.textContent = 'Please select an audio file to upload first.';
            previewError.style.display = 'block';
            previewLoading.style.display = 'none';
            return;
        }

        const formData = new FormData();
        formData.append('audio_file', audioFile);
        formData.append('min_commercial_duration', minCommercialDurationInput.value);
        formData.append('max_commercial_duration', maxCommercialDurationInput.value);
        formData.append('commercial_window_start', commercialWindowStartInput.value);
        formData.append('commercial_window_end', commercialWindowEndInput.value);
        formData.append('min_silence_duration', minSilenceDurationInput.value);
        formData.append('silence_threshold', silenceThresholdInput.value);

        try {
            const response = await fetch('/api/preview_breaks', {
                method: 'POST',
                body: formData,
            });

            if (!response.ok) {
                // Handle HTTP errors (e.g., 404, 500)
                const errorData = await response.json().catch(() => ({})); // Try to parse error message, fallback to empty object
                throw new Error(`Server responded with status ${response.status}: ${errorData.error || response.statusText}`);
            }

            const data = await response.json();

            if (data.success) {
                if (data.breaks && data.breaks.length > 0) {
                    const ul = document.createElement('ul');
                    ul.className = 'list-group mt-3'; // Example styling
                    data.breaks.forEach(breakItem => {
                        const li = document.createElement('li');
                        li.className = 'list-group-item'; // Example styling
                        const start = parseFloat(breakItem.start).toFixed(2); // Ensure float and format
                        const end = parseFloat(breakItem.end).toFixed(2);
                        li.textContent = `Break detected: Start ${start}s, End ${end}s`;
                        ul.appendChild(li);
                    });
                    detectedBreaksContainer.appendChild(ul);
                } else {
                    detectedBreaksContainer.innerHTML = '<p class="text-info mt-3">No breaks detected based on the current settings. Try adjusting the parameters.</p>';
                }
            } else {
                // Handle backend-specific logical errors (e.g., validation failed)
                previewError.textContent = `Error: ${data.error || 'An unknown server error occurred.'}`;
                previewError.style.display = 'block';
            }
        } catch (error) {
            console.error('Error during break preview:', error);
            previewError.textContent = `Failed to process request: ${error.message}`;
            previewError.style.display = 'block';
        } finally {
            previewLoading.style.display = 'none'; // Hide loading indicator
        }
    });
});