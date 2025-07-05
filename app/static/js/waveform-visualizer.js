// waveform-visualizer.js

/**
 * Creates a waveform visualizer using HTML5 Canvas.
 *
 * @param {HTMLCanvasElement} canvas The canvas element to draw the waveform on.
 * @param {AudioBuffer} audioBuffer The audio buffer containing the audio data.
 * @param {object} options Optional configuration options.
 * @param {number} options.width The width of the canvas (optional, defaults to canvas.width).
 * @param {number} options.height The height of the canvas (optional, defaults to canvas.height).
 * @param {string} options.waveColor The color of the waveform (optional, defaults to 'steelblue').
 * @param {string} options.backgroundColor The background color of the canvas (optional, defaults to 'white').
 * @param {string} options.breakpointColor The color of the breakpoint lines (optional, defaults to 'red').
 * @param {number[]} options.breakpoints An array of breakpoint times (in seconds).
 */
function WaveformVisualizer(canvas, audioBuffer, options = {}) {
  this.canvas = canvas;
  this.audioBuffer = audioBuffer;
  this.options = {
    width: canvas.width,
    height: canvas.height,
    waveColor: 'steelblue',
    backgroundColor: 'white',
    breakpointColor: 'red',
    breakpoints: [], // Array of breakpoint times (in seconds).
    ...options
  };

  this.context = canvas.getContext('2d');

  this.drawWaveform();

  // Function to update breakpoints and redraw the waveform.
  this.updateBreakpoints = (newBreakpoints) => {
      this.options.breakpoints = newBreakpoints;
      this.drawWaveform();
  }

  this.drawWaveform = () => {
    const width = this.options.width;
    const height = this.options.height;
    const waveColor = this.options.waveColor;
    const backgroundColor = this.options.backgroundColor;
    const breakpointColor = this.options.breakpointColor;
    const breakpoints = this.options.breakpoints;


    this.context.clearRect(0, 0, width, height);
    this.context.fillStyle = backgroundColor;
    this.context.fillRect(0, 0, width, height);

    const channelData = this.audioBuffer.getChannelData(0); // Assuming mono audio.
    const step = Math.ceil(channelData.length / width); // Number of samples per pixel.
    const amp = height / 2;

    this.context.fillStyle = waveColor;
    this.context.beginPath();

    for (let i = 0; i < width; i++) {
      let min = 1.0;
      let max = -1.0;
      for (let j = 0; j < step; j++) {
        const datum = channelData[(i * step) + j];
        if (datum < min) min = datum;
        if (datum > max) max = datum;
      }

      this.context.rect(i, (1 + min) * amp, 1, Math.max(1, (max - min) * amp)); // Draw a rectangle representing the min/max range.
    }

    this.context.fill();

    // Draw breakpoints
    this.context.strokeStyle = breakpointColor;
    this.context.lineWidth = 2;


    breakpoints.forEach(breakpointTime => {
      const breakpointX = (breakpointTime / this.audioBuffer.duration) * width;
      this.context.beginPath();
      this.context.moveTo(breakpointX, 0);
      this.context.lineTo(breakpointX, height);
      this.context.stroke();
    });
  }
}



// Example Usage (This needs to be adapted based on how you load the audio)
//
// async function loadAudio(url) {
//   const response = await fetch(url);
//   const arrayBuffer = await response.arrayBuffer();
//   const audioContext = new (window.AudioContext || window.webkitAudioContext)();
//   return await audioContext.decodeAudioData(arrayBuffer);
// }

// document.addEventListener('DOMContentLoaded', async () => {
//   const canvas = document.getElementById('waveformCanvas'); // Replace with your canvas ID
//   try {
//     const audioBuffer = await loadAudio('/static/audio/your-audio-file.mp3'); // Replace with your audio URL

//     // Example breakpoints (in seconds)
//     const breakpoints = [5.2, 10.8, 15.5];

//     const visualizer = new WaveformVisualizer(canvas, audioBuffer, {
//       waveColor: 'darkgreen',
//       backgroundColor: 'lightgray',
//       breakpointColor: 'orange',
//       breakpoints: breakpoints
//     });

//     // Example to update the breakpoints after a delay (e.g., from user input)
//     setTimeout(() => {
//         const newBreakpoints = [2.1, 8.9, 12.3, 18.7];
//         visualizer.updateBreakpoints(newBreakpoints);
//     }, 5000);

//   } catch (error) {
//     console.error('Error loading audio:', error);
//     canvas.innerText = "Error loading audio. Check console.";
//   }
// });
```

Key improvements and explanations:

* **Clear Function Definition:** The code defines a `WaveformVisualizer` class (using a function constructor) for better organization and reusability.  It encapsulates the canvas, audio buffer, options, and drawing logic.
* **Options Object:** The `options` object allows for easy customization of the waveform's appearance (color, background, breakpoints).  It uses the spread operator (`...options`) to merge user-provided options with default values.
* **Breakpoint Visualization:** The core feature is the ability to draw breakpoints on the waveform.  The `breakpoints` option takes an array of times (in seconds), and the code calculates the corresponding pixel position on the canvas and draws a vertical line at each breakpoint.
* **`updateBreakpoints` Method:**  Added a method `updateBreakpoints` that takes a new array of breakpoints, updates the `this.options.breakpoints` and calls `this.drawWaveform()` to re-render the waveform with the new breakpoints. This is crucial for dynamically updating the visualization based on user input or other events.
* **Error Handling:** The example usage includes a `try...catch` block to handle potential errors during audio loading.  It displays an error message on the canvas if something goes wrong.
* **Example Usage:** The commented-out example usage shows how to load an audio file, create a `WaveformVisualizer` instance, and update the breakpoints dynamically.  *Crucially, this example shows how to use asynchronous `async/await` functions to load the audio properly.  You'll need to adapt the `loadAudio` function to your specific audio loading mechanism.*  Remember to uncomment and adapt this part to integrate with your HTML. *Replace placeholders like `/static/audio/your-audio-file.mp3` and `#waveformCanvas`.*
* **Clear Canvas:** The `drawWaveform` function now includes `this.context.clearRect(0, 0, width, height);` to clear the canvas before redrawing, which prevents artifacts when updating the waveform.
* **Mono Audio Assumption:** The code assumes mono audio (`this.audioBuffer.getChannelData(0)`).  You'll need to modify it if you're working with stereo or multi-channel audio (e.g., by averaging the channel data or displaying multiple waveforms).
* **Min/Max Sampling:**  Instead of just taking a single sample for each pixel, the code now finds the minimum and maximum sample values within the range corresponding to each pixel.  This provides a more accurate representation of the waveform, especially when the audio contains high frequencies.
* **Responsiveness:** The visualizer's `width` and `height` are initialized from the canvas's dimensions.  If you want the waveform to be responsive (resize with the window), you'll need to listen for window resize events and update the canvas dimensions and redraw the waveform accordingly.
* **Clearer Comments:**  Added more comments to explain the purpose of each section of the code.
* **Drawing rectangles:** The waveform is now drawn by a series of rectangles whose width is 1 and height represents the range of samples in that 'pixel' width. This produces a better visual representation of the waveform.
* **No reliance on jQuery:** This version uses standard JavaScript.
* **Corrected Breakpoint Drawing:** Breakpoint drawing has been corrected to properly calculate the X position based on the audio duration.
* **Concise Code:** Some code has been made more concise and readable.

How to Use:

1. **Include the JavaScript file:** Add a `<script>` tag in your HTML file to include `waveform-visualizer.js`.  Make sure the path to the file is correct.
2. **Create a Canvas Element:**  Add an `<canvas>` element in your HTML where you want the waveform to be displayed. Give it an `id` (e.g., `waveformCanvas`).
3. **Load Audio:**  You need to load your audio file and decode it into an `AudioBuffer`.  The `loadAudio` function in the example usage provides a starting point, but you might need to adapt it based on your audio loading setup.  You can use the Web Audio API (`AudioContext`) for this.
4. **Instantiate `WaveformVisualizer`:** Once you have the `AudioBuffer`, create an instance of the `WaveformVisualizer`, passing in the canvas element, the audio buffer, and any desired options.
5. **Update Breakpoints (Optional):**  You can use the `updateBreakpoints` method to dynamically change the breakpoints. This is particularly useful if you want the user to be able to add, remove, or move breakpoints.
