document.addEventListener('DOMContentLoaded', () => {
    const previewBreaksButton = document.getElementById('previewBreaksButton');
    // Assuming there's an input field (could be hidden) that contains the path or URL of the audio file.
    // This value would typically be set after a file upload completes, or if the audio is already associated with a job.
    const audioFilePathInput = document.getElementById('audioFilePathInput'); 
    const breakTimestampsDisplay = document.getElementById('breakTimestampsDisplay');
    const breakPreviewLoading = document.getElementById('breakPreviewLoading'); // Optional: Element to show a loading spinner/message
    const breakPreviewError = document.getElementById('breakPreviewError');     // Optional: Element to display error messages

    // Basic validation to ensure required DOM elements exist
    if (!previewBreaksButton || !audioFilePathInput || !breakTimestampsDisplay) {
        console.error('Required DOM elements (previewBreaksButton, audioFilePathInput, breakTimestampsDisplay) not found for break preview functionality.');
        return;
    }

    previewBreaksButton.addEventListener('click', async () => {
        // 1. Clear previous results and errors
        breakTimestampsDisplay.innerHTML = '';
        if (breakPreviewError) {
            breakPreviewError.textContent = '';
            breakPreviewError.style.display = 'none';
        }
        breakTimestampsDisplay.className = ''; // Clear any previous info/error classes

        // 2. Show loading indicator and disable button
        if (breakPreviewLoading) {
            breakPreviewLoading.style.display = 'block';
        }
        previewBreaksButton.disabled = true;

        const audioFilePath = audioFilePathInput.value;

        // 3. Validate audio file path
        if (!audioFilePath) {
            if (breakPreviewError) {
                breakPreviewError.textContent = 'Audio file path/URL is required to preview breaks.';
                breakPreviewError.style.display = 'block';
            }
            if (breakPreviewLoading) {
                breakPreviewLoading.style.display = 'none';
            }
            previewBreaksButton.disabled = false;
            return;
        }

        try {
            // 4. Send AJAX request to the backend
            const response = await fetch('/api/analyze_breaks', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    // If your backend framework (e.g., Django) requires a CSRF token for POST requests,
                    // uncomment the line below and ensure getCookie function is available.
                    // 'X-CSRFToken': getCookie('csrftoken'), 
                },
                body: JSON.stringify({ audio_path: audioFilePath })
            });

            // 5. Handle HTTP response status
            if (!response.ok) {
                const errorData = await response.json(); // Attempt to parse error message from response
                throw new Error(errorData.message || `Server responded with status ${response.status}`);
            }

            const data = await response.json();

            // 6. Dynamically display the returned break timestamps
            if (data.breaks && Array.isArray(data.breaks) && data.breaks.length > 0) {
                const ul = document.createElement('ul');
                ul.className = 'list-group mt-2'; // Example: Bootstrap class for a list group

                data.breaks.forEach(breakItem => {
                    const li = document.createElement('li');
                    li.className = 'list-group-item'; // Example: Bootstrap class for list item

                    // Format timestamps (assuming breakItem.start_time and breakItem.end_time are in seconds)
                    const formatTime = (totalSeconds) => {
                        const minutes = Math.floor(totalSeconds / 60);
                        const seconds = Math.floor(totalSeconds % 60);
                        return `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
                    };

                    const startTimeFormatted = formatTime(breakItem.start_time);
                    const endTimeFormatted = formatTime(breakItem.end_time);

                    li.textContent = `Break: ${startTimeFormatted} - ${endTimeFormatted}`;
                    ul.appendChild(li);
                });
                breakTimestampsDisplay.appendChild(ul);
            } else {
                breakTimestampsDisplay.textContent = 'No breaks detected for this audio file.';
                breakTimestampsDisplay.className = 'alert alert-info mt-2'; // Example: Bootstrap info alert
            }

        } catch (error) {
            // 7. Handle any errors during the fetch operation or parsing
            console.error('Error during break analysis:', error);
            if (breakPreviewError) {
                breakPreviewError.textContent = `Error: ${error.message}`;
                breakPreviewError.style.display = 'block';
            }
        } finally {
            // 8. Hide loading indicator and re-enable button regardless of success or failure
            if (breakPreviewLoading) {
                breakPreviewLoading.style.display = 'none';
            }
            previewBreaksButton.disabled = false;
        }
    });

    // Helper function to get CSRF token from cookies (e.g., for Django applications)
    // Uncomment and use if your backend requires CSRF protection for AJAX POST requests.
    /*
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                // Does this cookie string begin with the name we want?
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }
    */
});