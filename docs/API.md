# API Documentation

## Base URL

All API endpoints are prefixed with `/api`.

## Story Endpoints

### Generate Story

Generate a new story with audio.

```
POST /api/story/generate
```

**Request Body:**
```json
{
    "animals": ["cat", "dog"],
    "tts_provider": "edge"  // optional
}
```

**Response:**
```json
{
    "full_text": "Once upon a time...",
    "audio_segments": [
        {
            "text": "First paragraph...",
            "audio": "/api/audio/edge_abc123.mp3"
        }
    ],
    "animals": ["cat", "dog"],
    "status": "success"
}
```

**Status Codes:**
- `200` - Success
- `400` - No animals selected
- `500` - Generation failed

### Get Current Story

Get the current story state.

```
GET /api/story/current
```

**Response:**
```json
{
    "selected_animals": ["cat"],
    "current_story": {
        "full_text": "...",
        "audio_segments": [...],
        "animals": [...],
        "status": "success",
        "created_at": "2024-01-01T12:00:00"
    },
    "is_generating": false,
    "is_playing": false,
    "current_segment_index": 0
}
```

## Audio Endpoints

### Serve Audio File

```
GET /api/audio/<filename>
```

Returns the audio file for playback.

## Card Management Endpoints

### List Cards

```
GET /api/cards
```

**Response:**
```json
{
    "123456": {
        "animal": "cat",
        "registered": "2024-01-01T12:00:00"
    },
    "789012": {
        "animal": "dog",
        "registered": "2024-01-01T12:05:00"
    }
}
```

### Register Card

```
POST /api/cards/save
```

**Request Body:**
```json
{
    "uid": "123456",
    "animal": "elephant"
}
```

**Response:**
```json
{
    "status": "saved",
    "uid": "123456",
    "animal": "elephant"
}
```

### Delete Card

```
DELETE /api/cards/delete/<uid>
```

**Response:**
```json
{
    "status": "deleted",
    "uid": "123456"
}
```

## Animal Endpoints

### Get Selected Animals

```
GET /api/animals
```

**Response:**
```json
{
    "animals": ["cat", "dog"]
}
```

### Add Animal

```
POST /api/animals
```

**Request Body:**
```json
{
    "animal": "lion"
}
```

### Remove Animal

```
DELETE /api/animals/<animal>
```

### Clear All Animals

```
POST /api/animals/clear
```

## Voice Endpoints

### Listen for Voice Command

```
POST /api/voice/listen
```

**Request Body:**
```json
{
    "timeout": 5  // optional, seconds
}
```

**Response:**
```json
{
    "text": "Tell me a story about a cat",
    "animals": ["cat"],
    "status": "success"
}
```

### Get Languages

```
GET /api/voice/languages
```

**Response:**
```json
{
    "languages": [
        {"code": "es-ES", "name": "Spanish (Spain)"},
        {"code": "en-US", "name": "English (US)"}
    ],
    "current": "es-ES"
}
```

### Set Language

```
POST /api/voice/language
```

**Request Body:**
```json
{
    "language": "en-US"
}
```

## Status Endpoints

### Get System Status

```
GET /api/status
```

**Response:**
```json
{
    "state": {...},
    "tts_provider": "edge",
    "cache": {
        "file_count": 10,
        "total_size_mb": 5.2,
        "max_size_mb": 500,
        "usage_percent": 1.0
    },
    "audio_devices": {
        "has_speaker": true,
        "has_microphone": true,
        "volume": 80
    }
}
```

### Clear Cache

```
POST /api/cache/clear
```

**Response:**
```json
{
    "status": "cleared"
}
```
