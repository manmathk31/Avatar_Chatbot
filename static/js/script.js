import { fetchEventSource } from 'https://unpkg.com/@microsoft/fetch-event-source@2.0.1/lib/esm/index.js';

// DOM Elements
const chatBox = document.getElementById('chat-box');
const chatForm = document.getElementById("chat-form");
const chatInput = document.getElementById("chat-input");
const recordButton = document.getElementById('recordButton');
const loader = document.getElementById('loader');

// Speech & Recording variables
let mediaRecorder;
let audioChunks = [];
let isRecording = false;
let currentAudio = null;

// --- Function to display the USER's message bubble ---
function displayUserMessage(messageText) {
    document.getElementById("greeting-message")?.classList.add("fade-out");

    const messageContainer = document.createElement('div');
    messageContainer.className = 'user-message-container';

    const messageContent = document.createElement('div');
    messageContent.className = 'user-message-content';
    messageContent.textContent = messageText;

    messageContainer.appendChild(messageContent);
    chatBox.appendChild(messageContainer);
    chatBox.scrollTop = chatBox.scrollHeight;
}

// --- Functions to manage the BOT's typing animation ---
function showTypingIndicator() {
    const indicatorContainer = document.createElement('div');
    indicatorContainer.className = 'typing-indicator-container';
    indicatorContainer.innerHTML = `
        <div class="typing-indicator">
            <span></span><span></span><span></span>
        </div>`;
    chatBox.appendChild(indicatorContainer);
    chatBox.scrollTop = chatBox.scrollHeight;
}

function removeTypingIndicator() {
    const indicator = chatBox.querySelector('.typing-indicator-container');
    if (indicator) {
        indicator.remove();
    }
}

// --- Avatar Thinking Animation ---
function startAvatarThinking() {
    const avatarCard = document.getElementById('avatar-card');
    if (avatarCard) {
        avatarCard.classList.add('thinking');
    }
}

function stopAvatarThinking() {
    const avatarCard = document.getElementById('avatar-card');
    if (avatarCard) {
        avatarCard.classList.remove('thinking');
    }
}

// --- Function to create the main container for the BOT's response ---
function createBotResponseContainer() {
    const responseContainer = document.createElement('div');
    responseContainer.className = 'bot-response-container';

    const contentDiv = document.createElement('div');
    contentDiv.className = 'bot-response-content';

    const timestampDiv = document.createElement('div');
    timestampDiv.className = 'bot-response-timestamp';
    timestampDiv.textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    responseContainer.appendChild(contentDiv);
    responseContainer.appendChild(timestampDiv);
    chatBox.appendChild(responseContainer);

    return contentDiv; // Return the element where text will be streamed
}

// --- Main Chat Logic (Streaming) ---
function handleStream(prompt) {
    showTypingIndicator();
    startAvatarThinking(); // Start avatar thinking animation

    let fullReply = "";
    let replyTextElement = null;

    fetchEventSource("/stream_response", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: prompt }),
        onopen: (res) => { if (!res.ok) throw new Error("Stream connection failed"); },
        onmessage(ev) {
            if (replyTextElement === null) {
                removeTypingIndicator();
                stopAvatarThinking(); // Stop thinking - response started
                replyTextElement = createBotResponseContainer();
            }

            try {
                // Parse the JSON data from the SSE message
                const data = JSON.parse(ev.data);
                const textChunk = data.text || "";

                // Get the event type from the message metadata
                const eventType = ev.event || "token"; // Default to token if not specified

                if (eventType === "token") {
                    // Accumulate token chunks for real-time streaming display
                    fullReply += textChunk;

                    // Re-render in real-time with markdown parsing
                    replyTextElement.innerHTML = marked.parse(fullReply);
                } else if (eventType === "final_response") {
                    // Final response received - apply polish and finalize
                    fullReply = textChunk; // Use the final complete response
                    replyTextElement.innerHTML = marked.parse(fullReply);

                    // Add copy buttons to all code blocks
                    replyTextElement.querySelectorAll('pre').forEach(pre => {
                        const codeBlock = pre.querySelector('code');
                        if (!codeBlock) return;

                        // Avoid adding duplicate buttons if we re-run this logic
                        if (pre.querySelector('.copy-code-btn')) return;

                        const copyButton = document.createElement('button');
                        copyButton.className = 'copy-code-btn';
                        copyButton.textContent = 'Copy';
                        copyButton.onclick = () => {
                            navigator.clipboard.writeText(codeBlock.innerText).then(() => {
                                copyButton.textContent = 'Copied!';
                                setTimeout(() => { copyButton.textContent = 'Copy'; }, 2000);
                            });
                        };
                        pre.appendChild(copyButton);
                    });

                    // Apply syntax highlighting to all code blocks
                    hljs.highlightAll();

                    // Speak the final response
                    speak(fullReply.replace(/```[\s\S]*?```/g, "Code block provided."));
                }
            } catch (e) {
                // If parsing fails, log and continue
                console.error("Failed to parse event data:", e);
            }

            chatBox.scrollTop = chatBox.scrollHeight;
        },
        onerror(err) {
            console.error("Stream error:", err);
            removeTypingIndicator();
            stopAvatarThinking(); // Stop thinking on error
            const errorElement = createBotResponseContainer();
            errorElement.textContent = "⚠️ Stream error. Please try again.";
        },
    });
}

// --- Event Listeners and Voice Recording (No significant changes here) ---
chatForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const message = chatInput.value.trim();
    if (!message) return;
    displayUserMessage(message);
    chatInput.value = "";
    handleStream(message);
});

async function sendAudioToBackend(audioBlob) {
    if (loader) loader.style.display = 'block';
    const formData = new FormData();
    formData.append('audio', audioBlob, 'recording.wav');
    try {
        const response = await fetch('/transcribe', { method: 'POST', body: formData });
        const data = await response.json();
        const transcribedText = data.transcribedText || "Transcription failed";
        displayUserMessage(transcribedText);
        handleStream(transcribedText);
    } catch (error) {
        console.error('Error during transcription:', error);
        const errElement = createBotResponseContainer();
        errElement.textContent = "Error: Could not transcribe audio.";
    } finally {
        if (loader) loader.style.display = 'none';
    }
}

recordButton.addEventListener('click', async () => {
    if (!isRecording) {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            mediaRecorder = new MediaRecorder(stream);
            audioChunks = [];
            mediaRecorder.ondataavailable = event => audioChunks.push(event.data);
            mediaRecorder.onstop = () => {
                const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
                sendAudioToBackend(audioBlob);
                stream.getTracks().forEach(track => track.stop());
            };
            mediaRecorder.start(); recordButton.textContent = '🛑 Stop'; isRecording = true;
        } catch (err) {
            console.error("Mic access error:", err);
            const errElement = createBotResponseContainer();
            errElement.textContent = "Microphone access denied.";
        }
    } else {
        mediaRecorder.stop(); recordButton.textContent = '🎤 Speak'; isRecording = false;
    }
});

function speak(text) {
    if (currentAudio && !currentAudio.paused) currentAudio.pause();

    fetch("/speak", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text })
    })
        .then(res => res.json())
        .then(data => {
            if (data.audio_url) {
                currentAudio = new Audio(data.audio_url);
                currentAudio.play();

                // 🔗 CONNECT AVATAR TO AUDIO
                if (window.avatarSpeak) {
                    window.avatarSpeak(currentAudio);
                }
            }
        })
        .catch(err => console.error("TTS Error:", err));
}