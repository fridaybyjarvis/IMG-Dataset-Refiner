"""AI backend integrations for IMG Dataset Refiner.

Encapsulates API calls to Ollama, LM Studio / OpenAI-compatible,
Anthropic Claude, and Google Gemini, plus helpers for API key
fallback, URL normalization, and token estimation.
"""

import os
import sys
import base64
import requests

try:
    import tiktoken
    _TIKTOKEN_ENC = tiktoken.get_encoding("cl100k_base")
    HAS_TIKTOKEN = True
except Exception:
    HAS_TIKTOKEN = False

# Default endpoint URLs (mirrored from lora_manager.py so this module
# is standalone; the main module still owns the user-facing constants).
DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"
DEFAULT_LM_STUDIO_URL = "http://127.0.0.1:1234"
DEFAULT_OPENAI_URL = "https://api.openai.com"
DEFAULT_ANTHROPIC_URL = "https://api.anthropic.com"
DEFAULT_GEMINI_URL = "https://generativelanguage.googleapis.com"


def _env_api_key(kind):
    """Récupère une clé API depuis l'environnement (.env) en fonction du backend.
    Retourne '' si aucune clé n'est trouvée. Permet d'éviter de coller des secrets
    dans l'UI."""
    env_map = {
        "ollama": None,
        "openai_compat": ["OPENAI_API_KEY"],
        "anthropic": ["ANTHROPIC_API_KEY", "CLAUDE_API_KEY"],
        "gemini": ["GEMINI_API_KEY", "GOOGLE_API_KEY"],
    }
    keys = env_map.get(kind)
    if not keys:
        return ""
    for k in keys:
        v = os.environ.get(k)
        if v:
            return v.strip()
    return ""


def _normalize_api_url(api_url, default):
    """Nettoie une URL d'API. Préfixe http:// si manquant, supprime trailing slash."""
    api_url = (str(api_url) if api_url else "").strip()
    if not api_url:
        api_url = default
    if not api_url.startswith("http"):
        api_url = "http://" + api_url
    if api_url.endswith("/"):
        api_url = api_url[:-1]
    return api_url


def _backend_kind(backend):
    """Renvoie une catégorie normalisée pour le backend choisi.
    Catégories : 'ollama', 'openai_compat', 'anthropic', 'gemini'."""
    if not backend:
        return "ollama"
    b = str(backend).lower()
    if "ollama" in b:
        return "ollama"
    if "anthropic" in b or "claude" in b:
        return "anthropic"
    if "gemini" in b or "google" in b:
        return "gemini"
    # Tout le reste (LM Studio, OpenAI, OpenRouter, Groq, etc.) parle OpenAI-compatible.
    return "openai_compat"


def _safe_output_tokens(ctx, default=1024, hard_cap=2048):
    """OpenAI-compatible max_tokens correspond à la sortie, pas à la fenêtre de contexte."""
    try:
        value = int(float(ctx))
    except Exception:
        value = default
    if value <= 0:
        value = default
    return max(64, min(value, hard_cap))


def _safe_context_tokens(ctx, default=4096):
    try:
        value = int(float(ctx))
    except Exception:
        value = default
    return max(1024, value if value > 0 else default)


def estimate_text_tokens(text):
    text = str(text or "")
    if not text:
        return 0
    if HAS_TIKTOKEN:
        try:
            return len(_TIKTOKEN_ENC.encode(text))
        except Exception:
            pass
    # Conservative multilingual fallback close enough for prompt budgeting.
    return max(1, int(len(text) / 3.6))


def _format_http_error(prefix, response, exc):
    detail = ""
    try:
        if response is not None:
            detail = response.text[:800]
    except Exception:
        detail = ""
    if detail:
        return f"{prefix}: {exc} | Réponse serveur: {detail}"
    return f"{prefix}: {exc}"


def _safe_timeout(value):
    """Convertit une valeur de timeout en entier (défaut 180, clampé [15, 1800])."""
    try:
        timeout = int(float(value))
    except Exception:
        timeout = 180
    return max(15, min(timeout, 1800))


def call_ai_api(prompt, model, image_path, api_backend, api_url, temp, ctx, sys_prompt, api_key="", timeout=180):
    """Appelle un backend IA. Supporte Ollama, OpenAI-compatible (LM Studio inclus),
    Anthropic Claude et Google Gemini. api_key est requis pour les services cloud."""
    kind = _backend_kind(api_backend)
    api_key = (api_key or "").strip()
    timeout = _safe_timeout(timeout)
    b64 = None
    if image_path:
        with open(image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")

    # --- OLLAMA (local, sans clé) ---
    if kind == "ollama":
        url = _normalize_api_url(api_url, DEFAULT_OLLAMA_URL)
        if not url.endswith("/api/generate") and not url.endswith("/api/chat"):
            url = url + "/api/generate"
        payload = {"model": model, "prompt": prompt, "stream": False,
                   "options": {"temperature": float(temp), "num_ctx": int(ctx)}}
        if sys_prompt:
            payload["system"] = str(sys_prompt).strip()
        if b64:
            payload["images"] = [b64]
        try:
            response = requests.post(url, json=payload, timeout=timeout)
            response.raise_for_status()
            return response.json().get("response", "").strip()
        except Exception as e:
            return f"Erreur API Ollama: {e}"

    # --- ANTHROPIC CLAUDE ---
    if kind == "anthropic":
        url = _normalize_api_url(api_url, DEFAULT_ANTHROPIC_URL)
        if not url.endswith("/v1/messages"):
            url = url + "/v1/messages"
        api_key = api_key or _env_api_key("anthropic")
        if not api_key:
            return "Erreur API Anthropic: clé API manquante (entrez-la dans Paramètres Avancés API ou définissez ANTHROPIC_API_KEY dans le fichier .env)."
        content = []
        if b64:
            content.append({"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b64}})
        content.append({"type": "text", "text": prompt})
        payload = {
            "model": model or "claude-sonnet-4-5",
            "max_tokens": int(ctx) if int(ctx) > 0 else 4096,
            "temperature": float(temp),
            "messages": [{"role": "user", "content": content}],
        }
        if sys_prompt:
            payload["system"] = str(sys_prompt).strip()
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=timeout)
            response.raise_for_status()
            data = response.json()
            blocks = data.get("content", [])
            return "".join(b.get("text", "") for b in blocks if b.get("type") == "text").strip()
        except Exception as e:
            return f"Erreur API Anthropic: {e}"

    # --- GOOGLE GEMINI ---
    if kind == "gemini":
        url = _normalize_api_url(api_url, DEFAULT_GEMINI_URL)
        api_key = api_key or _env_api_key("gemini")
        if not api_key:
            return "Erreur API Gemini: clé API manquante (entrez-la dans Paramètres Avancés API ou définissez GEMINI_API_KEY dans le fichier .env)."
        model_id = model or "gemini-2.5-flash"
        endpoint = f"{url}/v1beta/models/{model_id}:generateContent"
        parts = [{"text": prompt}]
        if b64:
            parts.insert(0, {"inline_data": {"mime_type": "image/jpeg", "data": b64}})
        payload = {
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {
                "temperature": float(temp),
                "maxOutputTokens": int(ctx) if int(ctx) > 0 else 4096,
            },
        }
        if sys_prompt:
            payload["systemInstruction"] = {"parts": [{"text": str(sys_prompt).strip()}]}
        headers = {
            "x-goog-api-key": api_key,
            "content-type": "application/json",
        }
        try:
            response = requests.post(endpoint, json=payload, headers=headers, timeout=timeout)
            response.raise_for_status()
            data = response.json()
            candidates = data.get("candidates", [])
            if not candidates:
                return f"Erreur API Gemini: réponse vide ({data.get('promptFeedback', '')})"
            parts_out = candidates[0].get("content", {}).get("parts", [])
            return "".join(p.get("text", "") for p in parts_out).strip()
        except Exception as e:
            return f"Erreur API Gemini: {e}"

    # --- OPENAI-COMPATIBLE (OpenAI, LM Studio, OpenRouter, Groq, ...) ---
    if not model:
        return "Erreur API OpenAI-compatible: aucun modèle texte n'est sélectionné."
    url = _normalize_api_url(api_url, DEFAULT_LM_STUDIO_URL)
    for suffix in ("/v1/chat/completions", "/v1", "/api/v1/chat/completions", "/api/v1", "/api/v0/chat/completions", "/api/v0"):
        if url.endswith(suffix):
            url = url[: -len(suffix)]
            break
    if not url.endswith("/v1/chat/completions"):
        url = url + "/v1/chat/completions"
    messages = []
    if sys_prompt:
        messages.append({"role": "system", "content": str(sys_prompt).strip()})
    if b64:
        messages.append({"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
        ]})
    else:
        messages.append({"role": "user", "content": prompt})
    payload = {"model": model, "messages": messages,
               "temperature": float(temp), "max_tokens": _safe_output_tokens(ctx)}
    headers = {"Content-Type": "application/json"}
    effective_key = api_key or _env_api_key("openai_compat")
    if effective_key:
        headers["Authorization"] = f"Bearer {effective_key}"
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=timeout)
        response.raise_for_status()
        return response.json().get("choices", [{}])[0].get("message", {}).get("content", "").strip()
    except requests.HTTPError as e:
        return _format_http_error("Erreur API OpenAI-compatible", getattr(e, "response", response), e)
    except Exception as e:
        return f"Erreur API OpenAI-compatible: {e}"