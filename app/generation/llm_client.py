import httpx
from app.errors import AppError


class LLMClient:
    def __init__(self, settings, transport=None):
        self.settings = settings
        self.transport = transport

    @property
    def configured(self):
        return self.settings.llm_provider != 'none' and bool(self.settings.llm_model.strip())

    def generate(self, messages) -> str:
        if not self.configured:
            raise AppError('No LLM configured. Set LLM_PROVIDER, LLM_MODEL and LLM_BASE_URL.', 503)
        settings = self.settings
        base = settings.llm_base_url.rstrip('/')
        headers = {}
        if settings.llm_api_key.get_secret_value():
            headers['Authorization'] = f'Bearer {settings.llm_api_key.get_secret_value()}'
        payload = {'model': settings.llm_model, 'messages': messages, 'stream': False}
        if settings.llm_provider == 'ollama':
            url = base + '/api/chat'
            payload['format'] = 'json'
            payload['options'] = {'temperature': 0, 'num_predict': 700}
        else:
            url = base + '/chat/completions'
            payload.update(temperature=0, max_tokens=700)
        try:
            with httpx.Client(timeout=settings.llm_timeout_seconds, transport=self.transport) as client:
                response = client.post(url, headers=headers, json=payload)
                response.raise_for_status()
            data = response.json()
            text = (data['message']['content'] if settings.llm_provider == 'ollama'
                    else data['choices'][0]['message']['content'])
            if not isinstance(text, str) or not text.strip():
                raise ValueError('Empty model response')
            return text.strip()
        except (httpx.HTTPError, KeyError, IndexError, ValueError, TypeError) as exc:
            raise AppError('The LLM request failed. Check provider availability, model, endpoint and credentials.', 502) from exc
