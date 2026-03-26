# Vocab Miner — Anki Add-on

An Anki add-on to mine vocabulary words and generate definitions, example sentences, IPA, synonyms, and audio — powered by Claude (Anthropic) or ChatGPT (OpenAI).

## Features

- Generate definition, example sentence, IPA, synonyms and vocabulary breakdown with one click
- Example sentence with the target word in **bold + underlined** on the Front
- IPA, definition, synonyms and breakdown on the Back
- Auto-detect duplicates — checks if you already mined the word
- Regenerate sentence if you don't like the first one
- Reset card progress directly from the plugin
- Preview card (Front + Back) before adding
- TTS audio via Google TTS (gTTS) — plays on preview and attaches to card automatically
- Supports Claude (Anthropic) and ChatGPT (OpenAI) as AI providers

---

## Installation

### Via AnkiWeb
Search for **Vocab Miner** on [ankiweb.net/shared/addons](https://ankiweb.net/shared/addons) or enter the add-on code directly in Anki:
**Tools → Add-ons → Get Add-ons** → paste the code → OK → restart Anki.

### Manual (from this repo)
1. Download or clone this repository
2. Copy the folder contents into a new folder named `vocab_miner` inside your Anki add-ons directory:
   - **macOS:** `~/Library/Application Support/Anki2/addons21/vocab_miner/`
   - **Windows:** `%APPDATA%\Anki2\addons21\vocab_miner\`
   - **Linux:** `~/.local/share/Anki2/addons21/vocab_miner/`
3. Copy `config.example.json` → `config.json` inside that folder (see Configuration below)
4. Restart Anki

---

## Configuration

### 1. API Key

You need an API key from at least one of the providers:

| Provider | Where to get |
|---|---|
| Claude (Anthropic) | [console.anthropic.com/settings/keys](https://console.anthropic.com/settings/keys) |
| ChatGPT (OpenAI) | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) |

### 2. Set up inside Anki

1. Open Anki and go to **Tools → Vocab Miner**
2. Click the **Settings** tab
3. Choose your AI provider (Claude or ChatGPT)
4. Paste your API Key in the corresponding field
5. Fill in your Anki settings:
   - **Deck** — name of the deck where cards will be added (e.g. `English`)
   - **Note type** — your note type (e.g. `Basic`)
   - **Front field** — name of the front field (e.g. `Front`)
   - **Back field** — name of the back field (e.g. `Back`)
6. Choose TTS accent (US, UK or Australian English)
7. Click **Save settings**

### 3. config.json (manual install only)

If you installed manually, create `config.json` from the template:

```bash
cp config.example.json config.json
```

Then fill in your keys directly in the file:

```json
{
    "provider": "claude",
    "claude_key": "sk-ant-YOUR_KEY_HERE",
    "openai_key": "",
    "deck_name": "English",
    "note_type": "Basic",
    "field_front": "Front",
    "field_back": "Back"
}
```

> **Never commit `config.json`** — it contains your API keys. The file is already in `.gitignore`.

---

## Usage

1. Open **Tools → Vocab Miner**
2. Type a word in the input field and press **Generate** (or hit Enter)
3. Review the generated content — you can edit any field freely
4. Click **Regenerate sentence** if you want a different example
5. Click **Preview card** to see Front + Back before saving
6. Click **Add to Anki** to save the card

---

## Audio (TTS)

The plugin uses **Google TTS (gTTS)** to generate audio automatically. It installs into the plugin's own folder on first use — no manual setup needed.

- Audio is generated from the example sentence
- The file is saved as `vocabminer_word.mp3` in your Anki media folder
- The `[sound:...]` tag is attached to the Front field automatically

To preview the audio before adding the card, use the **Preview card** window and click **▶ Play audio**.

> **Note:** Audio playback in preview uses `afplay` (macOS built-in). On Windows/Linux the preview audio may not play, but the card audio will still be attached correctly.

---

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
Vocabulary:
• journey: a long trip from one place to another
• ...
```

---

## Requirements

- Anki 23.10+
- Internet connection (for AI generation and TTS)
- API Key from Anthropic or OpenAI

---

## License

MIT
