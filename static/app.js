/**
 * AI Storyteller - Main JavaScript Application
 * Handles story generation, audio playback, and UI updates
 */

const API_BASE = '/api';

// State management
const state = {
    selectedAnimals: [],
    currentStory: null,
    audioSegments: [],
    currentSegmentIndex: 0,
    isGenerating: false,
    isPlaying: false
};

// DOM Elements
const elements = {
    selectedAnimals: document.getElementById('selected-animals'),
    clearAnimalsBtn: document.getElementById('clear-animals-btn'),
    generateBtn: document.getElementById('generate-btn'),
    voiceBtn: document.getElementById('voice-btn'),
    storySection: document.getElementById('story-section'),
    storyText: document.getElementById('story-text'),
    playBtn: document.getElementById('play-btn'),
    stopBtn: document.getElementById('stop-btn'),
    volumeSlider: document.getElementById('volume-slider'),
    audioPlayer: document.getElementById('audio-player'),
    currentSegment: document.getElementById('current-segment'),
    totalSegments: document.getElementById('total-segments'),
    loadingOverlay: document.getElementById('loading-overlay'),
    loadingText: document.getElementById('loading-text'),
    statusIndicator: document.getElementById('status-indicator'),
    statusText: document.getElementById('status-text')
};

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    setupEventListeners();
    loadCurrentState();
    // Poll for state updates (for RFID card detection)
    setInterval(loadCurrentState, 2000);
});

function setupEventListeners() {
    // Generate story button
    elements.generateBtn.addEventListener('click', generateStory);

    // Voice command button
    elements.voiceBtn.addEventListener('click', listenForVoice);

    // Clear animals button
    elements.clearAnimalsBtn.addEventListener('click', clearAnimals);

    // Audio controls
    elements.playBtn.addEventListener('click', playStory);
    elements.stopBtn.addEventListener('click', stopAudio);

    // Volume slider
    elements.volumeSlider.addEventListener('input', (e) => {
        elements.audioPlayer.volume = e.target.value / 100;
    });

    // Audio player events
    elements.audioPlayer.addEventListener('ended', onSegmentEnded);
    elements.audioPlayer.addEventListener('error', onAudioError);
}

async function loadCurrentState() {
    try {
        const response = await fetch(`${API_BASE}/story/current`);
        const data = await response.json();

        // Update animals if changed
        if (JSON.stringify(data.selected_animals) !== JSON.stringify(state.selectedAnimals)) {
            state.selectedAnimals = data.selected_animals;
            renderAnimals();
        }

        // Update status
        if (data.is_generating && !state.isGenerating) {
            setStatus('generating', 'Generating story...');
        } else if (data.is_playing && !state.isPlaying) {
            setStatus('playing', 'Playing audio...');
        } else if (!data.is_generating && !data.is_playing) {
            setStatus('idle', 'Ready');
        }

    } catch (error) {
        console.error('Failed to load state:', error);
    }
}

function renderAnimals() {
    const container = elements.selectedAnimals;

    if (state.selectedAnimals.length === 0) {
        container.innerHTML = '<p class="no-animals">No animals selected yet. Tap an RFID card or use voice command.</p>';
        elements.clearAnimalsBtn.disabled = true;
        return;
    }

    container.innerHTML = state.selectedAnimals.map(animal => `
        <span class="animal-chip">
            ${getAnimalEmoji(animal)} ${animal}
            <span class="remove" onclick="removeAnimal('${animal}')">&times;</span>
        </span>
    `).join('');

    elements.clearAnimalsBtn.disabled = false;
}

function getAnimalEmoji(animal) {
    const emojis = {
        cat: '🐱', gato: '🐱',
        dog: '🐶', perro: '🐶',
        lion: '🦁', leon: '🦁', león: '🦁',
        tiger: '🐯', tigre: '🐯',
        elephant: '🐘', elefante: '🐘',
        giraffe: '🦒', jirafa: '🦒',
        monkey: '🐒', mono: '🐒',
        bear: '🐻', oso: '🐻',
        rabbit: '🐰', conejo: '🐰',
        bird: '🐦', pajaro: '🐦', pájaro: '🐦',
        fish: '🐟', pez: '🐟',
        snake: '🐍', serpiente: '🐍',
        horse: '🐴', caballo: '🐴',
        wolf: '🐺', lobo: '🐺',
        fox: '🦊', zorro: '🦊',
        zebra: '🦓', cebra: '🦓',
        turtle: '🐢', tortuga: '🐢',
        dolphin: '🐬', delfin: '🐬', delfín: '🐬',
        whale: '🐋', ballena: '🐋',
        owl: '🦉', buho: '🦉', búho: '🦉',
    };
    return emojis[animal.toLowerCase()] || '🐾';
}

async function removeAnimal(animal) {
    try {
        await fetch(`${API_BASE}/animals/${animal}`, { method: 'DELETE' });
        state.selectedAnimals = state.selectedAnimals.filter(a => a !== animal);
        renderAnimals();
    } catch (error) {
        console.error('Failed to remove animal:', error);
    }
}

async function clearAnimals() {
    try {
        await fetch(`${API_BASE}/animals/clear`, { method: 'POST' });
        state.selectedAnimals = [];
        renderAnimals();
    } catch (error) {
        console.error('Failed to clear animals:', error);
    }
}

async function generateStory() {
    if (state.selectedAnimals.length === 0) {
        alert('Please select at least one animal first!');
        return;
    }

    showLoading('Generating story...');
    setStatus('generating', 'Generating...');
    state.isGenerating = true;

    try {
        const response = await fetch(`${API_BASE}/story/generate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ animals: state.selectedAnimals })
        });

        const data = await response.json();

        if (data.status === 'success' || data.status === 'partial') {
            state.currentStory = data.full_text;
            state.audioSegments = data.audio_segments;
            state.currentSegmentIndex = 0;

            // Display story
            elements.storyText.textContent = data.full_text;
            elements.storySection.style.display = 'block';

            // Update audio controls
            elements.totalSegments.textContent = data.audio_segments.length;
            elements.currentSegment.textContent = '0';
            elements.playBtn.disabled = data.audio_segments.length === 0;
            elements.stopBtn.disabled = true;

            setStatus('idle', 'Story ready!');
        } else {
            throw new Error(data.error || 'Story generation failed');
        }

    } catch (error) {
        console.error('Story generation failed:', error);
        setStatus('error', 'Generation failed');
        alert('Failed to generate story: ' + error.message);
    } finally {
        hideLoading();
        state.isGenerating = false;
    }
}

async function listenForVoice() {
    elements.voiceBtn.disabled = true;
    setStatus('listening', 'Listening...');

    try {
        showLoading('Listening for voice command...');

        const response = await fetch(`${API_BASE}/voice/listen`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ timeout: 5 })
        });

        const data = await response.json();

        hideLoading();

        if (data.status === 'success' && data.animals.length > 0) {
            // Add detected animals
            for (const animal of data.animals) {
                if (!state.selectedAnimals.includes(animal)) {
                    await fetch(`${API_BASE}/animals`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ animal })
                    });
                    state.selectedAnimals.push(animal);
                }
            }
            renderAnimals();

            // Show what was heard
            alert(`Heard: "${data.text}"\nAnimals: ${data.animals.join(', ')}`);

        } else if (data.status === 'no_speech') {
            alert('No speech detected. Please try again.');
        } else {
            alert('Could not understand voice command. Please try again.');
        }

        setStatus('idle', 'Ready');

    } catch (error) {
        hideLoading();
        console.error('Voice recognition failed:', error);
        setStatus('error', 'Voice error');
        alert('Voice recognition failed: ' + error.message);
    } finally {
        elements.voiceBtn.disabled = false;
    }
}

function playStory() {
    if (state.audioSegments.length === 0) return;

    state.isPlaying = true;
    state.currentSegmentIndex = 0;
    playCurrentSegment();

    elements.playBtn.disabled = true;
    elements.stopBtn.disabled = false;
    setStatus('playing', 'Playing...');
}

function playCurrentSegment() {
    if (state.currentSegmentIndex >= state.audioSegments.length) {
        onPlaybackComplete();
        return;
    }

    const segment = state.audioSegments[state.currentSegmentIndex];
    elements.currentSegment.textContent = state.currentSegmentIndex + 1;

    elements.audioPlayer.src = segment.audio;
    elements.audioPlayer.volume = elements.volumeSlider.value / 100;
    elements.audioPlayer.play().catch(error => {
        console.error('Playback error:', error);
        onAudioError();
    });
}

function onSegmentEnded() {
    state.currentSegmentIndex++;
    if (state.currentSegmentIndex < state.audioSegments.length) {
        // Small delay between segments
        setTimeout(playCurrentSegment, 300);
    } else {
        onPlaybackComplete();
    }
}

function onPlaybackComplete() {
    state.isPlaying = false;
    elements.playBtn.disabled = false;
    elements.stopBtn.disabled = true;
    elements.currentSegment.textContent = state.audioSegments.length;
    setStatus('idle', 'Playback complete');
}

function onAudioError() {
    console.error('Audio playback error');
    stopAudio();
    setStatus('error', 'Audio error');
}

function stopAudio() {
    elements.audioPlayer.pause();
    elements.audioPlayer.currentTime = 0;
    state.isPlaying = false;
    elements.playBtn.disabled = false;
    elements.stopBtn.disabled = true;
    setStatus('idle', 'Ready');
}

function setStatus(statusClass, text) {
    elements.statusIndicator.className = `status-indicator ${statusClass}`;
    elements.statusText.textContent = text;
}

function showLoading(text = 'Loading...') {
    elements.loadingText.textContent = text;
    elements.loadingOverlay.style.display = 'flex';
}

function hideLoading() {
    elements.loadingOverlay.style.display = 'none';
}

// Make removeAnimal available globally for onclick handlers
window.removeAnimal = removeAnimal;
