document.addEventListener('DOMContentLoaded', () => {
    const previewButton = document.getElementById('previewBreaksButton');
    const audioFileInput = document.getElementById('audioFile');
    const commercialLengthInput = document.getElementById('commercialLength');
    const commercialFrequencyInput = document.getElementById('commercialFrequency');
    const initialBreakOffsetInput = document.getElementById('initialBreakOffset');
    const breakTimelineDiv = document.getElementById('breakTimeline');

    // Ensure all required DOM elements are present
    if (!previewButton || !audioFileInput || !commercialLengthInput || !commercialFrequencyInput || !initialBreakOffsetInput || !breakTimelineDiv) {
        console.error('One or more required DOM elements for Preview Breaks are missing. Please check your index.html for correct IDs.');
        return;
    }

    /**
     * Formats total seconds into a human-readable HH:MM:SS string.
     * @param {number} totalSeconds - The total number of seconds.
     * @returns {string} The formatted time string.
     */
    function formatTime(totalSeconds) {
        const hours = Math.floor(totalSeconds / 3600);
        const minutes = Math.floor((totalSeconds % 3600) / 60);
        const seconds = Math.floor(totalSeconds % 60);

        const pad = (num) => num.toString().padStart(2, '0');
        return `${pad(hours)}:${pad(minutes)}:${pad(seconds)}`;
    }

    previewButton.addEventListener('click', async (event) => {
        event.preventDefault(); // Prevent default button action (e.g., form submission)

        // Clear previous results and show a loading message
        breakTimelineDiv.innerHTML = '<p>Generating break timeline...</p>';
        breakTimelineDiv.style.color = 'inherit'; // Reset any error styling

        const audioFile = audioFileInput.files[0];
        const commercialLength = commercialLengthInput.value;
        const commercialFrequency = commercialFrequencyInput.value;
        const initialBreakOffset = initialBreakOffsetInput.value;

        if (!audioFile) {
            breakTimelineDiv.innerHTML = '<p style="color: red;">Please upload an audio file before previewing breaks.</p>';
            return;
        }

        // Validate commercial settings are numbers and positive
        if (isNaN(commercialLength) || commercialLength <= 0 ||
            isNaN(commercialFrequency) || commercialFrequency <= 0 ||
            isNaN(initialBreakOffset) || initialBreakOffset < 0) {
            breakTimelineDiv.innerHTML = '<p style="color: red;">Please ensure commercial settings are valid positive numbers.</p>';
            return;
        }

        const formData = new FormData();
        formData.append('audioFile', audioFile);
        formData.append('commercialLength', commercialLength);
        formData.append('commercialFrequency', commercialFrequency);
        formData.append('initialBreakOffset', initialBreakOffset);

        try {
            const response = await fetch('/breaks/preview', {
                method: 'POST',
                body: formData,
            });

            if (!response.ok) {
                // Attempt to parse error message from response body
                let errorMessage = `HTTP error! Status: ${response.status}`;
                try {
                    const errorData = await response.json();
                    if (errorData && errorData.message) {
                        errorMessage = `Error: ${errorData.message} (Status: ${response.status})`;
                    } else if (response.statusText) {
                         errorMessage = `Error: ${response.statusText} (Status: ${response.status})`;
                    }
                } catch (e) {
                    // If JSON parsing fails, use generic error message
                    errorMessage = `Error: Server responded with status ${response.status} and no parseable error message.`;
                }
                throw new Error(errorMessage);
            }

            const data = await response.json();

            if (data.timestamps && Array.isArray(data.timestamps)) {
                if (data.timestamps.length > 0) {
                    breakTimelineDiv.innerHTML = '<h3>Predicted Break Timestamps:</h3>';
                    const ul = document.createElement('ul');
                    ul.style.listStyleType = 'none'; // Basic styling
                    ul.style.paddingLeft = '0';

                    data.timestamps.forEach(timestamp => {
                        const li = document.createElement('li');
                        li.textContent = `• ${formatTime(timestamp)}`;
                        ul.appendChild(li);
                    });
                    breakTimelineDiv.appendChild(ul);
                } else {
                    breakTimelineDiv.innerHTML = '<p>No breaks were predicted for the given audio and settings.</p>';
                }
            } else {
                breakTimelineDiv.innerHTML = '<p style="color: red;">Unexpected response format: "timestamps" array not found.</p>';
                console.error('Server response did not contain a "timestamps" array:', data);
            }

        } catch (error) {
            console.error('Error fetching break preview:', error);
            breakTimelineDiv.innerHTML = `<p style="color: red;">Failed to preview breaks: ${error.message}</p>`;
        }
    });
});