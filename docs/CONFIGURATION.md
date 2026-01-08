# Configuration Guide

## Environment Variables

The application is configured via environment variables, typically stored in a `.env` file.

### Flask Settings

| Variable | Description | Default |
|----------|-------------|---------|
| `FLASK_ENV` | Environment (development/production/testing) | development |
| `FLASK_DEBUG` | Enable debug mode | False |
| `FLASK_PORT` | Server port | 5000 |
| `SECRET_KEY` | Flask secret key | dev-secret-key |

### Ollama Settings

| Variable | Description | Default |
|----------|-------------|---------|
| `OLLAMA_HOST` | Ollama server URL | http://localhost:11434 |
| `OLLAMA_MODEL` | LLM model to use | gemma3:1b |
| `OLLAMA_TIMEOUT` | Request timeout (seconds) | 120 |

### TTS Settings

| Variable | Description | Default |
|----------|-------------|---------|
| `TTS_PROVIDER` | TTS provider (edge/pyttsx3/google) | pyttsx3 |
| `EDGE_TTS_VOICE` | Edge TTS voice ID | es-ES-PabloNeural |
| `GOOGLE_API_KEY` | Google Cloud API key | (empty) |

### Audio Settings

| Variable | Description | Default |
|----------|-------------|---------|
| `AUDIO_CACHE_DIR` | Audio cache directory | ./audio_cache |
| `MAX_CACHE_SIZE_MB` | Maximum cache size | 500 |

### Speech Recognition

| Variable | Description | Default |
|----------|-------------|---------|
| `SPEECH_LANGUAGE` | Recognition language | es-ES |
| `SPEECH_TIMEOUT` | Listen timeout (seconds) | 5 |

### Hardware Settings

| Variable | Description | Default |
|----------|-------------|---------|
| `MOCK_HARDWARE` | Simulate hardware | True |
| `MOCK_OLLAMA` | Use mock LLM responses | False |
| `LED_COUNT` | Number of LEDs | 12 |
| `LED_PIN` | GPIO pin for LEDs | 18 |
| `LED_BRIGHTNESS` | LED brightness (0-1) | 0.5 |
| `RFID_DEBOUNCE_TIME` | Card debounce (seconds) | 1.5 |

### Logging

| Variable | Description | Default |
|----------|-------------|---------|
| `LOG_LEVEL` | Log level | DEBUG |
| `LOG_FILE` | Log file path | logs/app.log |

## Configuration Classes

The application provides pre-configured classes:

### DevelopmentConfig

For local development:
- Debug enabled
- Mock hardware
- pyttsx3 TTS (offline)

### ProductionConfig

For Raspberry Pi deployment:
- Debug disabled
- Real hardware
- Edge TTS (better quality)

### TestingConfig

For running tests:
- All mocks enabled
- Temporary directories
- Reduced logging

## Example .env Files

### Local Development

```bash
FLASK_ENV=development
FLASK_DEBUG=True
MOCK_HARDWARE=True
TTS_PROVIDER=pyttsx3
LOG_LEVEL=DEBUG
```

### Raspberry Pi Production

```bash
FLASK_ENV=production
FLASK_DEBUG=False
MOCK_HARDWARE=False
TTS_PROVIDER=edge
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=gemma3:1b
LOG_LEVEL=INFO
LED_COUNT=12
LED_PIN=18
```

## TTS Provider Comparison

| Provider | Quality | Requires Internet | Speed |
|----------|---------|-------------------|-------|
| Edge TTS | High | Yes | Fast |
| pyttsx3 | Medium | No | Fast |
| Google TTS | High | Yes | Medium |

Recommendation:
- Use **pyttsx3** for offline/development
- Use **Edge TTS** for best quality with internet
- Use **Google TTS** if you have API quota
