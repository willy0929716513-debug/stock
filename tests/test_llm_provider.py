import src.data.providers.llm_provider as llm_provider


def test_analyze_returns_empty_when_api_key_missing(monkeypatch):
    monkeypatch.setattr(llm_provider, "GEMINI_API_KEY", "")
    result = llm_provider.analyze_potential_stocks({"AAPL": ["some news"]})
    assert result == []


def test_analyze_returns_empty_when_no_news(monkeypatch):
    monkeypatch.setattr(llm_provider, "GEMINI_API_KEY", "fake-key")
    result = llm_provider.analyze_potential_stocks({"AAPL": []})
    assert result == []


def test_extract_json_text_strips_code_fence():
    raw = '```json\n[{"symbol": "AAPL", "reason": "x", "beneficiary_of": "y"}]\n```'
    assert llm_provider._extract_json_text(raw) == '[{"symbol": "AAPL", "reason": "x", "beneficiary_of": "y"}]'


def test_extract_json_text_passthrough_when_no_fence():
    raw = '[{"symbol": "AAPL"}]'
    assert llm_provider._extract_json_text(raw) == raw


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_analyze_parses_valid_response(monkeypatch):
    monkeypatch.setattr(llm_provider, "GEMINI_API_KEY", "fake-key")

    payload = {
        "candidates": [{
            "finishReason": "STOP",
            "content": {"parts": [{"text": '[{"symbol": "2317.TW", "reason": "受惠AI伺服器需求", "beneficiary_of": "NVDA"}]'}]},
        }]
    }

    monkeypatch.setattr(llm_provider.requests, "post", lambda *a, **k: _FakeResponse(payload))

    result = llm_provider.analyze_potential_stocks({"2317.TW": ["某新聞標題"]})
    assert len(result) == 1
    assert result[0].symbol == "2317.TW"
    assert result[0].beneficiary_of == "NVDA"


def test_analyze_handles_empty_parts_gracefully(monkeypatch):
    monkeypatch.setattr(llm_provider, "GEMINI_API_KEY", "fake-key")

    payload = {"candidates": [{"finishReason": "MAX_TOKENS", "content": {"parts": []}}]}
    monkeypatch.setattr(llm_provider.requests, "post", lambda *a, **k: _FakeResponse(payload))

    result = llm_provider.analyze_potential_stocks({"2317.TW": ["某新聞標題"]})
    assert result == []
