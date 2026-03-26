# Vocab Miner — Anki Add-on

An Anki add-on to mine vocabulary words, generate definitions, example sentences, IPA, synonyms, and audio — all powered by Claude (Anthropic) or ChatGPT (OpenAI).

## Features

- Generate definition, example sentence, IPA, synonyms and vocabulary breakdown with one click
- Example sentence with the target word in **bold + underlined** on the Front
- IPA, definition, synonyms and breakdown on the Back
- Auto-detect duplicates — checks if you already mined the word (looks for bold+underlined in Front field)
- Reset card progress directly from the plugin
- Preview card (Front + Back) before adding
- TTS audio generation via Google TTS (gTTS) — plays on preview and attaches to card automatically
- Supports Claude (Anthropic) and ChatGPT (OpenAI) as AI providers

## Installation

### Via AnkiWeb
Search for **Vocab Miner** on [ankiweb.net/shared/addons](https://ankiweb.net/shared/addons) or use the add-on code.

### Manual
1. Download the latest `.ankiaddon` from [Releases](../../releases)
2. In Anki: **Tools → Add-ons → Install from file**
3. Restart Anki

## Setup

1. Open **Tools → Vocab Miner**
2. Go to the **Settings** tab
3. Choose your AI provider (Claude or ChatGPT)
4. Paste your API Key:
   - Claude: [console.anthropic.com/settings/keys](https://console.anthropic.com/settings/keys)
   - OpenAI: [platform.openai.com/api-keys](https://platform.openai.com/api-keys)
5. Set your deck name, note type, and field names
6. Click **Save settings**

## Audio (TTS)

The plugin uses **Google TTS (gTTS)** to generate audio. It installs automatically on first use — no manual setup needed.

Audio is generated from the example sentence and attached to the Front field as `[sound:vocabminer_word.mp3]`.

## Card Structure

**Front:**
```
She felt completely <b><u>exhausted</u></b> after the long journey.
[sound:vocabminer_exhausted.mp3]
```

**Back:**
```
exhausted  /ɪɡˈzɔːstɪd/

Definition: ...
Synonyms: ...
Vocabulary: ...
```

## Requirements

- Anki 23.10+
- Internet connection (for AI generation and gTTS)
- API Key from Anthropic or OpenAI

## License

MIT
