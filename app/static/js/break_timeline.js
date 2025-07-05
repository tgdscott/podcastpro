document.addEventListener('DOMContentLoaded', () => {
    const previewBreaksButton = document.getElementById('previewBreaksButton');
    const breakTimelineContainer = document.getElementById('breakTimelineContainer');
    const audioFilePathInput = document.getElementById('audioFilePath'); // Assumed hidden input with audio path or ID
    const loadingIndicator = document.getElementById('breakDetectionLoading');
    const errorMessageDisplay = document.getElementById('breakDetectionError');

    // Helper function to format seconds into MM:SS
    function formatTime(seconds) {
        const minutes = Math.floor(seconds / 60);
        const remainingSeconds = Math.floor(seconds % 60);
        return `${minutes.toString().padStart(2, '0')}:${remainingSeconds.toString().padStart(2, '0')}`;
    }

    if (previewBreaksButton && breakTimelineContainer && audioFilePathInput) {
        previewBreaksButton.addEventListener('click', async () => {
            const audioPathOrId = audioFilePathInput.value; // Get the audio identifier

            if (!audioPathOrId) {
                console.error("Audio file path or ID not found for break detection.");
                if (errorMessageDisplay) {
                    errorMessageDisplay.textContent = 'Error: Audio identifier is missing.';
                    errorMessageDisplay.style.display = 'block';
                }
                return;
            }

            // Clear previous results, errors, and show loading state
            breakTimelineContainer.innerHTML = '';
            if (errorMessageDisplay) {
                errorMessageDisplay.textContent = '';
                errorMessageDisplay.style.display = 'none';
            }
            if (loadingIndicator) {
                loadingIndicator.style.display = 'block';
            }
            previewBreaksButton.disabled = true; // Disable button during request

            try {
                const response = await fetch('/api/podcast/detect_breaks', { // Assumed server endpoint
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    // Send the audio identifier (e.g., path or ID) to the server
                    body: JSON.stringify({ audio_identifier: audioPathOrId }),
                });

                if (!response.ok) {
                    const errorData = await response.json().catch(() => ({ message: 'Server error occurred.' }));
                    throw new Error(errorData.message || `HTTP error! status: ${response.status}`);
                }

                const data = await response.json();
                // Assumed response format: { "timestamps": [10.5, 25.1, ...] }
                const detectedTimestamps = data.timestamps; 

                if (detectedTimestamps && Array.isArray(detectedTimestamps) && detectedTimestamps.length > 0) {
                    const breakList = document.createElement('ul');
                    breakList.className = 'break-list'; 

                    detectedTimestamps.forEach(timestamp => {
                        const listItem = document.createElement('li');
                        listItem.className = 'break-item';
                        listItem.textContent = `Break at: ${formatTime(timestamp)}`;
                        listItem.dataset.timestamp = timestamp; // Store raw timestamp for potential future use (e.g., seek on player)
                        breakList.appendChild(listItem);
                    });
                    breakTimelineContainer.appendChild(breakList);
                } else {
                    breakTimelineContainer.textContent = 'No breaks detected or data is empty.';
                }

            } catch (error) {
                console.error('Error during break detection:', error);
                if (errorMessageDisplay) {
                    errorMessageDisplay.textContent = `Error: ${error.message}`;
                    errorMessageDisplay.style.display = 'block';
                }
                breakTimelineContainer.innerHTML = ''; // Clear any partial content on error
            } finally {
                // Always hide loading indicator and re-enable button
                if (loadingIndicator) {
                    loadingIndicator.style.display = 'none';
                }
                previewBreaksButton.disabled = false;
            }
        });
    } else {
        console.warn("One or more required HTML elements for break detection functionality were not found:");
        if (!previewBreaksButton) console.warn("  - Element with ID 'previewBreaksButton' missing.");
        if (!breakTimelineContainer) console.warn("  - Element with ID 'breakTimelineContainer' missing.");
        if (!audioFilePathInput) console.warn("  - Element with ID 'audioFilePath' missing.");
    }
});