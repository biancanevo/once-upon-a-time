/**
 * AI Storyteller - Main JavaScript Application
 * Handles story generation, audio playback, and UI updates with card types
 */

const API_BASE = '/api';

// State management
const state = {
    selectedAnimals: [],  // Legacy compatibility
    selectedCards: [],
    hasCharacter: false,
    storyElements: null,
    currentStory: null,
    audioSegments: [],
    currentSegmentIndex: 0,
    isGenerating: false,
    isPlaying: false,
    storyLengthMinutes: 5,
    registeredCards: {}
};

// DOM Elements (will be initialized after DOM loads)
let elements = {};

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    // Initialize DOM elements after DOM is ready
    elements = {
        selectedCards: document.getElementById('selected-cards'),
        noCharacterWarning: document.getElementById('no-character-warning'),
        storyElementsPreview: document.getElementById('story-elements-preview'),
        previewEnvironment: document.getElementById('preview-environment'),
        previewMoral: document.getElementById('preview-moral'),
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
        statusText: document.getElementById('status-text'),
        ledRing: document.getElementById('led-ring'),
        rfidButtons: document.getElementById('rfid-buttons'),
        storyLengthSlider: document.getElementById('story-length-slider'),
        storyLengthMinutes: document.getElementById('story-length-minutes'),
        storyLengthDescription: document.getElementById('story-length-description'),
        roleSelectorOverlay: document.getElementById('role-selector-overlay'),
        roleSelectorCharacter: document.getElementById('role-selector-character'),
        roleCancelBtn: document.getElementById('role-cancel-btn')
    };

    setupEventListeners();
    initializeLEDRing();
    loadRegisteredCards();
    loadCurrentState();
    loadSliderState();
    // Poll for state updates (for RFID card detection)
    setInterval(loadCurrentState, 2000);
    // Poll for LED state updates
    setInterval(updateLEDRing, 200);
    // Poll for slider state updates (less frequent)
    setInterval(loadSliderState, 1000);
});

function setupEventListeners() {
    // Generate story button
    elements.generateBtn.addEventListener('click', generateStory);

    // Voice command button
    elements.voiceBtn.addEventListener('click', listenForVoice);

    // Clear cards button
    elements.clearAnimalsBtn.addEventListener('click', clearCards);

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

    // Story length slider
    if (elements.storyLengthSlider) {
        elements.storyLengthSlider.addEventListener('input', onStoryLengthChange);
        elements.storyLengthSlider.addEventListener('change', onStoryLengthCommit);
    }

    // Role selector modal
    if (elements.roleCancelBtn) {
        elements.roleCancelBtn.addEventListener('click', closeRoleSelector);
    }

    if (elements.roleSelectorOverlay) {
        elements.roleSelectorOverlay.addEventListener('click', (e) => {
            if (e.target === elements.roleSelectorOverlay) {
                closeRoleSelector();
            }
        });
    }

    // Role selector buttons (will be set up dynamically)
}

// Card type icons and emojis
function getCardTypeIcon(cardType) {
    const icons = {
        character: '🧑',
        environment: '🏞️',
        moral_lesson: '💖'
    };
    return icons[cardType] || '📇';
}

function getSpeciesEmoji(species, cardType) {
    if (cardType === 'character') {
        const emojis = {
            cat: '🐱', dog: '🐶', 'little boy': '👦', 'little girl': '👧',
            dragon: '🐉', wolf: '🐺', witch: '🧙‍♀️', wizard: '🧙‍♂️',
            troll: '🧌', pig: '🐷', donkey: '🫏', princess: '👸',
            prince: '🤴', knight: '🤺', fairy: '🧚', elf: '🧝',
            unicorn: '🦄', rabbit: '🐰', bear: '🐻', fox: '🦊',
            owl: '🦉', mouse: '🐭', frog: '🐸', lion: '🦁',
            turtle: '🐢', squirrel: '🐿️'
        };
        return emojis[species.toLowerCase()] || '🧑';
    } else if (cardType === 'environment') {
        const emojis = {
            village: '🏘️', city: '🏙️', park: '🏞️', forest: '🌲',
            mountain: '⛰️', lake: '🏞️', sea: '🌊', beach: '🏖️',
            castle: '🏰', cave: '🕳️', meadow: '🌾', river: '🏞️',
            desert: '🏜️', jungle: '🌴', island: '🏝️', garden: '🏡',
            farm: '🚜', tower: '🗼', bridge: '🌉', waterfall: '💦',
            valley: '🏔️', swamp: '🌿'
        };
        return emojis[species.toLowerCase()] || '🏞️';
    } else {
        return '💖';
    }
}

async function loadRegisteredCards() {
    try {
        const response = await fetch(`${API_BASE}/cards`);
        const cards = await response.json();
        state.registeredCards = cards;

        if (!elements.rfidButtons) return;

        // Clear existing buttons
        elements.rfidButtons.innerHTML = '';

        // Check if there are any registered cards
        if (Object.keys(cards).length === 0) {
            elements.rfidButtons.innerHTML = '<p class="no-cards">No cards registered yet. Go to <a href="/manage">Manage Cards</a> to register some.</p>';
            return;
        }

        // Create a button for each registered card
        for (const [uid, cardInfo] of Object.entries(cards)) {
            // Handle both legacy and new format
            const cardType = cardInfo.card_type || 'character';
            const species = cardInfo.species || cardInfo.animal || 'unknown';
            const name = cardInfo.name || cardInfo.animal || species;
            const emoji = getSpeciesEmoji(species, cardType);

            const button = document.createElement('button');
            button.className = `rfid-btn ${cardType}`;
            button.setAttribute('data-uid', uid);
            button.setAttribute('data-type', cardType);
            button.innerHTML = `${emoji} ${name.charAt(0).toUpperCase() + name.slice(1)}`;

            // Add click event listener
            button.addEventListener('click', () => {
                simulateRFIDTap(uid);
            });

            elements.rfidButtons.appendChild(button);
        }

        console.log(`Loaded ${Object.keys(cards).length} registered cards`);
    } catch (error) {
        console.error('Failed to load registered cards:', error);
        if (elements.rfidButtons) {
            elements.rfidButtons.innerHTML = '<p class="error">Failed to load cards. Check console for details.</p>';
        }
    }
}

async function loadCurrentState() {
    try {
        const response = await fetch(`${API_BASE}/story/current`);
        const data = await response.json();

        // Update selected cards if changed
        if (JSON.stringify(data.selected_cards) !== JSON.stringify(state.selectedCards)) {
            state.selectedCards = data.selected_cards || [];
            state.hasCharacter = data.has_character || false;
            state.storyElements = data.story_elements;
            renderCards();
        }

        // Update legacy animals for backward compatibility
        state.selectedAnimals = data.selected_animals || [];

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

function renderCards() {
    const container = elements.selectedCards;

    if (state.selectedCards.length === 0) {
        container.innerHTML = '<p class="no-animals">No cards selected yet. Tap an RFID card or use voice command.</p>';
        elements.clearAnimalsBtn.disabled = true;
        elements.noCharacterWarning.style.display = 'none';
        elements.storyElementsPreview.style.display = 'none';
        return;
    }

    // Group cards by type
    const cardsByType = {
        character: [],
        environment: [],
        moral_lesson: []
    };

    state.selectedCards.forEach(card => {
        const type = card.card_type || 'character';
        if (cardsByType[type]) {
            cardsByType[type].push(card);
        }
    });

    let html = '';

    // Render characters
    if (cardsByType.character.length > 0) {
        html += '<div class="cards-type-section">';
        html += '<h4><span class="indicator character"></span>Characters</h4>';
        cardsByType.character.forEach(card => {
            const emoji = getSpeciesEmoji(card.species, 'character');
            const name = card.name || card.species;
            const role = card.role || 'secondary';
            html += `<span class="card-chip character" data-uid="${card.uid}">
                <span class="type-icon">${emoji}</span>
                <span class="name">${name}</span>
                <span class="role" onclick="showRoleSelector('${card.uid}', '${name}')">${role}</span>
                <span class="remove" onclick="removeCard('${card.uid}')">&times;</span>
            </span>`;
        });
        html += '</div>';
    }

    // Render environments
    if (cardsByType.environment.length > 0) {
        html += '<div class="cards-type-section">';
        html += '<h4><span class="indicator environment"></span>Environments</h4>';
        cardsByType.environment.forEach(card => {
            const emoji = getSpeciesEmoji(card.species, 'environment');
            const name = card.name || card.species;
            html += `<span class="card-chip environment" data-uid="${card.uid}">
                <span class="type-icon">${emoji}</span>
                <span class="name">${name}</span>
                <span class="remove" onclick="removeCard('${card.uid}')">&times;</span>
            </span>`;
        });
        html += '</div>';
    }

    // Render moral lessons
    if (cardsByType.moral_lesson.length > 0) {
        html += '<div class="cards-type-section">';
        html += '<h4><span class="indicator moral_lesson"></span>Moral Lessons</h4>';
        cardsByType.moral_lesson.forEach(card => {
            html += `<span class="card-chip moral_lesson" data-uid="${card.uid}">
                <span class="type-icon">💖</span>
                <span class="name">${card.species}</span>
                <span class="remove" onclick="removeCard('${card.uid}')">&times;</span>
            </span>`;
        });
        html += '</div>';
    }

    container.innerHTML = html;
    elements.clearAnimalsBtn.disabled = false;

    // Show/hide character warning
    if (!state.hasCharacter) {
        elements.noCharacterWarning.style.display = 'block';
    } else {
        elements.noCharacterWarning.style.display = 'none';
    }

    // Show story elements preview
    if (state.storyElements) {
        elements.storyElementsPreview.style.display = 'block';
        elements.previewEnvironment.textContent = state.storyElements.environment || '(random)';
        elements.previewMoral.textContent = state.storyElements.moral_lesson || '(random)';
    } else {
        elements.storyElementsPreview.style.display = 'none';
    }
}

let currentRoleCardUid = null;

function showRoleSelector(uid, name) {
    currentRoleCardUid = uid;
    elements.roleSelectorCharacter.textContent = `Character: ${name}`;
    elements.roleSelectorOverlay.classList.add('active');

    // Set up role option click handlers
    const roleOptions = elements.roleSelectorOverlay.querySelectorAll('.role-option');
    roleOptions.forEach(option => {
        option.onclick = () => updateCardRole(uid, option.dataset.role);
    });
}

function closeRoleSelector() {
    elements.roleSelectorOverlay.classList.remove('active');
    currentRoleCardUid = null;
}

async function updateCardRole(uid, role) {
    try {
        const response = await fetch(`${API_BASE}/cards/selected/${uid}/role`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ role })
        });

        const data = await response.json();

        if (data.status === 'updated') {
            // Update local state
            const card = state.selectedCards.find(c => c.uid === uid);
            if (card) {
                card.role = role;
                renderCards();
            }
            closeRoleSelector();
        } else {
            console.error('Failed to update role:', data.error);
        }
    } catch (error) {
        console.error('Failed to update card role:', error);
    }
}

async function removeCard(uid) {
    try {
        await fetch(`${API_BASE}/cards/selected/${uid}`, { method: 'DELETE' });
        state.selectedCards = state.selectedCards.filter(c => c.uid !== uid);
        renderCards();
    } catch (error) {
        console.error('Failed to remove card:', error);
    }
}

async function clearCards() {
    try {
        await fetch(`${API_BASE}/cards/selected/clear`, { method: 'POST' });
        state.selectedCards = [];
        state.hasCharacter = false;
        state.storyElements = null;
        renderCards();
    } catch (error) {
        console.error('Failed to clear cards:', error);
    }
}

async function generateStory() {
    // Check for at least one character
    if (!state.hasCharacter && state.selectedCards.length > 0) {
        alert('Please add at least one character card to generate a story!');
        return;
    }

    // Legacy check for animals
    if (state.selectedAnimals.length === 0 && state.selectedCards.length === 0) {
        alert('Please select at least one character first!');
        return;
    }

    showLoading('Generating story...');
    setStatus('generating', 'Generating...');
    state.isGenerating = true;

    try {
        const response = await fetch(`${API_BASE}/story/generate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                animals: state.selectedAnimals,
                story_minutes: state.storyLengthMinutes
            })
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
            renderCards();

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

// LED Ring Functions

function initializeLEDRing() {
    if (!elements.ledRing) return;

    // Create 12 LED elements in a circle
    const ledCount = 12;
    for (let i = 0; i < ledCount; i++) {
        const led = document.createElement('div');
        led.className = 'led-pixel';
        led.dataset.index = i;
        elements.ledRing.appendChild(led);
    }
}

async function updateLEDRing() {
    if (!elements.ledRing) return;

    try {
        const response = await fetch(`${API_BASE}/hardware/leds`);
        if (!response.ok) return; // Silently fail if not in mock mode

        const data = await response.json();
        if (!data.mock) return;

        // Update each LED pixel
        const ledPixels = elements.ledRing.querySelectorAll('.led-pixel');
        data.pixels.forEach((color, index) => {
            if (ledPixels[index]) {
                const [r, g, b] = color;
                ledPixels[index].style.backgroundColor = `rgb(${r}, ${g}, ${b})`;
                // Add glow effect if LED is on
                if (r > 0 || g > 0 || b > 0) {
                    ledPixels[index].style.boxShadow = `0 0 10px rgba(${r}, ${g}, ${b}, 0.8)`;
                } else {
                    ledPixels[index].style.boxShadow = 'none';
                }
            }
        });
    } catch (error) {
        // Silently fail - hardware simulation may not be available
    }
}

// RFID Simulation Functions

async function simulateRFIDTap(uid) {
    try {
        const response = await fetch(`${API_BASE}/hardware/rfid/inject`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ uid })
        });

        const data = await response.json();

        if (data.status === 'injected') {
            // Visual feedback
            const btn = elements.rfidButtons.querySelector(`[data-uid="${uid}"]`);
            if (btn) {
                btn.classList.add('tapped');
                setTimeout(() => btn.classList.remove('tapped'), 500);
            }

            // The RFID polling loop will pick up the injected card
            // and add it to selected cards automatically
            setTimeout(loadCurrentState, 500);
        } else {
            console.error('Failed to inject RFID card:', data.error);
        }
    } catch (error) {
        console.error('RFID injection failed:', error);
    }
}

// Story Length Slider Functions

function getStoryLengthDescription(minutes) {
    if (minutes <= 3) return '(very short)';
    if (minutes <= 6) return '(short)';
    if (minutes <= 9) return '(medium)';
    if (minutes <= 12) return '(long)';
    return '(very long)';
}

function updateStoryLengthDisplay(minutes) {
    if (elements.storyLengthMinutes) {
        elements.storyLengthMinutes.textContent = minutes;
    }
    if (elements.storyLengthDescription) {
        elements.storyLengthDescription.textContent = getStoryLengthDescription(minutes);
    }
    state.storyLengthMinutes = minutes;
}

function onStoryLengthChange(e) {
    // Update display immediately for smooth feedback
    const minutes = parseInt(e.target.value);
    updateStoryLengthDisplay(minutes);
}

async function onStoryLengthCommit(e) {
    // Send final value to backend when user releases slider
    const minutes = parseInt(e.target.value);
    try {
        const response = await fetch(`${API_BASE}/hardware/slider/set`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ minutes })
        });

        if (!response.ok) {
            // Slider set failed (maybe not in mock mode)
            console.log('Slider set not available (hardware mode?)');
        }
    } catch (error) {
        console.error('Failed to set slider value:', error);
    }
}

async function loadSliderState() {
    if (!elements.storyLengthSlider) return;

    try {
        const response = await fetch(`${API_BASE}/hardware/slider`);
        if (!response.ok) return;

        const data = await response.json();

        // Only update if slider isn't being dragged
        if (document.activeElement !== elements.storyLengthSlider) {
            elements.storyLengthSlider.value = data.minutes;
            updateStoryLengthDisplay(data.minutes);
        }
    } catch (error) {
        // Silently fail - slider may not be available
    }
}

// Make functions globally accessible for onclick handlers
window.removeCard = removeCard;
window.showRoleSelector = showRoleSelector;
