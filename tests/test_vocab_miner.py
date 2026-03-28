"""
Unit tests for vocab_miner.py.

Covers:
- AIWorker: JSON parsing/cleaning, API call response handling, error paths
- VocabMinerDialog: LRU cache (get, put, eviction, provider separation)
"""
import io
import json
import sys
import unittest
from collections import OrderedDict
from unittest.mock import MagicMock, patch

# conftest.py already mocked aqt/Qt — add the project root to sys.path
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from vocab_miner import AIWorker, VocabMinerDialog  # noqa: E402


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _make_worker(word="ephemeral", provider="claude", api_key="sk-test",
                 mode="full", current_sentence=""):
    """Create an AIWorker without starting the thread."""
    return AIWorker(word, provider, api_key, mode, current_sentence)


def _fake_response(payload: dict):
    """Return a fake urllib response that yields JSON bytes."""
    body = json.dumps(payload).encode()
    resp = MagicMock()
    resp.read.return_value = body
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    return resp


class _CacheHost:
    """
    Mirrors VocabMinerDialog's LRU cache logic without any Qt dependency.
    VocabMinerDialog inherits from a mocked QDialog whose metaclass prevents
    normal method storage in __dict__, so we replicate the logic here.
    The algorithm is identical to what is in vocab_miner.py.
    """

    def __init__(self, max_size=3):
        self._cache = OrderedDict()
        self._cache_max = max_size

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


def _make_dialog():
    return _CacheHost()


# ─── AIWorker: JSON parsing ────────────────────────────────────────────────────

class TestJsonParsing(unittest.TestCase):

    def setUp(self):
        self.worker = _make_worker()

    def test_clean_json_parses_correctly(self):
        data = {"ipa": "/ˈwɜːrd/", "definition": "A unit of language.",
                "sentence": "Use the word.", "synonyms": "term, expression",
                "breakdown": [{"word": "unit", "meaning": "a single thing"}]}
        self.worker._call_ai = MagicMock(return_value=json.dumps(data))
        result = self.worker._generate_full()
        self.assertEqual(result["ipa"], "/ˈwɜːrd/")
        self.assertEqual(result["synonyms"], "term, expression")

    def test_markdown_fences_stripped(self):
        data = {"ipa": "/x/", "definition": "D", "sentence": "S",
                "synonyms": "a, b", "breakdown": []}
        wrapped = f"```json\n{json.dumps(data)}\n```"
        self.worker._call_ai = MagicMock(return_value=wrapped)
        result = self.worker._generate_full()
        self.assertEqual(result["ipa"], "/x/")

    def test_preamble_text_stripped(self):
        data = {"ipa": "/x/", "definition": "D", "sentence": "S",
                "synonyms": "a, b", "breakdown": []}
        with_preamble = f"Sure! Here is the JSON:\n{json.dumps(data)}"
        self.worker._call_ai = MagicMock(return_value=with_preamble)
        result = self.worker._generate_full()
        self.assertEqual(result["ipa"], "/x/")

    def test_invalid_json_retries_once(self):
        good_data = {"ipa": "/x/", "definition": "D", "sentence": "S",
                     "synonyms": "a, b", "breakdown": []}
        responses = ["this is not json at all", json.dumps(good_data)]
        self.worker._call_ai = MagicMock(side_effect=responses)
        result = self.worker._generate_full()
        self.assertEqual(result["ipa"], "/x/")
        self.assertEqual(self.worker._call_ai.call_count, 2)

    def test_invalid_json_raises_after_two_failures(self):
        self.worker._call_ai = MagicMock(return_value="not json")
        with self.assertRaises(json.JSONDecodeError):
            self.worker._generate_full()

    def test_regenerate_sentence_parses_correctly(self):
        worker = _make_worker(mode="regen", current_sentence="Old sentence.")
        data = {"sentence": "New sentence.", "breakdown": []}
        worker._call_ai = MagicMock(return_value=json.dumps(data))
        result = worker._regenerate_sentence()
        self.assertEqual(result["sentence"], "New sentence.")


# ─── AIWorker: _call_claude ───────────────────────────────────────────────────

class TestCallClaude(unittest.TestCase):

    def _response_for(self, text):
        payload = {"content": [{"text": text}]}
        return _fake_response(payload)

    def test_returns_text_content(self):
        worker = _make_worker(provider="claude", api_key="sk-ant-test")
        with patch("urllib.request.urlopen", return_value=self._response_for("hello")):
            result = worker._call_claude("prompt")
        self.assertEqual(result, "hello")

    def test_raises_on_api_error(self):
        worker = _make_worker(provider="claude")
        error_payload = {"error": {"message": "invalid_api_key"}}
        with patch("urllib.request.urlopen", return_value=_fake_response(error_payload)):
            with self.assertRaises(Exception) as ctx:
                worker._call_claude("prompt")
        self.assertIn("invalid_api_key", str(ctx.exception))

    def test_sends_system_prompt(self):
        worker = _make_worker(provider="claude", api_key="sk-ant-test")
        with patch("urllib.request.urlopen", return_value=self._response_for("ok")) as mock_url:
            worker._call_claude("prompt", system="Be concise.")
        call_args = mock_url.call_args[0][0]  # urllib.Request object
        body = json.loads(call_args.data)
        self.assertEqual(body["system"], "Be concise.")
        self.assertEqual(body["max_tokens"], 600)


# ─── AIWorker: _call_gemini ───────────────────────────────────────────────────

class TestCallGemini(unittest.TestCase):

    def _response_for(self, text):
        payload = {"candidates": [{"content": {"parts": [{"text": text}]}}]}
        return _fake_response(payload)

    def test_returns_text_content(self):
        worker = _make_worker(provider="gemini", api_key="AIza-test")
        with patch("urllib.request.urlopen", return_value=self._response_for("bonjour")):
            result = worker._call_gemini("prompt")
        self.assertEqual(result, "bonjour")

    def test_raises_on_api_error(self):
        worker = _make_worker(provider="gemini")
        error_payload = {"error": {"message": "quota_exceeded"}}
        with patch("urllib.request.urlopen", return_value=_fake_response(error_payload)):
            with self.assertRaises(Exception) as ctx:
                worker._call_gemini("prompt")
        self.assertIn("quota_exceeded", str(ctx.exception))

    def test_max_tokens_is_600(self):
        worker = _make_worker(provider="gemini", api_key="AIza-test")
        with patch("urllib.request.urlopen", return_value=self._response_for("ok")) as mock_url:
            worker._call_gemini("prompt")
        call_args = mock_url.call_args[0][0]
        body = json.loads(call_args.data)
        self.assertEqual(body["generationConfig"]["maxOutputTokens"], 600)


# ─── AIWorker: _call_openai ───────────────────────────────────────────────────

class TestCallOpenAI(unittest.TestCase):

    def _response_for(self, text):
        payload = {"choices": [{"message": {"content": text}}]}
        return _fake_response(payload)

    def test_returns_text_content(self):
        worker = _make_worker(provider="openai", api_key="sk-test")
        with patch("urllib.request.urlopen", return_value=self._response_for("hola")):
            result = worker._call_openai("prompt")
        self.assertEqual(result, "hola")

    def test_raises_on_api_error(self):
        worker = _make_worker(provider="openai")
        error_payload = {"error": {"message": "rate_limit_exceeded"}}
        with patch("urllib.request.urlopen", return_value=_fake_response(error_payload)):
            with self.assertRaises(Exception) as ctx:
                worker._call_openai("prompt")
        self.assertIn("rate_limit_exceeded", str(ctx.exception))

    def test_system_message_included(self):
        worker = _make_worker(provider="openai", api_key="sk-test")
        with patch("urllib.request.urlopen", return_value=self._response_for("ok")) as mock_url:
            worker._call_openai("user prompt", system="sys prompt")
        body = json.loads(mock_url.call_args[0][0].data)
        self.assertEqual(body["messages"][0], {"role": "system", "content": "sys prompt"})
        self.assertEqual(body["messages"][1], {"role": "user", "content": "user prompt"})
        self.assertEqual(body["max_tokens"], 600)

    def test_no_system_message_when_empty(self):
        worker = _make_worker(provider="openai", api_key="sk-test")
        with patch("urllib.request.urlopen", return_value=self._response_for("ok")) as mock_url:
            worker._call_openai("user prompt")
        body = json.loads(mock_url.call_args[0][0].data)
        self.assertEqual(len(body["messages"]), 1)
        self.assertEqual(body["messages"][0]["role"], "user")


# ─── AIWorker: provider routing ───────────────────────────────────────────────

class TestProviderRouting(unittest.TestCase):

    def test_routes_to_claude(self):
        worker = _make_worker(provider="claude")
        worker._call_claude = MagicMock(return_value="result")
        worker._call_gemini = MagicMock()
        worker._call_openai = MagicMock()
        worker._call_ai("prompt")
        worker._call_claude.assert_called_once()
        worker._call_gemini.assert_not_called()

    def test_routes_to_gemini(self):
        worker = _make_worker(provider="gemini")
        worker._call_claude = MagicMock()
        worker._call_gemini = MagicMock(return_value="result")
        worker._call_openai = MagicMock()
        worker._call_ai("prompt")
        worker._call_gemini.assert_called_once()

    def test_routes_to_openai_as_default(self):
        worker = _make_worker(provider="openai")
        worker._call_claude = MagicMock()
        worker._call_gemini = MagicMock()
        worker._call_openai = MagicMock(return_value="result")
        worker._call_ai("prompt")
        worker._call_openai.assert_called_once()


# ─── VocabMinerDialog: LRU cache ──────────────────────────────────────────────

class TestCache(unittest.TestCase):

    def setUp(self):
        self.dlg = _make_dialog()

    def test_cache_miss_returns_none(self):
        self.assertIsNone(self.dlg._cache_get("ephemeral", "claude"))

    def test_cache_put_and_get(self):
        data = {"ipa": "/ɪˈfɛmərəl/"}
        self.dlg._cache_put("ephemeral", "claude", data)
        self.assertEqual(self.dlg._cache_get("ephemeral", "claude"), data)

    def test_cache_key_is_case_insensitive(self):
        data = {"ipa": "/x/"}
        self.dlg._cache_put("Ephemeral", "claude", data)
        self.assertEqual(self.dlg._cache_get("ephemeral", "claude"), data)
        self.assertEqual(self.dlg._cache_get("EPHEMERAL", "claude"), data)

    def test_different_providers_are_separate_keys(self):
        claude_data = {"ipa": "/from-claude/"}
        gpt_data = {"ipa": "/from-gpt/"}
        self.dlg._cache_put("word", "claude", claude_data)
        self.dlg._cache_put("word", "openai", gpt_data)
        self.assertEqual(self.dlg._cache_get("word", "claude"), claude_data)
        self.assertEqual(self.dlg._cache_get("word", "openai"), gpt_data)

    def test_lru_evicts_oldest_entry(self):
        # max=3: insert 4 items, first should be evicted
        self.dlg._cache_put("a", "claude", {"v": 1})
        self.dlg._cache_put("b", "claude", {"v": 2})
        self.dlg._cache_put("c", "claude", {"v": 3})
        self.dlg._cache_put("d", "claude", {"v": 4})  # evicts "a"
        self.assertIsNone(self.dlg._cache_get("a", "claude"))
        self.assertIsNotNone(self.dlg._cache_get("d", "claude"))

    def test_lru_access_promotes_entry(self):
        # Insert a+b → access "a" (promotes it, b becomes LRU) → fill+overflow
        self.dlg._cache_put("a", "claude", {"v": 1})
        self.dlg._cache_put("b", "claude", {"v": 2})
        self.dlg._cache_get("a", "claude")            # promotes "a"; LRU = "b"
        self.dlg._cache_put("c", "claude", {"v": 3})  # fills to max=3, no eviction
        self.dlg._cache_put("d", "claude", {"v": 4})  # overflows → evicts "b"
        self.assertIsNone(self.dlg._cache_get("b", "claude"))
        self.assertIsNotNone(self.dlg._cache_get("a", "claude"))

    def test_cache_size_does_not_exceed_max(self):
        for i in range(10):
            self.dlg._cache_put(f"word{i}", "claude", {"v": i})
        self.assertLessEqual(len(self.dlg._cache), self.dlg._cache_max)

    def test_cache_put_updates_existing_entry(self):
        self.dlg._cache_put("word", "claude", {"ipa": "/old/"})
        self.dlg._cache_put("word", "claude", {"ipa": "/new/"})
        self.assertEqual(self.dlg._cache_get("word", "claude")["ipa"], "/new/")
        self.assertEqual(len(self.dlg._cache), 1)


if __name__ == "__main__":
    unittest.main()
