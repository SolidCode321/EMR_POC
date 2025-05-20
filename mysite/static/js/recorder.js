let mediaRecorder;
let audioChunks = [];

function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

const csrftoken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');

document.getElementById('recordButton').addEventListener('click', async () => {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaRecorder = new MediaRecorder(stream);
    audioChunks = [];  // Reset before new recording
    mediaRecorder.start();

    mediaRecorder.addEventListener('dataavailable', event => {
        audioChunks.push(event.data);
    });

    mediaRecorder.addEventListener('stop', async () => {
        const textDisplay = document.getElementById('textDisplay');
        textDisplay.innerHTML = `<p>🔄 <strong>Processing...</strong><br>Please wait while we transcribe your audio.</p>`;

        const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
        const formData = new FormData();
        formData.append('audio', audioBlob);

        try {
            // Upload audio
            const uploadResponse = await fetch('/upload/', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': csrftoken,
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: formData
            });

            const uploadData = await uploadResponse.json();

            if (uploadData.status !== 'success') {
                throw new Error('Upload failed');
            }

            // Transcribe audio
            const transcribeResponse = await fetch('/transcribe/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrftoken,
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify({ filename: uploadData.filename })
            });

            const transcribeData = await transcribeResponse.json();

            // Display transcription
            if (transcribeData.transcription) {
                textDisplay.innerHTML = `<p>📝 <strong>Transcription:</strong><br>${transcribeData.transcription}</p>`;
            } else {
                textDisplay.innerHTML = `<p>❌ <strong>Error:</strong> ${transcribeData.error || 'No transcription found.'}</p>`;
            }

        } catch (error) {
            console.error('Error:', error);
            textDisplay.innerHTML = `<p>❌ <strong>Error:</strong> ${error.message}</p>`;
        }
    });

    document.getElementById('stopButton').disabled = false;
});

document.getElementById('stopButton').addEventListener('click', () => {
    mediaRecorder.stop();
    document.getElementById('stopButton').disabled = true;
});
