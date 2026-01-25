# Story Text Post-Processing Design

**Date**: 2026-01-25
**Status**: Approved
**Author**: Design brainstorming session

## Problem Statement

LLM-generated stories sometimes contain markdown formatting (asterisks, headers, bold text) despite prompt instructions to avoid them. These symbols appear mainly at the beginning and end of stories but occasionally throughout. TTS engines cannot pronounce these symbols, degrading the audio experience.

## Solution Overview

Add conservative post-processing to clean markdown formatting from LLM output while preserving story content. Apply cleaning only to real LLM generation, not mock stories.

## Architecture

### Component: `StoryGenerator._clean_story_text()`

**Location**: `src/raspi_storyteller/services/story_generator.py`

**Purpose**: Remove markdown formatting from LLM-generated stories before TTS processing.

**Integration**:
- Called in `_generate_sync()` method (single point of cleaning)
- Applies to all LLM output paths: `generate_story()` and `generate_story_enhanced()`
- Mock stories bypass this cleaning (already clean)

## Cleaning Logic

### 1. Strip Beginning Markdown
Remove meta-text and formatting before story starts:
- Lines starting with `#` (markdown headers)
- Standalone `**text**` or `*text*` lines
- Meta-text: "Here is the story:", "Title:", etc.
- Stop at first paragraph of actual story content

### 2. Strip Ending Markdown
Remove closing markers after story ends:
- Lines containing `**The End**`, `**Fin**`, `**Fine**`, etc.
- Trailing separator lines: `---`, `***`
- Work backwards from end until real story content found

### 3. Clean Inline Markdown
Throughout the entire text:
- `**bold**` → `bold`
- `*italic*` → `italic`
- `__underline__` → `underline`
- `~~strikethrough~~` → `strikethrough`

### 4. Normalize Whitespace
- Collapse multiple blank lines to double newlines (paragraph breaks)
- Strip leading/trailing whitespace

## Implementation

### Method Signature

```python
def _clean_story_text(self, text: str) -> str:
    """
    Remove markdown formatting from LLM-generated stories.

    Cleans beginning/end meta-text and inline markdown formatting.
    Conservative approach - preserves story content.

    Args:
        text: Raw story text from LLM.

    Returns:
        Cleaned story text ready for TTS.
    """
```

### Integration Point

In `_generate_sync()` method (line ~356):

```python
def _generate_sync(self, prompt: str, num_predict: int = 500) -> str:
    try:
        response = self._client.generate(
            model=self.model,
            prompt=prompt,
            options={"temperature": 0.8, "num_predict": num_predict},
        )
        raw_text = response.get("response", "")
        return self._clean_story_text(raw_text)  # <-- Add cleaning here
    except Exception as e:
        logger.error(f"Ollama generation failed: {e}")
        raise
```

### Why Clean in `_generate_sync()`?

- Single point of cleaning for all LLM output
- Mock stories bypass this method (remain untouched)
- Consistent behavior across `generate_story()` and `generate_story_enhanced()`
- Simplifies maintenance

## Testing Strategy

### Unit Tests

Add to `tests/test_story_generator.py`:

1. **Test beginning markdown removal**
   - Input: `**Title**\n\nOnce upon a time...`
   - Expected: `Once upon a time...`

2. **Test ending markdown removal**
   - Input: `Once upon a time...\n\n**The End**`
   - Expected: `Once upon a time...`

3. **Test inline markdown removal**
   - Input: `The **brave** knight fought the *dragon*.`
   - Expected: `The brave knight fought the dragon.`

4. **Test no-markdown passthrough**
   - Input: `Once upon a time in a magical forest.`
   - Expected: `Once upon a time in a magical forest.`

5. **Test empty input**
   - Input: `""`
   - Expected: `""`

### Integration Tests

- Mock stories should remain unchanged (they bypass `_generate_sync()`)
- Real LLM stories automatically cleaned
- Existing tests should continue passing

## Edge Cases

| Case | Behavior | Rationale |
|------|----------|-----------|
| Empty string | Return empty string | Safe default |
| Only markdown, no story | Return empty string | No content to speak |
| Legitimate asterisks in dialogue | Will be cleaned | Acceptable trade-off |
| Already clean stories | Pass through unchanged | No-op is safe |

## Logging

Add debug logging for transparency:

```python
logger.debug(f"Cleaned story text: removed {chars_removed} characters")
```

Helps diagnose if LLM generates excessive markdown.

## Trade-offs

### Advantages
- Improves TTS audio quality
- Handles LLM prompt non-compliance
- Conservative approach preserves story content
- Single point of maintenance

### Limitations
- May remove legitimate asterisks in dialogue
- Regex-based (not markdown parser) - simpler but less precise
- Only cleans output, doesn't prevent LLM from generating markdown

## Future Enhancements

- Add metrics: track markdown removal frequency
- Enhance prompt engineering to reduce LLM markdown generation
- Consider language-specific cleaning patterns if needed
- Add configurable cleaning aggressiveness levels

## Example

**Input (from LLM)**:
```
**El Dragón y el Ratón**

Había una vez en un bosque mágico...

**Fin**
```

**Output (after cleaning)**:
```
Había una vez en un bosque mágico...
```
