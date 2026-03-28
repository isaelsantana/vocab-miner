import json
import os
import re
import sys
import tempfile
import urllib.request
from aqt import mw
from aqt.utils import showInfo

# Add vendor dir to path for auto-installed packages
_vendor_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor")
if os.path.exists(_vendor_dir) and _vendor_dir not in sys.path:
    sys.path.insert(0, _vendor_dir)
from aqt.qt import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QTextEdit, QPushButton, QComboBox, QGroupBox, QFormLayout,
    QMessageBox, Qt, QThread, pyqtSignal, QTabWidget, QWidget,
    QTextBrowser, QSplitter
)


# ─── Config ───────────────────────────────────────────────────────────────────

def get_config():
    cfg = mw.addonManager.getConfig(__name__) or {}
    return {
        "provider":     cfg.get("provider", "claude"),
        "claude_key":   cfg.get("claude_key", ""),
        "openai_key":   cfg.get("openai_key", ""),
        "gemini_key":   cfg.get("gemini_key", ""),
        "deck_name":    cfg.get("deck_name", "Default"),
        "note_type":    cfg.get("note_type", "Basic"),
        "field_front":  cfg.get("field_front", "Front"),
        "field_back":   cfg.get("field_back", "Back"),
        "tts_lang":     cfg.get("tts_lang", "en"),
        "tts_tld":      cfg.get("tts_tld", "com"),
    }

def save_config(data: dict):
    mw.addonManager.writeConfig(__name__, data)


# ─── AI Worker ────────────────────────────────────────────────────────────────

class AIWorker(QThread):
    result = pyqtSignal(dict)
    error  = pyqtSignal(str)

    def __init__(self, word, provider, api_key, mode="full", current_sentence=""):
        super().__init__()
        self.word = word
        self.provider = provider
        self.api_key = api_key
        self.mode = mode
        self.current_sentence = current_sentence

    def run(self):
        try:
            if self.mode == "full":
                data = self._generate_full()
            else:
                data = self._regenerate_sentence()
            self.result.emit(data)
        except Exception as e:
            self.error.emit(str(e))

    def _call_ai(self, prompt, system=""):
        if self.provider == "claude":
            return self._call_claude(prompt, system)
        if self.provider == "gemini":
            return self._call_gemini(prompt, system)
        return self._call_openai(prompt, system)

    def _call_claude(self, prompt, system=""):
        body = {
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 600,
            "messages": [{"role": "user", "content": prompt}]
        }
        if system:
            body["system"] = system
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=json.dumps(body).encode(),
            headers={
                "Content-Type": "application/json",
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
            },
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
            if "error" in data:
                raise Exception(data["error"].get("message", str(data["error"])))
            return "".join(c.get("text", "") for c in data.get("content", [])).strip()

    def _call_gemini(self, prompt, system=""):
        body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"maxOutputTokens": 600},
        }
        if system:
            body["system_instruction"] = {"parts": [{"text": system}]}
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={self.api_key}"
        req = urllib.request.Request(
            url,
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
            if "error" in data:
                raise Exception(data["error"].get("message", str(data["error"])))
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()

    def _call_openai(self, prompt, system=""):
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        body = {
            "model": "gpt-4o-mini",
            "max_tokens": 600,
            "messages": messages
        }
        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=json.dumps(body).encode(),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
            if "error" in data:
                raise Exception(data["error"].get("message", str(data["error"])))
            return data["choices"][0]["message"]["content"].strip()

    def _generate_full(self):
        system = "You are a vocabulary assistant. Always respond ONLY in valid JSON, no markdown, no extra text."
        prompt = f"""For the English word "{self.word}", return a JSON object with these keys:
- "ipa": the IPA pronunciation string only, e.g. /ɪˈfɛmərəl/ — no extra text
- "definition": a clear, natural English definition (2-3 sentences, no bullet points)
- "sentence": one natural example sentence using the word in context (intermediate level)
- "synonyms": a comma-separated string of 3-5 synonyms
- "breakdown": a JSON array of objects with "word" and "meaning" keys for every significant word in the sentence EXCEPT "{self.word}" itself. Skip very common words like: the, a, is, in, and, to, of, it, for, on, with, at, by, from, that, this, was, are, be, as, an"""
        raw = self._call_ai(prompt, system)
        cleaned = re.sub(r"```json|```", "", raw).strip()
        m = re.search(r'\{.*\}', cleaned, re.DOTALL)
        if m:
            cleaned = m.group(0)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            correction = (f'Your last response was not valid JSON. Raw:\n{raw}\n\n'
                          f'Return ONLY the JSON object for "{self.word}", nothing else.')
            raw2 = self._call_ai(correction, system)
            cleaned2 = re.sub(r"```json|```", "", raw2).strip()
            m2 = re.search(r'\{.*\}', cleaned2, re.DOTALL)
            if m2:
                cleaned2 = m2.group(0)
            return json.loads(cleaned2)

    def _regenerate_sentence(self):
        system = "You are a vocabulary assistant. Always respond ONLY in valid JSON, no markdown, no extra text."
        prompt = f"""Write ONE new natural example sentence using the English word "{self.word}" in a different context than: "{self.current_sentence}".
Return a JSON object with:
- "sentence": the new sentence
- "breakdown": a JSON array of objects with "word" and "meaning" keys for every significant word EXCEPT "{self.word}". Skip very common words like: the, a, is, in, and, to, of, it, for, on, with, at, by, from, that, this, was, are, be, as, an"""
        raw = self._call_ai(prompt, system)
        cleaned = re.sub(r"```json|```", "", raw).strip()
        m = re.search(r'\{.*\}', cleaned, re.DOTALL)
        if m:
            cleaned = m.group(0)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            correction = (f'Your last response was not valid JSON. Raw:\n{raw}\n\n'
                          f'Return ONLY the JSON object for "{self.word}", nothing else.')
            raw2 = self._call_ai(correction, system)
            cleaned2 = re.sub(r"```json|```", "", raw2).strip()
            m2 = re.search(r'\{.*\}', cleaned2, re.DOTALL)
            if m2:
                cleaned2 = m2.group(0)
            return json.loads(cleaned2)


# ─── Main Dialog ──────────────────────────────────────────────────────────────

class VocabMinerDialog(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Vocab Miner")
        self.setMinimumWidth(560)
        self.worker = None
        from collections import OrderedDict
        self._cache = OrderedDict()
        self._cache_max = 50
        self._build_ui()
        self._load_settings()
        self._check_anki_connection()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(12)
        tabs = QTabWidget()
        tabs.addTab(self._build_miner_tab(), "Miner")
        tabs.addTab(self._build_settings_tab(), "Settings")
        root.addWidget(tabs)

    # ── Miner tab ─────────────────────────────────────────────────────────────

    def _build_miner_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(10)

        # Word input
        word_row = QHBoxLayout()
        self.word_input = QLineEdit()
        self.word_input.setPlaceholderText("Type a word and press Generate...")
        self.word_input.returnPressed.connect(self._generate)
        self.btn_generate = QPushButton("Generate")
        self.btn_generate.clicked.connect(self._generate)
        self.btn_generate.setDefault(True)
        word_row.addWidget(self.word_input)
        word_row.addWidget(self.btn_generate)
        layout.addLayout(word_row)

        # Status row
        status_row = QHBoxLayout()
        self.lbl_word = QLabel("")
        self.lbl_word.setStyleSheet("font-size: 16px; font-weight: bold;")
        self.lbl_status = QLabel("")
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        status_row.addWidget(self.lbl_word)
        status_row.addWidget(self.lbl_status)
        layout.addLayout(status_row)

        # FRONT preview
        front_group = QGroupBox("FRONT (what goes on the front of the card)")
        front_layout = QVBoxLayout(front_group)

        layout.addWidget(QLabel("Example sentence (word will be bold in card):"))
        self.txt_sentence = QTextEdit()
        self.txt_sentence.setFixedHeight(55)
        front_layout.addWidget(self.txt_sentence)

        sentence_btns = QHBoxLayout()
        self.btn_regen = QPushButton("Regenerate sentence")
        self.btn_regen.clicked.connect(self._regenerate_sentence)
        self.btn_regen.setEnabled(False)
        sentence_btns.addWidget(self.btn_regen)
        sentence_btns.addStretch()
        front_layout.addLayout(sentence_btns)

        hint = QLabel("Audio [sound:word.mp3] will be added automatically by AwesomeTTS field tag")
        hint.setStyleSheet("font-size: 11px; color: gray;")
        front_layout.addWidget(hint)
        layout.addWidget(front_group)

        # BACK fields
        back_group = QGroupBox("BACK (what goes on the back of the card)")
        back_layout = QVBoxLayout(back_group)

        back_layout.addWidget(QLabel("IPA:"))
        self.txt_ipa = QLineEdit()
        self.txt_ipa.setPlaceholderText("/ɪˈfɛmərəl/")
        back_layout.addWidget(self.txt_ipa)

        back_layout.addWidget(QLabel("Definition:"))
        self.txt_definition = QTextEdit()
        self.txt_definition.setFixedHeight(70)
        back_layout.addWidget(self.txt_definition)

        back_layout.addWidget(QLabel("Synonyms:"))
        self.txt_synonyms = QTextEdit()
        self.txt_synonyms.setFixedHeight(40)
        back_layout.addWidget(self.txt_synonyms)

        back_layout.addWidget(QLabel("Vocabulary breakdown:"))
        self.txt_breakdown = QTextEdit()
        self.txt_breakdown.setFixedHeight(70)
        back_layout.addWidget(self.txt_breakdown)

        layout.addWidget(back_group)

        # Action buttons
        btn_row = QHBoxLayout()
        self.btn_add = QPushButton("Add to Anki")
        self.btn_add.clicked.connect(self._add_to_anki)
        self.btn_add.setEnabled(False)
        self.btn_add.setStyleSheet("QPushButton { background: #27ae60; color: white; padding: 6px 18px; border-radius: 5px; } QPushButton:disabled { background: #ccc; }")

        self.btn_reset = QPushButton("Reset card")
        self.btn_reset.clicked.connect(self._reset_card)
        self.btn_reset.setVisible(False)
        self.btn_reset.setStyleSheet("QPushButton { color: #c0392b; border: 1px solid #c0392b; padding: 6px 18px; border-radius: 5px; }")

        self.btn_clear = QPushButton("Clear")
        self.btn_clear.clicked.connect(self._clear)

        self.btn_preview = QPushButton("Preview card")
        self.btn_preview.clicked.connect(self._show_preview)
        self.btn_preview.setEnabled(False)
        self.btn_preview.setStyleSheet("QPushButton { color: #2980b9; border: 1px solid #2980b9; padding: 6px 18px; border-radius: 5px; } QPushButton:disabled { color: #ccc; border-color: #ccc; }")

        btn_row.addWidget(self.btn_add)
        btn_row.addWidget(self.btn_preview)
        btn_row.addWidget(self.btn_reset)
        btn_row.addStretch()
        btn_row.addWidget(self.btn_clear)
        layout.addLayout(btn_row)

        return tab

    # ── Settings tab ──────────────────────────────────────────────────────────

    def _build_settings_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(10)

        provider_group = QGroupBox("AI Provider")
        provider_form = QFormLayout(provider_group)
        self.cfg_provider = QComboBox()
        self.cfg_provider.addItem("Claude (Anthropic)", "claude")
        self.cfg_provider.addItem("ChatGPT (OpenAI)", "openai")
        self.cfg_provider.addItem("Gemini (Google)", "gemini")
        provider_form.addRow("Provider:", self.cfg_provider)
        layout.addWidget(provider_group)

        claude_group = QGroupBox("Claude API Key")
        claude_form = QFormLayout(claude_group)
        self.cfg_claude_key = QLineEdit()
        self.cfg_claude_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.cfg_claude_key.setPlaceholderText("sk-ant-...")
        claude_form.addRow("API Key:", self.cfg_claude_key)
        lbl_claude = QLabel('<a href="https://console.anthropic.com/settings/keys">console.anthropic.com</a>')
        lbl_claude.setOpenExternalLinks(True)
        claude_form.addRow("", lbl_claude)
        layout.addWidget(claude_group)

        openai_group = QGroupBox("ChatGPT API Key (OpenAI)")
        openai_form = QFormLayout(openai_group)
        self.cfg_openai_key = QLineEdit()
        self.cfg_openai_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.cfg_openai_key.setPlaceholderText("sk-...")
        openai_form.addRow("API Key:", self.cfg_openai_key)
        lbl_openai = QLabel('<a href="https://platform.openai.com/api-keys">platform.openai.com</a>')
        lbl_openai.setOpenExternalLinks(True)
        openai_form.addRow("", lbl_openai)
        layout.addWidget(openai_group)

        gemini_group = QGroupBox("Gemini API Key (Google)")
        gemini_form = QFormLayout(gemini_group)
        self.cfg_gemini_key = QLineEdit()
        self.cfg_gemini_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.cfg_gemini_key.setPlaceholderText("AIza...")
        gemini_form.addRow("API Key:", self.cfg_gemini_key)
        lbl_gemini = QLabel('<a href="https://aistudio.google.com/app/apikey">aistudio.google.com</a>')
        lbl_gemini.setOpenExternalLinks(True)
        gemini_form.addRow("", lbl_gemini)
        layout.addWidget(gemini_group)

        anki_group = QGroupBox("Anki")
        anki_form = QFormLayout(anki_group)
        self.cfg_deck = QLineEdit()
        self.cfg_note_type = QLineEdit()
        self.cfg_field_front = QLineEdit()
        self.cfg_field_back = QLineEdit()
        anki_form.addRow("Deck:", self.cfg_deck)
        anki_form.addRow("Note type:", self.cfg_note_type)
        anki_form.addRow("Front field:", self.cfg_field_front)
        anki_form.addRow("Back field:", self.cfg_field_back)
        layout.addWidget(anki_group)

        tts_group = QGroupBox("TTS Audio (Google)")
        tts_form = QFormLayout(tts_group)
        self.cfg_tts_lang = QLineEdit()
        self.cfg_tts_lang.setPlaceholderText("en")
        tts_form.addRow("Language:", self.cfg_tts_lang)
        self.cfg_tts_tld = QComboBox()
        self.cfg_tts_tld.addItem("US English (com)", "com")
        self.cfg_tts_tld.addItem("UK English (co.uk)", "co.uk")
        self.cfg_tts_tld.addItem("Australian (com.au)", "com.au")
        tts_form.addRow("Accent:", self.cfg_tts_tld)
        lbl_gtts = QLabel("Requires: <code>pip install gtts</code> in Terminal")
        lbl_gtts.setWordWrap(True)
        tts_form.addRow("", lbl_gtts)
        layout.addWidget(tts_group)

        btn_save = QPushButton("Save settings")
        btn_save.clicked.connect(self._save_settings)
        btn_save.setStyleSheet("QPushButton { background: #2c3e50; color: white; padding: 7px 20px; border-radius: 5px; }")
        layout.addWidget(btn_save)
        layout.addStretch()

        return tab

    # ── Logic ─────────────────────────────────────────────────────────────────

    def _load_settings(self):
        cfg = get_config()
        idx = self.cfg_provider.findData(cfg["provider"])
        if idx >= 0:
            self.cfg_provider.setCurrentIndex(idx)
        self.cfg_claude_key.setText(cfg["claude_key"])
        self.cfg_openai_key.setText(cfg["openai_key"])
        self.cfg_gemini_key.setText(cfg["gemini_key"])
        self.cfg_deck.setText(cfg["deck_name"])
        self.cfg_note_type.setText(cfg["note_type"])
        self.cfg_field_front.setText(cfg["field_front"])
        self.cfg_field_back.setText(cfg["field_back"])
        self.cfg_tts_lang.setText(cfg["tts_lang"])
        idx = self.cfg_tts_tld.findData(cfg["tts_tld"])
        if idx >= 0:
            self.cfg_tts_tld.setCurrentIndex(idx)

    def _save_settings(self):
        save_config({
            "provider":    self.cfg_provider.currentData(),
            "claude_key":  self.cfg_claude_key.text().strip(),
            "openai_key":  self.cfg_openai_key.text().strip(),
            "gemini_key":  self.cfg_gemini_key.text().strip(),
            "deck_name":   self.cfg_deck.text().strip(),
            "note_type":   self.cfg_note_type.text().strip(),
            "field_front": self.cfg_field_front.text().strip(),
            "field_back":  self.cfg_field_back.text().strip(),
            "tts_lang":    self.cfg_tts_lang.text().strip() or "en",
            "tts_tld":     self.cfg_tts_tld.currentData(),
        })
        QMessageBox.information(self, "Saved", "Settings saved!")

    def _get_active_key(self):
        provider = self.cfg_provider.currentData()
        if provider == "claude":
            key = self.cfg_claude_key.text().strip() or get_config()["claude_key"]
        elif provider == "gemini":
            key = self.cfg_gemini_key.text().strip() or get_config()["gemini_key"]
        else:
            key = self.cfg_openai_key.text().strip() or get_config()["openai_key"]
        return provider, key

    def _cache_get(self, word, provider):
        key = (word.lower().strip(), provider)
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        return None

    def _cache_put(self, word, provider, data):
        key = (word.lower().strip(), provider)
        if key in self._cache:
            self._cache.move_to_end(key)
        self._cache[key] = data
        if len(self._cache) > self._cache_max:
            self._cache.popitem(last=False)

    def _check_anki_connection(self):
        try:
            decks = mw.col.decks.all_names()
            cfg = get_config()
            if cfg["deck_name"] not in decks:
                self.lbl_status.setText(f"⚠ Deck '{cfg['deck_name']}' not found")
        except Exception:
            pass

    def _set_busy(self, busy: bool):
        self.btn_generate.setEnabled(not busy)
        self.btn_generate.setText("Generating..." if busy else "Generate")
        has_word = bool(self.word_input.text().strip())
        self.btn_regen.setEnabled(not busy and has_word)
        self.btn_add.setEnabled(not busy and has_word)
        self.btn_preview.setEnabled(not busy and has_word)

    def _generate(self):
        word = self.word_input.text().strip()
        if not word:
            return
        provider, api_key = self._get_active_key()
        if not api_key:
            QMessageBox.warning(self, "API Key missing", "Go to Settings and add your API Key.")
            return

        cached = self._cache_get(word, provider)
        if cached:
            self.lbl_word.setText(word)
            self.lbl_status.setText("(cached)")
            self._on_generated(cached)
            return

        self._set_busy(True)
        self.lbl_word.setText(word)
        provider_label = {"claude": "Claude", "openai": "ChatGPT", "gemini": "Gemini"}.get(provider, provider)
        self.lbl_status.setText(f"Generating via {provider_label}...")
        self.btn_reset.setVisible(False)

        self.worker = AIWorker(word, provider, api_key, mode="full")
        self.worker.result.connect(self._on_generated)
        self.worker.error.connect(self._on_error)
        self.worker.start()

    def _on_generated(self, data: dict):
        word = self.word_input.text().strip()
        provider, _ = self._get_active_key()
        self._cache_put(word, provider, data)
        self.txt_ipa.setText(data.get("ipa", ""))
        self.txt_definition.setPlainText(data.get("definition", ""))
        self.txt_synonyms.setPlainText(data.get("synonyms", ""))
        self.txt_sentence.setPlainText(data.get("sentence", ""))
        breakdown = data.get("breakdown", [])
        if isinstance(breakdown, list):
            self.txt_breakdown.setPlainText("\n".join(f"{b['word']}: {b['meaning']}" for b in breakdown))
        self._set_busy(False)
        self._check_duplicate(word)

    def _on_error(self, msg: str):
        self._set_busy(False)
        self.lbl_status.setText("Error")
        provider, key = self._get_active_key()
        provider_label = {"claude": "Claude", "openai": "ChatGPT", "gemini": "Gemini"}.get(provider, provider)
        key_preview = (key[:8] + "...") if key else "(no key set)"
        QMessageBox.critical(self, "Error",
            f"Provider: {provider_label}\nKey: {key_preview}\n\nError: {msg}\n\n"
            f"429 = sem créditos. Acesse platform.openai.com/billing ou console.anthropic.com.\n"
            f"Sem chave = vá em Settings e salve sua API Key.")

    def _regenerate_sentence(self):
        word = self.word_input.text().strip()
        if not word:
            return
        provider, api_key = self._get_active_key()
        current = self.txt_sentence.toPlainText()
        self._set_busy(True)
        self.lbl_status.setText("Regenerating sentence...")
        self.worker = AIWorker(word, provider, api_key, mode="regen", current_sentence=current)
        self.worker.result.connect(self._on_sentence_regenerated)
        self.worker.error.connect(self._on_error)
        self.worker.start()

    def _on_sentence_regenerated(self, data: dict):
        self.txt_sentence.setPlainText(data.get("sentence", ""))
        breakdown = data.get("breakdown", [])
        if isinstance(breakdown, list):
            self.txt_breakdown.setPlainText("\n".join(f"{b['word']}: {b['meaning']}" for b in breakdown))
        self._set_busy(False)
        self.lbl_status.setText("✓ Sentence regenerated")

    def _check_duplicate(self, word: str):
        try:
            # Search for notes where Front field contains the word bold+underlined
            # This way we only flag words we actually mined (not random matches)
            field_front = self.cfg_field_front.text().strip() or get_config()["field_front"]
            deck_name   = self.cfg_deck.text().strip() or get_config()["deck_name"]

            # Search in the configured deck for the word in the front field
            note_ids = mw.col.find_notes(f'deck:"{deck_name}" {field_front}:"*<b><u>{word}*"')
            if not note_ids:
                # fallback: broader search without deck restriction
                note_ids = mw.col.find_notes(f'{field_front}:"*<b><u>{word}*"')

            if note_ids:
                self.lbl_status.setText("⚠ Already mined")
                self.btn_reset.setVisible(True)
            else:
                self.lbl_status.setText("✓ New word")
                self.btn_reset.setVisible(False)
        except Exception:
            self.lbl_status.setText("Could not check deck")

    def _build_front_html(self) -> str:
        word     = self.word_input.text().strip()
        sentence = self.txt_sentence.toPlainText().strip()
        # Bold the target word in the sentence
        if sentence and word:
            front_sentence = re.sub(
                rf'\b({re.escape(word)})\b',
                r'<b><u>\1</u></b>',
                sentence,
                flags=re.IGNORECASE
            )
        else:
            front_sentence = sentence
        # AwesomeTTS uses the field content to generate audio — 
        # we store the plain sentence so AwesomeTTS can read it via TTS on the Front field
        # The [sound:] tag will be added by AwesomeTTS automatically when configured on this field
        return front_sentence

    def _build_back_html(self) -> str:
        word      = self.word_input.text().strip()
        ipa       = self.txt_ipa.text().strip()
        definition = self.txt_definition.toPlainText().strip()
        synonyms  = self.txt_synonyms.toPlainText().strip()
        breakdown = self.txt_breakdown.toPlainText().strip()

        parts = []
        # Word + IPA at top of back
        word_line = f"<b style='font-size:1.2em;'>{word}</b>"
        if ipa:
            word_line += f" &nbsp;<span style='color:#555;'>{ipa}</span>"
        parts.append(word_line)

        if definition:
            parts.append(f"<b>Definition</b><br>{definition}")
        if synonyms:
            parts.append(f"<b>Synonyms</b><br>{synonyms}")
        if breakdown:
            lines = [f"• {l}" for l in breakdown.splitlines() if l.strip()]
            parts.append("<b>Vocabulary</b><br>" + "<br>".join(lines))

        return "<br><br>".join(parts)

    def _get_tts_settings(self):
        lang = self.cfg_tts_lang.text().strip() or get_config()["tts_lang"] or "en"
        tld  = self.cfg_tts_tld.currentData() or get_config()["tts_tld"] or "com"
        return lang, tld

    def _ensure_gtts(self):
        """Try to import gTTS, auto-install into plugin folder if missing."""
        try:
            from gtts import gTTS
            return gTTS
        except ImportError:
            import subprocess
            # Install into the plugin's own folder so Anki's Python can find it
            plugin_dir = os.path.dirname(os.path.abspath(__file__))
            vendor_dir = os.path.join(plugin_dir, "vendor")
            os.makedirs(vendor_dir, exist_ok=True)
            if vendor_dir not in sys.path:
                sys.path.insert(0, vendor_dir)
            try:
                subprocess.run(
                    [sys.executable, "-m", "pip", "install", "gtts", f"--target={vendor_dir}", "--quiet"],
                    check=True
                )
                from gtts import gTTS
                return gTTS
            except Exception as e:
                raise Exception(
                    f"Could not auto-install gTTS: {e}\n\n"
                    "Try manually: pip install gtts"
                )

    def _generate_audio(self, text: str, word: str) -> str:
        """Generate audio via gTTS, save to Anki media folder, return filename."""
        gTTS = self._ensure_gtts()
        lang, tld = self._get_tts_settings()
        safe_word = re.sub(r"[^a-zA-Z0-9_-]", "_", word)
        filename = f"vocabminer_{safe_word}.mp3"
        filepath = os.path.join(mw.col.media.dir(), filename)
        tts = gTTS(text=text, lang=lang, tld=tld, slow=False)
        tts.save(filepath)
        return filename

    def _play_preview_audio(self, text: str):
        """Generate temp audio and play it for preview."""
        import threading
        def _play():
            try:
                gTTS = self._ensure_gtts()
                lang, tld = self._get_tts_settings()
                tmp = os.path.join(tempfile.gettempdir(), "vocabminer_preview.mp3")
                tts = gTTS(text=text, lang=lang, tld=tld, slow=False)
                tts.save(tmp)
                import subprocess
                if sys.platform == "darwin":
                    subprocess.Popen(["afplay", tmp])
                elif sys.platform == "win32":
                    os.startfile(tmp)
                else:
                    # Linux: try common players
                    for player in ("aplay", "mpg123", "xdg-open"):
                        try:
                            subprocess.Popen([player, tmp])
                            break
                        except FileNotFoundError:
                            continue
            except Exception as e:
                pass
        threading.Thread(target=_play, daemon=True).start()

    def _show_preview(self):
        word = self.word_input.text().strip()
        if not word:
            return
        front_html = self._build_front_html()
        back_html  = self._build_back_html()

        base_css = """
            body { font-family: Arial, sans-serif; font-size: 16px; padding: 20px; color: #222; line-height: 1.6; }
            b { font-weight: bold; }
            u { text-decoration: underline; }
            .side-label { font-size: 11px; font-weight: bold; text-transform: uppercase;
                          letter-spacing: 0.08em; color: #aaa; margin-bottom: 8px; }
            .card-face { background: #fff; border: 1px solid #ddd; border-radius: 8px;
                         padding: 20px; margin-bottom: 16px; }
            .audio-note { font-size: 12px; color: #27ae60; margin-top: 10px;
                          padding: 6px 10px; background: #edfaf3; border-radius: 4px; }
            hr { border: none; border-top: 1px solid #eee; margin: 12px 0; }
        """

        full_html = f"""
        <html><head><style>{base_css}</style></head><body>
        <div class="side-label">FRONT</div>
        <div class="card-face">
            {front_html}
            <div class="audio-note">&#9654; Audio will be generated by AwesomeTTS on this field</div>
        </div>
        <hr>
        <div class="side-label">BACK</div>
        <div class="card-face">
            {back_html}
        </div>
        </body></html>
        """

        sentence = self.txt_sentence.toPlainText().strip()

        dlg = QDialog(self)
        dlg.setWindowTitle(f"Preview — {word}")
        dlg.setMinimumSize(520, 520)
        layout = QVBoxLayout(dlg)

        browser = QTextBrowser()
        browser.setHtml(full_html)
        browser.setOpenExternalLinks(False)
        layout.addWidget(browser)

        btn_row = QHBoxLayout()
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(dlg.accept)

        btn_play = QPushButton("▶ Play audio")
        btn_play.setStyleSheet("QPushButton { color: #8e44ad; border: 1px solid #8e44ad; padding: 6px 18px; border-radius: 5px; }")
        btn_play.clicked.connect(lambda: self._play_preview_audio(sentence))

        btn_add = QPushButton("Add to Anki")
        btn_add.setStyleSheet("QPushButton { background: #27ae60; color: white; padding: 6px 18px; border-radius: 5px; }")
        btn_add.clicked.connect(lambda: (dlg.accept(), self._add_to_anki()))

        btn_row.addWidget(btn_close)
        btn_row.addWidget(btn_play)
        btn_row.addStretch()
        btn_row.addWidget(btn_add)
        layout.addLayout(btn_row)

        dlg.exec()

    def _add_to_anki(self):
        word = self.word_input.text().strip()
        if not word:
            return
        deck_name   = self.cfg_deck.text().strip()
        note_type   = self.cfg_note_type.text().strip()
        field_front = self.cfg_field_front.text().strip()
        field_back  = self.cfg_field_back.text().strip()
        try:
            if not mw.col.decks.by_name(deck_name):
                mw.col.decks.add_normal_deck_with_name(deck_name)
            deck = mw.col.decks.by_name(deck_name)
            model = mw.col.models.by_name(note_type)
            if not model:
                QMessageBox.warning(self, "Note type not found", f"Note type '{note_type}' not found.")
                return
            note = mw.col.new_note(model)
            front_html = self._build_front_html()
            # Generate and attach TTS audio
            sentence = self.txt_sentence.toPlainText().strip()
            audio_tag = ""
            try:
                audio_file = self._generate_audio(sentence, word)
                audio_tag = f"[sound:{audio_file}]"
            except Exception as audio_err:
                QMessageBox.warning(self, "Audio warning",
                    f"Could not generate audio: {audio_err}\nCard will be added without audio.")
            note[field_front] = front_html + (f"<br>{audio_tag}" if audio_tag else "")
            note[field_back]  = self._build_back_html()
            note.tags = ["vocab-miner"]
            mw.col.decks.select(deck["id"])
            note.note_type()["did"] = deck["id"]
            mw.col.add_note(note, deck["id"])
            mw.col.save()
            self.lbl_status.setText("✓ Added to Anki!")
            self.btn_reset.setVisible(True)
            QMessageBox.information(self, "Added!", f'"{word}" added to "{deck_name}".\n\nRemember to run AwesomeTTS on the Front field to generate the audio.')
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _reset_card(self):
        word = self.word_input.text().strip()
        if not word:
            return
        try:
            note_ids = mw.col.find_notes(f'"{word}"')
            if not note_ids:
                QMessageBox.information(self, "Not found", f'"{word}" not found.')
                return
            card_ids = []
            for nid in note_ids:
                note = mw.col.get_note(nid)
                card_ids.extend([c.id for c in note.cards()])
            mw.col.sched.forget_cards(card_ids)
            mw.col.save()
            self.lbl_status.setText("✓ Card reset")
            QMessageBox.information(self, "Reset!", f'Card for "{word}" reset to new.')
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _clear(self):
        self.word_input.clear()
        self.lbl_word.setText("")
        self.lbl_status.setText("")
        self.txt_ipa.clear()
        self.txt_definition.clear()
        self.txt_sentence.clear()
        self.txt_synonyms.clear()
        self.txt_breakdown.clear()
        self.btn_add.setEnabled(False)
        self.btn_regen.setEnabled(False)
        self.btn_preview.setEnabled(False)
        self.btn_reset.setVisible(False)
