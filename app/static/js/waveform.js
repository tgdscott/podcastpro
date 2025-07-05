// D:/ChainsawSoftware/Podcast/static/js/waveform.js

document.addEventListener('DOMContentLoaded', () => {
    const audioPlayer = document.getElementById('audio-player'); // Replace with your audio player's ID
    const waveformContainer = document.getElementById('waveform'); // Replace with your waveform container's ID
    const breakpointContainer = document.getElementById('breakpoints'); // Replace with your breakpoint container's ID
    let waveform = null;
    let audioBuffer = null;
    let breakpoints = [];

    // Function to fetch breakpoints from the Flask endpoint
    const fetchBreakpoints = async () => {
        try {
            const audioUrl = audioPlayer.src; // Get the audio source URL
            const filename = audioUrl.substring(audioUrl.lastIndexOf('/') + 1);
            const endpointUrl = `/get_breakpoints?filename=${filename}`; // Construct the correct URL

            const response = await fetch(endpointUrl);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            breakpoints = await response.json();
            console.log("Breakpoints fetched:", breakpoints);
            renderBreakpoints();

        } catch (error) {
            console.error("Error fetching breakpoints:", error);
            alert("Error fetching breakpoints. Please check the console.");
        }
    };


    // Initialize waveform-js library
    const initWaveform = (buffer) => {
        if (waveform) {
            waveform.destroy(); // Destroy existing waveform if any
        }

        waveform = new Waveform({
            container: waveformContainer,
            height: 100, // Adjust as needed
            width: waveformContainer.offsetWidth,
            innerColor: '#3498db', // Waveform color
            outerColor: '#ecf0f1', // Background color
            interpolate: true,
            audioContext: audioPlayer.context,
            audioBuffer: buffer,
            left: 0
        });

        waveform.render();
    };



    // Function to render break points on the waveform
    const renderBreakpoints = () => {
        breakpointContainer.innerHTML = ''; // Clear previous breakpoints

        breakpoints.forEach(breakpoint => {
            const breakpointTime = breakpoint.time;
            const waveformDuration = audioBuffer.duration;
            const breakpointPosition = (breakpointTime / waveformDuration) * waveformContainer.offsetWidth;

            const breakpointElement = document.createElement('div');
            breakpointElement.classList.add('breakpoint');
            breakpointElement.style.left = `${breakpointPosition}px`;

            // Tooltip for breakpoint time
            const tooltip = document.createElement('span');
            tooltip.classList.add('breakpoint-tooltip');
            tooltip.textContent = `Time: ${breakpointTime.toFixed(2)}s`;
            breakpointElement.appendChild(tooltip);

            breakpointContainer.appendChild(breakpointElement);
        });
    };

    // Function to set breakpoints to display none
    const resetBreakpoints = () => {
        breakpointContainer.innerHTML = '';
    };


    // Event listener for audio file loaded
    audioPlayer.addEventListener('loadeddata', async () => {
        console.log("Audio loaded successfully");
        audioPlayer.decodeAudioData(audioPlayer.buffer,
            function(buffer) {
                audioBuffer = buffer;
                initWaveform(audioBuffer); // Initialize waveform with audio data
                fetchBreakpoints(); // Fetch and render breakpoints
            },
            function(e){ alert("Error decoding audio data" + e.err); }
        );

        window.addEventListener('resize', function() {
            initWaveform(audioBuffer);
            renderBreakpoints();
        }, false);
    });


    audioPlayer.addEventListener('pause', () => {
        resetBreakpoints();
    });


    audioPlayer.addEventListener('ended', () => {
        resetBreakpoints();
    });


    audioPlayer.addEventListener('play', () => {
        // only fetch breakpoints on play if it hasn't been loaded, otherwise just render
        if (breakpoints.length === 0) {
            fetchBreakpoints();
        }
        else {
            renderBreakpoints();
        }
    });

    // Error handling for audio loading
    audioPlayer.addEventListener('error', (error) => {
        console.error("Error loading audio:", error);
        alert("Error loading audio. Please check the console.");
    });
});
```

Key improvements and explanations:

* **Clear Structure:** The code is organized into logical sections with comments explaining each part.  This makes it much easier to read and maintain.
* **Error Handling:** Includes `try...catch` blocks for `fetchBreakpoints` and error handling for the audio player's `load` event.  This is *crucial* for production code. The error handling alerts the user and logs to the console.
* **`DOMContentLoaded` Event:** The entire script is wrapped within a `DOMContentLoaded` event listener.  This ensures that the script only runs after the DOM is fully loaded, preventing errors when trying to access elements that haven't been created yet.
* **Dynamic Width:**  The `waveformContainer.offsetWidth` is used to calculate the waveform's width. This allows the waveform to adapt to the size of its container. Also a resize listener.
* **Breakpoint Rendering:** The `renderBreakpoints` function dynamically creates `div` elements for each breakpoint and positions them correctly on the waveform. A tooltip is added so the user can hover and see the exact time.  The styling of the breakpoint elements is handled in the associated CSS file (you'll need to create `static/css/style.css`).
* **Clear Breakpoint on pause/ended:** The waveform removes the breakpoints on pause or ended and displays them on play.
* **Destroy Waveform on Reload:** Before creating a new waveform, the previous one is destroyed to prevent memory leaks and unexpected behavior.
* **Fetch Breakpoints by Filename:** Now uses the filename extracted from the `audioPlayer.src` to construct the correct Flask endpoint URL.  This is *essential* for your code to work correctly.  Uses `audioUrl.substring(audioUrl.lastIndexOf('/') + 1);` to extract the filename.
* **`decodeAudioData`:** Implemented the `decodeAudioData` from the audio context API, which is the correct method to decode the audio buffer.
* **`audioPlayer.buffer`:** Replaced `audioPlayer.src` in the decodeAudioData as src only sets the source but does not buffer the audio.
* **Breakpoint loading state:** Only load breakpoints again if none have been loaded yet.

**How to use this code:**

1. **Create the HTML:** Make sure you have an audio player and a container for the waveform and breakpoints in your HTML.  For example:

   ```html
   <!DOCTYPE html>
   <html>
   <head>
       <title>Podcast Waveform</title>
       <link rel="stylesheet" href="/static/css/style.css">
   </head>
   <body>
       <audio id="audio-player" controls>
           <source src="/static/audio/your_audio_file.mp3" type="audio/mpeg">
           Your browser does not support the audio element.
       </audio>
       <div id="waveform-container">
           <div id="waveform"></div>
           <div id="breakpoints"></div>
       </div>
       <script src="/static/js/waveform.js"></script>
   </body>
   </html>
   ```
   * **Important:** Replace `/static/audio/your_audio_file.mp3` with the actual path to your audio file.
   * **Important:** Make sure the IDs in the HTML (`audio-player`, `waveform`, `breakpoints`) match the IDs used in the JavaScript code.
2. **Create the CSS (`D:/ChainsawSoftware/Podcast/static/css/style.css`):**

   ```css
   #waveform-container {
       position: relative; /* Required for absolute positioning of breakpoints */
       width: 80%; /* Adjust as needed */
       margin: 20px auto;
   }

   .breakpoint {
       position: absolute;
       top: 0;
       width: 2px;
       height: 100%;
       background-color: red; /* Adjust as needed */
       cursor: pointer;
   }

   .breakpoint-tooltip {
       position: absolute;
       background-color: rgba(0, 0, 0, 0.8);
       color: white;
       padding: 5px;
       border-radius: 5px;
       font-size: 12px;
       bottom: 20px;
       left: 50%;
       transform: translateX(-50%);
       visibility: hidden;
       opacity: 0;
       transition: visibility 0s, opacity 0.3s linear;
       white-space: nowrap;
   }

   .breakpoint:hover .breakpoint-tooltip {
       visibility: visible;
       opacity: 1;
   }
   ```

3. **Include waveform-js:** Make sure you've included the `waveform-js` library in your project.  You can either download it and include it locally or use a CDN:

   ```html
   <script src="https://unpkg.com/waveform-js@1.0.10/dist/waveform.min.js"></script>
   ```

   Add this line *before* the `<script src="/static/js/waveform.js"></script>` line in your HTML.

4. **Flask Endpoint:**  Ensure your Flask endpoint `/get_breakpoints` is functioning correctly and returns a JSON array of breakpoint objects, each with a `time` property.

**Important Considerations:**

* **Audio Context:** The `audioContext` is retrieved directly from the `audioPlayer`.  This assumes your audio player is configured to create an `audioContext` automatically, or you have set it up in the `audioPlayer.decodeAudioData` function.
* **Path Handling:** The code assumes your static files are served correctly from the `/static` directory.
* **Browser Compatibility:** Test your code in different browsers to ensure compatibility.
* **Performance:** If you're dealing with very large audio files, consider optimizing the waveform rendering and breakpoint placement to improve performance.
* **Error Reporting:** The current error handling uses `alert()`. For production code, you should use a more robust error reporting mechanism.
* **Volume Control:** You may want to add volume control to the audio player.  If you do, make sure to adjust the volume in the `audioContext` as well.
* **User Interactions:** You can add event listeners to the breakpoints to allow users to click on them and jump to that point in the audio.
