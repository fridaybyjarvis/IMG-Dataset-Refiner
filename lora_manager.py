import gradio as gr
import os
import re
import shutil
import json
import io
import copy
import math
import requests
import base64
import html
import sys
import time
from urllib.parse import unquote, urlparse
import plotly.express as px
import pandas as pd
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from PIL import Image, ImageOps, ImageDraw, ImageFont

try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# Import ImageHash
try:
    import imagehash
    HAS_IMAGEHASH = True
except ImportError:
    HAS_IMAGEHASH = False

# Import tiktoken pour un comptage de tokens CLIP précis
try:
    import tiktoken
    _TIKTOKEN_ENC = tiktoken.get_encoding("cl100k_base")
    HAS_TIKTOKEN = True
except Exception:
    HAS_TIKTOKEN = False

# Import OpenCV pour le Smart Crop
try:
    import cv2
    import numpy as np
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

# Import deep-translator
try:
    from deep_translator import GoogleTranslator
    HAS_TRANSLATOR = True
except ImportError:
    HAS_TRANSLATOR = False

# Import python-dotenv pour le chargement optionnel d'un fichier .env
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
    HAS_DOTENV = True
except ImportError:
    HAS_DOTENV = False

# ==========================================
# CONFIGURATION & DICTIONNAIRES DE LANGUE
# ==========================================

APP_DIR = os.path.dirname(os.path.abspath(__file__))
RECIPES_FILE = os.path.join(APP_DIR, "lora_recipes.json")
AI_RECIPES_FILE = os.path.join(APP_DIR, "ai_recipes.json")
FAVORITES_FILE = os.path.join(APP_DIR, "favorites.json")
LIBRARY_FILE = os.path.join(APP_DIR, "library.json")
AI_SETTINGS_FILE = os.path.join(APP_DIR, "ai_settings.json")
UI_SETTINGS_FILE = os.path.join(APP_DIR, "ui_settings.json")
LANGUAGES_DIR = os.path.join(APP_DIR, "languages")
DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"
DEFAULT_LM_STUDIO_URL = "http://127.0.0.1:1234"
DEFAULT_OPENAI_URL = "https://api.openai.com"
DEFAULT_ANTHROPIC_URL = "https://api.anthropic.com"
DEFAULT_GEMINI_URL = "https://generativelanguage.googleapis.com"
APP_VERSION = "v4.4.6 Pro"
APP_TITLE = f"IMG Dataset Refiner {APP_VERSION}"
VALID_IMAGE_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.webp')
DEFAULT_AI_SETTINGS = {
    "api_backend": "Ollama",
    "vlm_model": "llava",
    "llm_model": "llama3.1",
    "lm_studio_shared_model": "",
    "api_url": DEFAULT_OLLAMA_URL,
    "api_key": "",
    "temperature": 0.7,
    "context": 4096,
    "timeout": 180,
    "system_prompt": "",
}

# i18n dictionaries and helpers live in i18n.py; import them here so the
# rest of lora_manager.py can keep using MSG / UI_T / load_languages / etc.
from i18n import MSG, UI_T, load_languages, get_available_languages, import_language_file

LIVE_TRANSLATION_CACHE = {}
# Contact sheet constants, helpers, and rendering live in contact_sheets.py
# to keep this main module shorter.  All names below are imported back so the
# rest of the codebase (UI build, event handlers) is unaffected.
from contact_sheets import (
    CONTACT_SHEET_PREVIEW_IMAGE_CACHE, CONTACT_SHEET_PREVIEW_IMAGE_CACHE_MAX,
    CONTACT_SHEET_DEFAULTS, CONTACT_SHEET_SOURCE_CHOICES, CONTACT_SHEET_RATIO_CHOICES,
    CONTACT_SHEET_FIT_CHOICES, CONTACT_SHEET_LABEL_CHOICES, CONTACT_SHEET_FORMAT_CHOICES,
    CONTACT_SHEET_RATIO_MODE_CHOICES,
    _safe_int, _safe_float, _normalize_hex_color, _localized_choice,
    _valid_choice_value, _hex_to_rgb,
    _contact_source_choices, _contact_ratio_mode_choices, _contact_ratio_mode_from_setting,
    _contact_fit_choices, _contact_label_choices, _contact_format_choices,
    _contact_sheet_values_and_lang, _contact_sheet_settings_from_inputs,
    _contact_sheet_display_name, _contact_sheet_sort_name, _contact_sheet_source_items,
    _contact_sheet_batches, _contact_sheet_preview_cache_key, _remember_contact_sheet_preview,
    _load_contact_sheet_image, generate_contact_sheet_pil, _contact_sheet_status_text,
    preview_contact_sheets, preview_contact_sheet_live, export_contact_sheets,
)

DEFAULT_UI_SETTINGS = {
    "gallery_columns": 2,
    "contact_sheet_settings": CONTACT_SHEET_DEFAULTS.copy(),
}

CONTRADICTIONS_LOGIQUES = [
    ("day", "night"), ("daytime", "night"),
    ("solo", "multiple girls"), ("solo", "multiple boys"),
    ("indoors", "outdoors"), ("outside", "inside"),
    ("1girl", "1boy"), ("monochrome", "colorful")
]

# CSS theme and custom JS bridge live in frontend_assets.py to keep this
# main module short.  The strings are imported here so launch() and
# app.load(..., js=custom_js) keep working unchanged.
from frontend_assets import css_code, custom_js

# AI backend integrations (Ollama / LM Studio / Anthropic / Gemini)
# live in ai_backends.py.  _safe_timeout is shared because it is used
# both by call_ai_api and by several translation/settings callbacks
# in this module.
from ai_backends import (
    call_ai_api,
    _env_api_key,
    _normalize_api_url,
    _backend_kind,
    _safe_output_tokens,
    _safe_context_tokens,
    estimate_text_tokens,
    _format_http_error,
    _safe_timeout,
)


# ==========================================
# FONCTIONS LOGIQUES PYTHON & UTILITAIRES
# ==========================================

def _dataset_folder_name(item):
    name = str(item.get('rel_path') or item.get('display_name') or item.get('img_name', '')).replace("\\", "/")
    folder = os.path.dirname(name).replace("\\", "/").strip("/")
    return "" if folder in ("", ".") else folder

def _gallery_folder_label(folder, lang):
    return f"📁 {folder or ('Dataset root' if lang == 'EN' else 'Racine du dataset')}"

def get_gallery_items(filtered_dataset, lang):
    items = filtered_dataset or []
    folders = [_dataset_folder_name(item) for item in items]
    has_folders = any(folders)
    gallery_items = []
    previous_folder = None
    for item, folder in zip(items, folders):
        caption = ""
        if has_folders and folder != previous_folder:
            caption = "__IDR_FOLDER__" + _gallery_folder_label(folder, lang) + "__IDR_END__"
        gallery_items.append((item['img_path'], caption))
        previous_folder = folder
    return gallery_items

def extract_all_tags(dataset):
    all_tags = set()
    for item in dataset:
        tags = [t.strip() for t in item['caption'].split(',') if t.strip()]
        all_tags.update(tags)
    return "|".join(sorted(list(all_tags)))

def browse_folder():
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.attributes('-topmost', True)
        root.withdraw()
        folder_path = filedialog.askdirectory(title="Folder")
        root.destroy()
        return folder_path if folder_path else ""
    except Exception as e: return ""

def normalize_dataset_path(raw_path, allow_file_parent=True):
    """Nettoie les chemins collés/déposés : guillemets, file://, ~, variables env.
    Si un fichier image/txt est fourni au lieu d'un dossier, remonte à son parent."""
    p = (raw_path or "").strip()
    if not p:
        return ""
    lines = [line.strip() for line in p.splitlines() if line.strip() and not line.strip().startswith("#")]
    p = lines[0] if lines else p
    p = p.strip().strip('"').strip("'").rstrip(";")
    if p.lower().startswith("file:"):
        try:
            parsed = urlparse(p)
            p = unquote(parsed.path or "")
            if os.name == "nt" and re.match(r"^/[A-Za-z]:/", p):
                p = p[1:]
            p = p.replace("/", os.sep)
        except Exception:
            p = p.replace("file:///", "").replace("file://", "")
    p = os.path.expandvars(os.path.expanduser(p))
    if allow_file_parent and os.path.isfile(p):
        p = os.path.dirname(p)
    return os.path.abspath(p) if p else ""

def render_dataset_drop_zone(lang):
    t = UI_T.get(lang, UI_T.get("FR", {}))
    m = MSG.get(lang, MSG.get("FR", {}))
    title = html.escape(t.get("dataset_drop_title", "Glissez un dossier ici"))
    hint = html.escape(t.get("dataset_drop_hint", "Ou collez un chemin absolu dans le champ ci-dessus."))
    blocked = html.escape(m.get("drop_path_blocked", "⚠️ No usable local path was provided."), quote=True)
    loading = html.escape(m.get("drop_path_loading", "✅ Path detected, loading dataset..."), quote=True)
    searching = html.escape(m.get("drop_path_searching", "🔎 Searching matching local folder..."), quote=True)
    return f"<div id='dataset_drop_zone' class='dataset-drop-zone' data-blocked-msg='{blocked}' data-loading-msg='{loading}' data-searching-msg='{searching}'><strong>{title}</strong><span>{hint}</span></div>"

def _safe_scandir(path):
    try:
        return list(os.scandir(path))
    except Exception:
        return []

def _windows_drive_roots():
    if os.name != "nt":
        return []
    roots = []
    for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        root = f"{letter}:\\"
        if os.path.exists(root):
            roots.append(root)
    return roots

def _pinokio_drop_search_roots():
    """Racines probables Pinokio/ComfyUI, y compris sur les lecteurs externes."""
    bases = []
    if os.name == "nt":
        for drive in _windows_drive_roots():
            bases.append(os.path.join(drive, "Pinokio"))
            bases.append(os.path.join(drive, "pinokio"))
    else:
        bases.append("/pinokio")
    bases.append(os.path.join(os.path.expanduser("~"), "pinokio"))

    rels = (
        os.path.join("ComfyUI.git", "app", "models", "loras"),
        os.path.join("ComfyUI.git", "app", "models"),
        os.path.join("ComfyUI.git", "app"),
        "ComfyUI.git",
        os.path.join("api", "comfyui.git", "app", "models", "loras"),
        os.path.join("api", "comfyui.git", "app", "models"),
        os.path.join("api", "comfyui.git", "app"),
        os.path.join("api", "comfyui.git"),
        "api",
        "",
    )

    roots = []
    seen = set()
    for base in bases:
        for rel in rels:
            path = os.path.join(base, rel) if rel else base
            key = os.path.normcase(os.path.abspath(path))
            if key in seen:
                continue
            seen.add(key)
            if os.path.isdir(path):
                roots.append(path)
    return roots

def _iter_drop_search_roots(root_name=""):
    roots = []
    def add(p):
        if not p:
            return
        try:
            p = os.path.abspath(os.path.expanduser(os.path.expandvars(p)))
        except Exception:
            return
        if os.path.isdir(p) and p not in roots:
            roots.append(p)

    try:
        for fav in load_favorites():
            add(fav)
            add(os.path.dirname(fav))
    except Exception:
        pass

    add(os.getcwd())
    add(os.path.join(os.getcwd(), "dataset"))
    add(os.path.expanduser("~"))
    add(os.environ.get("TEMP"))
    add(os.environ.get("TMP"))
    for pinokio_root in _pinokio_drop_search_roots():
        add(pinokio_root)
    for sub in (
        "pinokio",
        os.path.join("pinokio", "api"),
        os.path.join("pinokio", "api", "comfyui.git"),
        os.path.join("pinokio", "api", "comfyui.git", "app"),
        os.path.join("pinokio", "api", "comfyui.git", "app", "models"),
        os.path.join("pinokio", "api", "comfyui.git", "app", "models", "loras"),
        "Desktop", "Documents", "Downloads", "Pictures",
    ):
        add(os.path.join(os.path.expanduser("~"), sub))
    if os.name == "nt":
        for root in _windows_drive_roots():
            add(root)
    else:
        add("/")

    if root_name:
        direct = []
        for root in list(roots):
            direct.append(os.path.join(root, root_name))
        for p in direct:
            add(p)
    return roots

def _likely_drop_search_roots(root_name=""):
    roots = []
    def add(p):
        if not p:
            return
        try:
            p = os.path.abspath(os.path.expanduser(os.path.expandvars(p)))
        except Exception:
            return
        if os.path.isdir(p) and p not in roots:
            roots.append(p)

    for pinokio_root in _pinokio_drop_search_roots():
        add(pinokio_root)
    for fav in load_favorites():
        add(fav)
        add(os.path.dirname(fav))
    home = os.path.expanduser("~")
    for sub in (
        os.path.join("pinokio", "api", "comfyui.git", "app", "models", "loras"),
        os.path.join("pinokio", "api", "comfyui.git", "app", "models"),
        os.path.join("pinokio", "api"),
        "pinokio",
        "Documents",
        "Downloads",
        "Desktop",
        "Pictures",
    ):
        add(os.path.join(home, sub))
    add(os.getcwd())
    add(os.path.join(os.getcwd(), "dataset"))
    add(os.environ.get("TEMP"))
    add(os.environ.get("TMP"))
    return roots

def _candidate_file_signature(directory, limit=240):
    files = []
    for root, dirnames, filenames in os.walk(directory):
        dirnames[:] = [d for d in dirnames if d.lower() not in {".git", "__pycache__", "venv", "node_modules"}]
        rel_root = os.path.relpath(root, directory)
        for name in filenames:
            rel = name if rel_root == "." else os.path.join(rel_root, name)
            files.append(rel.replace("\\", "/"))
            if len(files) >= limit:
                return files
    return files

def _candidate_file_signature_shallow(directory, limit=240):
    files = []
    entries = _safe_scandir(directory)
    pruned = {".git", "__pycache__", "venv", "node_modules"}
    child_dirs = []
    for entry in entries:
        try:
            if entry.is_file(follow_symlinks=False):
                files.append(entry.name)
            elif entry.is_dir(follow_symlinks=False) and entry.name.lower() not in pruned:
                child_dirs.append(entry)
        except Exception:
            continue
        if len(files) >= limit:
            return files
    for child_dir in child_dirs:
        for child in _safe_scandir(child_dir.path):
            try:
                if child.is_file(follow_symlinks=False):
                    files.append(os.path.join(child_dir.name, child.name).replace("\\", "/"))
            except Exception:
                continue
            if len(files) >= limit:
                return files
    return files

def _score_file_signature(candidate_files, signature_files):
    candidate_lower = {os.path.basename(f).lower() for f in candidate_files}
    candidate_rel = {f.lower().replace("\\", "/") for f in candidate_files}
    sig_rel = {str(f).lower().replace("\\", "/") for f in signature_files if f}
    sig_names = {os.path.basename(f).lower() for f in sig_rel}
    image_names = {n for n in sig_names if n.endswith(VALID_IMAGE_EXTENSIONS)}
    if image_names and not any(n in candidate_lower for n in image_names):
        return 0
    return (len(sig_rel & candidate_rel) * 3) + len(sig_names & candidate_lower)

def _score_drop_candidate(directory, signature_files, recursive=True):
    shallow_score = _score_file_signature(_candidate_file_signature_shallow(directory), signature_files)
    if shallow_score or not recursive:
        return shallow_score
    return _score_file_signature(_candidate_file_signature(directory), signature_files)

def _walk_dirs_limited(root, timeout_at, max_dirs=12000, max_depth=12):
    root = os.path.abspath(root)
    stack = [(root, 0)]
    seen = set()
    scanned = 0
    pruned = {"$recycle.bin", "system volume information", "windows", "program files", "program files (x86)", "programdata", ".git", "venv", "node_modules", "__pycache__"}
    while stack and time.monotonic() <= timeout_at and scanned < max_dirs:
        current, depth = stack.pop()
        key = os.path.normcase(os.path.abspath(current))
        if key in seen:
            continue
        seen.add(key)
        scanned += 1
        yield current
        if depth >= max_depth:
            continue
        for entry in reversed(_safe_scandir(current)):
            try:
                if entry.is_dir(follow_symlinks=False) and entry.name.lower() not in pruned:
                    stack.append((entry.path, depth + 1))
            except Exception:
                pass

def find_dataset_dir_from_drop_signature(signature, timeout_sec=10):
    if not isinstance(signature, dict):
        return ""
    root_name = (signature.get("rootName") or "").strip().strip("\\/")
    signature_files = [f for f in signature.get("files", []) if isinstance(f, str) and f.strip()]
    if not root_name and not signature_files:
        return ""

    start = time.monotonic()
    best_path = ""
    best_score = 0
    seen = set()
    pruned = {"$recycle.bin", "system volume information", "windows", "program files", "program files (x86)", "programdata", ".git", "venv", "node_modules", "__pycache__"}
    expected_name = root_name.lower()
    roots = _iter_drop_search_roots(root_name)
    likely_roots = _likely_drop_search_roots(root_name)

    def consider(path, recursive=True):
        nonlocal best_path, best_score
        if not os.path.isdir(path):
            return
        score = _score_drop_candidate(path, signature_files, recursive=recursive)
        if score > best_score:
            best_score = score
            best_path = path

    needed_score = max(3, min(12, len(signature_files)))

    direct_candidates = []
    if root_name:
        for root in likely_roots + roots:
            direct_candidates.append(os.path.join(root, root_name))
    direct_candidates.extend(likely_roots)
    direct_candidates.extend(roots)

    for root in direct_candidates:
        if time.monotonic() - start > timeout_sec:
            break
        if expected_name and os.path.basename(root).lower() == expected_name:
            consider(root)
            if best_score >= needed_score:
                return best_path
        elif not expected_name:
            consider(root, recursive=False)
            if best_score >= needed_score:
                return best_path

    focused_timeout = start + min(timeout_sec, 7)
    for likely_root in likely_roots:
        for candidate in _walk_dirs_limited(likely_root, focused_timeout, max_dirs=18000, max_depth=14):
            if expected_name and os.path.basename(candidate).lower() != expected_name:
                continue
            consider(candidate, recursive=bool(expected_name))
            if best_score >= needed_score:
                return best_path
        if time.monotonic() > focused_timeout:
            break

    stack = [r for r in reversed(roots) if os.path.isdir(r)]
    scanned = 0
    while stack and time.monotonic() - start <= timeout_sec and scanned < 45000:
        current = stack.pop()
        current_key = os.path.normcase(os.path.abspath(current))
        if current_key in seen:
            continue
        seen.add(current_key)
        scanned += 1
        base = os.path.basename(current).lower()
        if base in pruned:
            continue
        if expected_name and base == expected_name:
            consider(current)
            if best_score >= needed_score:
                return best_path
        elif not expected_name:
            consider(current, recursive=False)
            if best_score >= needed_score:
                return best_path
        for entry in _safe_scandir(current):
            if entry.is_dir(follow_symlinks=False) and entry.name.lower() not in pruned:
                stack.append(entry.path)
    return best_path if best_score >= 3 else ""

def set_dataset_path_from_drop(raw_path, lang):
    m = MSG.get(lang, MSG.get("FR", {}))
    if isinstance(raw_path, str) and raw_path.startswith("__DROP_SIGNATURE__"):
        try:
            signature = json.loads(raw_path[len("__DROP_SIGNATURE__"):])
        except Exception:
            signature = {}
        directory = find_dataset_dir_from_drop_signature(signature)
        if directory:
            msg = m.get("drop_path_detected", "✅ Path detected: {path}").format(path=directory)
            gr.Info(msg)
            return gr.update(value=directory), msg, f"__RESOLVED_PATH__{directory}"
        msg = m.get("drop_path_not_resolved", "⚠️ Could not locate this dropped folder on local disks. Paste its path or add it to Favorites once.")
        gr.Warning(msg)
        return gr.update(), msg, ""
    if raw_path == "__DROP_PATH_BLOCKED__":
        msg = m.get(
            "drop_path_blocked",
            "⚠️ Browser security did not expose a usable local folder path. Paste the folder path or use Browse.",
        )
        gr.Warning(msg)
        return gr.update(), msg, ""
    directory = normalize_dataset_path(raw_path)
    if directory and os.path.isdir(directory):
        msg = m.get("drop_path_detected", "✅ Path detected: {path}").format(path=directory)
        gr.Info(msg)
        return gr.update(value=directory), msg, f"__RESOLVED_PATH__{directory}"
    msg = m.get("folder_not_found", "Folder not found.")
    gr.Warning(msg)
    return gr.update(value=directory), msg, ""

def natural_sort_key(s):
    """Clé de tri 'naturel' (style Windows Explorer) : 'img2' < 'img10'.
    Insensible à la casse. Découpe la chaîne en segments alphabétiques
    et numériques, et trie chaque segment dans son type natif."""
    if not isinstance(s, str):
        s = str(s)
    parts = re.split(r'(\d+)', s.lower())
    out = []
    for p in parts:
        if p.isdigit():
            out.append((1, int(p)))
        else:
            out.append((0, p))
    return out

def selection_summary_html(selected_count, filtered_count, total_count, lang):
    selected_count = int(selected_count or 0)
    filtered_count = int(filtered_count or 0)
    total_count = int(total_count or 0)
    if lang == "EN":
        text = f"✅ {selected_count} selected · {filtered_count} filtered · {total_count} total"
    else:
        text = f"✅ {selected_count} sélectionnées · {filtered_count} filtrées · {total_count} au total"
    return f"<div class='selection-status-pill'>{text}</div>"

def _reindex_dataset(dataset):
    for idx, item in enumerate(dataset or []):
        item['id'] = idx
    return dataset

def _refresh_duplicate_mapping_ids(mapping, dataset):
    if not mapping:
        return {}
    by_path = {item.get('img_path'): item.get('id') for item in dataset or []}
    refreshed = {}
    for name, data in list(mapping.items()):
        id_a = by_path.get(data.get("imgA"))
        id_b = by_path.get(data.get("imgB"))
        if id_a is None or id_b is None:
            continue
        data = dict(data)
        data["idA"] = id_a
        data["idB"] = id_b
        refreshed[name] = data
    return refreshed

def sort_dataset(dataset, order, lang, msg_no_sel, all_tags_str=""):
    if not dataset: return [], [], [], "", "{}", -1
    reverse = (order == "Z-A")
    dataset = sorted(dataset, key=lambda x: natural_sort_key(x['img_name']), reverse=reverse)
    _reindex_dataset(dataset)
        
    gal_items = get_gallery_items(dataset, lang)
    success_msg = MSG[lang].get("images_loaded", "{count} images loaded.").format(count=len(dataset))
    gr.Info(success_msg)
    return dataset, dataset, [], success_msg, gal_items, [], selection_summary_html(0, len(dataset), len(dataset), lang), "{}", all_tags_str or extract_all_tags(dataset), -1

def _iter_dataset_image_files(directory, include_subfolders=False):
    valid_extensions = ('.png', '.jpg', '.jpeg', '.webp')
    if include_subfolders:
        pruned = {".git", "__pycache__", "venv", "node_modules"}
        for root, dirnames, filenames in os.walk(directory):
            dirnames[:] = sorted(
                [d for d in dirnames if d.lower() not in pruned],
                key=natural_sort_key,
            )
            for filename in sorted(filenames, key=natural_sort_key):
                if filename.lower().endswith(valid_extensions):
                    yield os.path.join(root, filename)
    else:
        for filename in sorted(os.listdir(directory), key=natural_sort_key):
            img_path = os.path.join(directory, filename)
            if os.path.isfile(img_path) and filename.lower().endswith(valid_extensions):
                yield img_path

def load_dataset(directory, sort_order, lang, include_subfolders=False):
    msg_no_sel = MSG[lang].get("no_selection", "Aucune sélection active.")
    # Accepter aussi bien les chemins absolus que relatifs ; normaliser.
    directory = normalize_dataset_path(directory)
    if not directory or not os.path.isdir(directory):
        return [], [], [], MSG[lang].get("folder_not_found", "Dossier introuvable."), [], [], selection_summary_html(0, 0, 0, lang), "{}", "", -1
    dataset = []
    idx = 0
    for img_path in _iter_dataset_image_files(directory, include_subfolders):
        rel_name = os.path.relpath(img_path, directory).replace("\\", "/")
        img_name = rel_name if include_subfolders else os.path.basename(img_path)
        txt_path = os.path.splitext(img_path)[0] + '.txt'
        caption = ""
        if os.path.exists(txt_path):
            with open(txt_path, 'r', encoding='utf-8') as f: caption = f.read().strip()
        else:
            with open(txt_path, 'w', encoding='utf-8') as f: pass
        dataset.append({'id': idx, 'img_name': img_name, 'img_path': img_path, 'txt_path': txt_path, 'caption': caption})
        idx += 1
    if not dataset:
        msg = MSG[lang].get("no_images_found", "No supported images found in this folder.")
        gr.Warning(msg)
        return [], [], [], msg, [], [], selection_summary_html(0, 0, 0, lang), "{}", "", -1
    save_recent_path(directory)
    return sort_dataset(dataset, sort_order, lang, msg_no_sel, extract_all_tags(dataset))

def filter_gallery(dataset, search_text, sort_order, lang):
    if not dataset: return [], [], [], selection_summary_html(0, 0, 0, lang), "{}", -1
    filtered = dataset
    if search_text:
        tags = [t.strip().lower() for t in search_text.split(',') if t.strip()]
        if len(tags) > 1:
            filtered = [item for item in dataset if all(tag in item['caption'].lower() for tag in tags)]
        else:
            filtered = [item for item in dataset if search_text.lower() in item['caption'].lower()]
    reverse = (sort_order == "Z-A")
    filtered = sorted(filtered, key=lambda x: natural_sort_key(x['img_name']), reverse=reverse)
    return filtered, get_gallery_items(filtered, lang), [], selection_summary_html(0, len(filtered), len(dataset), lang), "{}", -1

def get_highlighted_html(caption, tracked_words_str):
    if not caption: return "<div style='padding:10px; background:var(--bg-color); border-radius:5px;'></div>"
    html_caption = caption
    if tracked_words_str:
        tracked_words = [w.split(':')[0].strip() for w in tracked_words_str.split(',') if w.strip()]
        tracked_words = sorted([w for w in tracked_words if w], key=len, reverse=True)
        if tracked_words:
            escaped_words = [re.escape(w) for w in tracked_words]
            pattern = re.compile(r'(?i)\b(' + '|'.join(escaped_words) + r')\b')
            html_caption = pattern.sub(r'<mark style="background-color: #ffcc00; color: #000; font-weight: bold; padding: 2px 4px; border-radius: 4px; box-shadow: 0 0 5px rgba(255, 204, 0, 0.5);">\1</mark>', html_caption)
    return f"<div style='padding:15px; border:1px solid #555; background-color: #222; border-radius:8px; line-height:1.6; font-size:1.1em;'>{html_caption}</div>"

def update_word_count(text, lang):
    if not text: return MSG[lang].get("0_words", "0 words")
    words = len(text.split())
    if HAS_TIKTOKEN:
        try:
            tokens = len(_TIKTOKEN_ENC.encode(text))
        except Exception:
            tokens = int(words * 1.3)
    else:
        tokens = int(words * 1.3)
    color = "#ff4444" if tokens > 225 else "#44ff44"
    warning = MSG[lang].get("truncation_risk", "") if tokens > 225 else ""
    return f"<div style='color:{color}; font-weight:bold;'>{words} {MSG[lang].get('word_count','words')} (~{tokens} {MSG[lang].get('token_count','tokens')}){warning}</div>"

def get_updated_viewer_data(filtered_dataset, idx, tracked_words, lang):
    if not filtered_dataset or idx < 0 or idx >= len(filtered_dataset): 
        return "", get_highlighted_html("", tracked_words), update_word_count("", lang)
    item = filtered_dataset[idx]
    return item['caption'], get_highlighted_html(item['caption'], tracked_words), update_word_count(item['caption'], lang)

def update_viewer(filtered_dataset, idx, tracked_words, lang):
    if not filtered_dataset or idx < 0 or idx >= len(filtered_dataset): 
        return None, "", "", MSG[lang].get("0_words", "0 words"), -1, MSG[lang].get("no_img_sel", "No image")
    item = filtered_dataset[idx]
    msg = MSG[lang].get("viewing_img", "Viewing: {name}").format(name=item['img_name'])
    return item['img_path'], get_highlighted_html(item['caption'], tracked_words), item['caption'], update_word_count(item['caption'], lang), idx, msg

def show_first_after_dataset_load(filtered_dataset, tracked_words, lang):
    """Affiche directement la première image après un chargement de dataset."""
    return update_viewer(filtered_dataset, 0 if filtered_dataset else -1, tracked_words, lang)


def silent_save(dataset, filtered_dataset, idx, new_caption, lang):
    if not filtered_dataset or idx < 0 or idx >= len(filtered_dataset): return
    item_filtered = filtered_dataset[idx]
    if item_filtered['caption'] == new_caption: return 
    real_id = item_filtered['id']
    if os.path.exists(item_filtered['txt_path']) and os.path.getsize(item_filtered['txt_path']) > 0: 
        shutil.copy2(item_filtered['txt_path'], item_filtered['txt_path'] + ".bak")
    item_filtered['caption'] = new_caption
    dataset[real_id]['caption'] = new_caption
    with open(item_filtered['txt_path'], 'w', encoding='utf-8') as f: f.write(new_caption)

def clear_selection(dataset, filtered_dataset, lang):
    return [], selection_summary_html(0, len(filtered_dataset or []), len(dataset or []), lang), "{}"

def handle_sync(payload_str, dataset, filtered_dataset, old_idx, old_caption, tracked_words, lang):
    silent_save(dataset, filtered_dataset, old_idx, old_caption, lang)
    try:
        data = json.loads(payload_str)
        sel_js = data.get("selected", [])
        view_idx = int(data.get("viewIndex", 0))
    except:
        sel_js = []; view_idx = 0
    real_ids = [filtered_dataset[i]['id'] for i in sel_js if 0 <= i < len(filtered_dataset)] if filtered_dataset else []
    sel_text = selection_summary_html(len(real_ids), len(filtered_dataset or []), len(dataset or []), lang)
    img_path, hl_html, cap, wc, c_idx, v_status = update_viewer(filtered_dataset, view_idx, tracked_words, lang)
    return dataset, filtered_dataset, real_ids, sel_text, img_path, hl_html, cap, wc, c_idx, v_status, extract_all_tags(dataset)

def save_all_captions(dataset):
    for item in dataset:
        with open(item['txt_path'], 'w', encoding='utf-8') as f: f.write(item['caption'])

def save_single_caption(dataset, filtered_dataset, idx, new_caption, lang):
    if not filtered_dataset or idx < 0 or idx >= len(filtered_dataset): 
        return dataset, filtered_dataset, MSG[lang].get("error", "Error")
    item_filtered = filtered_dataset[idx]
    real_id = item_filtered['id']
    if os.path.exists(item_filtered['txt_path']) and os.path.getsize(item_filtered['txt_path']) > 0: 
        shutil.copy2(item_filtered['txt_path'], item_filtered['txt_path'] + ".bak")
    item_filtered['caption'] = new_caption
    dataset[real_id]['caption'] = new_caption
    with open(item_filtered['txt_path'], 'w', encoding='utf-8') as f: f.write(new_caption)
    msg_success = MSG[lang].get("saved", "Saved: {name}").format(name=item_filtered['img_name'])
    gr.Info(msg_success)
    return dataset, filtered_dataset, msg_success

def nav_prev(dataset, filtered_dataset, idx, current_caption, tracked_words, lang):
    silent_save(dataset, filtered_dataset, idx, current_caption, lang)
    if not filtered_dataset: return dataset, filtered_dataset, None, "", "", MSG[lang].get("0_words", "0 words"), -1, ""
    new_idx = (idx - 1) % len(filtered_dataset) if idx >= 0 else 0
    res = update_viewer(filtered_dataset, new_idx, tracked_words, lang)
    return (dataset, filtered_dataset) + res

def nav_next(dataset, filtered_dataset, idx, current_caption, tracked_words, lang):
    silent_save(dataset, filtered_dataset, idx, current_caption, lang)
    if not filtered_dataset: return dataset, filtered_dataset, None, "", "", MSG[lang].get("0_words", "0 words"), -1, ""
    new_idx = (idx + 1) % len(filtered_dataset) if idx >= 0 else 0
    res = update_viewer(filtered_dataset, new_idx, tracked_words, lang)
    return (dataset, filtered_dataset) + res

def delete_current_image(dataset, filtered_dataset, idx, tracked_words, lang):
    if not filtered_dataset or idx < 0 or idx >= len(filtered_dataset):
        msg = MSG[lang].get("no_img_sel", "No image selected.")
        return (
            dataset, filtered_dataset, get_gallery_items(filtered_dataset, lang),
            None, get_highlighted_html("", tracked_words), "", update_word_count("", lang),
            msg, -1, [], selection_summary_html(0, len(filtered_dataset or []), len(dataset or []), lang),
            "{}", extract_all_tags(dataset)
        )
    item_to_del = filtered_dataset[idx]
    try:
        if os.path.exists(item_to_del['img_path']):
            os.remove(item_to_del['img_path'])
        if os.path.exists(item_to_del['txt_path']):
            os.remove(item_to_del['txt_path'])
    except Exception as e:
        msg = f"Impossible de supprimer: {e}"
        gr.Warning(msg)
        img_path, hl_html, cap, wc, c_idx, v_status = update_viewer(filtered_dataset, idx, tracked_words, lang)
        return (
            dataset, filtered_dataset, get_gallery_items(filtered_dataset, lang),
            img_path, hl_html, cap, wc, msg, c_idx, [], selection_summary_html(0, len(filtered_dataset or []), len(dataset or []), lang),
            "{}", extract_all_tags(dataset)
        )

    deleted_id = item_to_del.get('id')
    dataset = [x for x in dataset if x.get('id') != deleted_id]
    filtered_dataset = [x for x in filtered_dataset if x.get('id') != deleted_id]
    _reindex_dataset(dataset)
    id_by_path = {item.get('img_path'): item.get('id') for item in dataset}
    for item in filtered_dataset:
        if item.get('img_path') in id_by_path:
            item['id'] = id_by_path[item.get('img_path')]
    new_idx = min(idx, len(filtered_dataset) - 1)
    img_path, hl_html, cap, wc, c_idx, v_status = update_viewer(filtered_dataset, new_idx, tracked_words, lang)
    msg = f"🗑️ Supprimé : {item_to_del.get('img_name', '')}"
    gr.Info(msg)
    return (
        dataset, filtered_dataset, get_gallery_items(filtered_dataset, lang),
        img_path, hl_html, cap, wc, msg if not v_status else v_status,
        c_idx, [], selection_summary_html(0, len(filtered_dataset or []), len(dataset or []), lang),
        "{}", extract_all_tags(dataset)
    )

def undo_last_action(dataset, history, current_idx, tracked_words, lang):
    if not history: return dataset, dataset, MSG[lang].get("nothing_to_undo", "Nothing"), "", get_highlighted_html("", tracked_words), update_word_count("", lang)
    dataset = copy.deepcopy(history)
    save_all_captions(dataset)
    gr.Warning(MSG[lang].get("undo_success", "Undone"))
    cap, hl_html, wc = get_updated_viewer_data(dataset, current_idx, tracked_words, lang)
    return dataset, dataset, MSG[lang].get("undo_success", "Undone"), cap, hl_html, wc

def load_recipes():
    if os.path.exists(RECIPES_FILE):
        with open(RECIPES_FILE, 'r') as f: return json.load(f)
    return {"Default": "1girl, solo, looking at viewer"}

def save_recipe(name, words):
    if not name: return gr.update(), "Empty name"
    recipes = load_recipes()
    recipes[name] = words
    with open(RECIPES_FILE, 'w') as f: json.dump(recipes, f)
    gr.Info("✅ Recette sauvegardée avec succès !")
    return gr.update(choices=list(recipes.keys()), value=name), "✅ Saved"

def apply_recipe(name):
    return load_recipes().get(name, "")

def delete_recipe(name, lang):
    """Supprime une recette par son nom. Renvoie un dropdown mis à jour."""
    m = MSG.get(lang, MSG.get("FR", {}))
    if not name:
        return gr.update(), m.get("recipe_not_found", "Recipe not found")
    recipes = load_recipes()
    if name not in recipes:
        return gr.update(choices=list(recipes.keys())), m.get("recipe_not_found", "Recipe not found")
    del recipes[name]
    with open(RECIPES_FILE, 'w', encoding='utf-8') as f:
        json.dump(recipes, f, ensure_ascii=False, indent=2)
    msg = m.get("recipe_deleted", "🗑️ Recipe '{name}' deleted.").format(name=name)
    gr.Info(msg)
    choices = list(recipes.keys())
    new_value = choices[0] if choices else None
    return gr.update(choices=choices, value=new_value), msg

# ==========================================
# ⭐ FAVORIS DE DATASETS (chemins persistants)
# ==========================================

def load_favorites():
    """Charge la liste des chemins favoris depuis favorites.json. Renvoie une liste."""
    if not os.path.exists(FAVORITES_FILE):
        return []
    try:
        with open(FAVORITES_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, list):
            return [p for p in data if isinstance(p, str) and p]
        return []
    except Exception:
        return []

def save_favorites(favs):
    """Sauvegarde la liste des chemins favoris."""
    try:
        with open(FAVORITES_FILE, 'w', encoding='utf-8') as f:
            json.dump(favs, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"⚠️ Impossible de sauver favorites.json : {e}")
        return False

def add_favorite(current_path, lang):
    """Ajoute le chemin courant aux favoris."""
    m = MSG.get(lang, MSG.get("FR", {}))
    p = normalize_dataset_path(current_path)
    if not p:
        gr.Warning(m.get("fav_empty_path", "⚠️ Please enter a folder path first."))
        return gr.update(), m.get("fav_empty_path", "⚠️ Please enter a folder path first.")
    if not os.path.isdir(p):
        msg = m.get("folder_not_found", "❌ Folder not found.")
        gr.Warning(msg)
        return gr.update(choices=load_favorites()), msg
    favs = load_favorites()
    if p in favs:
        gr.Info(m.get("fav_already", "ℹ️ Already a favorite."))
        return gr.update(choices=favs, value=p), m.get("fav_already", "ℹ️ Already a favorite.")
    favs.append(p)
    save_favorites(favs)
    msg = m.get("fav_added", "⭐ Favorite added: {path}").format(path=p)
    gr.Info(msg)
    return gr.update(choices=favs, value=p), msg

def remove_favorite(current_path, lang):
    """Retire le chemin sélectionné des favoris."""
    m = MSG.get(lang, MSG.get("FR", {}))
    p = (current_path or "").strip()
    favs = load_favorites()
    if p and p in favs:
        favs.remove(p)
        save_favorites(favs)
        msg = m.get("fav_removed", "🗑️ Favorite removed.")
        gr.Info(msg)
        new_val = favs[0] if favs else None
        return gr.update(choices=favs, value=new_val), msg
    return gr.update(choices=favs), m.get("fav_empty_path", "")

def pick_favorite(selected, lang):
    """Sélectionne un favori : renvoie le chemin pour le champ dir_input."""
    return selected or ""

def load_favorite_dataset(selected, sort_order, lang, include_subfolders=False):
    """Charge directement le dataset choisi dans les favoris."""
    path = selected or ""
    return (gr.update(value=path),) + tuple(load_dataset(path, sort_order, lang, include_subfolders))

# ==========================================
# 🤖 PARAMÈTRES IA PERSISTANTS
# ==========================================

def load_ai_settings():
    """Charge les réglages IA locaux en gardant des valeurs sûres si le JSON manque."""
    settings = DEFAULT_AI_SETTINGS.copy()
    if not os.path.exists(AI_SETTINGS_FILE):
        return settings
    try:
        with open(AI_SETTINGS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, dict):
            for key in settings:
                if key in data:
                    settings[key] = data[key]
    except Exception as e:
        print(f"⚠️ Impossible de lire {AI_SETTINGS_FILE} : {e}")
    return settings

def load_ai_settings_for_ui():
    settings = load_ai_settings()
    return (
        settings.get("api_backend", DEFAULT_AI_SETTINGS["api_backend"]),
        settings.get("vlm_model", DEFAULT_AI_SETTINGS["vlm_model"]),
        settings.get("llm_model", DEFAULT_AI_SETTINGS["llm_model"]),
        settings.get("api_url", DEFAULT_AI_SETTINGS["api_url"]),
        settings.get("api_key", DEFAULT_AI_SETTINGS["api_key"]),
        settings.get("temperature", DEFAULT_AI_SETTINGS["temperature"]),
        settings.get("context", DEFAULT_AI_SETTINGS["context"]),
        settings.get("timeout", DEFAULT_AI_SETTINGS["timeout"]),
        settings.get("system_prompt", DEFAULT_AI_SETTINGS["system_prompt"]),
    )

def _write_ai_settings(settings):
    try:
        with open(AI_SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ Impossible de sauver {AI_SETTINGS_FILE} : {e}")

def save_ai_settings(api_backend, vlm_model, llm_model, api_url, api_key, temperature, context, timeout, system_prompt):
    settings = load_ai_settings()
    settings.update({
        "api_backend": api_backend or DEFAULT_AI_SETTINGS["api_backend"],
        "vlm_model": vlm_model or "",
        "llm_model": llm_model or "",
        "api_url": api_url or "",
        "api_key": api_key or "",
        "temperature": float(temperature) if temperature not in (None, "") else DEFAULT_AI_SETTINGS["temperature"],
        "context": int(float(context)) if context not in (None, "") else DEFAULT_AI_SETTINGS["context"],
        "timeout": _safe_timeout(timeout),
        "system_prompt": system_prompt or "",
    })
    _write_ai_settings(settings)

def load_ui_settings():
    settings = DEFAULT_UI_SETTINGS.copy()
    if not os.path.exists(UI_SETTINGS_FILE):
        return settings
    try:
        with open(UI_SETTINGS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, dict):
            settings.update({k: data[k] for k in settings if k in data})
    except Exception as e:
        print(f"⚠️ Impossible de lire {UI_SETTINGS_FILE} : {e}")
    return settings

def save_ui_settings_value(key, value):
    settings = load_ui_settings()
    settings[key] = value
    try:
        with open(UI_SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ Impossible de sauver {UI_SETTINGS_FILE} : {e}")

def update_gallery_columns(cols):
    try:
        cols = int(cols)
    except Exception:
        cols = DEFAULT_UI_SETTINGS["gallery_columns"]
    cols = max(1, min(6, cols))
    save_ui_settings_value("gallery_columns", cols)
    return gr.update(columns=cols)

def load_gallery_columns_for_ui():
    cols = load_ui_settings().get("gallery_columns", DEFAULT_UI_SETTINGS["gallery_columns"])
    try:
        cols = int(cols)
    except Exception:
        cols = DEFAULT_UI_SETTINGS["gallery_columns"]
    cols = max(1, min(6, cols))
    return gr.update(value=cols), gr.update(columns=cols)

def load_contact_sheet_settings():
    saved = load_ui_settings().get("contact_sheet_settings", {})
    settings = CONTACT_SHEET_DEFAULTS.copy()
    if isinstance(saved, dict):
        for key in settings:
            if key in saved:
                settings[key] = saved[key]
    return settings

def _safe_float(value, default, min_value=None, max_value=None):
    try:
        value = float(value)
    except Exception:
        value = default
    if min_value is not None:
        value = max(min_value, value)
    if max_value is not None:
        value = min(max_value, value)
    return value

def _normalize_hex_color(value, default="#00ff00"):
    value = str(value or "").strip()
    if re.fullmatch(r"#?[0-9a-fA-F]{6}", value):
        return value if value.startswith("#") else f"#{value}"
    return default

def _localized_choice(label, value):
    return (label, value)

def _valid_choice_value(value, valid_values, default):
    return value if value in valid_values else default

def _contact_source_choices(lang):
    t = UI_T.get(lang, UI_T.get("FR", {}))
    return [
        _localized_choice(t.get("contact_source_filtered", "Galerie filtrée"), "Galerie filtrée"),
        _localized_choice(t.get("contact_source_multi", "Sélection multi"), "Sélection multi"),
    ]

def _contact_ratio_mode_choices(lang):
    t = UI_T.get(lang, UI_T.get("FR", {}))
    return [
        _localized_choice(t.get("contact_ratio_original", "Original (mélange)"), "Original (mélange)"),
        _localized_choice(t.get("contact_ratio_square", "Tous carrés 1:1"), "Tous carrés 1:1"),
        _localized_choice(t.get("contact_ratio_autofit", "Auto-fit (remplir)"), "Auto-fit (remplir)"),
    ]

def _contact_ratio_mode_from_setting(ratio):
    ratio = str(ratio or "").lower()
    if "variable" in ratio:
        return "Original (mélange)"
    if "1:1" in ratio:
        return "Tous carrés 1:1"
    return "Auto-fit (remplir)"

def _contact_fit_choices(lang):
    t = UI_T.get(lang, UI_T.get("FR", {}))
    return [
        _localized_choice(t.get("contact_fit_crop", "Remplir et Couper (Crop)"), "Remplir et Couper (Crop)"),
        _localized_choice(t.get("contact_fit_pad", "Ajuster avec bandes (Pad)"), "Ajuster avec bandes (Pad)"),
    ]

def _contact_label_choices(lang):
    t = UI_T.get(lang, UI_T.get("FR", {}))
    return [
        _localized_choice(t.get("contact_label_none", "Aucun"), "Aucun"),
        _localized_choice(t.get("contact_label_numbering", "Numérotation (1, 2, 3...)"), "Numérotation (1, 2, 3...)"),
        _localized_choice(t.get("contact_label_filename", "Nom du fichier"), "Nom du fichier"),
        _localized_choice(t.get("contact_label_captions", "Captions (1ère ligne)"), "Captions (1ère ligne)"),
    ]

def _contact_format_choices(lang):
    t = UI_T.get(lang, UI_T.get("FR", {}))
    return [
        _localized_choice(t.get("contact_export_format_jpeg", "JPEG"), "JPEG"),
        _localized_choice(t.get("contact_export_format_png", "PNG"), "PNG"),
        _localized_choice(t.get("contact_export_format_webp", "WEBP"), "WEBP"),
    ]

def _contact_sheet_values_and_lang(values):
    values = list(values)
    if values and str(values[-1]) in UI_T:
        return values[:-1], str(values[-1])
    return values, "FR"

def _hex_to_rgb(value):
    value = _normalize_hex_color(value).lstrip("#")
    return tuple(int(value[i:i+2], 16) for i in (0, 2, 4))

def _contact_sheet_settings_from_inputs(
    source_mode, output_width, flexible_cols, images_per_row, spacing, margin, background,
    ratio_mode, fit_mode, sort_alpha, label_mode, font_size, label_opacity,
    limit_enabled, images_per_sheet, continue_numbering, output_dir,
    filename_prefix, export_format, quality, resize_final,
):
    defaults = CONTACT_SHEET_DEFAULTS
    # Mapper le mode radio simple vers la valeur interne
    ratio_map = {
        "Original (mélange)": "Hauteur variable (Original)",
        "Tous carrés 1:1": "Carré (1:1)",
        "Auto-fit (remplir)": "Carré (1:1)",  # Voir note ci-dessous
    }
    ratio = ratio_map.get(ratio_mode, defaults["ratio"])
    # Note: "Auto-fit (remplir)" utilise le même ratio 1:1 que "Tous carrés"
    # La différence se fait via fit_mode (Crop vs Pad)
    if ratio not in CONTACT_SHEET_RATIO_CHOICES:
        ratio = defaults["ratio"]
    fit_mode = fit_mode if fit_mode in CONTACT_SHEET_FIT_CHOICES else defaults["fit_mode"]
    label_mode = label_mode if label_mode in CONTACT_SHEET_LABEL_CHOICES else defaults["label_mode"]
    export_format = export_format if export_format in CONTACT_SHEET_FORMAT_CHOICES else defaults["export_format"]
    source_mode = source_mode if source_mode in CONTACT_SHEET_SOURCE_CHOICES else defaults["source_mode"]

    output_width_safe = _safe_int(output_width, defaults["output_width"], 256, 12000)
    spacing_safe = _safe_int(spacing, defaults["spacing"], 0, 1000)
    margin_safe = _safe_int(margin, defaults["margin"], 0, 2000)

    # Auto-calculer les colonnes si flexible_cols est activé
    if flexible_cols:
        available_width = output_width_safe - (2 * margin_safe)
        min_col_width = 100
        cols = max(1, min(24, (available_width + spacing_safe) // (min_col_width + spacing_safe)))
        images_per_row = cols
    else:
        images_per_row = _safe_int(images_per_row, defaults["images_per_row"], 1, 40)

    return {
        "source_mode": source_mode,
        "output_width": output_width_safe,
        "images_per_row": images_per_row,
        "spacing": spacing_safe,
        "margin": margin_safe,
        "background": _normalize_hex_color(background, defaults["background"]),
        "ratio": ratio,
        "fit_mode": fit_mode,
        "sort_alpha": bool(sort_alpha),
        "label_mode": label_mode,
        "font_size": _safe_int(font_size, defaults["font_size"], 6, 500),
        "label_opacity": _safe_float(label_opacity, defaults["label_opacity"], 0, 100),
        "limit_enabled": bool(limit_enabled),
        "images_per_sheet": _safe_int(images_per_sheet, defaults["images_per_sheet"], 1, 1000),
        "continue_numbering": bool(continue_numbering),
        "output_dir": str(output_dir or "").strip(),
        "filename_prefix": re.sub(r'[<>:"/\\|?*]+', "_", str(filename_prefix or defaults["filename_prefix"]).strip()) or defaults["filename_prefix"],
        "export_format": export_format,
        "quality": _safe_int(quality, defaults["quality"], 1, 100),
        "resize_final": _safe_int(resize_final, 100, 25, 200),
    }

def save_contact_sheet_settings(*values):
    values, lang = _contact_sheet_values_and_lang(values)
    t = UI_T.get(lang, UI_T.get("FR", {}))
    settings = _contact_sheet_settings_from_inputs(*values)
    save_ui_settings_value("contact_sheet_settings", settings)
    info = t.get("contact_status_saved_info", "✅ Réglages de planche sauvegardés.")
    gr.Info(info)
    return t.get("contact_status_saved", "✅ Réglages sauvegardés pour les prochaines sessions.")

def get_gradio_allowed_paths():
    """Autorise Gradio à servir les images depuis les lecteurs locaux.
    Sans cela, les chemins hors dossier de l'app sont chargés côté Python mais bloqués côté galerie."""
    paths = {os.path.abspath(os.getcwd())}
    if os.name == "nt":
        for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            root = f"{letter}:\\"
            if os.path.exists(root):
                paths.add(root)
    else:
        paths.add("/")
    return sorted(paths)

def get_gradio_major_version():
    try:
        return int(str(getattr(gr, "__version__", "4")).split(".")[0])
    except Exception:
        return 4

# ==========================================
# 🎯 LM STUDIO : LISTE ET CHARGEMENT AUTO DES MODÈLES
# ==========================================

def lm_studio_list_models(api_url):
    """Liste les modèles disponibles dans LM Studio.
    Utilise l'endpoint /api/v0/models, puis retombe sur /v1/models si besoin."""
    url = (api_url or DEFAULT_LM_STUDIO_URL).strip()
    if not url.startswith("http"):
        url = "http://" + url
    base = url.rstrip("/")
    # Stripper d'éventuels suffixes laissés par l'utilisateur
    for suffix in ("/v1/chat/completions", "/v1", "/api/v1/chat/completions", "/api/v1", "/api/v0/chat/completions", "/api/v0", "/api/generate", "/api/chat"):
        if base.endswith(suffix):
            base = base[: -len(suffix)]
            break
    endpoint = base + "/api/v0/models"
    try:
        r = requests.get(endpoint, timeout=10)
        r.raise_for_status()
        data = r.json()
        models = data.get("data", []) if isinstance(data, dict) else []
        ids = [m.get("id") for m in models if m.get("id")]
        all_choices = list(dict.fromkeys(ids))
        return all_choices, all_choices, None
    except Exception as e:
        # Endpoint v0 indisponible : tenter le /v1/models (OpenAI-compatible, plus minimal)
        try:
            endpoint = base + "/v1/models"
            r = requests.get(endpoint, timeout=10)
            r.raise_for_status()
            data = r.json()
            models = data.get("data", []) if isinstance(data, dict) else []
            ids = [m.get("id") for m in models if m.get("id")]
            all_choices = list(dict.fromkeys(ids))
            return all_choices, all_choices, None
        except Exception as e2:
            return [], [], f"{e2}"

def refresh_lm_studio_models(api_url, lang):
    """Rafraîchit les listes déroulantes VLM/LLM/partagé des modèles LM Studio."""
    m = MSG.get(lang, MSG.get("FR", {}))
    vlms, llms, err = lm_studio_list_models(api_url)
    if err:
        warning = m.get("lm_studio_list_error", "⚠️ Cannot list models: {error}").format(error=err)
        gr.Warning(warning)
        return gr.update(choices=[]), gr.update(choices=[]), gr.update(choices=[]), warning
    all_choices = list(dict.fromkeys(vlms + llms))  # union ordonnée, visible dans les deux listes
    vlm_choices = all_choices
    llm_choices = all_choices
    return gr.update(choices=vlm_choices), gr.update(choices=llm_choices), gr.update(choices=all_choices), f"✅ {len(all_choices)} modèles trouvés."

def lm_studio_load_model(model_id, api_url, lang):
    """Demande à LM Studio de charger un modèle en mémoire (v1 REST API).
    Retombe silencieusement si le serveur ne supporte pas /api/v1/models/load."""
    m = MSG.get(lang, MSG.get("FR", {}))
    if not model_id:
        return m.get("lm_studio_error", "❌ LM Studio error: {error}").format(error="aucun modèle sélectionné")
    url = (api_url or DEFAULT_LM_STUDIO_URL).strip()
    if not url.startswith("http"):
        url = "http://" + url
    base = url.rstrip("/")
    for suffix in ("/v1/chat/completions", "/v1", "/api/v1/chat/completions", "/api/v1", "/api/v0/chat/completions", "/api/v0", "/api/generate", "/api/chat"):
        if base.endswith(suffix):
            base = base[: -len(suffix)]
            break
    gr.Info(m.get("lm_studio_loading", "⏳ Loading model '{model}'...").format(model=model_id))
    # Tentative v1
    try:
        r = requests.post(base + "/api/v1/models/load", json={"model": model_id}, timeout=300)
        if r.status_code in (200, 201, 202, 204):
            msg = m.get("lm_studio_loaded", "✅ Model '{model}' loaded in LM Studio.").format(model=model_id)
            gr.Info(msg)
            return msg
    except Exception:
        pass
    # Tentative v0 (anciennes versions)
    try:
        r = requests.post(base + "/api/v0/models/load", json={"model": model_id}, timeout=300)
        if r.status_code in (200, 201, 202, 204):
            msg = m.get("lm_studio_loaded", "✅ Model '{model}' loaded in LM Studio.").format(model=model_id)
            gr.Info(msg)
            return msg
    except Exception as e:
        return m.get("lm_studio_error", "❌ LM Studio error: {error}").format(error=str(e))
    # Fallback : émettre une requête de chat triviale pour forcer le chargement (compatible toutes versions)
    try:
        payload = {"model": model_id, "messages": [{"role": "user", "content": "ping"}], "max_tokens": 1}
        r = requests.post(base + "/v1/chat/completions", json=payload, timeout=300)
        if r.status_code == 200:
            msg = m.get("lm_studio_loaded", "✅ Model '{model}' loaded in LM Studio.").format(model=model_id)
            gr.Info(msg)
            return msg
        return m.get("lm_studio_error", "❌ LM Studio error: {error}").format(error=f"HTTP {r.status_code}: {r.text[:200]}")
    except Exception as e:
        return m.get("lm_studio_error", "❌ LM Studio error: {error}").format(error=str(e))

def lm_studio_unload_model(model_id, api_url, lang):
    """Demande à LM Studio de décharger un modèle en mémoire."""
    m = MSG.get(lang, MSG.get("FR", {}))
    if not model_id:
        return m.get("lm_studio_error", "❌ LM Studio error: {error}").format(error="aucun modèle sélectionné")
    url = (api_url or DEFAULT_LM_STUDIO_URL).strip()
    if not url.startswith("http"):
        url = "http://" + url
    base = url.rstrip("/")
    for suffix in ("/v1/chat/completions", "/v1", "/api/v1", "/api/v0/chat/completions", "/api/v0", "/api/generate", "/api/chat"):
        if base.endswith(suffix):
            base = base[: -len(suffix)]
            break
    gr.Info(m.get("lm_studio_unloading", "⏳ Unloading model '{model}'...").format(model=model_id))
    payloads = [
        ("api/v1", {"instance_id": model_id}),
        ("api/v1", {"model": model_id}),
        ("api/v0", {"instance_id": model_id}),
        ("api/v0", {"model": model_id}),
    ]
    last_error = ""
    for api_version, payload in payloads:
        try:
            r = requests.post(f"{base}/{api_version}/models/unload", json=payload, timeout=120)
            if r.status_code in (200, 201, 202, 204):
                msg = m.get("lm_studio_unloaded", "✅ Model '{model}' unloaded from LM Studio.").format(model=model_id)
                gr.Info(msg)
                return msg
            last_error = f"HTTP {r.status_code}: {r.text[:200]}"
        except Exception as e:
            last_error = str(e)
    return m.get("lm_studio_error", "❌ LM Studio error: {error}").format(error=last_error)

def save_lm_studio_model_choices(vlm_choice, llm_choice, shared_choice, api_backend, api_url, api_key, temperature, context, timeout, system_prompt, lang):
    """Sauvegarde les choix LM Studio et synchronise les champs utilisés par les actions IA."""
    m = MSG.get(lang, MSG.get("FR", {}))
    shared = (shared_choice or "").strip()
    vlm = shared or (vlm_choice or "").strip()
    llm = shared or (llm_choice or "").strip()
    settings = load_ai_settings()
    settings.update({
        "api_backend": api_backend or DEFAULT_AI_SETTINGS["api_backend"],
        "vlm_model": vlm,
        "llm_model": llm,
        "lm_studio_shared_model": shared,
        "api_url": api_url or "",
        "api_key": api_key or "",
        "temperature": float(temperature) if temperature not in (None, "") else DEFAULT_AI_SETTINGS["temperature"],
        "context": int(float(context)) if context not in (None, "") else DEFAULT_AI_SETTINGS["context"],
        "timeout": _safe_timeout(timeout),
        "system_prompt": system_prompt or "",
    })
    _write_ai_settings(settings)
    msg = m.get("lm_studio_saved", "💾 LM Studio model choices saved.")
    gr.Info(msg)
    return gr.update(value=vlm), gr.update(value=llm), msg

# ==========================================
# 📚 NOUVEAU MODULE: BIBLIOTHÈQUE CUSTOM
# ==========================================

def load_library():
    if not os.path.exists(LIBRARY_FILE):
        return []
    try:
        with open(LIBRARY_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, list):
            normalized = []
            for item in data:
                if isinstance(item, str):
                    text = item.strip()
                elif isinstance(item, dict):
                    text = str(item.get("text", "")).strip()
                else:
                    text = ""
                if text and not any(x["text"].lower() == text.lower() for x in normalized):
                    normalized.append({"text": text, "selected": False})
            return normalized
    except Exception as e:
        print(f"⚠️ Impossible de lire {LIBRARY_FILE} : {e}")
    return []

def save_library(lib_state):
    try:
        cleaned = []
        for item in lib_state or []:
            text = str(item.get("text", "") if isinstance(item, dict) else item).strip()
            if text and not any(x["text"].lower() == text.lower() for x in cleaned):
                cleaned.append({"text": text})
        with open(LIBRARY_FILE, 'w', encoding='utf-8') as f:
            json.dump(cleaned, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ Impossible de sauver {LIBRARY_FILE} : {e}")

# ==========================================
# CHEMINS RÉCENTS
# ==========================================

def load_recent_paths():
    settings = load_ui_settings()
    return settings.get("recent_paths", [])

def save_recent_path(path):
    if not path:
        return
    settings = load_ui_settings()
    recents = settings.get("recent_paths", [])
    path = os.path.normpath(path)
    if path in recents:
        recents.remove(path)
    recents.insert(0, path)
    recents = recents[:10]
    settings["recent_paths"] = recents
    try:
        with open(UI_SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ Impossible de sauver recent_paths : {e}")

# ==========================================
# IMPORT / EXPORT CSV CAPTIONS
# ==========================================

def export_captions_csv(dataset, lang):
    import csv
    m = MSG.get(lang, MSG.get("FR", {}))
    if not dataset:
        msg = m.get("no_dataset", "No dataset.")
        gr.Warning(msg)
        return msg
    first_img_path = dataset[0].get("img_path") if isinstance(dataset[0], dict) else ""
    export_dir = os.path.dirname(first_img_path) if first_img_path else ""
    if not export_dir or not os.path.isdir(export_dir):
        msg = m.get("folder_not_found", "Dossier introuvable.")
        gr.Warning(msg)
        return msg
    stamp = time.strftime("%Y%m%d_%H%M%S")
    path = os.path.normpath(os.path.join(export_dir, f"captions_{stamp}.csv"))
    try:
        # Séparateur ";" car les captions contiennent des virgules (listes de tags)
        # et Excel en locale française utilise aussi ";" par défaut
        with open(path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f, delimiter=';')
            writer.writerow(["Numéro", "Fichier", "Caption"])
            for i, item in enumerate(dataset):
                writer.writerow([i + 1, item['img_name'], item['caption']])
        if not os.path.isfile(path):
            raise FileNotFoundError(path)
        filename = os.path.basename(path)
        if lang == "EN":
            msg = f"✅ Captions CSV exported in current dataset folder: {filename}\n📁 {export_dir}"
        else:
            msg = f"✅ CSV captions exporté dans le dossier du dataset : {filename}\n📁 {export_dir}"
        gr.Info(msg)
        return msg
    except Exception as e:
        return f"❌ {e}"

def _get_dataset_export_dir(dataset, lang):
    m = MSG.get(lang, MSG.get("FR", {}))
    if not dataset:
        msg = m.get("no_dataset", "No dataset.")
        gr.Warning(msg)
        return None, msg
    first_img_path = dataset[0].get("img_path") if isinstance(dataset[0], dict) else ""
    export_dir = os.path.dirname(first_img_path) if first_img_path else ""
    if not export_dir or not os.path.isdir(export_dir):
        msg = m.get("folder_not_found", "Dossier introuvable.")
        gr.Warning(msg)
        return None, msg
    return export_dir, ""

def export_captions_md(dataset, lang):
    export_dir, error_msg = _get_dataset_export_dir(dataset, lang)
    if not export_dir:
        return error_msg
    stamp = time.strftime("%Y%m%d_%H%M%S")
    path = os.path.normpath(os.path.join(export_dir, f"captions_{stamp}.md"))
    try:
        with open(path, 'w', encoding='utf-8') as f:
            f.write("# IMG Dataset Refiner Caption Export\n\n")
            f.write("| Numéro | Fichier | Caption |\n")
            f.write("| ---: | --- | --- |\n\n")
            for i, item in enumerate(dataset):
                caption = str(item.get('caption', '')).replace("```", "'''").strip()
                f.write(f"## {i + 1}. {item.get('img_name', '')}\n\n")
                f.write(f"- Numéro: {i + 1}\n")
                f.write(f"- Fichier: {item.get('img_name', '')}\n")
                f.write("- Caption:\n\n")
                f.write("```caption\n")
                f.write(caption)
                f.write("\n```\n\n")
        if not os.path.isfile(path):
            raise FileNotFoundError(path)
        filename = os.path.basename(path)
        if lang == "EN":
            msg = f"✅ Captions MD exported in current dataset folder: {filename}\n📁 {export_dir}"
        else:
            msg = f"✅ MD captions exporté dans le dossier du dataset : {filename}\n📁 {export_dir}"
        gr.Info(msg)
        return msg
    except Exception as e:
        return f"❌ {e}"

def _detect_csv_delimiter(path):
    """Détecte automatiquement le séparateur du CSV (,  ou ;  ou tab)."""
    import csv
    try:
        with open(path, 'r', encoding='utf-8-sig', errors='replace') as f:
            sample = f.read(4096)
        dialect = csv.Sniffer().sniff(sample, delimiters=',;\t')
        return dialect.delimiter
    except Exception:
        # Fallback : compte les occurrences de ; et , sur la première ligne
        first_line = sample.split('\n')[0] if sample else ''
        return ';' if first_line.count(';') >= first_line.count(',') else ','

def import_captions_csv(csv_file, dataset, lang):
    import csv as csv_mod
    m = MSG.get(lang, MSG.get("FR", {}))
    if not csv_file or not dataset:
        msg = m.get("no_dataset", "No dataset.")
        gr.Warning(msg)
        return dataset, msg
    try:
        src = csv_file if isinstance(csv_file, str) else (csv_file.name if hasattr(csv_file, "name") else str(csv_file))
        delim = _detect_csv_delimiter(src)
        with open(src, 'r', encoding='utf-8-sig', errors='replace') as f:
            reader = csv_mod.DictReader(f, delimiter=delim)
            rows = list(reader)
        name_to_item = {item['img_name']: item for item in dataset}
        basename_to_items = {}
        for item in dataset:
            basename_to_items.setdefault(os.path.basename(item.get('img_name', '')), []).append(item)
        count = 0
        for row in rows:
            filename = (row.get('Fichier') or row.get('File') or row.get('fichier') or '').strip()
            caption = (row.get('Caption') or row.get('caption') or '').strip()
            item = name_to_item.get(filename)
            if item is None:
                basename_matches = basename_to_items.get(os.path.basename(filename), [])
                item = basename_matches[0] if len(basename_matches) == 1 else None
            if item is not None and caption:
                item['caption'] = caption
                dataset[item['id']]['caption'] = caption
                with open(item['txt_path'], 'w', encoding='utf-8') as f:
                    f.write(caption)
                count += 1
        msg = m.get("csv_imported", "✅ {count} caption(s) importée(s).").format(count=count)
        gr.Info(msg)
        return dataset, msg
    except Exception as e:
        return dataset, m.get("csv_import_error", "❌ Erreur CSV : {error}").format(error=e)

def _parse_captions_md(path):
    text = ""
    with open(path, 'r', encoding='utf-8-sig', errors='replace') as f:
        text = f.read()
    pattern = re.compile(
        r"(?ms)^##\s+(?P<num>\d+)\.\s+(?P<title>.+?)\s*$"
        r".*?^- Fichier:\s*(?P<file>.+?)\s*$"
        r".*?^- Caption:\s*$"
        r"\s*```(?:caption)?\s*\n(?P<caption>.*?)\n```"
    )
    rows = []
    for match in pattern.finditer(text):
        filename = (match.group("file") or "").strip()
        caption = (match.group("caption") or "").strip()
        if filename:
            rows.append({"Fichier": filename, "Caption": caption})
    return rows

def import_captions_md(md_file, dataset, lang):
    m = MSG.get(lang, MSG.get("FR", {}))
    if not md_file or not dataset:
        msg = m.get("no_dataset", "No dataset.")
        gr.Warning(msg)
        return dataset, msg
    try:
        src = md_file if isinstance(md_file, str) else (md_file.name if hasattr(md_file, "name") else str(md_file))
        rows = _parse_captions_md(src)
        name_to_item = {item['img_name']: item for item in dataset}
        basename_to_items = {}
        for item in dataset:
            basename_to_items.setdefault(os.path.basename(item.get('img_name', '')), []).append(item)
        count = 0
        for row in rows:
            filename = (row.get('Fichier') or '').strip()
            caption = (row.get('Caption') or '').strip()
            item = name_to_item.get(filename)
            if item is None:
                basename_matches = basename_to_items.get(os.path.basename(filename), [])
                item = basename_matches[0] if len(basename_matches) == 1 else None
            if item is not None and caption:
                item['caption'] = caption
                dataset[item['id']]['caption'] = caption
                with open(item['txt_path'], 'w', encoding='utf-8') as f:
                    f.write(caption)
                count += 1
        msg = f"✅ {count} caption(s) importée(s) depuis le MD." if lang == "FR" else f"✅ {count} caption(s) imported from MD."
        gr.Info(msg)
        return dataset, msg
    except Exception as e:
        msg = f"❌ Erreur import MD : {e}" if lang == "FR" else f"❌ MD import error: {e}"
        return dataset, msg

def import_captions_file(caption_file, dataset, lang):
    src = caption_file if isinstance(caption_file, str) else (caption_file.name if hasattr(caption_file, "name") else str(caption_file or ""))
    ext = os.path.splitext(src)[1].lower()
    if ext == ".md":
        return import_captions_md(caption_file, dataset, lang)
    return import_captions_csv(caption_file, dataset, lang)

def _sync_filtered_from_dataset(dataset, filtered_dataset):
    if not dataset or not filtered_dataset:
        return filtered_dataset or []
    by_id = {item.get('id'): item for item in dataset if isinstance(item, dict)}
    return [by_id.get(item.get('id'), item) for item in filtered_dataset if isinstance(item, dict)]

def import_captions_file_refresh(caption_file, dataset, filtered_dataset, idx, tracked_words, lang):
    dataset, msg = import_captions_file(caption_file, dataset, lang)
    filtered_dataset = _sync_filtered_from_dataset(dataset, filtered_dataset)
    if (not filtered_dataset) and dataset:
        filtered_dataset = dataset
    img_path, hl_html, cap, wc, c_idx, v_status = update_viewer(filtered_dataset, idx, tracked_words, lang)
    return dataset, filtered_dataset, get_gallery_items(filtered_dataset, lang), img_path, hl_html, cap, wc, c_idx, v_status, extract_all_tags(dataset), msg

# ==========================================
# COPIER CAPTION VERS L'IMAGE SUIVANTE (Ctrl+D)
# ==========================================

def copy_caption_to_next(dataset, filtered_dataset, idx, current_caption, tracked_words, lang):
    silent_save(dataset, filtered_dataset, idx, current_caption, lang)
    if not filtered_dataset or idx < 0 or idx >= len(filtered_dataset):
        return dataset, filtered_dataset, None, "", current_caption, update_word_count(current_caption, lang), idx, ""
    next_idx = (idx + 1) % len(filtered_dataset)
    next_item = filtered_dataset[next_idx]
    real_id = next_item['id']
    next_item['caption'] = current_caption
    dataset[real_id]['caption'] = current_caption
    with open(next_item['txt_path'], 'w', encoding='utf-8') as f:
        f.write(current_caption)
    res = update_viewer(filtered_dataset, next_idx, tracked_words, lang)
    return (dataset, filtered_dataset) + res

def render_lib_html(lib_state, lang):
    if not lib_state:
        empty_msg = MSG.get(lang, MSG["FR"]).get("lib_empty", "Bibliothèque vide... Entrez des mots ci-dessous.")
        return f"<div style='padding:10px; color:#9ca3af; font-style:italic;'>{empty_msg}</div>"
    html = "<div id='custom_library_container' style='display:flex; flex-direction:column; gap:8px; margin-top:10px;'>"
    for idx, item in enumerate(lib_state):
        text = item['text']
        is_sel = item.get('selected', False)
        bg_color = "rgba(249, 115, 22, 0.2)" if is_sel else "#1f2937"
        border_color = "#f97316" if is_sel else "#374151"
        safe_t = text.replace("'", "&#39;").replace('"', '&quot;')
        html += f"""
        <div class='lib-item-custom' data-idx='{idx}' style='border: 2px solid {border_color}; background-color: {bg_color}; padding: 10px 15px; border-radius: 6px; display: flex; justify-content: space-between; align-items: center; cursor: pointer; margin-bottom: 5px;'>
            <span style='color: #fff; font-size: 1.05em; pointer-events: none;'>{safe_t}</span>
            <span class='lib-item-delete' data-idx='{idx}' style='color: #fb923c; font-weight: bold; cursor: pointer; padding: 2px 6px; border-radius:4px; font-size:1.1em; background-color: rgba(251, 146, 60, 0.1);' title='Supprimer'>X</span>
        </div>
        """
    html += "</div>"
    return html

def add_to_lib_html(text, lib_state, lang):
    if not text: return gr.update(), lib_state, ""
    new_lib = copy.deepcopy(lib_state)
    items = [x.strip() for x in re.split(r'[\n;]', text) if x.strip()]
    for item in items:
        if not any(x['text'] == item for x in new_lib) and item.lower() != "none":
            new_lib.append({"text": item, "selected": False})
    save_library(new_lib)
    return render_lib_html(new_lib, lang), new_lib, ""

def toggle_lib_item(idx_str, lib_state, lang):
    new_lib = copy.deepcopy(lib_state)
    try:
        idx = int(str(idx_str).split('_')[0])
        if 0 <= idx < len(new_lib):
            new_lib[idx]['selected'] = not new_lib[idx].get('selected', False)
    except: pass
    save_library(new_lib)
    return render_lib_html(new_lib, lang), new_lib

def delete_lib_item(idx_str, lib_state, lang):
    new_lib = copy.deepcopy(lib_state)
    try:
        idx = int(str(idx_str).split('_')[0])
        if 0 <= idx < len(new_lib):
            new_lib.pop(idx)
    except: pass
    save_library(new_lib)
    return render_lib_html(new_lib, lang), new_lib

def uncheck_all_lib(lib_state, lang):
    new_lib = copy.deepcopy(lib_state)
    for x in new_lib: x['selected'] = False
    save_library(new_lib)
    return render_lib_html(new_lib, lang), new_lib

def clear_lib(lang):
    save_library([])
    return render_lib_html([], lang), []

def batch_library_cb(dataset, lib_state, mode, replace_target, selected_ids, search_text, current_idx, tracked_words, lang):
    history = copy.deepcopy(dataset)
    new_dataset = copy.deepcopy(dataset)
    count = 0
    m = MSG.get(lang, MSG["FR"])

    selected_items = [x['text'] for x in lib_state if x.get('selected', False)]
    target = str(replace_target).strip() if replace_target else ""

    if "Ajouter" in mode or "Add" in mode:
        action_mode = "Add"
    elif "Retirer" in mode or "Remove" in mode:
        action_mode = "Remove"
    else:
        action_mode = "Replace"

    if action_mode == "Add" and not selected_items:
        gr.Warning(m.get("lib_warn_add", "⚠️ Veuillez cocher au moins un mot !"))
        cap, hl, wc = get_updated_viewer_data(new_dataset, current_idx, tracked_words, lang)
        return new_dataset, new_dataset, history, m.get("text_empty", ""), pd.DataFrame(), cap, hl, wc, gr.update()
        
    elif action_mode == "Remove" and not selected_items and not target:
        gr.Warning(m.get("lib_warn_rem", "⚠️ Entrez une Cible OU cochez un mot !"))
        cap, hl, wc = get_updated_viewer_data(new_dataset, current_idx, tracked_words, lang)
        return new_dataset, new_dataset, history, m.get("text_empty", ""), pd.DataFrame(), cap, hl, wc, gr.update()
        
    elif action_mode == "Replace" and not target:
        gr.Warning(m.get("lib_warn_rep", "⚠️ Spécifiez ce qu'il faut remplacer !"))
        cap, hl, wc = get_updated_viewer_data(new_dataset, current_idx, tracked_words, lang)
        return new_dataset, new_dataset, history, m.get("text_empty", ""), pd.DataFrame(), cap, hl, wc, gr.update()

    for item in new_dataset:
        if selected_ids and item['id'] not in selected_ids: continue
        cap = item['caption']; original_cap = cap

        if action_mode == "Add":
            existing_tags = [t.strip().lower() for t in cap.split(',')]
            for lib_item in selected_items:
                if lib_item.lower() not in existing_tags:
                    sep = ", " if cap and not cap.endswith(", ") else ""
                    cap = cap + sep + lib_item
                    existing_tags.append(lib_item.lower())
                    
        elif action_mode == "Remove":
            for lib_item in selected_items:
                cap = re.sub(r'(?i)\b' + re.escape(lib_item) + r'\b,?', '', cap)
            if target:
                cap = re.sub(r'(?i)\b' + re.escape(target) + r'\b,?', '', cap)
            cap = re.sub(r',\s*,', ',', cap).strip(', ')
            
        elif action_mode == "Replace":
            if target and re.search(r'(?i)\b' + re.escape(target) + r'\b', cap):
                replacement = ", ".join(selected_items)
                pattern = re.compile(r'(?i)\b' + re.escape(target) + r'\b')
                cap = pattern.sub(replacement, cap)

        if cap != original_cap:
            item['caption'] = cap; count += 1

    save_all_captions(new_dataset)
    cible_msg = m.get("target_sel", "(sur {count} ciblées)").format(count=len(selected_ids)) if selected_ids else m.get("target_all", "(sur TOUT le dataset)")
    msg = m.get("lib_batch_success", "✅ Mass Batch appliqué dans {count} images {cible_msg}.").format(count=count, cible_msg=cible_msg)
    gr.Info(msg)
    
    filtered_dataset = [item for item in new_dataset if search_text.lower() in item['caption'].lower()] if search_text else new_dataset
    cap_disp, hl_disp, wc_disp = get_updated_viewer_data(filtered_dataset, current_idx, tracked_words, lang)
    
    changes = []
    for old, new in zip(history, new_dataset):
        if old['caption'] != new['caption']:
            changes.append({"File" if lang=="EN" else "Fichier": old['img_name'], "Avant" if lang=="FR" else "Before": old['caption'], "Après" if lang=="FR" else "After": new['caption']})
            if len(changes) >= 10: break
    if not changes: df_res = pd.DataFrame([{"Message": m.get("no_changes", "Aucun changement.")}])
    else: df_res = pd.DataFrame(changes)
        
    return new_dataset, filtered_dataset, history, msg, df_res, cap_disp, hl_disp, wc_disp, get_gallery_items(filtered_dataset, lang)

# === TRADUCTION ===
def translate_text(text, engine, source_lang, dest_lang, api_backend, api_url, llm_model, lang="FR", api_key="", timeout=180):
    m = MSG.get(lang, MSG["FR"])
    if not text: return ""
    if engine == "Google (Online)":
        if not HAS_TRANSLATOR: return m.get("err_trans_no_install", "⚠️ Error: deep-translator not installed.")
        lang_map = {"auto": "auto", "fr": "fr", "es": "es", "de": "de", "it": "it", "pt": "pt", "ru": "ru", "ja": "ja", "ko": "ko", "zh-CN": "zh-CN", "en": "en"}
        src = lang_map.get(source_lang, source_lang.split(" ")[0]) if source_lang else "auto"
        dst = lang_map.get(dest_lang, dest_lang.split(" ")[0]) if dest_lang else "en"
        try: 
            translator = GoogleTranslator(source=src, target=dst)
            parts = [p.strip() for p in text.split(',')]
            translated_parts = []
            for p in parts:
                if not p: continue
                try:
                    trans = translator.translate(p)
                    translated_parts.append(trans if trans else p)
                except:
                    translated_parts.append(p)
            return ", ".join(translated_parts)
        except Exception as e: return m.get("err_google_trans", "⚠️ Google Translate Error: {error}").format(error=str(e))
    else:
        return call_ai_api(
            f"Translate the following text from {source_lang} to {dest_lang}. ONLY output the translation, nothing else.\nText: {text}",
            llm_model, None, api_backend, api_url, 0.3, 1024,
            "You are a professional translator.", api_key=api_key, timeout=timeout
        )

def do_live_translation(caption, engine, dest_lang, api_backend, api_url, llm_model, lang, api_key="", timeout=180):
    if not caption: return ""
    caption = str(caption).strip()
    if len(caption) < 2: return ""
    cache_key = (caption, engine, dest_lang, api_backend, api_url, llm_model, api_key, _safe_timeout(timeout))
    if cache_key in LIVE_TRANSLATION_CACHE:
        return LIVE_TRANSLATION_CACHE[cache_key]
    try:
        if engine == "Google (Online)":
            m = MSG.get(lang, MSG["FR"])
            if not HAS_TRANSLATOR:
                return m.get("err_trans_no_install", "⚠️ Error: deep-translator is not installed.")
            lang_map = {"auto": "auto", "fr": "fr", "es": "es", "de": "de", "it": "it", "pt": "pt", "ru": "ru", "ja": "ja", "ko": "ko", "zh-CN": "zh-CN", "en": "en"}
            dst = lang_map.get(dest_lang, dest_lang.split(" ")[0]) if dest_lang else "en"
            res = GoogleTranslator(source="auto", target=dst).translate(caption)
        else:
            res = translate_text(caption, engine, "auto", dest_lang, api_backend, api_url, llm_model, lang, api_key, timeout)
        if res and res.startswith("⚠️"): return res
        if len(LIVE_TRANSLATION_CACHE) > 200:
            LIVE_TRANSLATION_CACHE.clear()
        LIVE_TRANSLATION_CACHE[cache_key] = res or ""
        return res
    except Exception as e:
        return f"Erreur: {e}"

def reverse_live_translation(translated_caption, engine, source_lang, api_backend, api_url, llm_model, tracked_words, lang, api_key="", timeout=180):
    if not translated_caption:
        return "", get_highlighted_html("", tracked_words), update_word_count("", lang)
    translated_caption = str(translated_caption).strip()
    if len(translated_caption) < 2:
        return translated_caption, get_highlighted_html(translated_caption, tracked_words), update_word_count(translated_caption, lang)
    cache_key = ("reverse", translated_caption, engine, source_lang or "auto", api_backend, api_url, llm_model, api_key, _safe_timeout(timeout))
    if cache_key in LIVE_TRANSLATION_CACHE:
        res = LIVE_TRANSLATION_CACHE[cache_key]
    elif engine == "Google (Online)":
        m = MSG.get(lang, MSG["FR"])
        if not HAS_TRANSLATOR:
            res = m.get("err_trans_no_install", "⚠️ Error: deep-translator is not installed.")
        else:
            try:
                lang_map = {"auto": "auto", "fr": "fr", "es": "es", "de": "de", "it": "it", "pt": "pt", "ru": "ru", "ja": "ja", "ko": "ko", "zh-CN": "zh-CN", "en": "en"}
                src = lang_map.get(source_lang, source_lang.split(" ")[0]) if source_lang else "auto"
                res = GoogleTranslator(source=src, target="en").translate(translated_caption)
            except Exception as e:
                res = m.get("err_google_trans", "⚠️ Google Translate Error: {error}").format(error=str(e))
    else:
        res = translate_text(translated_caption, engine, source_lang or "auto", "en", api_backend, api_url, llm_model, lang, api_key, timeout)
    if len(LIVE_TRANSLATION_CACHE) > 200:
        LIVE_TRANSLATION_CACHE.clear()
    LIVE_TRANSLATION_CACHE[cache_key] = res or ""
    if res and not res.startswith("⚠️"):
        return res, get_highlighted_html(res, tracked_words), update_word_count(res, lang)
    if res and res.startswith("⚠️"):
        gr.Warning(res)
    return translated_caption, get_highlighted_html(translated_caption, tracked_words), update_word_count(translated_caption, lang)

def translate_entire_caption_action(dataset, filtered_dataset, idx, caption, engine, source_lang, api_backend, api_url, llm_model, tracked_words, lang, api_key="", timeout=180):
    new_dataset = copy.deepcopy(dataset)
    new_filtered = [item for item in new_dataset if item['id'] in [x['id'] for x in filtered_dataset]]
    m = MSG.get(lang, MSG["FR"])

    if not caption: 
        cap, hl_html, wc = get_updated_viewer_data(new_filtered, idx, tracked_words, lang)
        return new_dataset, new_filtered, cap, hl_html, wc, m.get("trans_no_text", "Aucun texte")
        
    res = translate_text(caption, engine, source_lang, "en", api_backend, api_url, llm_model, lang, api_key, timeout)
    
    if res and res.startswith("⚠️"):
        gr.Warning(res)
        cap, hl_html, wc = get_updated_viewer_data(new_filtered, idx, tracked_words, lang)
        return new_dataset, new_filtered, cap, hl_html, wc, ""
    elif res:
        gr.Info(m.get("trans_entire_success", "✅ Caption complet traduit !"))
        if idx >= 0 and idx < len(new_filtered):
            new_filtered[idx]['caption'] = res
            new_dataset[new_filtered[idx]['id']]['caption'] = res
            txt_path = new_filtered[idx]['txt_path']
            if os.path.exists(txt_path) and os.path.getsize(txt_path) > 0:
                shutil.copy2(txt_path, txt_path + ".bak")
            with open(txt_path, 'w', encoding='utf-8') as f:
                f.write(res)
                
            cap, hl_html, wc = get_updated_viewer_data(new_filtered, idx, tracked_words, lang)
            return new_dataset, new_filtered, cap, hl_html, wc, m.get("trans_to_en_success", "✅ Traduit")
        else:
            return new_dataset, new_filtered, res, get_highlighted_html(res, tracked_words), update_word_count(res, lang), m.get("trans_to_en_success", "✅ Traduit")
        
    cap, hl_html, wc = get_updated_viewer_data(new_filtered, idx, tracked_words, lang)
    return new_dataset, new_filtered, cap, hl_html, wc, ""

def trans_insert(text_to_trans, current_caption, engine, source_lang, api_backend, api_url, llm_model, lang, api_key="", timeout=180):
    if not text_to_trans: return current_caption
    res = translate_text(text_to_trans, engine, source_lang, "en", api_backend, api_url, llm_model, lang, api_key, timeout)
    if res and not res.startswith("⚠️"):
        sep = ", " if current_caption and not current_caption.endswith(", ") else ""
        return current_caption + sep + res
    elif res and res.startswith("⚠️"):
        gr.Warning(res)
    return current_caption

# =========================================================================
# RESTE DES FONCTIONS STANDARD (Export, Doublons, IA, Stats)
# =========================================================================

def create_preview_df(old_dataset, new_dataset, lang):
    changes = []
    for old, new in zip(old_dataset, new_dataset):
        if old['caption'] != new['caption']:
            changes.append({"File" if lang=="EN" else "Fichier": old['img_name'], "Avant" if lang=="FR" else "Before": old['caption'], "Après" if lang=="FR" else "After": new['caption']})
            if len(changes) >= 10: break
    if not changes: return pd.DataFrame([{"Message": MSG[lang].get("no_changes", "No change")}])
    return pd.DataFrame(changes)

def batch_add(dataset, text, pos, selected_ids, search_text, current_idx, tracked_words, lang):
    if not text: 
        cap, hl, wc = get_updated_viewer_data(dataset, current_idx, tracked_words, lang)
        return dataset, dataset, dataset, MSG[lang].get("text_empty", ""), pd.DataFrame(), cap, hl, wc
    history = copy.deepcopy(dataset)
    count = 0
    for item in dataset:
        if selected_ids and item['id'] not in selected_ids: continue
        if pos in ["Début", "Start"]:
            sep = ", " if item['caption'] else ""
            item['caption'] = text + sep + item['caption']
        else:
            sep = ", " if item['caption'] and not item['caption'].endswith(", ") else ""
            item['caption'] = item['caption'] + sep + text
        count += 1
    save_all_captions(dataset)
    msg = MSG[lang].get("added_to", "Added").format(count=count)
    gr.Info(msg)
    filtered_dataset = [item for item in dataset if search_text.lower() in item['caption'].lower()] if search_text else dataset
    cap, hl, wc = get_updated_viewer_data(filtered_dataset, current_idx, tracked_words, lang)
    return dataset, filtered_dataset, history, msg, create_preview_df(history, dataset, lang), cap, hl, wc

def batch_replace(dataset, old_text, new_text, use_regex, selected_ids, search_text, current_idx, tracked_words, lang):
    history = copy.deepcopy(dataset)
    count = 0
    for item in dataset:
        if selected_ids and item['id'] not in selected_ids: continue
        if use_regex:
            try:
                new_cap = re.sub(old_text, new_text, item['caption'])
                if new_cap != item['caption']: item['caption'] = new_cap; count += 1
            except: pass
        else:
            if old_text in item['caption']: item['caption'] = item['caption'].replace(old_text, new_text); count += 1
    save_all_captions(dataset)
    msg = MSG[lang].get("replaced_in", "Replaced").format(count=count)
    gr.Info(msg)
    filtered_dataset = [item for item in dataset if search_text.lower() in item['caption'].lower()] if search_text else dataset
    cap, hl, wc = get_updated_viewer_data(filtered_dataset, current_idx, tracked_words, lang)
    return dataset, filtered_dataset, history, msg, create_preview_df(history, dataset, lang), cap, hl, wc

def batch_clean_commas(dataset, selected_ids, search_text, current_idx, tracked_words, lang):
    history = copy.deepcopy(dataset)
    count = 0
    for item in dataset:
        if selected_ids and item['id'] not in selected_ids: continue
        cap = item['caption']
        cap = re.sub(r'\s+', ' ', cap)
        cap = re.sub(r'\s*,\s*', ', ', cap)
        cap = re.sub(r'(,\s*){2,}', ', ', cap)
        cap = cap.strip(', ')
        if cap != item['caption']: item['caption'] = cap; count += 1
    save_all_captions(dataset)
    msg = MSG[lang].get("cleaned_in", "Cleaned").format(count=count)
    gr.Info(msg)
    filtered_dataset = [item for item in dataset if search_text.lower() in item['caption'].lower()] if search_text else dataset
    cap, hl, wc = get_updated_viewer_data(filtered_dataset, current_idx, tracked_words, lang)
    return dataset, filtered_dataset, history, msg, create_preview_df(history, dataset, lang), cap, hl, wc

def batch_remove_duplicates(dataset, selected_ids, search_text, current_idx, tracked_words, lang):
    history = copy.deepcopy(dataset)
    count = 0
    for item in dataset:
        if selected_ids and item['id'] not in selected_ids: continue
        parts = [p.strip() for p in item['caption'].split(',')]
        seen = set(); new_parts = []
        for p in parts:
            if p.lower() not in seen and p != "": seen.add(p.lower()); new_parts.append(p)
        new_cap = ", ".join(new_parts)
        if new_cap != item['caption']: item['caption'] = new_cap; count += 1
    save_all_captions(dataset)
    msg = MSG[lang].get("dups_removed", "Removed").format(count=count)
    gr.Info(msg)
    filtered_dataset = [item for item in dataset if search_text.lower() in item['caption'].lower()] if search_text else dataset
    cap, hl, wc = get_updated_viewer_data(filtered_dataset, current_idx, tracked_words, lang)
    return dataset, filtered_dataset, history, msg, create_preview_df(history, dataset, lang), cap, hl, wc

def batch_synonyms(dataset, target_tag, synonyms_str, selected_ids, search_text, current_idx, tracked_words, lang):
    history = copy.deepcopy(dataset)
    if not target_tag: 
        cap, hl, wc = get_updated_viewer_data(dataset, current_idx, tracked_words, lang)
        return dataset, dataset, dataset, MSG[lang].get("target_empty", ""), pd.DataFrame(), cap, hl, wc
    count = 0
    syn_list = [s.strip() for s in synonyms_str.split(',')] if synonyms_str else []
    for item in dataset:
        if selected_ids and item['id'] not in selected_ids: continue
        original = item['caption']
        tags = [t.strip() for t in original.split(',')]
        first_found = False; syn_idx = 0; new_tags = []
        for t in tags:
            if t.lower() == target_tag.strip().lower():
                if not first_found: first_found = True; new_tags.append(t)
                else:
                    if syn_list and syn_list[0]: new_tags.append(syn_list[syn_idx % len(syn_list)]); syn_idx += 1
            else: new_tags.append(t)
        new_cap = ", ".join([t for t in new_tags if t])
        if new_cap != original: item['caption'] = new_cap; count += 1
    save_all_captions(dataset)
    msg = MSG[lang].get("synonyms_replaced", "Replaced").format(count=count)
    gr.Info(msg)
    filtered_dataset = [item for item in dataset if search_text.lower() in item['caption'].lower()] if search_text else dataset
    cap, hl, wc = get_updated_viewer_data(filtered_dataset, current_idx, tracked_words, lang)
    return dataset, filtered_dataset, history, msg, create_preview_df(history, dataset, lang), cap, hl, wc

def _safe_folder_name(name):
    name = re.sub(r'[<>:"/\\|?*]+', '_', str(name or '').strip())
    name = re.sub(r'\s+', ' ', name).strip(' .')
    return name or "dataset"

def _format_export_suffix(pattern, number):
    pattern = str(pattern or "").strip() or "-Sx"
    if "{n}" in pattern:
        try:
            return pattern.format(n=number)
        except Exception:
            return f"-S{number}"
    if "x" in pattern.lower():
        chars = []
        replaced = False
        for ch in pattern:
            if ch.lower() == "x" and not replaced:
                chars.append(str(number))
                replaced = True
            else:
                chars.append(ch)
        return "".join(chars)
    return f"{pattern}{number}"

def _build_unique_export_dir(dataset, export_parent, suffix_pattern):
    dataset_dir = os.path.dirname(dataset[0]['img_path']) if dataset else ""
    dataset_name = _safe_folder_name(os.path.basename(dataset_dir) or "dataset")
    parent = normalize_dataset_path(export_parent, allow_file_parent=False) if export_parent and str(export_parent).strip() else os.path.join(os.getcwd(), "output")
    os.makedirs(parent, exist_ok=True)
    for idx in range(1, 10000):
        candidate = os.path.join(parent, dataset_name + _format_export_suffix(suffix_pattern, idx))
        if not os.path.exists(candidate):
            return candidate
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    return os.path.join(parent, f"{dataset_name}-{timestamp}")

def simulate_and_export(dataset, export_dir, export_suffix, config_df, is_simulation, selected_ids, strategy, max_images, lang):
    if not dataset: return MSG[lang].get("no_dataset", ""), [], None, None
    if config_df is None or config_df.empty: 
        config_df = pd.DataFrame([{MSG[lang].get("df_prio", "Prio"): 1, MSG[lang].get("df_kw", "Kw"): "", MSG[lang].get("df_tgt", "Tgt"): 0}])
    else:
        prio_col = "Priority" if "Priority" in config_df.columns else "Priorité"
        config_df[prio_col] = pd.to_numeric(config_df[prio_col], errors='coerce').fillna(999).astype(int)
        config_df = config_df.sort_values(by=prio_col)
    
    targets = {}; ordered_tags = []
    for _, row in config_df.iterrows():
        tag = str(row.get("Mot-clé", row.get("Keyword", ""))).strip().lower()
        if tag and tag not in ["aucun", "none"]:
            try: c = float(str(row.get("Cible %", row.get("Target %", 0))).replace('%', '').strip())
            except: c = 0.0
            targets[tag] = c
            ordered_tags.append(tag)

    base_pool = [item for item in dataset if not selected_ids or item['id'] in selected_ids]
    to_export = []
    limit = int(max_images)

    if strategy in ["Filtre Classique", "Classic Filter", "Filtre Classique (Contient au moins un tag)", "Classic Filter (Contains at least one tag)"]:
        for item in base_pool:
            if not ordered_tags or any(re.search(r'\b' + re.escape(t) + r'\b', item['caption'].lower()) for t in ordered_tags):
                to_export.append(item)
        if limit > 0: to_export = to_export[:limit]

    elif strategy in ["Priorité", "Priority", "Priorité (Ordre du tableau)", "Priority (Table Order)"]:
        seen = set()
        lim = limit if limit > 0 else len(base_pool)
        for tag in ordered_tags:
            for item in base_pool:
                if len(to_export) >= lim: break
                if item['id'] not in seen and re.search(r'\b' + re.escape(tag) + r'\b', item['caption'].lower()):
                    to_export.append(item); seen.add(item['id'])
            if len(to_export) >= lim: break

    elif strategy in ["Équilibrage Auto (Pourcentages)", "Auto Balancing (Percentages)"]:
        relevant = [it for it in base_pool if not ordered_tags or any(re.search(r'\b'+re.escape(t)+r'\b', it['caption'].lower()) for t in ordered_tags)]
        lim = limit if limit > 0 else len(relevant)
        if lim > 0 and ordered_tags:
            needs = {tag: int((pct / 100.0) * lim) for tag, pct in targets.items() if pct > 0}
            if sum(needs.values()) == 0: to_export = relevant[:lim]
            else:
                available = relevant.copy()
                while len(to_export) < lim and available:
                    best_score = -9999; best_idx = -1
                    for i, item in enumerate(available):
                        cap = available[i]['caption'].lower(); score = 0; has_tag = False
                        for tag in ordered_tags:
                            if re.search(r'\b' + re.escape(tag) + r'\b', cap):
                                has_tag = True
                                if tag in needs: score += (10 * needs[tag]) if needs[tag] > 0 else -5
                        if has_tag and score > best_score: best_score = score; best_idx = i
                    if best_idx == -1: break
                    chosen = available.pop(best_idx)
                    to_export.append(chosen)
                    for tag in ordered_tags:
                        if re.search(r'\b' + re.escape(tag) + r'\b', chosen['caption'].lower()) and tag in needs: needs[tag] -= 1
        else: to_export = relevant[:lim]

    sim_stats = {t: 0 for t in ordered_tags}
    for item in to_export:
        cap = item['caption'].lower()
        for t in ordered_tags:
            if re.search(r'\b' + re.escape(t) + r'\b', cap): sim_stats[t] += 1
            
    pie_data = {k: v for k, v in sim_stats.items() if v > 0}
    if not pie_data:
        p_fig = px.pie(names=[MSG[lang].get("none", "Aucun")], values=[1], title=MSG[lang].get("no_tag_found", "Aucun tag trouvé"))
        b_fig = px.bar(x=[MSG[lang].get("none", "Aucun")], y=[0], title=MSG[lang].get("no_tag_found", "Aucun tag trouvé"))
    else:
        p_fig = px.pie(names=list(pie_data.keys()), values=list(pie_data.values()), title=MSG[lang].get("overall_dist", "Répartition Globale"))
        p_fig.update_traces(textposition='inside', textinfo='percent+label')
        b_fig = px.bar(x=list(pie_data.keys()), y=list(pie_data.values()), title=MSG[lang].get("occ_by_keyword", "Occurrences par Mot-clé"))

    gallery_preview = [item['img_path'] for item in to_export]
    
    if is_simulation:
        rep = MSG[lang].get("simul_res", "Simul: {count}").format(count=len(to_export))
        gr.Info("📊 Simulation terminée !")
        return rep, gallery_preview, p_fig, b_fig
    else:
        export_dir = _build_unique_export_dir(dataset, export_dir, export_suffix)
        os.makedirs(export_dir, exist_ok=True)
        for item in to_export:
            shutil.copy2(item['img_path'], os.path.join(export_dir, item['img_name']))
            shutil.copy2(item['txt_path'], os.path.join(export_dir, os.path.basename(item['txt_path'])))
        msg = MSG[lang].get("export_success", "Success").format(count=len(to_export), dest=export_dir)
        gr.Info(f"✅ Export réussi dans {export_dir}")
        return msg, gallery_preview, p_fig, b_fig

def simulate_and_clear_selection(dataset, export_dir, export_suffix, config_df, selected_ids, strategy, max_images, lang):
    """Lance une simulation sur tout le dataset et remet la sélection galerie à zéro."""
    status, gallery_preview, p_fig, b_fig = simulate_and_export(
        dataset, export_dir, export_suffix, config_df, True, [], strategy, max_images, lang
    )
    return status, gallery_preview, p_fig, b_fig, [], selection_summary_html(0, len(dataset or []), len(dataset or []), lang), "{}"

def _caption_tags(caption):
    tags = []
    for raw in str(caption or "").split(","):
        tag = re.sub(r"\s+", " ", raw).strip(" \t\r\n\"'`")
        if tag:
            tags.append(tag)
    return tags

# Limites pour qu'un "mot-clé" reste un vrai mot-clé et pas une phrase
# entière recopiée par le LLM. Volontairement permissif pour les concepts
# multi-mots type "pup play mask black" mais strict sur les phrases.
KEYWORD_MAX_WORDS = 6
KEYWORD_MAX_CHARS = 50

# Indices qu'un fragment est une phrase descriptive et non un tag.
_PHRASE_HINTS = re.compile(
    r"\b(the\s+image|this\s+image|the\s+photo|the\s+picture|"
    r"il\s+y\s+a|on\s+voit|l[ae]\s+photo|cette\s+image|"
    r"appears\s+to|seems\s+to|is\s+wearing|is\s+sitting|is\s+standing|"
    r"is\s+holding|in\s+the\s+background|the\s+overall|the\s+lighting|"
    r"se\s+trouve|porte\s+un|tient\s+un|en\s+arri[èe]re|au\s+fond)\b",
    re.I,
)

def _is_valid_keyword(tag):
    """Filtre un fragment : doit ressembler à un mot-clé (court, sans verbe conjugué de description)."""
    if not tag:
        return False
    t = tag.strip()
    if not t:
        return False
    # Longueur en mots et en caractères
    words = t.split()
    if len(words) > KEYWORD_MAX_WORDS:
        return False
    if len(t) > KEYWORD_MAX_CHARS:
        return False
    # Trop court : un seul caractère, pas pertinent
    if len(t) < 2:
        return False
    # Phrase descriptive détectée par tournures typiques de captions VLM
    if _PHRASE_HINTS.search(t):
        return False
    # Phrase terminée par un point (sauf abréviations très courtes)
    if t.rstrip().endswith(".") and len(words) > 1:
        return False
    return True

# Triggers LoRA fréquents : majuscules/minuscules mélangées avec chiffres,
# underscores, ou patterns "leetspeak" type "D4lle", "photosh00tsP0ses".
_TRIGGER_HINT = re.compile(r"[A-Za-z].*[0-9]|[0-9].*[A-Za-z]|_")

def _looks_like_trigger(tag):
    """Heuristique pour reconnaître un trigger word/concept LoRA (à mettre en tête de recette)."""
    if not tag or " " in tag.strip():
        return False  # la plupart des triggers sont en un seul "mot"
    t = tag.strip()
    if len(t) < 3 or len(t) > 30:
        return False
    return bool(_TRIGGER_HINT.search(t))

# Stopwords bilingues FR/EN pour l'extraction de n-grams sur prose libre.
# Volontairement compact : on veut filtrer les determinants, prepositions,
# verbes auxiliaires/copules tres frequents qui n'apportent rien comme tag.
_STOPWORDS = frozenset([
    # Anglais
    "a", "an", "the", "this", "that", "these", "those",
    "is", "are", "was", "were", "be", "been", "being", "am",
    "has", "have", "had", "having",
    "do", "does", "did", "doing",
    "will", "would", "shall", "should", "can", "could", "may", "might", "must",
    "and", "or", "but", "nor", "so", "yet", "if", "then", "than",
    "as", "of", "in", "on", "at", "to", "for", "with", "by", "from",
    "into", "onto", "out", "up", "down", "over", "under", "above", "below",
    "between", "through", "during", "before", "after",
    "he", "she", "it", "we", "they", "you", "i", "me", "him", "her", "us", "them",
    "his", "hers", "its", "their", "our", "your", "my", "mine", "yours", "theirs", "ours",
    "who", "whom", "which", "what", "when", "where", "why", "how",
    "there", "here", "very", "more", "most", "less", "least", "much", "many", "some", "any", "all",
    "also", "just", "only", "even", "still", "again", "ever", "never",
    "appears", "seems", "looks", "shows", "shown", "showing", "showed",
    "wearing", "sitting", "standing", "holding", "lying", "covered", "covering",
    "image", "picture", "photo", "scene",
    "overall", "background", "foreground",
    # Francais
    "le", "la", "les", "un", "une", "des", "du", "de", "d", "l",
    "ce", "cet", "cette", "ces", "ça", "ca",
    "est", "sont", "était", "etait", "étaient", "etaient", "etre", "être", "été", "ete",
    "ont", "avait", "avaient", "avoir", "eu",
    "et", "ou", "mais", "ni", "donc", "car",
    "qui", "que", "quoi", "dont", "où", "comme",
    "il", "elle", "ils", "elles", "nous", "vous", "je", "tu", "se", "s",
    "son", "sa", "ses", "leur", "leurs", "mon", "ma", "mes", "ton", "ta", "tes", "notre", "votre",
    "au", "aux", "dans", "sur", "sous", "par", "pour", "vers", "avec", "sans",
    "tres", "plus", "moins", "tout", "tous", "toute", "toutes", "même", "meme",
    "aussi", "encore", "déjà", "deja", "ici",
    "scène", "fond",
    "porte", "tient", "montre", "semble", "apparaît", "apparait",
    "ne", "pas", "n",
])

# Mots courts (< 3 lettres) qu'on garde quand meme car ils sont semantiques.
_SHORT_KEEP = frozenset(["ai", "3d", "2d", "vfx", "cgi", "hdr", "uv", "ui", "ux"])

# Tokens autorises : lettres (FR/EN), chiffres, tirets internes, apostrophe.
_TOKEN_RE = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ][A-Za-zÀ-ÖØ-öø-ÿ0-9'\-]{1,}", re.UNICODE)

def _is_useful_token(tok):
    """Un token est utile s'il n'est pas stopword et qu'il a une longueur correcte."""
    t = tok.lower().strip("-'")
    if not t or t in _STOPWORDS:
        return False
    if len(t) < 3 and t not in _SHORT_KEEP:
        return False
    return True

def _extract_keyword_ngrams(caption, ngram_range=(1, 3)):
    """Extrait des n-grams candidats depuis une caption en prose libre.
    Decoupe en phrases, retire les stopwords, garde les sequences continues
    de tokens utiles. Retourne 1-grams, 2-grams et 3-grams sans doublon.

    Exemple sur 'The image shows a young man lying on the beach with his
    tentacles wrapped around his body' :
    -> young, man, beach, tentacles, body, young man, ...
    """
    if not caption:
        return []
    text = str(caption)
    # On decoupe par ponctuation forte pour eviter de chevaucher des phrases
    # qui n'ont rien a voir entre elles.
    sentences = re.split(r"[.!?;:\n,()\[\]{}\"]+", text)
    out = []
    seen = set()
    lo, hi = ngram_range
    for sent in sentences:
        tokens = _TOKEN_RE.findall(sent)
        # On marque chaque token comme utile ou non, puis on extrait les
        # n-grams qui ne contiennent QUE des tokens utiles (pas de stopword
        # au milieu). Ca capture 'young man', 'wet suit', 'cloudy sky' mais
        # pas 'man on beach' (car 'on' est stopword).
        useful_flags = [_is_useful_token(t) for t in tokens]
        n = len(tokens)
        i = 0
        while i < n:
            if not useful_flags[i]:
                i += 1
                continue
            # On etend le run de tokens utiles consecutifs
            j = i
            while j < n and useful_flags[j]:
                j += 1
            # On extrait tous les n-grams de longueur [lo, hi] dans ce run
            run = tokens[i:j]
            run_len = len(run)
            for size in range(lo, hi + 1):
                if size > run_len:
                    break
                for k in range(run_len - size + 1):
                    ngram_tokens = run[k:k + size]
                    ngram = " ".join(ngram_tokens)
                    # Filtre final via _is_valid_keyword (taille, phrase hints)
                    if not _is_valid_keyword(ngram):
                        continue
                    key = ngram.lower()
                    if key in seen:
                        continue
                    seen.add(key)
                    out.append(ngram)
            i = j
    return out

def _shared_caption_candidates(dataset):
    """Compte les mots-clés partagés entre captions, en ignorant les fragments
    qui ne ressemblent pas à des tags (phrases longues, descriptions VLM).

    Deux passes :
    1) Split par virgule (efficace pour les captions de type 'tag1, tag2, ...').
    2) Extraction de n-grams (1, 2 et 3 mots) pour les captions en prose pure
       type VLM ('The image shows a young man lying on the beach...').
    Les deux passes sont fusionnees et triees par frequence inter-images.
    """
    counts = Counter()
    canonical = {}
    for item in dataset or []:
        seen = set()
        caption = item.get("caption", "")
        # Passe 1 : tags separes par virgules
        for tag in _caption_tags(caption):
            if not _is_valid_keyword(tag):
                continue
            key = tag.lower()
            if key in seen:
                continue
            seen.add(key)
            counts[key] += 1
            canonical.setdefault(key, tag)
        # Passe 2 : n-grams extraits de la prose
        for ngram in _extract_keyword_ngrams(caption):
            key = ngram.lower()
            if key in seen:
                continue
            seen.add(key)
            counts[key] += 1
            canonical.setdefault(key, ngram)
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], canonical.get(kv[0], kv[0])))
    return [(canonical.get(key, key), count) for key, count in ranked]

def _detect_trigger_words(dataset, candidates):
    """Repère les tags ressemblant à des triggers LoRA dans les premières positions
    de captions et parmi les candidats. Retourne une liste ordonnée par fréquence."""
    triggers = []
    seen = set()
    # 1) Premier tag de chaque caption : très souvent le trigger
    head_counts = Counter()
    for item in dataset or []:
        tags = _caption_tags(item.get("caption", ""))
        for t in tags[:2]:  # on tolère trigger sur position 1 ou 2
            if _looks_like_trigger(t):
                head_counts[t.lower()] += 1
    # On classe par fréquence en tête
    canonical_head = {}
    for item in dataset or []:
        for t in _caption_tags(item.get("caption", ""))[:2]:
            canonical_head.setdefault(t.lower(), t)
    for key, _ in head_counts.most_common():
        canonical = canonical_head.get(key, key)
        if canonical.lower() not in seen:
            triggers.append(canonical)
            seen.add(canonical.lower())
    # 2) Filet de sécurité : triggers détectés dans les candidats globaux
    for tag, _ in candidates:
        if _looks_like_trigger(tag) and tag.lower() not in seen:
            triggers.append(tag)
            seen.add(tag.lower())
    return triggers

# --- Deduplication intelligente de la recette finale ---
# Tags "trop generiques" pour rester en doublon avec leur version specifique.
# Ex: "AI" est rarement utile seul si "AI generated" est present, mais "dark"
# garde sa valeur meme si "dark mysterious" est present (concepts distincts).
_GENERIC_SHORT_TAGS = frozenset([
    "ai", "art", "photo", "image", "picture", "shot", "view",
    "man", "woman", "person", "people", "body", "face", "head",
    "color", "colour", "style", "look", "mood", "tone",
])

def _normalize_tag_for_dedup(tag):
    """Normalisation pour comparer des variantes orthographiques.
    Met en minuscules, retire ponctuation legere et pluriels simples."""
    t = tag.lower().strip()
    # Retire ponctuation et separateurs internes (D4lle, Dall-e, Dall_e -> meme racine)
    t = re.sub(r"[\-_\.\s]+", "", t)
    # Pluriel anglais simple
    if t.endswith("ies") and len(t) > 4:
        t = t[:-3] + "y"
    elif t.endswith("es") and len(t) > 4:
        t = t[:-2]
    elif t.endswith("s") and len(t) > 3 and not t.endswith("ss"):
        t = t[:-1]
    # Leetspeak basique : remplace chiffres frequents par leur lettre
    leet = {"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a"}
    t = "".join(leet.get(c, c) for c in t)
    return t

def _are_orthographic_variants(a, b, threshold=0.82):
    """True si a et b sont des variantes orthographiques tres proches
    (ex: 'D4lle' vs 'Dall-e' apres normalisation leetspeak + ponctuation)."""
    na, nb = _normalize_tag_for_dedup(a), _normalize_tag_for_dedup(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    # Difference de longueur trop grande : pas des variantes
    if abs(len(na) - len(nb)) > max(2, min(len(na), len(nb)) // 3):
        return False
    return SequenceMatcher(None, na, nb).ratio() >= threshold

def _deduplicate_recipe(tags, freq_lookup=None):
    """Deduplique une liste de tags en 3 passes :
    1) Doublons exacts (deja garantis par seen_low en amont, mais on re-verifie).
    2) Variantes orthographiques (D4lle/Dall-e, leetspeak/typos).
    3) Inclusion stricte d'un tag court generique dans un tag plus long
       (AI / AI generated, photo / black photo).

    `freq_lookup` (dict tag.lower() -> count) sert a choisir laquelle garder :
    on prefere la variante la plus frequente, sinon la plus longue, sinon la
    premiere rencontree.
    """
    if not tags:
        return []
    freq = freq_lookup or {}

    def _score(t):
        # Plus le score est haut, plus le tag est "interessant" a garder.
        return (freq.get(t.lower(), 0), len(t))

    result = []
    for tag in tags:
        t_low = tag.lower()
        merged = False
        for i, kept in enumerate(result):
            k_low = kept.lower()
            # Passe 1 : identique (case-insensitive)
            if t_low == k_low:
                merged = True
                break
            # Passe 2 : variantes orthographiques (D4lle vs Dall-e)
            if _are_orthographic_variants(tag, kept):
                # On garde celle qui a le meilleur score
                if _score(tag) > _score(kept):
                    result[i] = tag
                merged = True
                break
            # Passe 3 : inclusion stricte d'un generique court
            kept_words = k_low.split()
            tag_words = t_low.split()
            # Le candidat court est-il un generique inclus dans le plus long ?
            if len(tag_words) == 1 and tag_words[0] in _GENERIC_SHORT_TAGS:
                if tag_words[0] in kept_words and len(kept_words) > 1:
                    merged = True  # on garde le plus long deja en place
                    break
            if len(kept_words) == 1 and kept_words[0] in _GENERIC_SHORT_TAGS:
                if kept_words[0] in tag_words and len(tag_words) > 1:
                    # Le nouveau est plus specifique : on remplace
                    result[i] = tag
                    merged = True
                    break
        if not merged:
            result.append(tag)
    return result

def _parse_ai_recipe_tags(ai_text, allowed_tags, limit):
    allowed_map = {tag.lower(): tag for tag in allowed_tags}
    cleaned = re.sub(r"```.*?```", " ", str(ai_text or ""), flags=re.S)
    cleaned = cleaned.replace("\n", ",").replace(";", ",").replace("|", ",")
    parts = re.split(r",|•|- |\d+\.", cleaned)
    result = []
    seen = set()
    for part in parts:
        tag = re.sub(r"^[\s:]+|[\s.]+$", "", part).strip("\"'`")
        tag = re.sub(r"\s+", " ", tag)
        if not tag:
            continue
        tag = re.sub(r"^(keywords?|mots-cl[ée]s?|tags?)\s*:\s*", "", tag, flags=re.I).strip()
        # Garde-fou final : on rejette les fragments qui ne ressemblent pas
        # à un mot-clé (phrase recopiée par un LLM trop bavard).
        if not _is_valid_keyword(tag):
            continue
        key = tag.lower()
        if key in allowed_map:
            tag = allowed_map[key]
        elif key not in allowed_map:
            continue
        if key not in seen:
            result.append(tag)
            seen.add(key)
        if len(result) >= limit:
            break
    return result

def auto_fill_recipe_from_ai(dataset, count, api_backend, api_url, llm_model, temp, ctx, sys_prompt, lang, api_key="", timeout=180):
    m = MSG.get(lang, MSG.get("FR", {}))
    if not dataset:
        msg = m.get("no_dataset", "No dataset.")
        gr.Warning(msg)
        return gr.update(), msg

    try:
        limit = max(1, min(100, int(float(count or 20))))
    except Exception:
        limit = 20

    candidates = _shared_caption_candidates(dataset)
    if not candidates:
        msg = m.get("ai_recipe_no_tags", "⚠️ No usable caption keywords found.")
        gr.Warning(msg)
        return gr.update(), msg

    # Triggers détectés en amont : on les épinglera en tête, quoi que dise le LLM.
    triggers = _detect_trigger_words(dataset, candidates)

    dataset_dir = os.path.dirname(dataset[0].get("img_path", "")) if dataset else ""
    dataset_name = os.path.basename(dataset_dir) or "dataset"
    total = len(dataset)
    candidate_limit = max(limit * 5, 120)
    candidate_lines = "\n".join(
        f"- {tag} ({count}/{total})" for tag, count in candidates[:candidate_limit]
    )
    fallback_tags = [tag for tag, _ in candidates[:limit]]
    trigger_hint = (
        f"\nTriggers detectes a placer en TETE: {', '.join(triggers[:3])}\n"
        if triggers else ""
    )
    # Prompt strict : on impose le format, on donne un exemple positif et
    # un exemple negatif, on interdit explicitement les descriptions VLM.
    prompt = (
        "Tu es un assistant expert en datasets LoRA / Flux / Stable Diffusion.\n"
        f"Dataset: {dataset_name}\n"
        f"Nombre d'images analysees: {total}\n"
        f"Objectif: produire une RECETTE GLOBALE de {limit} mots-cles au maximum.\n"
        "\n"
        "REGLES STRICTES (obligatoires):\n"
        "1. Reponds UNIQUEMENT par une seule ligne de mots-cles separes par des virgules.\n"
        "2. Chaque mot-cle fait MOINS DE 6 MOTS (ex: 'pup play mask', 'studio lighting').\n"
        "3. INTERDIT de recopier des phrases complètes comme 'The image shows...' ou 'a portrait of a woman with...'.\n"
        "4. INTERDIT d'inclure des verbes conjugues de description ('is wearing', 'appears to be', 'porte un', etc.).\n"
        "5. Place le trigger word/concept (s'il existe) EN PREMIERE position.\n"
        "6. Choisis les mots-cles les plus partages entre images, puis les concepts distinctifs.\n"
        "7. INTERDIT les doublons : un seul mot-cle par concept. Pas de 'AI' + 'AI generated', pas de 'Dall-e' + 'Dall-e style', pas de 'D4lle' + 'Dall-e' (memes triggers en variantes orthographiques).\n"
        "8. Aucune explication, aucun titre, aucun prefixe type 'Keywords:'.\n"
        "\n"
        "EXEMPLE DE BONNE REPONSE:\n"
        "D4lle, Dall-e style, AI generated, romantic atmosphere, dramatic lighting, portrait, dark background\n"
        "\n"
        "EXEMPLE DE MAUVAISE REPONSE (a ne pas faire):\n"
        "D4lle, The image is a close-up portrait of a woman with bright yellow hair, AI generated\n"
        f"{trigger_hint}"
        f"\nMots-cles candidats (frequence sur le dataset):\n{candidate_lines}\n"
        "\n"
        f"Reponds maintenant avec UNE SEULE LIGNE de {limit} mots-cles maximum, separes par des virgules."
    )

    ai_response = call_ai_api(
        prompt, llm_model, None, api_backend, api_url, temp, ctx, sys_prompt, api_key=api_key, timeout=timeout
    )
    allowed_tags = [tag for tag, _ in candidates]
    picked = []
    if ai_response and not str(ai_response).startswith("Erreur API"):
        picked = _parse_ai_recipe_tags(ai_response, allowed_tags, limit)
    else:
        gr.Warning(str(ai_response or m.get("error", "Error.")))

    # Table de frequences (utilisee par la dedup pour choisir la meilleure variante)
    freq_lookup = {tag.lower(): count for tag, count in candidates}

    # On assemble une liste large (triggers + IA + fallback) SANS limiter,
    # puis on deduplique intelligemment, puis on coupe a `limit`. Ainsi la
    # dedup peut absorber les variantes et le pool reste assez riche pour
    # remplir la recette demandee.
    raw = []
    seen_exact = set()
    # 1) Triggers detectes en TETE (priorite absolue)
    for trig in triggers:
        if trig.lower() in seen_exact:
            continue
        raw.append(trig)
        seen_exact.add(trig.lower())
    # 2) Selection IA
    for tag in picked:
        if tag.lower() in seen_exact:
            continue
        raw.append(tag)
        seen_exact.add(tag.lower())
    # 3) Filet de securite : candidats les plus partages
    # On prend large pour avoir une marge apres dedup.
    for tag in [t for t, _ in candidates[:limit * 3]]:
        if tag.lower() in seen_exact:
            continue
        raw.append(tag)
        seen_exact.add(tag.lower())

    # Dedup variantes orthographiques + inclusions generiques
    deduped = _deduplicate_recipe(raw, freq_lookup=freq_lookup)

    # On reordonne pour replacer les triggers en tete (la dedup peut les avoir
    # remplaces par une variante; on garantit le placement en tete).
    trigger_set = {_normalize_tag_for_dedup(t) for t in triggers}
    head = [t for t in deduped if _normalize_tag_for_dedup(t) in trigger_set]
    tail = [t for t in deduped if _normalize_tag_for_dedup(t) not in trigger_set]
    final = (head + tail)[:limit]

    recipe = ", ".join(final)
    msg = m.get("ai_recipe_success", "✅ AI recipe generated from {count} captions: {tags} keywords.").format(
        count=total, tags=len(final)
    )
    gr.Info(msg)
    return recipe, msg

def analyze_dataset(dataset, tracked_words_str, lang):
    lang = lang or "FR"
    if not dataset: 
        empty_df = pd.DataFrame()
        return None, None, empty_df, "{}", empty_df, "{}", MSG[lang].get("no_dataset", "")
    if not tracked_words_str: 
        empty_conf = pd.DataFrame([{MSG[lang].get("df_prio", "Prio"): 1, MSG[lang].get("df_kw", "Kw"): "", MSG[lang].get("df_tgt", "Tgt"): 0}])
        empty_stats = pd.DataFrame([{MSG[lang].get("df_kw", "Kw"): "", MSG[lang].get("df_tgt", "Tgt"): ""}])
        return None, None, empty_stats, "{}", empty_conf, "{}", MSG[lang].get("enter_keywords", "")
    
    total_images = len(dataset)
    raw_words = [w.strip() for w in tracked_words_str.split(',') if w.strip()]
    targets = {}; stats = {}
    for w in raw_words:
        if ':' in w:
            parts = w.split(':'); word = parts[0].strip()
            try: targets[word] = float(parts[1].strip())
            except: targets[word] = 0.0
            stats[word] = 0
        else: stats[w] = 0
    for item in dataset:
        cap = item['caption'].lower()
        for word in stats.keys():
            if re.search(r'\b' + re.escape(word.lower()) + r'\b', cap): stats[word] += 1
    
    df_stats = []
    for word, count in stats.items():
        pct = (count / total_images) * 100 if total_images > 0 else 0
        row = {MSG[lang].get("df_kw", "Keyword"): word, "Count" if lang=="EN" else "Compte": count, "Current %" if lang=="EN" else "Actuel %": f"{pct:.1f}%"}
        if word in targets:
            row[MSG[lang].get("df_tgt", "Target %")] = f"{targets[word]}%"
            row["Diff" if lang=="EN" else "Écart"] = f"{'+' if (pct - targets[word])>0 else ''}{pct - targets[word]:.1f}%"
        else:
            row[MSG[lang].get("df_tgt", "Target %")] = "-"; row["Diff" if lang=="EN" else "Écart"] = "-"
        df_stats.append(row)
        
    df = pd.DataFrame(df_stats).sort_values(by="Count" if lang=="EN" else "Compte", ascending=False)
    df_json = df.to_json(orient='records')
    
    df_config = []
    for i, word in enumerate(stats.keys()):
        cible = targets.get(word, 0)
        df_config.append({MSG[lang].get("df_prio", "Priority"): i+1, MSG[lang].get("df_kw", "Keyword"): word, MSG[lang].get("df_tgt", "Target %"): cible})
    df_conf = pd.DataFrame(df_config)
    df_conf_json = df_conf.to_json(orient='records')

    pie_data = {k: v for k, v in stats.items() if v > 0}
    if not pie_data:
        fig_pie = px.pie(names=[MSG[lang].get("none", "None")], values=[1], title=MSG[lang].get("no_tag_found", "No tag"))
        fig_bar = px.bar(x=[MSG[lang].get("none", "None")], y=[0], title=MSG[lang].get("no_tag_found", "No tag"))
    else:
        fig_pie = px.pie(names=list(pie_data.keys()), values=list(pie_data.values()), title=MSG[lang].get("overall_dist", "Distribution"))
        fig_pie.update_traces(textposition='inside', textinfo='percent+label')
        fig_bar = px.bar(x=list(pie_data.keys()), y=list(pie_data.values()), title=MSG[lang].get("occ_by_keyword", "Occurrences"))
    
    return fig_pie, fig_bar, df, df_json, df_conf, df_conf_json, MSG[lang].get("stats_updated", "Updated")

def toggle_tracked_word(current_tracker, selected_text):
    if not selected_text: return gr.update()
    word = selected_text.strip(', ')
    if not word: return gr.update()
    current_list = [w.strip() for w in current_tracker.split(',') if w.strip()]
    existing = []; found = False
    for w in current_list:
        if w.split(':')[0].strip().lower() == word.lower(): found = True 
        else: existing.append(w)
    if not found: existing.append(word) 
    return ", ".join(existing)

def scan_duplicates_advanced(dataset, tolerance, algo="phash"):
    if not HAS_IMAGEHASH:
        gr.Warning("Installez imagehash: pip install imagehash")
        return gr.update(choices=[], value=None), {}
    
    hashes = {}
    dups_pairs = []
    hash_fn = getattr(imagehash, str(algo or "phash"), imagehash.phash)
    
    for item in dataset:
        try:
            img = Image.open(item['img_path'])
            h = hash_fn(img)
            
            found_dup = False
            for prev_h, prev_item in hashes.items():
                if abs(h - prev_h) <= int(tolerance):
                    pair_name = f"{prev_item['img_name']} VS {item['img_name']}"
                    dups_pairs.append({
                        "name": pair_name, 
                        "imgA": prev_item['img_path'], "imgB": item['img_path'],
                        "idA": prev_item['id'], "idB": item['id']
                    })
                    found_dup = True
                    break
            if not found_dup: hashes[h] = item
        except: pass
    
    if not dups_pairs:
        gr.Info("Aucun doublon visuel trouvé avec cette tolérance !")
        return gr.update(choices=[], value=None), {}
        
    choices = [p["name"] for p in dups_pairs]
    mapping = {p["name"]: p for p in dups_pairs}
    gr.Warning(f"{len(choices)} paires suspectes trouvées !")
    return gr.update(choices=choices, value=choices[0]), mapping

def load_duplicate_pair(pair_name, mapping, dataset, lang):
    if not pair_name or pair_name not in mapping: return None, None, -1, -1, "", "", ""
    data = mapping[pair_name]
    cap_a = next((x.get('caption', '') for x in dataset if x.get('id') == data["idA"]), "")
    cap_b = next((x.get('caption', '') for x in dataset if x.get('id') == data["idB"]), "")
    recommendation, _ = _duplicate_recommendation(pair_name, mapping, dataset, lang)
    return data["imgA"], data["imgB"], data["idA"], data["idB"], cap_a, cap_b, recommendation

def delete_duplicate(dataset, filtered_dataset, id_to_delete, pair_name, mapping, lang):
    if id_to_delete < 0:
        return dataset, filtered_dataset, get_gallery_items(filtered_dataset, lang), gr.update(), mapping, "Erreur suppression"
    item_to_del = next((x for x in dataset if x['id'] == id_to_delete), None)
    if item_to_del:
        try:
            os.remove(item_to_del['img_path'])
            if os.path.exists(item_to_del['txt_path']): os.remove(item_to_del['txt_path'])
            dataset = [x for x in dataset if x['id'] != id_to_delete]
            filtered_dataset = [x for x in filtered_dataset if x['id'] != id_to_delete]
            _reindex_dataset(dataset)
            id_by_path = {item.get('img_path'): item.get('id') for item in dataset}
            for item in filtered_dataset:
                if item.get('img_path') in id_by_path:
                    item['id'] = id_by_path[item.get('img_path')]
            gr.Info(f"Fichier {item_to_del['img_name']} supprimé.")
        except Exception as e:
            gr.Warning(f"Impossible de supprimer: {e}")
            
    if pair_name in mapping:
        del mapping[pair_name]
    mapping = _refresh_duplicate_mapping_ids(mapping, dataset)
        
    choices = list(mapping.keys())
    val = choices[0] if choices else None
    return dataset, filtered_dataset, get_gallery_items(filtered_dataset, lang), gr.update(choices=choices, value=val), mapping, f"Supprimé. Reste {len(choices)} doublons."

def skip_duplicate(pair_name, mapping):
    if pair_name and pair_name in mapping:
        del mapping[pair_name]
    choices = list(mapping.keys()) if mapping else []
    val = choices[0] if choices else None
    return gr.update(choices=choices, value=val), mapping, f"Ignoré. Reste {len(choices)} doublons."

def delete_all_duplicates_b(dataset, filtered_dataset, mapping, lang):
    if not mapping:
        return dataset, filtered_dataset, get_gallery_items(filtered_dataset, lang), gr.update(choices=[], value=None), {}, "Aucun doublon à supprimer."
    ids_to_delete = {data.get("idB") for data in mapping.values() if data.get("idB") is not None}
    deleted = 0
    errors = []
    for item in list(dataset):
        if item.get('id') not in ids_to_delete:
            continue
        try:
            if os.path.exists(item['img_path']):
                os.remove(item['img_path'])
            if os.path.exists(item['txt_path']):
                os.remove(item['txt_path'])
            deleted += 1
        except Exception as e:
            errors.append(f"{item.get('img_name', '')}: {e}")
    dataset = [x for x in dataset if x.get('id') not in ids_to_delete]
    filtered_dataset = [x for x in filtered_dataset if x.get('id') not in ids_to_delete]
    _reindex_dataset(dataset)
    id_by_path = {item.get('img_path'): item.get('id') for item in dataset}
    for item in filtered_dataset:
        if item.get('img_path') in id_by_path:
            item['id'] = id_by_path[item.get('img_path')]
    msg = f"🗑️ {deleted} fichiers B supprimés."
    if errors:
        msg += f" ⚠️ {len(errors)} erreurs."
    gr.Info(msg)
    return dataset, filtered_dataset, get_gallery_items(filtered_dataset, lang), gr.update(choices=[], value=None), {}, msg

def _image_metrics(path):
    metrics = {"pixels": 0, "size": 0, "dims": "?", "exists": False}
    try:
        if os.path.exists(path):
            metrics["exists"] = True
            metrics["size"] = os.path.getsize(path)
        with Image.open(path) as img:
            w, h = img.size
            metrics["pixels"] = w * h
            metrics["dims"] = f"{w}x{h}"
    except Exception:
        pass
    return metrics

def _duplicate_recommendation(pair_name, mapping, dataset, lang):
    if not pair_name or pair_name not in (mapping or {}):
        return "", None
    data = mapping[pair_name]
    item_a = next((x for x in dataset or [] if x.get('id') == data.get("idA")), None)
    item_b = next((x for x in dataset or [] if x.get('id') == data.get("idB")), None)
    if not item_a or not item_b:
        return "", None

    metrics_a = _image_metrics(item_a.get("img_path", ""))
    metrics_b = _image_metrics(item_b.get("img_path", ""))
    cap_a = len(str(item_a.get("caption", "")).strip())
    cap_b = len(str(item_b.get("caption", "")).strip())
    score_a = metrics_a["pixels"] + cap_a * 800 + metrics_a["size"] * 0.02
    score_b = metrics_b["pixels"] + cap_b * 800 + metrics_b["size"] * 0.02
    recommended_item = item_a if score_a < score_b else item_b
    recommended_label = "A" if recommended_item is item_a else "B"
    reasons = []
    if metrics_a["pixels"] != metrics_b["pixels"]:
        smaller = "A" if metrics_a["pixels"] < metrics_b["pixels"] else "B"
        if smaller == recommended_label:
            reasons.append("résolution plus basse" if lang == "FR" else "lower resolution")
    if cap_a != cap_b:
        shorter = "A" if cap_a < cap_b else "B"
        if shorter == recommended_label:
            reasons.append("caption plus courte" if lang == "FR" else "shorter caption")
    if not reasons:
        reasons.append("meilleur candidat à retirer" if lang == "FR" else "best removal candidate")
    label = "Recommandé" if lang == "FR" else "Recommended"
    action_word = "supprimer" if lang == "FR" else "delete"
    txt = (
        f"**{label}: {action_word} {recommended_label}** · "
        f"A: {metrics_a['dims']} / {cap_a} chars · B: {metrics_b['dims']} / {cap_b} chars · "
        f"{', '.join(reasons)}"
    )
    return txt, recommended_item.get("id")

def describe_duplicate_recommendation(pair_name, mapping, dataset, lang):
    txt, _ = _duplicate_recommendation(pair_name, mapping, dataset, lang)
    return txt

def delete_recommended_duplicate(dataset, filtered_dataset, pair_name, mapping, lang):
    txt, recommended_id = _duplicate_recommendation(pair_name, mapping, dataset, lang)
    if recommended_id is None:
        return dataset, filtered_dataset, get_gallery_items(filtered_dataset, lang), gr.update(), mapping, "Aucune recommandation disponible."
    return delete_duplicate(dataset, filtered_dataset, recommended_id, pair_name, mapping, lang)

def batch_rename_dataset(dataset, prefix):
    if not dataset or not prefix.strip(): return dataset, "Veuillez entrer un préfixe."
    prefix = prefix.strip()
    count = 1
    dir_path = os.path.dirname(dataset[0]['img_path'])
    for item in dataset:
        ext = os.path.splitext(item['img_name'])[1]
        new_img_name = f"{prefix}_{count:04d}{ext}"
        new_txt_name = f"{prefix}_{count:04d}.txt"
        new_img_path = os.path.join(dir_path, new_img_name)
        new_txt_path = os.path.join(dir_path, new_txt_name)
        try:
            os.rename(item['img_path'], new_img_path)
            if os.path.exists(item['txt_path']): os.rename(item['txt_path'], new_txt_path)
            item['img_name'] = new_img_name
            item['img_path'] = new_img_path
            item['txt_path'] = new_txt_path
        except: pass
        count += 1
    gr.Info("Renommage par lot effectué !")
    return dataset, "✅ Dataset renommé."

def _prep_format_info(format_choice):
    fmt = str(format_choice or "WebP").strip().upper()
    if fmt == "PNG":
        return ".png", "PNG", {"optimize": True}
    if fmt in ("JPEG", "JPG"):
        return ".jpg", "JPEG", {"quality": 95, "optimize": True}
    return ".webp", "WEBP", {"quality": 95}

def _image_has_alpha(img):
    return img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info)

def _flatten_alpha_on_white(img):
    if img.mode == "P":
        img = img.convert("RGBA")
    if img.mode in ("RGBA", "LA"):
        alpha = img.getchannel("A") if img.mode == "RGBA" else img.getchannel(1)
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img.convert("RGBA"), (0, 0), alpha)
        return bg
    return img.convert("RGB") if img.mode != "RGB" else img

def _apply_batch_crop_mode(img, crop_mode):
    if crop_mode == "Smart Face Crop (OpenCV)" and HAS_CV2:
        img_cv = cv2.cvtColor(np.array(img.convert("RGB")), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
        face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        faces = face_cascade.detectMultiScale(gray, 1.1, 4)
        w, h = img.size
        min_dim = min(w, h)
        if len(faces) > 0:
            x, y, w_face, h_face = faces[0]
            center_x, center_y = x + w_face // 2, y + h_face // 2
            left = max(0, center_x - min_dim // 2)
            top = max(0, center_y - min_dim // 2)
            right = min(w, left + min_dim)
            bottom = min(h, top + min_dim)
            if right - left < min_dim:
                left = right - min_dim
            if bottom - top < min_dim:
                top = bottom - min_dim
            return img.crop((left, top, right, bottom))
        return img.crop(((w - min_dim) / 2, (h - min_dim) / 2, (w + min_dim) / 2, (h + min_dim) / 2))
    if crop_mode == "1:1 (Carré Centre)":
        w, h = img.size
        min_dim = min(w, h)
        return img.crop(((w - min_dim) / 2, (h - min_dim) / 2, (w + min_dim) / 2, (h + min_dim) / 2))
    return img

def _prepare_image_for_export(img, target_size, format_choice, crop_mode="Conserver Ratio", handle_alpha=True):
    _, save_format, _ = _prep_format_info(format_choice)
    img = img.copy()
    img = _apply_batch_crop_mode(img, crop_mode)

    if _image_has_alpha(img) and (handle_alpha or save_format == "JPEG"):
        img = _flatten_alpha_on_white(img)
    elif save_format in ("PNG", "WEBP") and _image_has_alpha(img):
        img = img.convert("RGBA")
    elif img.mode not in ("RGB", "L"):
        img = img.convert("RGB")

    img.thumbnail((int(target_size), int(target_size)), Image.Resampling.LANCZOS)
    return img

def _copy_caption_for_export(item, dest_folder):
    txt_path = item.get("txt_path")
    new_txt_name = os.path.splitext(item.get("img_name", "caption"))[0] + ".txt"
    dest_txt = os.path.join(dest_folder, new_txt_name)
    if txt_path and os.path.exists(txt_path):
        shutil.copy2(txt_path, dest_txt)
    else:
        with open(dest_txt, "w", encoding="utf-8") as f:
            f.write(str(item.get("caption", "")))
    return dest_txt

PREP_WORKFLOW_PRESETS = {
    "Flux LoRA 1024 · WebP": {"size": "1024", "format": "WebP", "crop": "Conserver Ratio", "alpha": True},
    "Flux carré 1024 · WebP": {"size": "1024", "format": "WebP", "crop": "1:1 (Carré Centre)", "alpha": True},
    "PNG transparent 1024": {"size": "1024", "format": "PNG", "crop": "Conserver Ratio", "alpha": False},
    "JPEG léger 768": {"size": "768", "format": "JPEG", "crop": "Conserver Ratio", "alpha": True},
    "Portrait smart crop 1024": {"size": "1024", "format": "JPEG", "crop": "Smart Face Crop (OpenCV)", "alpha": True},
}

def _auto_prep_dest(items, size, format_choice):
    dataset_dir = os.path.dirname(items[0].get('img_path', "")) if items else os.getcwd()
    fmt = str(format_choice or "WebP").strip().lower().replace("jpeg", "jpg")
    return os.path.join(dataset_dir, f"_processed_{size}_{fmt}")

def apply_prep_workflow_preset(name):
    preset = PREP_WORKFLOW_PRESETS.get(name or "")
    if not preset:
        return gr.update(), gr.update(), gr.update(), gr.update(), gr.update()
    return (
        gr.update(value=preset["size"]),
        gr.update(value=preset["format"]),
        gr.update(value=preset["crop"]),
        gr.update(value=preset["alpha"]),
        gr.update(value=""),
    )

def prep_workflow_summary(dataset, selected_ids, dest_folder, size, format_choice, crop_mode, handle_alpha, lang):
    total = len(dataset or [])
    selected = len(selected_ids or [])
    target = selected if selected else total
    auto_dest = _auto_prep_dest(dataset or [], size or "1024", format_choice or "WebP")
    dest = str(dest_folder or "").strip() or auto_dest
    scope = f"{target} image(s)"
    if selected:
        scope += " sélectionnée(s)" if lang == "FR" else " selected"
    elif total:
        scope += " du dataset" if lang == "FR" else " from dataset"
    else:
        scope = "aucun dataset" if lang == "FR" else "no dataset"
    alpha_txt = "fond transparent aplati" if handle_alpha and lang == "FR" else "alpha flattened" if handle_alpha else "alpha conservé" if lang == "FR" else "alpha preserved"
    title = "Résumé avant traitement" if lang == "FR" else "Processing summary"
    return (
        f"<div class='prep-summary-box'><strong>{title}</strong>"
        f"<span>{scope}</span>"
        f"<span>{size}px · {format_choice} · {crop_mode}</span>"
        f"<span>{alpha_txt}</span>"
        f"<span class='prep-summary-path'>{html.escape(dest)}</span></div>"
    )

def render_manual_cropper(lang):
    if lang == "FR":
        empty = "Chargez l'image courante pour commencer."
        help_txt = "Cadre fixe: glissez l'image sous le cadre. Molette: zoom/dezoom. Libre: déplacez les coins du cadre. Raccourcis: ←/→ image precedente/suivante, ↑/↓ inverse portrait/paysage, Entree ecrase le crop et passe a l'image suivante."
        load = "Charger l'image courante"
        overwrite = "Écraser l'image courante"
        ratios = [("free", "Libre"), ("1:1", "1:1"), ("4:5", "4:5"), ("3:4", "3:4"), ("16:9", "16:9")]
    else:
        empty = "Load the current image to begin."
        help_txt = "Fixed frame: drag the image under the frame. Mouse wheel: zoom in/out. Free: drag frame corners. Shortcuts: Left/Right previous/next image, Up/Down flips portrait/landscape, Enter overwrites the crop and moves to the next image."
        load = "Load current image"
        overwrite = "Overwrite current image"
        ratios = [("free", "Free"), ("1:1", "1:1"), ("4:5", "4:5"), ("3:4", "3:4"), ("16:9", "16:9")]
    ratio_buttons = "".join(
        f"<button type='button' class='manual-ratio-btn{' active' if value == '1:1' else ''}' data-ratio='{html.escape(value)}'>{html.escape(label)}</button>"
        for value, label in ratios
    )
    return f"""
<div id="manual_crop_canvas_tool" data-empty="{html.escape(empty, quote=True)}">
  <div class="manual-crop-toolbar">
    <button type="button" id="manual_crop_use_loaded">↙️ {html.escape(load)}</button>
    {ratio_buttons}
    <button type="button" id="manual_crop_overwrite" class="primary">💾 {html.escape(overwrite)}</button>
    <span id="manual_crop_canvas_status" class="manual-crop-status">{html.escape(empty)}</span>
  </div>
  <div id="manual_crop_canvas_wrap">
    <canvas id="manual_crop_canvas"></canvas>
  </div>
  <div class="manual-crop-help">{html.escape(help_txt)}</div>
</div>
"""

def batch_process_images(dataset, selected_ids, dest_folder, size, format_choice, crop_mode, handle_alpha, progress=gr.Progress()):
    if not dataset: return "Aucun dataset."
    if not dest_folder: dest_folder = _auto_prep_dest(dataset, size, format_choice)
    os.makedirs(dest_folder, exist_ok=True)
    count = 0
    target_size = int(size)
    selected_ids = set(selected_ids or [])
    items_to_process = [item for item in dataset if not selected_ids or item.get('id') in selected_ids]
    total = len(items_to_process)
    ext, save_format, save_kwargs = _prep_format_info(format_choice)
    for i, item in enumerate(items_to_process):
        try:
            if progress:
                progress((i + 1) / total if total else 1, desc=f"Traitement {i+1}/{total} : {item['img_name']}")
            with Image.open(item['img_path']) as src_img:
                img = _prepare_image_for_export(src_img, target_size, format_choice, crop_mode, handle_alpha)
            new_name = os.path.splitext(item['img_name'])[0] + ext
            save_path = os.path.join(dest_folder, new_name)
            img.save(save_path, format=save_format, **save_kwargs)
            _copy_caption_for_export(item, dest_folder)
            count += 1
        except Exception as e: print(f"Erreur pré-traitement sur {item['img_name']}: {e}")
    return f"✅ {count} images traitées avec succès !"

def _get_filtered_item(filtered_dataset, current_idx):
    if not filtered_dataset:
        return None, -1
    try:
        idx = int(current_idx)
    except Exception:
        idx = 0
    idx = max(0, min(idx, len(filtered_dataset) - 1))
    return filtered_dataset[idx], idx

def _extract_editor_image(editor_value):
    if editor_value is None:
        return None
    if isinstance(editor_value, Image.Image):
        return editor_value.copy()
    if isinstance(editor_value, str) and os.path.exists(editor_value):
        return Image.open(editor_value)
    if isinstance(editor_value, dict):
        for key in ("composite", "image", "background"):
            img = editor_value.get(key)
            extracted = _extract_editor_image(img)
            if extracted is not None:
                return extracted
    if "np" in globals() and hasattr(editor_value, "shape"):
        return Image.fromarray(editor_value)
    return None

def load_manual_crop_image(filtered_dataset, current_idx, lang):
    item, idx = _get_filtered_item(filtered_dataset, current_idx)
    if not item:
        msg = "Aucune image à charger." if lang == "FR" else "No image to load."
        return gr.update(value=None), msg
    msg = f"✂️ Image chargée pour crop manuel : {item.get('img_name', '')}"
    if lang == "EN":
        msg = f"✂️ Loaded for manual crop: {item.get('img_name', '')}"
    return gr.update(value=item.get("img_path")), msg

def save_manual_crop_image(editor_value, filtered_dataset, current_idx, dest_folder, size, format_choice, handle_alpha, lang):
    item, idx = _get_filtered_item(filtered_dataset, current_idx)
    if not item:
        return "Aucune image sélectionnée." if lang == "FR" else "No selected image."
    img = _extract_editor_image(editor_value)
    if img is None:
        return "Chargez ou recadrez une image avant de sauvegarder." if lang == "FR" else "Load or crop an image before saving."
    if not dest_folder:
        dest_folder = _auto_prep_dest(filtered_dataset or [], size, format_choice)
    os.makedirs(dest_folder, exist_ok=True)
    try:
        ext, save_format, save_kwargs = _prep_format_info(format_choice)
        processed = _prepare_image_for_export(img, int(size), format_choice, "Conserver Ratio", handle_alpha)
        save_path = os.path.join(dest_folder, os.path.splitext(item.get("img_name", "image"))[0] + ext)
        processed.save(save_path, format=save_format, **save_kwargs)
        _copy_caption_for_export(item, dest_folder)
        msg = f"✅ Crop sauvegardé : {os.path.basename(save_path)}"
        return msg if lang == "FR" else f"✅ Crop saved: {os.path.basename(save_path)}"
    except Exception as e:
        return f"Erreur crop manuel : {e}" if lang == "FR" else f"Manual crop error: {e}"

def save_manual_crop_and_next(editor_value, filtered_dataset, current_idx, dest_folder, size, format_choice, handle_alpha, tracked_words, lang):
    status = save_manual_crop_image(editor_value, filtered_dataset, current_idx, dest_folder, size, format_choice, handle_alpha, lang)
    if not filtered_dataset:
        return gr.update(value=None), status, "", get_highlighted_html("", tracked_words), update_word_count("", lang), -1, ""
    _, idx = _get_filtered_item(filtered_dataset, current_idx)
    next_idx = min(idx + 1, len(filtered_dataset) - 1)
    next_item = filtered_dataset[next_idx]
    cap, hl, wc = get_updated_viewer_data(filtered_dataset, next_idx, tracked_words, lang)
    viewer_status = f"Viewing: {next_item.get('img_name', '')}"
    if lang == "FR":
        viewer_status = f"Affichage : {next_item.get('img_name', '')}"
    return gr.update(value=next_item.get("img_path")), status, next_item.get("img_path"), hl, cap, wc, next_idx, viewer_status

def _save_image_over_original(img, path):
    ext = os.path.splitext(path)[1].lower()
    if ext in (".jpg", ".jpeg"):
        img = img.convert("RGB")
        img.save(path, format="JPEG", quality=95, optimize=False)
    elif ext == ".webp":
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGB")
        img.save(path, format="WEBP", quality=95, method=0)
    elif ext == ".png":
        img.save(path, format="PNG", optimize=False)
    else:
        img.convert("RGB").save(path)
    try:
        os.utime(path, None)
    except Exception:
        pass

def overwrite_manual_crop_from_payload(payload, dataset, filtered_dataset, current_idx, tracked_words, lang):
    item, idx = _get_filtered_item(filtered_dataset, current_idx)
    if not item:
        msg = "Aucune image sélectionnée." if lang == "FR" else "No selected image."
        return dataset, filtered_dataset, gr.update(), "", get_highlighted_html("", tracked_words), "", update_word_count("", lang), -1, msg
    try:
        data = json.loads(payload or "{}")
        go_next = bool(data.get("goNext"))
        crop = data.get("crop", {})
        x = float(crop.get("x", 0))
        y = float(crop.get("y", 0))
        w = float(crop.get("w", 0))
        h = float(crop.get("h", 0))
        if w < 2 or h < 2:
            raise ValueError("crop trop petit")
        img_path = item.get("img_path", "")
        with Image.open(img_path) as img:
            iw, ih = img.size
            left = max(0, min(iw - 1, int(round(x))))
            top = max(0, min(ih - 1, int(round(y))))
            right = max(left + 1, min(iw, int(round(x + w))))
            bottom = max(top + 1, min(ih, int(round(y + h))))
            cropped = img.crop((left, top, right, bottom))
            _save_image_over_original(cropped, img_path)
        view_idx = min(idx + 1, len(filtered_dataset) - 1) if go_next else idx
        view_item = filtered_dataset[view_idx] if filtered_dataset else item
        cap, hl, wc = get_updated_viewer_data(filtered_dataset, view_idx, tracked_words, lang)
        msg = f"✅ Image écrasée avec le crop : {item.get('img_name', '')}"
        if lang == "EN":
            msg = f"✅ Image overwritten with crop: {item.get('img_name', '')}"
        gr.Info(msg)
        return dataset, filtered_dataset, gr.update(), view_item.get("img_path", ""), hl, cap, wc, view_idx, msg
    except Exception as e:
        msg = f"Erreur écrasement crop : {e}" if lang == "FR" else f"Crop overwrite error: {e}"
        gr.Warning(msg)
        cap, hl, wc = get_updated_viewer_data(filtered_dataset, idx, tracked_words, lang)
        return dataset, filtered_dataset, gr.update(), item.get("img_path", ""), hl, cap, wc, idx, msg

def manual_crop_jump(filtered_dataset, current_idx, direction, tracked_words, lang):
    if not filtered_dataset:
        msg = "Aucune image à charger." if lang == "FR" else "No image to load."
        return gr.update(value=None), "", get_highlighted_html("", tracked_words), "", update_word_count("", lang), -1, msg, msg
    _, idx = _get_filtered_item(filtered_dataset, current_idx)
    if direction == "prev":
        next_idx = max(0, idx - 1)
    else:
        next_idx = min(len(filtered_dataset) - 1, idx + 1)
    item = filtered_dataset[next_idx]
    cap, hl, wc = get_updated_viewer_data(filtered_dataset, next_idx, tracked_words, lang)
    viewer_status = f"Viewing: {item.get('img_name', '')}"
    status = f"✂️ Loaded {next_idx + 1}/{len(filtered_dataset)}: {item.get('img_name', '')}"
    if lang == "FR":
        viewer_status = f"Affichage : {item.get('img_name', '')}"
        status = f"✂️ Image {next_idx + 1}/{len(filtered_dataset)} chargée : {item.get('img_name', '')}"
    return gr.update(value=item.get("img_path")), item.get("img_path"), hl, cap, wc, next_idx, viewer_status, status

def update_prep_button_label(selected_ids, lang):
    count = len(selected_ids or [])
    if count:
        label = f"Lancer sur la sélection ({count} images)" if lang == "FR" else f"Run on selection ({count} images)"
    else:
        label = UI_T.get(lang, UI_T.get("FR", {})).get("btn_prep", "Lancer le Traitement")
    return gr.update(value=label)

def detect_low_resolution_images(dataset, min_resolution, lang):
    try:
        threshold = int(float(min_resolution or 0))
    except Exception:
        threshold = 0
    rows = []
    if not dataset or threshold <= 0:
        return pd.DataFrame(columns=["ID", "Image", "Largeur", "Hauteur", "Min"]), "Aucun seuil actif."
    for item in dataset:
        try:
            with Image.open(item['img_path']) as img:
                w, h = img.size
            if min(w, h) < threshold:
                rows.append({"ID": item.get('id'), "Image": item.get('img_name'), "Largeur": w, "Hauteur": h, "Min": min(w, h)})
        except Exception:
            pass
    msg = f"🔍 {len(rows)} images sous {threshold}px."
    return pd.DataFrame(rows, columns=["ID", "Image", "Largeur", "Hauteur", "Min"]), msg

def move_low_resolution_images(dataset, filtered_dataset, min_resolution, lang):
    df, status = detect_low_resolution_images(dataset, min_resolution, lang)
    if df.empty:
        return dataset, filtered_dataset, get_gallery_items(filtered_dataset, lang), df, status, [], selection_summary_html(0, len(filtered_dataset or []), len(dataset or []), lang), "{}"
    ids_to_move = set(int(x) for x in df["ID"].dropna().tolist())
    dataset_dir = os.path.dirname(dataset[0]['img_path']) if dataset else os.getcwd()
    dest_dir = os.path.join(dataset_dir, "_trop_petites")
    os.makedirs(dest_dir, exist_ok=True)
    moved = 0
    for item in list(dataset):
        if item.get('id') not in ids_to_move:
            continue
        try:
            shutil.move(item['img_path'], os.path.join(dest_dir, item['img_name']))
            if os.path.exists(item['txt_path']):
                shutil.move(item['txt_path'], os.path.join(dest_dir, os.path.basename(item['txt_path'])))
            moved += 1
        except Exception as e:
            print(f"Erreur déplacement basse résolution {item.get('img_name')}: {e}")
    dataset = [x for x in dataset if x.get('id') not in ids_to_move]
    filtered_dataset = [x for x in filtered_dataset if x.get('id') not in ids_to_move]
    _reindex_dataset(dataset)
    id_by_path = {item.get('img_path'): item.get('id') for item in dataset}
    for item in filtered_dataset:
        if item.get('img_path') in id_by_path:
            item['id'] = id_by_path[item.get('img_path')]
    msg = f"📦 {moved} images déplacées vers {dest_dir}"
    return dataset, filtered_dataset, get_gallery_items(filtered_dataset, lang), pd.DataFrame(), msg, [], selection_summary_html(0, len(filtered_dataset or []), len(dataset or []), lang), "{}"

def update_advanced_stats(dataset):
    if not dataset: return None, None, "Aucun dataset", "Aucune contradiction"
    
    pairs = defaultdict(int)
    tag_counts = defaultdict(int)
    for item in dataset:
        tags = [t.strip().lower() for t in item['caption'].split(',') if t.strip()]
        for i in range(len(tags)):
            tag_counts[tags[i]] += 1
            for j in range(i+1, len(tags)):
                pairs[tuple(sorted([tags[i], tags[j]]))] += 1
                
    top_tags = [t for t, _ in sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:20]]
    
    z_data = []
    for t1 in top_tags:
        row = []
        for t2 in top_tags:
            if t1 == t2: row.append(0)
            else: row.append(pairs.get(tuple(sorted([t1, t2])), 0))
        z_data.append(row)
    fig_heatmap = px.imshow(z_data, x=top_tags, y=top_tags, color_continuous_scale='Viridis', title="Matrice de Co-occurrence")
    
    widths, heights, names = [], [], []
    for item in dataset:
        try:
            w, h = Image.open(item['img_path']).size
            widths.append(w); heights.append(h); names.append(item['img_name'])
        except: pass
    df_bucket = pd.DataFrame({'Largeur': widths, 'Hauteur': heights, 'Nom': names})
    fig_scatter = px.scatter(df_bucket, x='Largeur', y='Hauteur', hover_data=['Nom'], title="Distribution des Résolutions")
    fig_scatter.add_vline(x=1024, line_dash="dash", line_color="red"); fig_scatter.add_hline(y=1024, line_dash="dash", line_color="red")
    
    anti_pairs = []
    for i in range(len(top_tags)):
        for j in range(i+1, len(top_tags)):
            if pairs.get(tuple(sorted([top_tags[i], top_tags[j]])), 0) == 0:
                anti_pairs.append(f"[{top_tags[i]}] ❌ [{top_tags[j]}]")
    anti_txt = "\n".join(anti_pairs[:15]) if anti_pairs else "Tous les tops tags sont interconnectés."
    
    contradictions_found = []
    for item in dataset:
        cap = item['caption'].lower()
        for (a, b) in CONTRADICTIONS_LOGIQUES:
            if re.search(r'\b' + re.escape(a) + r'\b', cap) and re.search(r'\b' + re.escape(b) + r'\b', cap):
                contradictions_found.append(f"Image {item['img_name']} : Contient '{a}' ET '{b}'")
    contra_txt = "\n".join(contradictions_found) if contradictions_found else "✅ Aucune contradiction logique détectée."
    
    return fig_heatmap, fig_scatter, anti_txt, contra_txt

def find_orphans(dataset, lang):
    lang = lang or "FR"
    if not dataset: return MSG[lang].get("no_dataset", "")
    all_words = []
    for item in dataset:
        tags = [t.strip().lower() for t in item['caption'].split(',')]
        all_words.extend(tags)
    counts = Counter(all_words)
    orphans = [tag for tag, count in counts.items() if count == 1 and len(tag) > 2]
    if not orphans: return MSG[lang].get("no_orphans", "No orphans")
    return MSG[lang].get("unique_tags", "Unique:\n") + ", ".join(sorted(orphans))

def auto_fill_top_tags(dataset):
    if not dataset: return ""
    all_words = []
    for item in dataset:
        tags = [t.strip().lower() for t in item['caption'].split(',')]
        all_words.extend([t for t in tags if t])
    counts = Counter(all_words)
    return ", ".join([tag for tag, count in counts.most_common(20)])

def generate_civitai_format(df):
    if df is None or df.empty: return ""
    md = "| " + " | ".join(df.columns) + " |\n"
    md += "|" + "|".join(["---" for _ in df.columns]) + "|\n"
    for _, row in df.iterrows(): md += "| " + " | ".join(str(x) for x in row.values) + " |\n"
    gr.Info("✅ Format CivitAI généré ! Copiez le texte ci-dessous.")
    return md

def export_stats_table(df, export_format, lang):
    m = MSG.get(lang, MSG.get("FR", {}))
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        msg = m.get("no_stats_to_export", "No statistics to export.")
        gr.Warning(msg)
        return None, msg
    export_dir = os.path.join(APP_DIR, "stats_exports")
    os.makedirs(export_dir, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    if export_format == "csv":
        path = os.path.join(export_dir, f"stats_{stamp}.csv")
        df.to_csv(path, index=False, encoding="utf-8-sig")
    else:
        path = os.path.join(export_dir, f"stats_{stamp}.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(generate_civitai_format(df))
    msg = m.get("stats_exported", "Statistics exported: {path}").format(path=path)
    gr.Info(msg)
    return path, msg

def export_stats_csv(df, lang):
    return export_stats_table(df, "csv", lang)

def export_stats_md(df, lang):
    return export_stats_table(df, "md", lang)

# === Recettes / Tables Helpers (Pour l'Export) ===
def df_to_tracked_words(df):
    if df is None or df.empty: return ""
    words = []
    for _, row in df.iterrows():
        mot = str(row.get("Mot-clé", row.get("Keyword", ""))).strip()
        if not mot or mot.lower() in ["aucun", "none"]: continue
        cible = str(row.get("Cible %", row.get("Target %", ""))).replace('%', '').strip()
        if cible and cible != "-" and cible != "0.0" and cible != "0": words.append(f"{mot}:{cible}")
        else: words.append(mot)
    return ", ".join(words)

def norm_tracked_words(s):
    if not s or not isinstance(s, str): return ""
    return ",".join(sorted([w.strip().lower() for w in s.split(',') if w.strip()]))

def safe_df_to_tracked_words(df, current_str):
    new_str = df_to_tracked_words(df)
    if norm_tracked_words(new_str) == norm_tracked_words(current_str): return gr.update()
    return new_str

def get_row_index(evt: gr.SelectData, state_json):
    row_idx = evt.index[0]
    if not state_json or state_json == "{}": return row_idx, gr.update(), gr.update()
    df = pd.read_json(io.StringIO(state_json), orient='records')
    if df.empty or row_idx >= len(df): return row_idx, gr.update(), gr.update()
    prio_col = "Priorité" if "Priorité" in df.columns else "Priority"
    tgt_col = "Cible %" if "Cible %" in df.columns else "Target %"
    prio_val = str(df.at[row_idx, prio_col])
    tgt_val = str(df.at[row_idx, tgt_col]).replace('%', '')
    try: tgt_val = float(tgt_val)
    except: tgt_val = 0.0
    return row_idx, prio_val, tgt_val

def filter_gallery_from_stats_row(evt: gr.SelectData, stats_df, dataset, sort_order, lang):
    if stats_df is None or not isinstance(stats_df, pd.DataFrame) or stats_df.empty:
        return gr.update(), [], [], [], selection_summary_html(0, 0, len(dataset or []), lang), "{}", -1
    try:
        row_idx = evt.index[0] if isinstance(evt.index, (list, tuple)) else evt.index
        row_idx = int(row_idx)
    except Exception:
        row_idx = -1
    if row_idx < 0 or row_idx >= len(stats_df):
        return gr.update(), [], [], [], selection_summary_html(0, 0, len(dataset or []), lang), "{}", -1
    kw_col = "Mot-clé" if "Mot-clé" in stats_df.columns else "Keyword"
    keyword = str(stats_df.iloc[row_idx].get(kw_col, "")).strip()
    if not keyword or keyword.lower() in ("aucun", "none"):
        return gr.update(), [], [], [], selection_summary_html(0, 0, len(dataset or []), lang), "{}", -1
    filtered, gal_items, selected, summary, sync_payload, current_idx = filter_gallery(dataset, keyword, sort_order, lang)
    return gr.update(value=keyword), filtered, gal_items, selected, summary, sync_payload, current_idx

def apply_quick_prio(new_prio, row_idx, state_json):
    if row_idx < 0 or not state_json or state_json == "{}": return gr.update(), state_json, gr.update(), row_idx
    df = pd.read_json(io.StringIO(state_json), orient='records')
    if df.empty or row_idx >= len(df): return gr.update(), state_json, gr.update(), row_idx
    prio_col = "Priorité" if "Priorité" in df.columns else "Priority"
    try: new_prio_int = int(new_prio)
    except: return gr.update(), state_json, gr.update(), row_idx
    max_prio = len(df)
    if new_prio_int < 1: new_prio_int = 1
    if new_prio_int > max_prio: new_prio_int = max_prio
    old_prio = df.at[row_idx, prio_col]
    if old_prio == new_prio_int: return gr.update(), state_json, gr.update(), row_idx
    conflict_mask = df[prio_col] == new_prio_int
    if conflict_mask.any():
        conflict_idx = conflict_mask.idxmax()
        df.at[conflict_idx, prio_col] = old_prio
    df.at[row_idx, prio_col] = new_prio_int
    df = df.sort_values(by=prio_col).reset_index(drop=True)
    df[prio_col] = range(1, len(df) + 1)
    new_row_idx = df.index[df[prio_col] == new_prio_int].tolist()[0]
    new_json = df.to_json(orient='records')
    return df, new_json, df_to_tracked_words(df), new_row_idx

def apply_quick_target(new_tgt, row_idx, state_json):
    if row_idx < 0 or not state_json or state_json == "{}": return gr.update(), state_json, gr.update()
    df = pd.read_json(io.StringIO(state_json), orient='records')
    if df.empty or row_idx >= len(df): return gr.update(), state_json, gr.update()
    tgt_col = "Cible %" if "Cible %" in df.columns else "Target %"
    old_tgt = str(df.at[row_idx, tgt_col]).replace('%', '')
    try: old_tgt = float(old_tgt)
    except: old_tgt = 0.0
    if new_tgt is None: new_tgt = 0.0
    if old_tgt == new_tgt: return gr.update(), state_json, gr.update()
    df.at[row_idx, tgt_col] = new_tgt
    new_json = df.to_json(orient='records')
    return df, new_json, df_to_tracked_words(df)

def df_move_up(df, row_idx):
    if df is None or df.empty or row_idx <= 0 or row_idx >= len(df): return df, row_idx, df_to_tracked_words(df)
    d = df.to_dict('records')
    d[row_idx], d[row_idx-1] = d[row_idx-1], d[row_idx]
    ndf = pd.DataFrame(d)
    col = "Priorité" if "Priorité" in ndf.columns else "Priority"
    ndf[col] = range(1, len(ndf)+1)
    return ndf, row_idx - 1, df_to_tracked_words(ndf)

def df_move_down(df, row_idx):
    if df is None or df.empty or row_idx < 0 or row_idx >= len(df)-1: return df, row_idx, df_to_tracked_words(df)
    d = df.to_dict('records')
    d[row_idx], d[row_idx+1] = d[row_idx+1], d[row_idx]
    ndf = pd.DataFrame(d)
    col = "Priorité" if "Priorité" in ndf.columns else "Priority"
    ndf[col] = range(1, len(ndf)+1)
    return ndf, row_idx + 1, df_to_tracked_words(ndf)

def df_delete_row(df, row_idx):
    if df is None or df.empty or row_idx < 0 or row_idx >= len(df): return df, -1, df_to_tracked_words(df)
    d = df.to_dict('records')
    d.pop(row_idx)
    ndf = pd.DataFrame(d) if d else pd.DataFrame(columns=df.columns)
    if not ndf.empty:
        col = "Priorité" if "Priorité" in ndf.columns else "Priority"
        ndf[col] = range(1, len(ndf)+1)
    return ndf, -1, df_to_tracked_words(ndf)

def handle_df_edit(new_df, old_df):
    if new_df is None or new_df.empty: return new_df, new_df, df_to_tracked_words(new_df)
    prio_col = "Priorité" if "Priorité" in new_df.columns else "Priority"
    if old_df is not None and not old_df.empty and len(new_df) == len(old_df):
        try:
            new_series = pd.to_numeric(new_df[prio_col], errors='coerce').fillna(999).astype(int)
            old_series = pd.to_numeric(old_df[prio_col], errors='coerce').fillna(999).astype(int)
            diff_mask = new_series != old_series
            if diff_mask.any():
                changed_idx = diff_mask.idxmax()
                new_prio = new_series.iloc[changed_idx]
                old_prio = old_series.iloc[changed_idx]
                max_prio = len(new_df)
                if new_prio < 1: new_prio = 1
                if new_prio > max_prio: new_prio = max_prio
                new_df.at[changed_idx, prio_col] = new_prio
                new_series.iloc[changed_idx] = new_prio
                conflict_mask = (new_series == new_prio) & (new_series.index != changed_idx)
                if conflict_mask.any():
                    conflict_idx = conflict_mask.idxmax()
                    new_df.at[conflict_idx, prio_col] = old_prio
        except Exception: pass
    try:
        new_df[prio_col] = pd.to_numeric(new_df[prio_col], errors='coerce').fillna(999).astype(int)
        new_df = new_df.sort_values(by=prio_col).reset_index(drop=True)
        new_df[prio_col] = range(1, len(new_df) + 1)
    except: pass
    return new_df, new_df, df_to_tracked_words(new_df)

def handle_recipe_df_safe(new_df, state_json, current_str):
    if new_df is None or new_df.empty: return gr.update(), "{}", gr.update()
    new_json = new_df.to_json(orient='records')
    if new_json == state_json: return gr.update(), state_json, gr.update()
    old_df = pd.read_json(io.StringIO(state_json), orient='records') if state_json != "{}" else pd.DataFrame()
    processed_df, _, new_str = handle_df_edit(new_df, old_df)
    processed_json = processed_df.to_json(orient='records')
    str_update = new_str if norm_tracked_words(new_str) != norm_tracked_words(current_str) else gr.update()
    return processed_df, processed_json, str_update

def handle_stats_df_safe(new_df, state_json, current_str):
    if new_df is None or new_df.empty: return gr.update(), "{}", gr.update()
    new_json = new_df.to_json(orient='records')
    if new_json == state_json: return gr.update(), state_json, gr.update()
    new_str = df_to_tracked_words(new_df)
    str_update = new_str if norm_tracked_words(new_str) != norm_tracked_words(current_str) else gr.update()
    return gr.update(), new_json, str_update

def handle_drag_and_drop(dnd_data, current_df):
    if not dnd_data or current_df is None or current_df.empty:
        return current_df, "{}", gr.update()
    try:
        rows_to_move = []
        new_idx = -1
        raw = str(dnd_data).strip()
        if raw.startswith("{"):
            payload = json.loads(raw)
            rows_to_move = sorted({int(x) for x in payload.get("rows", [])})
            new_idx = int(payload.get("to", -1))
        else:
            old_idx, new_idx = map(int, raw.split(','))
            rows_to_move = [old_idx]
        if not rows_to_move:
            return current_df, current_df.to_json(orient='records'), gr.update()
        row_count = len(current_df)
        rows_to_move = [idx for idx in rows_to_move if 0 <= idx < row_count]
        if not rows_to_move or new_idx < 0 or new_idx >= row_count:
            return current_df, current_df.to_json(orient='records'), gr.update()
        df_list = current_df.to_dict('records')
        moving = [df_list[idx] for idx in rows_to_move]
        remaining = [row for idx, row in enumerate(df_list) if idx not in set(rows_to_move)]
        insert_at = new_idx - sum(1 for idx in rows_to_move if idx < new_idx)
        if new_idx > max(rows_to_move):
            insert_at += 1
        insert_at = max(0, min(len(remaining), insert_at))
        df_list = remaining[:insert_at] + moving + remaining[insert_at:]
        new_df = pd.DataFrame(df_list)
        prio_col = "Priorité" if "Priorité" in new_df.columns else "Priority"
        new_df[prio_col] = range(1, len(new_df) + 1)
        return new_df, new_df.to_json(orient='records'), df_to_tracked_words(new_df)
    except Exception:
        return current_df, current_df.to_json(orient='records'), gr.update()

AI_FORMAT_PRESETS = {
    "Personnalisé": {},
    "Booru (virgules)": {
        "action": "Tag Sorting & Standardisation",
        "prompt": "",
        "injection": "Remplacer tout",
        "vision": False,
    },
    "Flux phrase naturelle": {
        "action": "Traducteur Visuel (Booru ↔ Phrase Naturelle)",
        "prompt": "",
        "injection": "Remplacer tout",
        "vision": False,
    },
    "Minimal (trigger + 5 tags)": {
        "action": "✨ Prompt Personnalisé (Texte/Vision)",
        "prompt": "À partir de ces tags: {tags}\nRenvoie uniquement le trigger principal puis 5 tags essentiels, séparés par des virgules. Pas de phrase.",
        "injection": "Remplacer tout",
        "vision": False,
    },
}

def load_ai_format_presets():
    recipes = load_ai_recipes()
    custom = recipes.get("__format_presets__", {}) if isinstance(recipes, dict) else {}
    presets = copy.deepcopy(AI_FORMAT_PRESETS)
    if isinstance(custom, dict):
        for name, data in custom.items():
            if isinstance(data, dict):
                presets[name] = data
    return presets

def apply_ai_format_preset(name):
    presets = load_ai_format_presets()
    data = presets.get(name or "Personnalisé", {})
    if not data:
        return gr.update(), gr.update(), gr.update(), gr.update()
    return (
        gr.update(value=data.get("action", "Auto-Taggage / Super OCR (VLM)")),
        gr.update(value=data.get("prompt", "")),
        gr.update(value=data.get("injection", "Remplacer tout")),
        gr.update(value=bool(data.get("vision", False))),
    )

def load_ai_recipes():
    if os.path.exists(AI_RECIPES_FILE):
        with open(AI_RECIPES_FILE, 'r') as f: return json.load(f)
    return {"Default Flux Style": "Réécris ces tags en une phrase naturelle parfaite pour le modèle Flux : {tags}"}

def load_ai_template_choices():
    recipes = load_ai_recipes()
    if not isinstance(recipes, dict):
        return []
    return [name for name, prompt in recipes.items() if not str(name).startswith("__") and isinstance(prompt, str)]

def save_ai_recipe(name, prompt):
    if not name: return gr.update()
    recipes = load_ai_recipes()
    recipes[name] = prompt
    with open(AI_RECIPES_FILE, 'w', encoding="utf-8") as f: json.dump(recipes, f, ensure_ascii=False, indent=2)
    gr.Info("Template IA sauvegardé !")
    return gr.update(choices=load_ai_template_choices(), value=name)

def apply_ai_recipe(name):
    prompt = load_ai_recipes().get(name, "")
    return prompt if isinstance(prompt, str) else ""

BUILTIN_AI_ACTIONS = [
    "Auto-Taggage / Super OCR (VLM)",
    "Reality Check & Hallucinations (VLM)",
    "Concept Isolator (Spécial LoRA)",
    "Traducteur Visuel (Booru ↔ Phrase Naturelle)",
    "Tag Sorting & Standardisation",
    "Traduction Batch (Vers Anglais)",
    "✨ Prompt Personnalisé (Texte/Vision)",
]

AI_ACTION_PROMPTS = {
    "Auto-Taggage / Super OCR (VLM)": "Décris cette image en détail (virgules). Ajoute le texte lu sous la forme text: \"le texte\".",
    "Reality Check & Hallucinations (VLM)": "Tags actuels: '{tags}'. Ne renvoie QUE les tags réellement présents.",
    "Concept Isolator (Spécial LoRA)": "Décris l'arrière-plan et le style, NE DÉCRIS PAS le sujet principal.",
    "Traducteur Visuel (Booru ↔ Phrase Naturelle)": "Transforme en phrase anglaise fluide pour Flux : {tags}",
    "Tag Sorting & Standardisation": "Ordonne (Sujet, Vêtements, Fond) et corrige: {tags}",
    "Traduction Batch (Vers Anglais)": "Translate into English, keep comma format: {tags}",
    "✨ Prompt Personnalisé (Texte/Vision)": "{tags}",
}

AI_ACTION_DESCRIPTIONS = {
    "Auto-Taggage / Super OCR (VLM)": "**Vision :** Analyse complète de l'image et extraction du texte.",
    "Reality Check & Hallucinations (VLM)": "**Vision :** Supprime les tags inexistants dans l'image réelle.",
    "Concept Isolator (Spécial LoRA)": "**Vision :** Décrit tout SAUF le sujet central.",
    "Traducteur Visuel (Booru ↔ Phrase Naturelle)": "**Texte :** Convertit des tags bruts en une belle phrase.",
    "Tag Sorting & Standardisation": "**Texte :** Ordonne l'importance des tags et corrige l'orthographe.",
    "Traduction Batch (Vers Anglais)": "**Texte batch :** traduit les captions ciblées vers l'anglais. Pour traduire seulement l'image courante, utilisez le module Traduction du viewer.",
    "Traduction Automatique (Vers Anglais)": "**Texte batch :** traduit les captions ciblées vers l'anglais. Pour traduire seulement l'image courante, utilisez le module Traduction du viewer.",
    "✨ Prompt Personnalisé (Texte/Vision)": "**Custom :** Utilisez le champ 'Prompt Personnalisé' ci-dessous."
}

def load_custom_ai_actions():
    recipes = load_ai_recipes()
    custom = recipes.get("__custom_actions__", {}) if isinstance(recipes, dict) else {}
    if not isinstance(custom, dict):
        return {}
    clean = {}
    for name, data in custom.items():
        if isinstance(name, str) and isinstance(data, dict) and str(data.get("prompt", "")).strip():
            clean[name] = data
    return clean

def save_custom_ai_actions(actions):
    recipes = load_ai_recipes()
    if not isinstance(recipes, dict):
        recipes = {}
    recipes["__custom_actions__"] = actions
    with open(AI_RECIPES_FILE, "w", encoding="utf-8") as f:
        json.dump(recipes, f, ensure_ascii=False, indent=2)

def load_ai_action_choices():
    choices = list(BUILTIN_AI_ACTIONS)
    for name in sorted(load_custom_ai_actions().keys(), key=lambda x: x.lower()):
        if name not in choices:
            choices.append(name)
    return choices

def _action_uses_vision(action):
    if action in load_custom_ai_actions():
        return bool(load_custom_ai_actions()[action].get("vision", False))
    return action in (
        "Auto-Taggage / Super OCR (VLM)",
        "Reality Check & Hallucinations (VLM)",
        "Concept Isolator (Spécial LoRA)",
    )

def _render_action_prompt(template, caption, item):
    return str(template or "").replace("{tags}", str(caption or "")).replace("{caption}", str(caption or "")).replace("{filename}", str(item.get("img_name", "")))

def update_ai_action_desc(action):
    show_custom = action == "✨ Prompt Personnalisé (Texte/Vision)"
    custom = load_custom_ai_actions().get(action)
    desc = custom.get("description", "") if custom else AI_ACTION_DESCRIPTIONS.get(action, "")
    if custom:
        desc = f"**Action personnalisée :** {desc or 'Prompt JSON éditable.'}"
    return f"<div class='ai-desc-box'>ℹ️ {desc}</div>", gr.update(visible=show_custom), gr.update(visible=True)

def load_ai_action_for_edit(action):
    custom = load_custom_ai_actions().get(action)
    if custom:
        return (
            action,
            custom.get("prompt", ""),
            custom.get("description", ""),
            bool(custom.get("vision", False)),
            custom.get("injection", "Remplacer tout"),
            "Action personnalisée chargée. Sauver mettra à jour cette action.",
        )
    prompt = AI_ACTION_PROMPTS.get(action, "{tags}")
    desc = AI_ACTION_DESCRIPTIONS.get(action, "")
    return (
        action or "",
        prompt,
        desc.replace("**Vision :** ", "").replace("**Texte :** ", "").replace("**Texte batch :** ", "").replace("**Custom :** ", ""),
        _action_uses_vision(action),
        "Remplacer tout",
        "Action native chargée. Sauver créera une surcharge personnalisée modifiable.",
    )

def save_custom_ai_action(name, prompt, description, vision, injection):
    name = str(name or "").strip()
    prompt = str(prompt or "").strip()
    if not name or not prompt:
        return gr.update(choices=load_ai_action_choices()), "Nom et prompt requis."
    actions = load_custom_ai_actions()
    actions[name] = {
        "prompt": prompt,
        "description": str(description or "").strip(),
        "vision": bool(vision),
        "injection": injection or "Remplacer tout",
    }
    save_custom_ai_actions(actions)
    gr.Info(f"Action IA sauvegardée : {name}")
    return gr.update(choices=load_ai_action_choices(), value=name), f"✅ Action sauvegardée : {name}"

def delete_custom_ai_action(name):
    name = str(name or "").strip()
    actions = load_custom_ai_actions()
    if name not in actions:
        return gr.update(choices=load_ai_action_choices()), "Cette action est native ou inexistante : rien à supprimer."
    del actions[name]
    save_custom_ai_actions(actions)
    gr.Info(f"Action IA supprimée : {name}")
    return gr.update(choices=load_ai_action_choices(), value="Auto-Taggage / Super OCR (VLM)"), f"🗑️ Action supprimée : {name}"

def export_ai_actions_json():
    export_dir = os.path.join(APP_DIR, "stats_exports")
    os.makedirs(export_dir, exist_ok=True)
    path = os.path.join(export_dir, f"ai_actions_{time.strftime('%Y%m%d_%H%M%S')}.json")
    payload = {
        "app": APP_TITLE,
        "version": APP_VERSION,
        "actions": load_custom_ai_actions(),
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return path, f"✅ Export JSON : {path}"

def import_ai_actions_json(file_path):
    if isinstance(file_path, dict):
        file_path = file_path.get("name") or file_path.get("path")
    if not file_path or not os.path.exists(file_path):
        return gr.update(choices=load_ai_action_choices()), "Aucun fichier JSON valide."
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        incoming = data.get("actions") or data.get("__custom_actions__") or data
        if not isinstance(incoming, dict):
            return gr.update(choices=load_ai_action_choices()), "Format JSON non reconnu."
        actions = load_custom_ai_actions()
        imported = 0
        for name, config in incoming.items():
            if not isinstance(config, dict):
                continue
            prompt = str(config.get("prompt", "")).strip()
            if not name or not prompt:
                continue
            actions[str(name).strip()] = {
                "prompt": prompt,
                "description": str(config.get("description", "")).strip(),
                "vision": bool(config.get("vision", False)),
                "injection": config.get("injection", "Remplacer tout"),
            }
            imported += 1
        save_custom_ai_actions(actions)
        msg = f"✅ {imported} actions importées."
        gr.Info(msg)
        return gr.update(choices=load_ai_action_choices()), msg
    except Exception as e:
        return gr.update(choices=load_ai_action_choices()), f"Erreur import JSON : {e}"

def process_ai_action(dataset, selected_ids, search_text, action, custom_prompt, injection_mode, use_vision_for_custom, vlm_model, llm_model, api_backend, api_url, temp, ctx, sys_prompt, current_idx, tracked_words, lang, api_key="", api_timeout=180, progress=gr.Progress()):
    if not dataset: return dataset, dataset, dataset, "Dataset vide.", extract_all_tags(dataset), "", get_highlighted_html("", tracked_words), ""
    history = copy.deepcopy(dataset)
    count = 0; errors = []
    selected_ids = set(selected_ids or [])
    items_to_process = [item for item in dataset if not selected_ids or item.get('id') in selected_ids]
    total = len(items_to_process)
    custom_actions = load_custom_ai_actions()
    for i, item in enumerate(items_to_process):
        if progress:
            progress((i + 1) / total if total else 1, desc=f"IA {i+1}/{total} : {item['img_name']}")
        current_cap = item['caption']; new_cap = current_cap; res = ""; effective_injection = injection_mode
        try:
            if action in custom_actions:
                custom_action = custom_actions[action]
                model_to_use = vlm_model if bool(custom_action.get("vision", False)) else llm_model
                img_path_to_use = item['img_path'] if bool(custom_action.get("vision", False)) else None
                effective_injection = custom_action.get("injection") or injection_mode
                res = call_ai_api(
                    _render_action_prompt(custom_action.get("prompt", ""), current_cap, item),
                    model_to_use,
                    img_path_to_use,
                    api_backend,
                    api_url,
                    temp,
                    ctx,
                    sys_prompt,
                    api_key=api_key,
                    timeout=api_timeout,
                )
            elif action == "Auto-Taggage / Super OCR (VLM)": res = call_ai_api("Décris cette image en détail (virgules). Ajoute le texte lu sous la forme text: \"le texte\".", vlm_model, item['img_path'], api_backend, api_url, temp, ctx, sys_prompt, api_key=api_key, timeout=api_timeout)
            elif action == "Reality Check & Hallucinations (VLM)": res = call_ai_api(f"Tags actuels: '{current_cap}'. Ne renvoie QUE les tags réellement présents.", vlm_model, item['img_path'], api_backend, api_url, temp, ctx, sys_prompt, api_key=api_key, timeout=api_timeout)
            elif action == "Concept Isolator (Spécial LoRA)": res = call_ai_api("Décris l'arrière-plan et le style, NE DÉCRIS PAS le sujet principal.", vlm_model, item['img_path'], api_backend, api_url, temp, ctx, sys_prompt, api_key=api_key, timeout=api_timeout)
            elif action == "Traducteur Visuel (Booru ↔ Phrase Naturelle)": res = call_ai_api(f"Transforme en phrase anglaise fluide pour Flux : {current_cap}", llm_model, None, api_backend, api_url, temp, ctx, sys_prompt, api_key=api_key, timeout=api_timeout)
            elif action in ("Traduction Batch (Vers Anglais)", "Traduction Automatique (Vers Anglais)"): res = call_ai_api(f"Translate into English, keep comma format: {current_cap}", llm_model, None, api_backend, api_url, temp, ctx, sys_prompt, api_key=api_key, timeout=api_timeout)
            elif action == "Tag Sorting & Standardisation": res = call_ai_api(f"Ordonne (Sujet, Vêtements, Fond) et corrige: {current_cap}", llm_model, None, api_backend, api_url, temp, ctx, sys_prompt, api_key=api_key, timeout=api_timeout)
            elif action == "✨ Prompt Personnalisé (Texte/Vision)":
                model_to_use = vlm_model if use_vision_for_custom else llm_model
                img_path_to_use = item['img_path'] if use_vision_for_custom else None
                res = call_ai_api(custom_prompt.replace("{tags}", current_cap), model_to_use, img_path_to_use, api_backend, api_url, temp, ctx, sys_prompt, api_key=api_key, timeout=api_timeout)
            
            if res.startswith("Erreur API"): errors.append(item['img_name']); gr.Warning(res); continue
            if effective_injection in ("Remplacer tout", "Replace all") or not effective_injection:
                new_cap = res
            elif effective_injection in ("Ajouter au début", "Add at start"):
                new_cap = res + ", " + current_cap if current_cap else res
            elif effective_injection in ("Ajouter à la fin", "Add at end"):
                new_cap = current_cap + ", " + res if current_cap else res
            
            if new_cap != current_cap: item['caption'] = new_cap; count += 1
        except: errors.append(item['img_name'])
    save_all_captions(dataset)
    msg = f"✅ IA Appliquée ({count} modifiés)."
    if errors: msg += f" ⚠️ Échecs sur {len(errors)} fichiers."
    gr.Info(msg)
    filtered_dataset = [item for item in dataset if search_text.lower() in item['caption'].lower()] if search_text else dataset
    
    cap, hl, wc = get_updated_viewer_data(filtered_dataset, current_idx, tracked_words, lang)
    return dataset, filtered_dataset, history, msg, extract_all_tags(dataset), cap, hl, wc

def process_ai_current_image(dataset, filtered_dataset, search_text, action, custom_prompt, injection_mode, use_vision_for_custom, vlm_model, llm_model, api_backend, api_url, temp, ctx, sys_prompt, current_idx, tracked_words, lang, api_key="", api_timeout=180):
    if not filtered_dataset or current_idx < 0 or current_idx >= len(filtered_dataset):
        return dataset, filtered_dataset, dataset, MSG[lang].get("no_img_sel", "No image selected."), extract_all_tags(dataset), "", get_highlighted_html("", tracked_words), update_word_count("", lang)
    current_id = filtered_dataset[current_idx].get('id')
    return process_ai_action(
        dataset, [current_id], search_text, action, custom_prompt, injection_mode,
        use_vision_for_custom, vlm_model, llm_model, api_backend, api_url, temp,
        ctx, sys_prompt, current_idx, tracked_words, lang, api_key, api_timeout,
    )

def select_images_without_caption(dataset, filtered_dataset, lang):
    selected_visual = [i for i, item in enumerate(filtered_dataset or []) if not str(item.get('caption', '')).strip()]
    selected_ids = [filtered_dataset[i].get('id') for i in selected_visual]
    payload = "__SET_SELECTION__" + json.dumps({"selected": selected_visual, "viewIndex": selected_visual[0] if selected_visual else 0})
    return selected_ids, selection_summary_html(len(selected_ids), len(filtered_dataset or []), len(dataset or []), lang), payload

def _split_caption_tags(caption):
    return [tag.strip() for tag in str(caption or "").split(",") if tag.strip()]

def _build_bias_profile(dataset, sample_size=30):
    total = len(dataset)
    caps = [str(item.get("caption", "")).strip() for item in dataset]
    non_empty_caps = [cap for cap in caps if cap]
    tag_lists = [_split_caption_tags(cap) for cap in non_empty_caps]
    tag_counts = Counter(tag for tags in tag_lists for tag in tags)
    per_image_counts = [len(tags) for tags in tag_lists]
    avg_tags = (sum(per_image_counts) / len(per_image_counts)) if per_image_counts else 0
    top_tags = tag_counts.most_common(35)
    rare_tags = [(tag, count) for tag, count in tag_counts.items() if count == 1][:35]
    empty_count = total - len(non_empty_caps)
    samples = []
    if non_empty_caps:
        step = max(1, len(non_empty_caps) // sample_size)
        samples = non_empty_caps[::step][:sample_size]
    return {
        "total_images": total,
        "captioned_images": len(non_empty_caps),
        "empty_captions": empty_count,
        "unique_tags": len(tag_counts),
        "avg_tags_per_caption": round(avg_tags, 1),
        "top_tags": top_tags,
        "rare_tags": rare_tags,
        "caption_samples": samples,
    }

def _build_bias_prompt(profile, output_lang, top_limit=30, rare_limit=25, sample_limit=30, sample_chars=260, compact_note=False):
    top_tags = ", ".join([f"{tag} ({count})" for tag, count in profile["top_tags"][:top_limit]])
    rare_tags = ", ".join([tag for tag, _ in profile["rare_tags"][:rare_limit]])
    caption_samples = "\n".join([f"- {cap[:sample_chars]}" for cap in profile["caption_samples"][:sample_limit]])
    compact_line = ""
    if compact_note:
        compact_line = "\nNote: le profil fourni est compacté automatiquement pour respecter la fenêtre de contexte du modèle local."
    return f"""
Tu es un expert senior en préparation de datasets pour Stable Diffusion, Flux et entraînement LoRA.
Analyse ce dataset à partir de ses captions réelles. Réponds en {output_lang}, de façon concrète et actionnable.{compact_line}

Résumé quantitatif:
- Images: {profile['total_images']}
- Captions non vides: {profile['captioned_images']}
- Captions vides: {profile['empty_captions']}
- Tags uniques: {profile['unique_tags']}
- Moyenne de tags par caption: {profile['avg_tags_per_caption']}

Tags les plus fréquents:
{top_tags or "Aucun"}

Tags rares ou potentiellement isolés:
{rare_tags or "Aucun"}

Échantillon représentatif des captions:
{caption_samples or "Aucun"}

Produit un rapport structuré avec ces sections:
1. Diagnostic rapide: ce que le dataset semble apprendre en priorité.
2. Biais probables: sujet, pose, cadrage, style, fond, lumière, vêtements/objets, vocabulaire répétitif.
3. Risques pour un LoRA: surapprentissage, trigger trop faible, tags contradictoires, tags trop génériques, manque de diversité.
4. Corrections prioritaires: actions concrètes à faire dans les captions ou dans le tri des images.
5. Tags à surveiller: liste courte des tags à fusionner, supprimer, renforcer ou renommer.

Ne reste pas générique: appuie chaque remarque sur les tags ou captions fournis. Si une information manque, indique comment la vérifier dans l'outil.
""".strip()

def _build_context_safe_bias_prompt(profile, output_lang, ctx, sys_prompt=""):
    ctx_tokens = _safe_context_tokens(ctx)
    output_budget = _safe_output_tokens(ctx)
    system_tokens = estimate_text_tokens(sys_prompt)
    # Leave room for chat formatting, system prompt and the model response.
    input_budget = max(700, min(2600, ctx_tokens - output_budget - system_tokens - 420))
    variants = [
        (30, 25, 30, 260),
        (24, 18, 12, 180),
        (18, 12, 8, 150),
        (14, 8, 5, 120),
        (10, 5, 3, 90),
        (8, 0, 2, 70),
    ]
    chosen = None
    compacted = False
    for i, (top_limit, rare_limit, sample_limit, sample_chars) in enumerate(variants):
        prompt = _build_bias_prompt(
            profile,
            output_lang,
            top_limit=top_limit,
            rare_limit=rare_limit,
            sample_limit=sample_limit,
            sample_chars=sample_chars,
            compact_note=i > 0,
        )
        chosen = prompt
        compacted = i > 0
        if estimate_text_tokens(prompt) <= input_budget:
            return prompt, compacted
    return chosen, compacted

def _is_context_overflow_error(text):
    low = str(text or "").lower()
    return any(marker in low for marker in ("n_keep", "context length", "context_length", "prompt is too long", "too many tokens"))

def analyze_bias(dataset, llm_model, api_backend, api_url, temp, ctx, sys_prompt, lang="FR", api_key="", api_timeout=180):
    if not dataset:
        return MSG.get(lang, MSG.get("FR", {})).get("no_dataset", "Aucun dataset.")
    profile = _build_bias_profile(dataset)
    output_lang = "français" if lang == "FR" else "English"
    prompt, compacted = _build_context_safe_bias_prompt(profile, output_lang, ctx, sys_prompt)
    result = call_ai_api(prompt, llm_model, None, api_backend, api_url, temp, ctx, sys_prompt, api_key=api_key, timeout=api_timeout)
    if _is_context_overflow_error(result):
        fallback_prompt = _build_bias_prompt(profile, output_lang, top_limit=8, rare_limit=0, sample_limit=1, sample_chars=50, compact_note=True)
        result = call_ai_api(fallback_prompt, llm_model, None, api_backend, api_url, temp, ctx, sys_prompt, api_key=api_key, timeout=api_timeout)
        compacted = True
    if compacted and result and not str(result).startswith("Erreur API"):
        note = "Note: rapport généré avec un profil compacté pour respecter le contexte du modèle local.\n\n"
        if lang == "EN":
            note = "Note: report generated with a compacted profile to fit the local model context.\n\n"
        return note + result
    return result

def bias_stale_note(lang):
    t = UI_T.get(lang, UI_T.get("FR", {}))
    return t.get("bias_stale_note", "⚠️ Le dataset a changé : relancez le rapport de biais IA pour actualiser l'analyse.")

# ==========================================
# GESTION DYNAMIQUE DU CHANGEMENT DE LANGUE
# ==========================================
def _strategy_key(strategy):
    strategy = str(strategy or "").strip()
    if strategy in ["Filtre Classique", "Classic Filter", "Filtre Classique (Contient au moins un tag)", "Classic Filter (Contains at least one tag)"]:
        return "classic"
    if strategy in ["Équilibrage Auto (Pourcentages)", "Auto Balancing (Percentages)"]:
        return "balance"
    if strategy in ["Priorité", "Priority", "Priorité (Ordre du tableau)", "Priority (Table Order)"]:
        return "priority"
    return "classic"

def _localized_strategy_value(strategy, lang):
    choices = UI_T.get(lang, UI_T.get("FR", {})).get("strat_choices", [])
    if not choices:
        return ""
    idx_by_key = {"classic": 0, "balance": 1, "priority": 2}
    idx = idx_by_key.get(_strategy_key(strategy), 0)
    return choices[idx] if idx < len(choices) else choices[0]

def _compact_select_all_label(label, lang="FR"):
    if lang == "EN":
        return "☑️ All"
    return "☑️ Tout"

def _compact_multi_select_label(label, lang="FR"):
    return "✅ Multi"

def include_subfolders_label(enabled, lang):
    t = UI_T.get(lang, UI_T.get("FR", {}))
    key = "include_subfolders_on" if enabled else "include_subfolders_off"
    fallback = "📁 Sous-dossiers : ON" if lang == "FR" and enabled else "📁 Sous-dossiers : OFF" if lang == "FR" else "📁 Subfolders: ON" if enabled else "📁 Subfolders: OFF"
    return t.get(key, fallback)

def toggle_include_subfolders(enabled, lang):
    enabled = not bool(enabled)
    return enabled, gr.update(value=include_subfolders_label(enabled, lang))

def change_language(
    lang, stats_df, config_df, lib_state, current_strategy, include_subfolders_enabled=False,
    contact_source_value=None, contact_ratio_mode_value=None, contact_fit_value=None,
    contact_label_value=None, contact_format_value=None,
):
    t = UI_T.get(lang, UI_T.get("FR", {})) 
    m = MSG.get(lang, MSG.get("FR", {}))
    new_stats = stats_df
    new_config = config_df
    kw = m.get("df_kw", "Mot-clé")
    tgt = m.get("df_tgt", "Cible %")
    prio = m.get("df_prio", "Priorité")
    if isinstance(stats_df, pd.DataFrame) and not stats_df.empty:
        new_stats = stats_df.rename(columns={
            "Mot-clé": kw, "Keyword": kw,
            "Compte": "Count" if lang=="EN" else "Compte", "Count": "Compte" if lang=="FR" else "Count",
            "Actuel %": "Current %" if lang=="EN" else "Actuel %", "Current %": "Actuel %" if lang=="FR" else "Current %",
            "Cible %": tgt, "Target %": tgt,
            "Écart": "Diff" if lang=="EN" else "Écart", "Diff": "Écart" if lang=="FR" else "Diff"
        })
    if isinstance(config_df, pd.DataFrame) and not config_df.empty:
        new_config = config_df.rename(columns={
            "Priorité": prio, "Priority": prio, "Mot-clé": kw, "Keyword": kw, "Cible %": tgt, "Target %": tgt
        })
    lbl_pie = "Graphique (Répartition)" if lang == "FR" else "Chart (Distribution)"
    lbl_bar = "Graphique (Occurrences)" if lang == "FR" else "Chart (Occurrences)"
    
    m_add = t.get("lib_mode_choices", ["Ajouter", "Retirer", "Remplacer"])[0]
    m_rem = t.get("lib_mode_choices", ["Ajouter", "Retirer", "Remplacer"])[1]
    m_rep = t.get("lib_mode_choices", ["Ajouter", "Retirer", "Remplacer"])[2]

    return (
        gr.update(value=t.get("title", "")),
        gr.update(label=t.get("settings_title", "⚙️ Paramètres")),
        gr.update(label=t.get("guide_title", "")),
        gr.update(value=t.get("guide_text", "")),
        gr.update(value=render_dataset_drop_zone(lang)),
        gr.update(value=t.get("browse", "")),
        gr.update(value=t.get("load", "")),
        gr.update(value=include_subfolders_label(include_subfolders_enabled, lang)),
        gr.update(value=t.get("status_wait", "")),
        
        gr.update(value=t.get("recipe_global", "")),
        gr.update(label=t.get("recipes_dd", "")),
        gr.update(label=t.get("recipe_name", "")),
        gr.update(value=t.get("save_recipe", "")),
        gr.update(placeholder=t.get("tracked_ph", "")),
        gr.update(label=t.get("ai_recipe_count", "Nombre de mots-clés IA")),
        gr.update(value=t.get("btn_ai_recipe", "🤖 Remplir par IA")),
        gr.update(value=t.get("btn_analyze_recipe", "📊 Analyser")),
        
        gr.update(value=t.get("gallery_title", "")),
        gr.update(label=t.get("search", ""), placeholder=t.get("search_ph", "")),
        gr.update(label=_compact_multi_select_label(t.get("multi_cb", ""), lang)),
        gr.update(value=_compact_select_all_label(t.get("btn_select_all", ""), lang)),
        gr.update(value=t.get("clear_sel", "")),
        gr.update(label=t.get("cols", "")),
        
        gr.update(value=t.get("hide_gal", "")),
        gr.update(label=t.get("tab_view", "")),
        gr.update(value=t.get("btn_prev", "")),
        gr.update(value=t.get("btn_next", "")),
        gr.update(value=t.get("btn_delete_current", "🗑️ Supprimer cette image")),
        gr.update(value=t.get("shortcuts", "")),
        gr.update(value=t.get("toggle_stat", "")),
        
        gr.update(label=t.get("live_trans_label", "")),
        gr.update(value=t.get("save_cap", "")),
        
        gr.update(value=t.get("trans_module_title", "")),
        gr.update(label=t.get("trans_engine", "")),
        gr.update(label=t.get("trans_source", "")),
        gr.update(label=t.get("trans_target", "")),
        
        gr.update(value=t.get("btn_translate_entire", "")),
        gr.update(value=t.get("trans_insert_title", "")),
        gr.update(placeholder=t.get("trans_input_ph", "")),
        gr.update(value=t.get("btn_insert_trans", "")),
        
        gr.update(label=t.get("tab_batch", "")),
        gr.update(value=t.get("btn_undo", "")),
        gr.update(value=t.get("btn_clean_com", "")),
        gr.update(value=t.get("btn_clean_dup", "")),
        gr.update(label=t.get("df_preview", "")),
        
        gr.update(label=t.get("tab_prep", "")),
        gr.update(value=t.get("dup_title", "")),
        gr.update(label=t.get("hash_algo", "Algorithme de hash")),
        gr.update(label=t.get("hash_tol", "")),
        gr.update(value=t.get("hash_tol_help", "")),
        gr.update(value=t.get("btn_scan_dups", "")),
        gr.update(label=t.get("dup_dd", "")),
        gr.update(label=t.get("dup_caption_A", "Caption A")),
        gr.update(label=t.get("dup_caption_B", "Caption B")),
        gr.update(value=t.get("btn_del_A", "")),
        gr.update(value=t.get("btn_skip_dup", "⏭️ Ignorer ce doublon")),
        gr.update(value=t.get("btn_del_B", "")),
        gr.update(value=t.get("btn_delete_all_b", "🗑️ Supprimer tous les B")),
        
        gr.update(value=t.get("rename_title", "")),
        gr.update(label=t.get("rename_prefix", "")),
        gr.update(value=t.get("btn_rename", "")),
        gr.update(value=t.get("resize_title", "")),
        gr.update(label=t.get("prep_size", "")),
        gr.update(label=t.get("prep_format", "")),
        gr.update(label=t.get("prep_crop", "")),
        gr.update(label=t.get("prep_alpha", "")),
        gr.update(label=t.get("prep_dest", "")),
        gr.update(value=t.get("btn_prep", "")),
        gr.update(label=t.get("prep_min_res", "Résolution minimum (px) — 0 = pas de filtre")),
        gr.update(value=t.get("btn_detect_low_res", "🔍 Détecter sous ce seuil")),
        gr.update(value=t.get("btn_move_low_res", "📦 Déplacer dans '_trop_petites'")),
        
        gr.update(label=t.get("tab_ai", "")),
        gr.update(value=t.get("ai_conf_title", "")),
        gr.update(label=t.get("api_backend", "")),
        gr.update(label=t.get("vlm_model", "")),
        gr.update(label=t.get("llm_model", "")),
        gr.update(label=t.get("ai_adv_acc", "")),
        gr.update(label=t.get("api_url_input", "")),
        gr.update(label=t.get("ai_temp", "")),
        gr.update(label=t.get("ai_ctx", "")),
        gr.update(label=t.get("ai_timeout", "Timeout API (secondes)")),
        gr.update(label=t.get("ai_sys", "")),
        
        gr.update(value=t.get("ai_act_title", "")),
        gr.update(label=t.get("ai_format_preset", "📋 Preset de format"), choices=list(load_ai_format_presets().keys())),
        gr.update(label=t.get("ai_action_dd", ""), choices=load_ai_action_choices()),
        gr.update(label=t.get("ai_tpl_dd", ""), choices=load_ai_template_choices()),
        gr.update(label=t.get("ai_tpl_name", "")),
        gr.update(value=t.get("btn_save_tpl", "")),
        gr.update(label=t.get("custom_prompt_input", "")),
        gr.update(label=t.get("use_vision_custom", "")),
        gr.update(label=t.get("injection_mode", "")),
        gr.update(value=t.get("ai_injection_note", "")),
        gr.update(value=t.get("btn_run_ai", "")),
        gr.update(value=t.get("btn_test_ai", "🧪 Tester sur l'image courante")),
        gr.update(value=t.get("btn_select_no_caption", "🎯 Sélectionner sans caption")),
        gr.update(value=t.get("btn_undo_ai", "")),
        
        gr.update(value=t.get("bias_title", "")),
        gr.update(value=t.get("btn_bias", "")),
        gr.update(label=t.get("txt_bias", "")),
        
        gr.update(label=t.get("tab_export", "")),
        gr.update(value=t.get("exp_edit", "")),
        gr.update(value=t.get("btn_up", "")),
        gr.update(value=t.get("btn_down", "")),
        gr.update(value=t.get("btn_del", "")),
        gr.update(label=t.get("quick_prio", "")),
        gr.update(label=t.get("quick_tgt", "")),
        gr.update(value=new_config, headers=t.get("exp_df_headers", [])),
        gr.update(label=t.get("strat", ""), choices=t.get("strat_choices", []), value=_localized_strategy_value(current_strategy, lang)),
        gr.update(label=t.get("max_img", "")),
        gr.update(label=t.get("dest_folder", ""), placeholder=t.get("dest_ph", "")),
        gr.update(label=t.get("export_suffix", "Suffixe d'export"), placeholder=t.get("export_suffix_ph", "-Sx → -S1, -S2, -S3...")),
        gr.update(value=t.get("btn_simul", "")),
        gr.update(value=t.get("btn_exp", "")),
        gr.update(label=lbl_pie),
        gr.update(value=t.get("exp_gal", "")),
        
        gr.update(label=t.get("tab_stats", "")),
        gr.update(value=new_stats, headers=t.get("stat_df_headers", [])),
        gr.update(value=t.get("btn_civitai", "")),
        gr.update(value=t.get("btn_export_stats_csv", "Exporter CSV")),
        gr.update(value=t.get("btn_export_stats_md", "Exporter Markdown")),
        gr.update(value=t.get("btn_top20", "")),
        gr.update(value=t.get("btn_orph", "")),
        gr.update(label=t.get("txt_orph", "")),
        gr.update(label=lbl_pie),
        gr.update(label=lbl_bar),
        gr.update(value=t.get("adv_stats_title", "")),
        gr.update(value=t.get("adv_stats_help", "")),
        gr.update(value=t.get("btn_calc_adv", "")),
        gr.update(label=t.get("adv_heatmap_label", "Matrice")),
        gr.update(value=t.get("adv_heatmap_help", "")),
        gr.update(label=t.get("adv_bucket_label", "Résolutions")),
        gr.update(value=t.get("adv_bucket_help", "")),
        gr.update(label=t.get("anti_title", "")),
        gr.update(value=t.get("anti_help", "")),
        gr.update(label=t.get("contra_title", "")),
        gr.update(value=t.get("contra_help", "")),
        
        gr.update(value=t.get("lib_title", "")),
        gr.update(label=t.get("lib_mode", ""), choices=[m_add, m_rem, m_rep], value=m_add),
        gr.update(label=t.get("lib_target_rem", "")),
        gr.update(value=t.get("btn_apply_lib_add", "")),
        gr.update(placeholder=t.get("lib_add_text_ph", "")),
        gr.update(value=t.get("btn_add_to_lib", "")),
        gr.update(value=t.get("btn_uncheck_all", "")),
        gr.update(value=t.get("btn_clear_lib", "")),
        gr.update(value=t.get("lib_list_title", "")),
        gr.update(value=render_lib_html(lib_state, lang)),

        # ⭐ Favoris + 🌐 Import langue + 🗑️ Suppression recette + 🎯 LM Studio + 🔑 API Key
        gr.update(label=t.get("fav_section_title", "")),
        gr.update(label=t.get("fav_dropdown", "")),
        gr.update(value=t.get("btn_add_fav", "")),
        gr.update(value=t.get("btn_remove_fav", "")),
        gr.update(label=t.get("lang_import_acc", "")),
        gr.update(value=t.get("lang_import_info", "")),
        gr.update(label=t.get("lang_import_file", "")),
        gr.update(value=t.get("lang_import_btn", "")),
        gr.update(value=t.get("btn_delete_recipe", "")),
        gr.update(label=t.get("sort_label", "")),
        gr.update(label=t.get("api_key_input", "")),
        gr.update(label=t.get("lm_studio_acc", "")),
        gr.update(value=t.get("lm_studio_list_btn", "")),
        gr.update(label=t.get("lm_studio_vlm_dd", "")),
        gr.update(label=t.get("lm_studio_llm_dd", "")),
        gr.update(label=t.get("lm_studio_shared_dd", "")),
        gr.update(value=t.get("lm_studio_load_vlm", "")),
        gr.update(value=t.get("lm_studio_load_llm", "")),
        gr.update(value=t.get("lm_studio_load_shared", "")),
        gr.update(value=t.get("lm_studio_unload_vlm", "")),
        gr.update(value=t.get("lm_studio_unload_llm", "")),
        gr.update(value=t.get("lm_studio_unload_shared", "")),
        gr.update(value=t.get("lm_studio_save_choices", "")),
        # Nouveaux composants v4.4
        gr.update(label=t.get("recent_paths_dd", "Chemins récents")),
        gr.update(label=t.get("csv_acc_title", "📋 Import / Export CSV")),
        gr.update(value=t.get("csv_acc_hint", "")),
        gr.update(value=t.get("btn_export_csv_captions", "⬇️ Exporter CSV")),
        gr.update(value=t.get("btn_import_csv_captions", "⬆️ Importer CSV")),
        gr.update(label=t.get("csv_import_dropzone", "📥 Déposer le CSV/MD rempli ici")),
        gr.update(value=t.get("btn_export_md_captions", "⬇️ Exporter MD")),
        gr.update(value=t.get("btn_import_md_captions", "⬆️ Importer MD rempli")),
        gr.update(value=t.get("csv_contact_hint", "**💡 Ou créer directement des planches de compilation** (aperçu et export depuis l'onglet dédié)")),
        gr.update(value=t.get("btn_open_contact_sheet", "🖼️ Créer planche(s) compilation")),

        gr.update(label=t.get("contact_tab_title", "🖼️ Planche(s) compilation(s)")),
        gr.update(label=t.get("contact_source_label", "📸 Images à compiler"), choices=_contact_source_choices(lang), value=_valid_choice_value(contact_source_value, CONTACT_SHEET_SOURCE_CHOICES, CONTACT_SHEET_DEFAULTS["source_mode"])),
        gr.update(value=t.get("contact_btn_preview", "👁️ Aperçu")),
        gr.update(value=t.get("contact_btn_export", "🚀 Exporter")),
        gr.update(label=t.get("contact_layout_acc", "📐 Mise en page")),
        gr.update(label=t.get("contact_output_width", "Largeur finale (px)")),
        gr.update(label=t.get("contact_flexible", "🔄 Flexible (auto-colonnes)")),
        gr.update(label=t.get("contact_images_per_row", "Colonnes")),
        gr.update(label=t.get("contact_spacing", "Espacement (px)")),
        gr.update(label=t.get("contact_margin", "Marge (px)")),
        gr.update(label=t.get("contact_background", "Couleur fond")),
        gr.update(label=t.get("contact_format_acc", "🖼️ Format images")),
        gr.update(label=t.get("contact_ratio_label", "Rapport d'aspect"), choices=_contact_ratio_mode_choices(lang), value=_valid_choice_value(contact_ratio_mode_value, CONTACT_SHEET_RATIO_MODE_CHOICES, CONTACT_SHEET_RATIO_MODE_CHOICES[0])),
        gr.update(label=t.get("contact_fit_mode", "Remplissage"), choices=_contact_fit_choices(lang), value=_valid_choice_value(contact_fit_value, CONTACT_SHEET_FIT_CHOICES, CONTACT_SHEET_DEFAULTS["fit_mode"])),
        gr.update(label=t.get("contact_sort_alpha", "↪️ Ignorer le tri de la galerie")),
        gr.update(label=t.get("contact_text_acc", "🔤 Texte & Labels")),
        gr.update(label=t.get("contact_label_mode", "Type de label"), choices=_contact_label_choices(lang), value=_valid_choice_value(contact_label_value, CONTACT_SHEET_LABEL_CHOICES, CONTACT_SHEET_DEFAULTS["label_mode"])),
        gr.update(label=t.get("contact_font_size", "Taille police (px)")),
        gr.update(label=t.get("contact_label_opacity", "Opacité fond (%)")),
        gr.update(label=t.get("contact_export_acc", "⚙️ Export avancé")),
        gr.update(label=t.get("contact_multi_sheets", "📚 Multiples planches")),
        gr.update(label=t.get("contact_images_per_sheet", "Images par planche")),
        gr.update(label=t.get("contact_continue_numbering", "↪️ Continuer numérotation")),
        gr.update(label=t.get("contact_output_dir", "Dossier sortie"), placeholder=t.get("contact_output_dir_ph", "= dataset/planches_compilation")),
        gr.update(label=t.get("contact_filename_prefix", "Préfixe fichier")),
        gr.update(label=t.get("contact_export_format", "Format"), choices=_contact_format_choices(lang), value=_valid_choice_value(contact_format_value, CONTACT_SHEET_FORMAT_CHOICES, CONTACT_SHEET_DEFAULTS["export_format"])),
        gr.update(label=t.get("contact_quality", "Qualité")),
        gr.update(label=t.get("contact_resize_final", "🔍 Resize final (%)")),
        gr.update(value=t.get("contact_btn_save", "💾 Sauvegarder")),
        gr.update(value=t.get("contact_status_loading", "⏳ Chargement...")),
        gr.update(value=f"### {t.get('contact_preview_title', '👁️ Aperçu live')}"),
        gr.update(value=t.get("contact_preview_back", "🔄 Planche témoin")),
        gr.update(label=t.get("contact_preview_exported", "📥 Fichiers exportés")),
    )

# ==========================================
# INTERFACE GRADIO
# ==========================================

blocks_kwargs = {"title": APP_TITLE}
if get_gradio_major_version() < 6:
    blocks_kwargs["css"] = css_code

with gr.Blocks(**blocks_kwargs) as app:

    dataset_state = gr.State([])
    filtered_state = gr.State([])
    history_state = gr.State([])
    current_idx_state = gr.State(-1) 
    selected_indices_state = gr.State([]) 
    config_df_state = gr.State("{}") 
    stats_df_state = gr.State("{}")
    recipe_selected_row = gr.State(-1)
    include_subfolders_state = gr.State(False)
    
    # State pour la bibliothèque Custom HTML
    initial_library = load_library()
    lib_state = gr.State(initial_library)
    
    dup_mapping_state = gr.State({})
    dup_idA = gr.State(-1)
    dup_idB = gr.State(-1)
    
    dummy_selection = gr.Textbox(visible=False, elem_id="dummy_selection")
    ui_hidden_sync_input = gr.Textbox(value="{}", elem_id="hidden_sync_input")
    ui_hidden_sync_btn = gr.Button(elem_id="hidden_sync_btn")
    ui_hidden_calc_btn = gr.Button(elem_id="hidden_calc_btn")
    ui_hidden_live_translation_btn = gr.Button(elem_id="hidden_live_translation_btn")
    ui_hidden_reverse_translation_btn = gr.Button(elem_id="hidden_reverse_translation_btn")
    ui_hidden_delete_current_btn = gr.Button(elem_id="hidden_delete_current_btn")
    ui_hidden_dnd_input = gr.Textbox(elem_id="hidden_dnd_input")
    ui_hidden_dnd_btn = gr.Button(elem_id="hidden_dnd_btn")
    ui_hidden_tags_input = gr.Textbox(elem_id="hidden_tags_input")
    ui_hidden_dataset_path_input = gr.Textbox(elem_id="hidden_dataset_path_input")
    ui_hidden_dataset_path_btn = gr.Button(elem_id="hidden_dataset_path_btn")
    
    # Inputs cachés pour le module Custom Library
    ui_hidden_lib_toggle_input = gr.Textbox(elem_id="hidden_lib_toggle_input")
    ui_hidden_lib_toggle_btn = gr.Button(elem_id="hidden_lib_toggle_btn")
    ui_hidden_lib_delete_input = gr.Textbox(elem_id="hidden_lib_delete_input")
    ui_hidden_lib_delete_btn = gr.Button(elem_id="hidden_lib_delete_btn")
    ui_hidden_copy_next_btn = gr.Button(elem_id="hidden_copy_next_btn")
    ui_hidden_manual_crop_payload = gr.Textbox(elem_id="hidden_manual_crop_payload")
    ui_hidden_manual_crop_btn = gr.Button(elem_id="hidden_manual_crop_btn")
    
    default_lang = "EN" if "EN" in get_available_languages() else (get_available_languages()[0] if get_available_languages() else "FR")
    t_init = UI_T.get(default_lang, UI_T.get("FR", {}))
    ai_settings_init = load_ai_settings()
    ui_settings_init = load_ui_settings()
    contact_settings_init = load_contact_sheet_settings()

    with gr.Row(elem_id="top_workspace"):
        with gr.Column(scale=2, elem_id="dataset_header"):
            with gr.Row(elem_id="dataset_title_row"):
                with gr.Column(scale=3):
                    ui_title = gr.Markdown(t_init.get("title", ""), elem_id="app_title")
                with gr.Column(scale=1, elem_id="dataset_settings_col"):
                    ui_settings_acc = gr.Accordion(t_init.get("settings_title", "⚙️ Paramètres"), open=False)
                    with ui_settings_acc:
                        lang_radio = gr.Radio(get_available_languages(), value=default_lang, label="Language / Langue", elem_id="language_selector")
                        ui_guide_acc = gr.Accordion(t_init.get("guide_title", ""), open=False)
                        with ui_guide_acc:
                            ui_guide_text = gr.Markdown(t_init.get("guide_text", ""))
                        ui_lang_import_acc = gr.Accordion(t_init.get("lang_import_acc", "🌐 Import langue"), open=False)
                        with ui_lang_import_acc:
                            ui_lang_import_info = gr.Markdown(t_init.get("lang_import_info", ""))
                            ui_lang_import_file = gr.File(label=t_init.get("lang_import_file", "JSON file"),
                                                          file_types=[".json"], file_count="single", type="filepath")
                            ui_lang_import_btn = gr.Button(t_init.get("lang_import_btn", "📥 Importer"), variant="secondary")
                            ui_lang_import_status = gr.Markdown()
            
            _init_recents = load_recent_paths()
            _init_favs = load_favorites()
            with gr.Row(elem_id="dataset_quick_row"):
                with gr.Column(scale=3, elem_id="dataset_path_col"):
                    with gr.Row(elem_id="dataset_path_row"):
                        dir_input = gr.Textbox(placeholder="C:\\mon\\dataset, D:\\autre\\concept, ~/datasets/portrait, ...", show_label=False, scale=4, elem_id="dataset_dir_input")
                        ui_browse_btn = gr.Button(t_init.get("browse", ""), scale=1)
                    ui_include_subfolders = gr.Button(
                        include_subfolders_label(False, default_lang),
                        variant="secondary",
                        elem_id="include_subfolders_btn",
                    )
                    ui_recent_paths_dd = gr.Dropdown(choices=_init_recents, label=t_init.get("recent_paths_dd", "Chemins récents"), interactive=True, allow_custom_value=False, value=None)
                    ui_fav_section_title = gr.Accordion(t_init.get("fav_section_title", "⭐ Favoris"), open=False)
                    with ui_fav_section_title:
                        ui_fav_dropdown = gr.Dropdown(choices=_init_favs, value=None,
                                                       label=t_init.get("fav_dropdown", "Charger un favori"),
                                                       interactive=True, allow_custom_value=False)
                        with gr.Row():
                            ui_btn_add_fav = gr.Button(t_init.get("btn_add_fav", "⭐ Ajouter aux favoris"), size="sm", scale=1)
                            ui_btn_remove_fav = gr.Button(t_init.get("btn_remove_fav", "🗑️ Retirer ce favori"),
                                                            variant="stop", size="sm", scale=1)
                with gr.Column(scale=2, elem_id="dataset_drop_col"):
                    ui_dataset_drop_zone = gr.HTML(render_dataset_drop_zone(default_lang))
                    ui_load_btn = gr.Button(t_init.get("load", ""), variant="primary", elem_id="dataset_load_btn")
                    ui_status_text = gr.Markdown(t_init.get("status_wait", ""), elem_id="dataset_status_text")

        with gr.Column(scale=3, elem_id="recipe_header"):
            ui_recipe_global = gr.Markdown(t_init.get("recipe_global", ""))
            with gr.Row(elem_id="recipe_save_row"):
                ui_recipes_dropdown = gr.Dropdown(choices=list(load_recipes().keys()), label=t_init.get("recipes_dd", ""), scale=2)
                ui_recipe_name = gr.Textbox(label=t_init.get("recipe_name", ""), scale=1)
                ui_save_recipe_btn = gr.Button(t_init.get("save_recipe", ""), scale=1)
                ui_btn_delete_recipe = gr.Button(t_init.get("btn_delete_recipe", "🗑️ Supprimer"),
                                                  variant="stop", size="sm", scale=1)
            ui_tracked_words = gr.Textbox(show_label=False, placeholder=t_init.get("tracked_ph", ""), lines=1, elem_id="tracked_words_input")
            with gr.Row(elem_id="recipe_ai_row"):
                ui_ai_recipe_count = gr.Number(
                    value=20, precision=0,
                    label=t_init.get("ai_recipe_count", "Nombre de mots-clés IA"),
                    scale=1,
                )
                ui_btn_ai_recipe = gr.Button(
                    t_init.get("btn_ai_recipe", "🤖 Remplir par IA"),
                    variant="secondary", size="sm", scale=2, elem_id="ai_recipe_btn",
                )
                ui_btn_analyze_recipe = gr.Button(t_init.get("btn_analyze_recipe", "📊 Analyser"), variant="secondary", size="sm", scale=2, elem_id="analyze_recipe_btn")

    with gr.Row(elem_id="workbench_row"):
        with gr.Column(scale=0, elem_id="left_panel") as left_panel:
            ui_gallery_title = gr.Markdown(t_init.get("gallery_title", ""))
            ui_search_box = gr.Textbox(label=t_init.get("search", ""), placeholder=t_init.get("search_ph", ""), elem_id="gallery_search_box")
            with gr.Row(elem_id="gallery_sort_select_row"):
                ui_sort_order = gr.Radio(["A-Z", "Z-A"], value="A-Z", label=t_init.get("sort_label", "Trier / Sort"), elem_id="gallery_sort_radio", scale=2)
                ui_multi_select_cb = gr.Checkbox(label=_compact_multi_select_label(t_init.get("multi_cb", ""), default_lang), value=False, interactive=True, elem_id="multi_cb", scale=2)
                ui_select_all_btn = gr.Button(_compact_select_all_label(t_init.get("btn_select_all", ""), default_lang), elem_id="select_all_btn", size="sm", scale=1)
                ui_clear_sel_btn = gr.Button(t_init.get("clear_sel", ""), elem_id="clear_sel_btn", size="sm", scale=1)
                
            ui_selection_status = gr.Markdown("", elem_id="ui_selection_status")
            ui_csv_acc = gr.Accordion(t_init.get("csv_acc_title", "📋 Import / Export CSV (IA Captioning)"), open=False, elem_id="gallery_csv_acc")
            with ui_csv_acc:
                # Texte explicatif de l'usage de l'encart
                ui_csv_hint = gr.Markdown(t_init.get("csv_acc_hint", ""))
                # Dropzone en haut pour drag/drop
                ui_csv_import_file = gr.File(
                    label=t_init.get("csv_import_dropzone", "📥 Drop filled CSV/MD here"),
                    file_types=[".csv", ".md"],
                    file_count="single",
                    type="filepath",
                    visible=True,
                    elem_id="caption_import_dropzone",
                    min_width=200,
                )
                # Boutons compacts en grille 2x2
                with gr.Row():
                    ui_btn_export_csv_captions = gr.Button(t_init.get("btn_export_csv_captions", "⬇️ Export captions CSV"), scale=1, size="sm", variant="secondary")
                    ui_btn_export_md_captions = gr.Button(t_init.get("btn_export_md_captions", "⬇️ Export captions MD"), scale=1, size="sm", variant="secondary")
                with gr.Row():
                    ui_btn_import_csv_captions = gr.Button(t_init.get("btn_import_csv_captions", "⬆️ Import filled CSV"), scale=1, size="sm")
                    ui_btn_import_md_captions = gr.Button(t_init.get("btn_import_md_captions", "⬆️ Import filled MD"), scale=1, size="sm")
                ui_csv_status = gr.Markdown()
                # Texte explicatif et bouton Créer planche
                ui_csv_contact_hint = gr.Markdown(t_init.get("csv_contact_hint", "**💡 Or create contact sheets directly** (preview and export from the dedicated tab)"))
                with gr.Row():
                    ui_btn_open_contact_sheet = gr.Button(t_init.get("btn_open_contact_sheet", "🖼️ Create contact sheet(s)"), variant="primary", size="sm", scale=1)
            initial_gallery_cols = int(ui_settings_init.get("gallery_columns", DEFAULT_UI_SETTINGS["gallery_columns"]))
            ui_gallery_cols = gr.Slider(minimum=1, maximum=6, step=1, value=initial_gallery_cols, label=t_init.get("cols", ""), interactive=True, elem_id="gallery_cols_slider")
            gallery = gr.Gallery(label="Dataset", columns=initial_gallery_cols, rows=6, height=750, object_fit="cover", allow_preview=False, elem_id="main_gallery")
            
        with gr.Column(scale=1, elem_id="center_panel"):
            with gr.Row(elem_id="panel_toggles_row"):
                ui_toggle_panel_btn = gr.Button(t_init.get("hide_gal", ""), elem_id="toggle_gallery_btn", variant="secondary", size="sm")
                ui_toggle_right_btn = gr.Button(t_init.get("hide_lib", "Masquer la Bibliothèque ▶"), elem_id="toggle_right_btn", variant="secondary", size="sm")
            
            with gr.Tabs():
                ui_tab_view = gr.Tab(t_init.get("tab_view", ""))
                with ui_tab_view:
                    with gr.Row():
                        ui_btn_prev = gr.Button(t_init.get("btn_prev", ""), elem_id="prev_btn")
                        ui_btn_next = gr.Button(t_init.get("btn_next", ""), elem_id="next_btn")
                        ui_btn_delete_current = gr.Button(t_init.get("btn_delete_current", "🗑️ Supprimer cette image"), variant="stop", elem_id="delete_current_btn")
                    ui_viewer_status = gr.Markdown("")
                    with gr.Row():
                        current_img = gr.Image(interactive=False, type="filepath", height=350, elem_id="viewer_area")
                        with gr.Column(elem_id="viewer_area_text"):
                            highlight_preview = gr.HTML()
                            word_counter = gr.HTML("<div style='color:green;'>0</div>")
                            with gr.Accordion("🎹 Actions / Shortcuts", open=False, elem_id="viewer_shortcuts_acc"):
                                ui_viewer_shortcuts = gr.Markdown(t_init.get("shortcuts", ""))
                            ui_toggle_tag_btn = gr.Button(t_init.get("toggle_stat", ""), variant="secondary", elem_id="toggle_tag_btn")
                    
                    current_caption = gr.Textbox(show_label=False, lines=4, elem_id="viewer_caption_area")
                    ui_live_translation_output = gr.Textbox(label=t_init.get("live_trans_label", ""), interactive=True, lines=3, elem_id="live_translation_preview")
                    
                    ui_save_single_btn = gr.Button(t_init.get("save_cap", ""), variant="primary", elem_id="save_single_btn")
                    ui_single_save_status = gr.Markdown()
                    
                    with gr.Accordion(t_init.get("trans_module_title", "🌍 Assistant de Traduction"), open=False, elem_classes="panel-translate") as ui_trans_module_acc:
                        ui_trans_module_title = gr.Markdown(visible=False)
                        with gr.Row():
                            with gr.Column(scale=2):
                                ui_trans_engine = gr.Radio(["Google (Online)", "IA Locale (Ollama/LM Studio)"], label=t_init.get("trans_engine", ""), value="Google (Online)")
                            with gr.Column(scale=1):
                                ui_trans_source = gr.Dropdown(["auto", "fr", "es", "de", "it", "pt", "ru", "ja", "ko", "zh-CN"], label=t_init.get("trans_source", ""), value="auto")
                            with gr.Column(scale=1):
                                ui_trans_target = gr.Dropdown(["fr", "en", "es", "de", "it", "pt", "ru", "ja", "ko", "zh-CN"], label=t_init.get("trans_target", ""), value="fr")
                        
                        ui_btn_translate_entire_caption = gr.Button(t_init.get("btn_translate_entire", ""), elem_id="btn_translate_entire")
                        gr.Markdown("---")
                        ui_trans_insert_title = gr.Markdown(t_init.get("trans_insert_title", ""))
                        with gr.Row():
                            with gr.Column(scale=3):
                                ui_trans_input = gr.Textbox(show_label=False, placeholder=t_init.get("trans_input_ph", ""), lines=1)
                            with gr.Column(scale=1):
                                ui_btn_insert_trans = gr.Button(t_init.get("btn_insert_trans", ""))

                ui_tab_batch = gr.Tab(t_init.get("tab_batch", ""))
                with ui_tab_batch:
                    ui_btn_undo = gr.Button(t_init.get("btn_undo", ""), variant="stop")
                    ui_batch_status = gr.Markdown()
                    with gr.Row():
                        with gr.Group():
                            ui_btn_clean_com = gr.Button(t_init.get("btn_clean_com", ""))
                            ui_btn_clean_dup = gr.Button(t_init.get("btn_clean_dup", ""))
                    ui_preview_table = gr.Dataframe(label=t_init.get("df_preview", ""), interactive=False)

                ui_tab_prep = gr.Tab(t_init.get("tab_prep", ""))
                with ui_tab_prep:
                    with gr.Row(elem_id="prep_workspace"):
                        with gr.Column(scale=1, elem_id="prep_duplicate_panel"):
                            ui_dup_title = gr.Markdown(t_init.get("dup_title", ""))
                            prep_hash_algo = gr.Dropdown(["average_hash", "phash", "dhash", "whash"], value="phash", label=t_init.get("hash_algo", "Algorithme de hash"))
                            ui_hash_tol = gr.Slider(0, 20, 5, step=1, label=t_init.get("hash_tol", ""))
                            ui_hash_tol_help = gr.Markdown(t_init.get("hash_tol_help", ""))
                            btn_scan_dups = gr.Button(t_init.get("btn_scan_dups", ""))
                            dup_dropdown = gr.Dropdown(label=t_init.get("dup_dd", ""), interactive=True)
                            dup_recommendation = gr.Markdown(elem_id="dup_recommendation")
                            with gr.Row():
                                dup_img_A = gr.Image(label="Image A", interactive=False, height=200)
                                dup_img_B = gr.Image(label="Image B", interactive=False, height=200)
                            with gr.Row():
                                dup_caption_A = gr.Textbox(label=t_init.get("dup_caption_A", "Caption A"), interactive=False, lines=4)
                                dup_caption_B = gr.Textbox(label=t_init.get("dup_caption_B", "Caption B"), interactive=False, lines=4)
                            with gr.Row():
                                btn_del_A = gr.Button(t_init.get("btn_del_A", ""), variant="stop")
                                btn_skip_dup = gr.Button(t_init.get("btn_skip_dup", "⏭️ Ignorer ce doublon"))
                                btn_del_B = gr.Button(t_init.get("btn_del_B", ""), variant="stop")
                            btn_delete_recommended_dup = gr.Button(t_init.get("btn_delete_recommended_dup", "🧠 Delete recommended duplicate"), variant="stop")
                            btn_delete_all_b = gr.Button(t_init.get("btn_delete_all_b", "🗑️ Supprimer tous les B"), variant="stop")
                            dup_status = gr.Markdown()
                        with gr.Column(scale=1, elem_id="prep_transform_panel"):
                            ui_rename_title = gr.Markdown(t_init.get("rename_title", ""))
                            ui_rename_prefix = gr.Textbox(label=t_init.get("rename_prefix", ""), placeholder="concept")
                            btn_rename = gr.Button(t_init.get("btn_rename", ""))
                            gr.Markdown("---")
                            ui_resize_title = gr.Markdown(t_init.get("resize_title", ""))
                            with gr.Row(elem_id="prep_preset_row"):
                                prep_preset = gr.Dropdown(
                                    list(PREP_WORKFLOW_PRESETS.keys()),
                                    value="Flux LoRA 1024 · WebP",
                                    label=t_init.get("prep_preset", "Workflow preset"),
                                    interactive=True,
                                )
                                btn_apply_prep_preset = gr.Button(t_init.get("btn_apply_prep_preset", "⚡ Apply"), size="sm")
                            prep_size = gr.Dropdown(["512", "768", "1024", "1536"], value="1024", label=t_init.get("prep_size", ""))
                            prep_format = gr.Dropdown(["WebP", "JPEG", "PNG"], value="WebP", label=t_init.get("prep_format", ""))
                            prep_crop = gr.Dropdown(["Conserver Ratio", "1:1 (Carré Centre)", "Smart Face Crop (OpenCV)"], value="Conserver Ratio", label=t_init.get("prep_crop", ""))
                            prep_alpha = gr.Checkbox(value=True, label=t_init.get("prep_alpha", ""))
                            prep_dest = gr.Textbox(label=t_init.get("prep_dest", ""), placeholder="...")
                            prep_quick_summary = gr.HTML(prep_workflow_summary([], [], "", "1024", "WebP", "Conserver Ratio", True, default_lang))
                            btn_prep = gr.Button(t_init.get("btn_prep", ""), variant="primary")
                            prep_status = gr.Markdown()
                            gr.Markdown("---")
                            with gr.Group(elem_id="prep_low_res_panel"):
                                prep_min_res = gr.Number(label=t_init.get("prep_min_res", "Résolution minimum (px) — 0 = pas de filtre"), value=0, precision=0)
                                with gr.Row():
                                    btn_detect_low_res = gr.Button(t_init.get("btn_detect_low_res", "🔍 Détecter sous ce seuil"))
                                    btn_move_low_res = gr.Button(t_init.get("btn_move_low_res", "📦 Déplacer dans '_trop_petites'"), variant="secondary")
                                low_res_df = gr.Dataframe(headers=["ID", "Image", "Largeur", "Hauteur", "Min"], interactive=False)

                    with gr.Accordion(t_init.get("manual_crop_acc", "✂️ Manual crop (image by image)"), open=False, elem_id="manual_crop_acc"):
                        manual_crop_hint = gr.Markdown(t_init.get("manual_crop_hint", "Load the current image, choose a ratio, adjust the crop on the canvas, then overwrite the image file directly."))
                        manual_crop_canvas = gr.HTML(render_manual_cropper(default_lang))
                        with gr.Row(elem_id="manual_crop_nav"):
                            btn_manual_crop_prev = gr.Button(t_init.get("btn_manual_crop_prev", "⬅️ Previous"), size="sm", elem_id="manual_crop_prev_btn")
                            btn_manual_crop_next = gr.Button(t_init.get("btn_manual_crop_next", "➡️ Next / Skip"), size="sm", elem_id="manual_crop_next_btn")
                        manual_crop_editor = gr.ImageEditor(
                            label=t_init.get("manual_crop_editor", "Crop source"),
                            type="pil",
                            image_mode="RGBA",
                            transforms=("crop",),
                            brush=False,
                            eraser=False,
                            layers=False,
                            height=420,
                            elem_id="manual_crop_editor",
                            buttons=["fullscreen", "download"],
                        )
                        with gr.Row(elem_id="manual_crop_actions", visible=False):
                            btn_load_manual_crop = gr.Button(t_init.get("btn_load_manual_crop", "↙️ Load current image"), size="sm", elem_id="manual_crop_backend_load_btn")
                            btn_save_manual_crop = gr.Button(t_init.get("btn_save_manual_crop", "💾 Save crop"), variant="secondary", size="sm")
                            btn_save_manual_crop_next = gr.Button(t_init.get("btn_save_manual_crop_next", "💾 Save & next"), variant="secondary", size="sm")
                        manual_crop_status = gr.Markdown()

                ui_tab_ai = gr.Tab(t_init.get("tab_ai", ""))
                with ui_tab_ai:
                    with gr.Row():
                        with gr.Column(scale=1, elem_classes="panel-purple"):
                            ui_ai_conf_title = gr.Markdown(t_init.get("ai_conf_title", ""))
                            api_backend = gr.Radio(
                                [
                                    "Ollama",
                                    "API OpenAI / LM Studio (GGUF locaux)",
                                    "Anthropic Claude (Cloud)",
                                    "Google Gemini (Cloud)",
                                ],
                                label=t_init.get("api_backend", ""),
                                value=ai_settings_init.get("api_backend", DEFAULT_AI_SETTINGS["api_backend"]),
                            )
                            vlm_model = gr.Textbox(value=ai_settings_init.get("vlm_model", DEFAULT_AI_SETTINGS["vlm_model"]), label=t_init.get("vlm_model", ""))
                            llm_model = gr.Textbox(value=ai_settings_init.get("llm_model", DEFAULT_AI_SETTINGS["llm_model"]), label=t_init.get("llm_model", ""))
                            with gr.Accordion(t_init.get("ai_adv_acc", ""), open=False) as ui_ai_adv_acc:
                                api_url_input = gr.Textbox(value=ai_settings_init.get("api_url", DEFAULT_AI_SETTINGS["api_url"]), label=t_init.get("api_url_input", ""))
                                api_key_input = gr.Textbox(
                                    value=ai_settings_init.get("api_key", DEFAULT_AI_SETTINGS["api_key"]), label=t_init.get("api_key_input", "API Key (cloud services)"),
                                    type="password",
                                    placeholder="sk-..., AIza..., ...",
                                )
                                ai_temp = gr.Slider(minimum=0.0, maximum=2.0, value=ai_settings_init.get("temperature", DEFAULT_AI_SETTINGS["temperature"]), step=0.1, label=t_init.get("ai_temp", ""))
                                ai_ctx = gr.Number(value=ai_settings_init.get("context", DEFAULT_AI_SETTINGS["context"]), label=t_init.get("ai_ctx", ""))
                                api_timeout = gr.Number(value=ai_settings_init.get("timeout", DEFAULT_AI_SETTINGS["timeout"]), precision=0, label=t_init.get("ai_timeout", "Timeout API (secondes)"))
                                ai_sys = gr.Textbox(value=ai_settings_init.get("system_prompt", DEFAULT_AI_SETTINGS["system_prompt"]), label=t_init.get("ai_sys", ""), lines=2)

                            # 🎯 LM Studio : Chargement automatique des modèles favoris
                            ui_lm_studio_acc = gr.Accordion(t_init.get("lm_studio_acc", "🎯 LM Studio: Auto-Load"), open=False)
                            with ui_lm_studio_acc:
                                ui_lm_studio_list_btn = gr.Button(
                                    t_init.get("lm_studio_list_btn", "🔄 Refresh models list"),
                                    size="sm",
                                )
                                ui_lm_studio_vlm_dd = gr.Dropdown(
                                    choices=[], label=t_init.get("lm_studio_vlm_dd", "VLM"),
                                    value=ai_settings_init.get("vlm_model", DEFAULT_AI_SETTINGS["vlm_model"]),
                                    allow_custom_value=True, interactive=True,
                                )
                                ui_lm_studio_llm_dd = gr.Dropdown(
                                    choices=[], label=t_init.get("lm_studio_llm_dd", "LLM"),
                                    value=ai_settings_init.get("llm_model", DEFAULT_AI_SETTINGS["llm_model"]),
                                    allow_custom_value=True, interactive=True,
                                )
                                ui_lm_studio_shared_dd = gr.Dropdown(
                                    choices=[], label=t_init.get("lm_studio_shared_dd", "Same model for VLM + LLM"),
                                    value=ai_settings_init.get("lm_studio_shared_model", DEFAULT_AI_SETTINGS["lm_studio_shared_model"]),
                                    allow_custom_value=True, interactive=True,
                                )
                                with gr.Row():
                                    ui_lm_studio_load_vlm = gr.Button(
                                        t_init.get("lm_studio_load_vlm", "⚡ Load VLM"), size="sm",
                                    )
                                    ui_lm_studio_load_llm = gr.Button(
                                        t_init.get("lm_studio_load_llm", "⚡ Load LLM"), size="sm",
                                    )
                                    ui_lm_studio_load_shared = gr.Button(
                                        t_init.get("lm_studio_load_shared", "⚡ Load shared model"), size="sm",
                                    )
                                with gr.Row():
                                    ui_lm_studio_unload_vlm = gr.Button(
                                        t_init.get("lm_studio_unload_vlm", "🧹 Unload VLM"), size="sm",
                                    )
                                    ui_lm_studio_unload_llm = gr.Button(
                                        t_init.get("lm_studio_unload_llm", "🧹 Unload LLM"), size="sm",
                                    )
                                    ui_lm_studio_unload_shared = gr.Button(
                                        t_init.get("lm_studio_unload_shared", "🧹 Unload shared"), size="sm",
                                    )
                                ui_lm_studio_save_choices = gr.Button(
                                    t_init.get("lm_studio_save_choices", "💾 Save model choices"), size="sm", variant="secondary",
                                )
                                ui_lm_studio_status = gr.Markdown(label=t_init.get("lm_studio_status", "LM Studio Status"))
                        with gr.Column(scale=2):
                            ui_ai_act_title = gr.Markdown(t_init.get("ai_act_title", ""))
                            ai_format_preset = gr.Dropdown(choices=list(load_ai_format_presets().keys()), value="Personnalisé", label=t_init.get("ai_format_preset", "📋 Caption structure preset"))
                            ai_action_dropdown = gr.Dropdown(load_ai_action_choices(), label=t_init.get("ai_action_dd", "⚙️ AI action to run"), value="Auto-Taggage / Super OCR (VLM)")
                            ai_action_desc = gr.HTML()
                            with gr.Group(visible=False) as custom_prompt_group:
                                with gr.Row():
                                    ai_template_dd = gr.Dropdown(choices=load_ai_template_choices(), label=t_init.get("ai_tpl_dd", ""))
                                    ai_template_name = gr.Textbox(label=t_init.get("ai_tpl_name", ""))
                                    btn_save_template = gr.Button(t_init.get("btn_save_tpl", ""))
                                custom_prompt_input = gr.Textbox(label=t_init.get("custom_prompt_input", ""), placeholder="...", lines=3)
                                use_vision_for_custom = gr.Checkbox(label=t_init.get("use_vision_custom", ""))
                            with gr.Group(visible=True) as injection_group:
                                injection_mode = gr.Radio(["Remplacer tout", "Ajouter au début", "Ajouter à la fin"], label=t_init.get("injection_mode", ""), value="Remplacer tout")
                                ai_injection_note = gr.Markdown(t_init.get("ai_injection_note", ""))
                            with gr.Accordion(t_init.get("ai_action_manager_acc", "🛠️ Edit / create AI actions (JSON)"), open=False, elem_id="ai_action_manager"):
                                with gr.Row():
                                    ai_action_edit_name = gr.Textbox(label=t_init.get("ai_action_edit_name", "Action name"), value="Auto-Taggage / Super OCR (VLM)")
                                    ai_action_edit_vision = gr.Checkbox(label=t_init.get("ai_action_edit_vision", "Use image/VLM"), value=True)
                                    ai_action_edit_injection = gr.Radio(["Remplacer tout", "Ajouter au début", "Ajouter à la fin"], label=t_init.get("ai_action_edit_injection", "Default injection"), value="Remplacer tout")
                                ai_action_edit_desc = gr.Textbox(label=t_init.get("ai_action_edit_desc", "Short description"), lines=2, value="Analyse complète de l'image et extraction du texte.")
                                ai_action_edit_prompt = gr.Textbox(
                                    label=t_init.get("ai_action_edit_prompt", "Prompt template"),
                                    placeholder="{tags} / {caption} / {filename}",
                                    lines=5,
                                    value=AI_ACTION_PROMPTS["Auto-Taggage / Super OCR (VLM)"],
                                )
                                with gr.Row(elem_id="ai_action_manager_buttons"):
                                    btn_save_ai_action = gr.Button(t_init.get("btn_save_ai_action", "💾 Save action"), variant="primary", size="sm")
                                    btn_delete_ai_action = gr.Button(t_init.get("btn_delete_ai_action", "🗑️ Delete custom override"), variant="stop", size="sm")
                                with gr.Row(elem_id="ai_action_json_buttons"):
                                    ai_actions_import_file = gr.File(label=t_init.get("ai_actions_import_file", "Import JSON"), file_types=[".json"], file_count="single", type="filepath")
                                    btn_import_ai_actions = gr.Button(t_init.get("btn_import_ai_actions", "⬆️ Import actions"), size="sm")
                                    btn_export_ai_actions = gr.Button(t_init.get("btn_export_ai_actions", "⬇️ Export actions"), size="sm")
                                ai_actions_export_file = gr.File(label=t_init.get("ai_actions_export_file", "Exported JSON"), interactive=False)
                                ai_actions_manage_status = gr.Markdown()
                            with gr.Row():
                                btn_run_ai = gr.Button(t_init.get("btn_run_ai", ""), variant="primary")
                                btn_test_ai = gr.Button(t_init.get("btn_test_ai", "🧪 Tester sur l'image courante"), variant="secondary")
                                btn_select_no_caption = gr.Button(t_init.get("btn_select_no_caption", "🎯 Sélectionner sans caption"), variant="secondary")
                                btn_undo_ai = gr.Button(t_init.get("btn_undo_ai", ""), variant="stop")
                            ai_status = gr.Markdown()
                    gr.Markdown("---")
                    ui_bias_title = gr.Markdown(t_init.get("bias_title", ""))
                    btn_bias = gr.Button(t_init.get("btn_bias", ""), variant="secondary")
                    bias_stale_notice = gr.Markdown()
                    txt_bias = gr.Textbox(label=t_init.get("txt_bias", ""), lines=5, interactive=False)

                ui_tab_export = gr.Tab(t_init.get("tab_export", ""))
                with ui_tab_export:
                    with gr.Row():
                        with gr.Column(scale=1):
                            ui_exp_edit = gr.Markdown(t_init.get("exp_edit", ""))
                            with gr.Row():
                                ui_btn_up = gr.Button(t_init.get("btn_up", ""), variant="secondary", size="sm", elem_id="btn_move_up")
                                ui_btn_down = gr.Button(t_init.get("btn_down", ""), variant="secondary", size="sm", elem_id="btn_move_down")
                                ui_btn_del = gr.Button(t_init.get("btn_del", ""), variant="stop", size="sm")
                            with gr.Row():
                                ui_quick_prio = gr.Dropdown(label=t_init.get("quick_prio", ""), choices=[str(i) for i in range(1, 101)], allow_custom_value=True, scale=1)
                                ui_quick_target = gr.Number(label=t_init.get("quick_tgt", ""), scale=1)
                                
                            ui_export_config_df = gr.Dataframe(headers=t_init.get("exp_df_headers", []), interactive=True, type="pandas", row_count=("dynamic"), column_count=(3, "fixed"), elem_id="export_recipe_df")
                            ui_strategy_radio = gr.Radio(t_init.get("strat_choices", []), value=t_init.get("strat_choices", [""])[0] if t_init.get("strat_choices") else "", label=t_init.get("strat", ""))
                            ui_max_img_input = gr.Number(label=t_init.get("max_img", ""), value=0, precision=0)
                            ui_export_dir = gr.Textbox(label=t_init.get("dest_folder", ""), placeholder=t_init.get("dest_ph", ""))
                            ui_export_suffix = gr.Textbox(value="-Sx", label=t_init.get("export_suffix", "Suffixe d'export"), placeholder=t_init.get("export_suffix_ph", "-Sx → -S1, -S2, -S3..."))
                            with gr.Row():
                                ui_btn_simul = gr.Button(t_init.get("btn_simul", ""), variant="secondary")
                                ui_btn_exp = gr.Button(t_init.get("btn_exp", ""), variant="primary")
                        with gr.Column(scale=1):
                            ui_export_status = gr.Markdown()
                            export_pie = gr.Plot(label=t_init.get("overall_dist", ""))
                    ui_exp_gal = gr.Markdown(t_init.get("exp_gal", ""))
                    export_gallery = gr.Gallery(columns=8, rows=2, height=250, object_fit="contain", allow_preview=False)

                ui_tab_stats = gr.Tab(t_init.get("tab_stats", ""))
                with ui_tab_stats:
                    ui_stats_status = gr.Markdown()
                    with gr.Row():
                        with gr.Column(scale=1):
                            ui_stats_table = gr.Dataframe(headers=t_init.get("stat_df_headers", []), interactive=True, type="pandas", row_count=("dynamic"))
                            ui_btn_civitai = gr.Button(t_init.get("btn_civitai", ""), variant="secondary")
                            with gr.Row():
                                ui_btn_export_stats_csv = gr.Button(t_init.get("btn_export_stats_csv", "Exporter CSV"), size="sm")
                                ui_btn_export_stats_md = gr.Button(t_init.get("btn_export_stats_md", "Exporter Markdown"), size="sm")
                            ui_stats_export_file = gr.File(label=t_init.get("stats_export_file", "Fichier exporté"), interactive=False)
                            ui_civitai_output = gr.Textbox(label="Format", interactive=False, lines=5)
                            with gr.Row():
                                ui_btn_top20 = gr.Button(t_init.get("btn_top20", ""))
                                ui_btn_orph = gr.Button(t_init.get("btn_orph", ""))
                            ui_txt_orph = gr.Textbox(label=t_init.get("txt_orph", ""), lines=4)
                        with gr.Column(scale=2):
                            pie_chart = gr.Plot(label="Graphique (Répartition)")
                            bar_chart = gr.Plot(label="Graphique (Occurrences)")
                            gr.Markdown("---")
                            ui_adv_stats_title = gr.Markdown(t_init.get("adv_stats_title", ""))
                            ui_adv_stats_help = gr.Markdown(t_init.get("adv_stats_help", ""))
                            btn_calc_adv = gr.Button(t_init.get("btn_calc_adv", ""), variant="primary")
                            with gr.Row():
                                with gr.Column():
                                    plot_heatmap = gr.Plot(label=t_init.get("adv_heatmap_label", "Matrice"))
                                    ui_heatmap_help = gr.Markdown(t_init.get("adv_heatmap_help", ""))
                                with gr.Column():
                                    plot_bucket = gr.Plot(label=t_init.get("adv_bucket_label", "Résolutions"))
                                    ui_bucket_help = gr.Markdown(t_init.get("adv_bucket_help", ""))
                            with gr.Row():
                                with gr.Column():
                                    txt_anti = gr.Textbox(label=t_init.get("anti_title", ""), lines=6, interactive=False)
                                    ui_anti_help = gr.Markdown(t_init.get("anti_help", ""))
                                with gr.Column():
                                    txt_contra = gr.Textbox(label=t_init.get("contra_title", ""), lines=6, interactive=False)
                                    ui_contra_help = gr.Markdown(t_init.get("contra_help", ""))

                ui_tab_contact = gr.Tab(t_init.get("contact_tab_title", "🖼️ Planche(s) compilation(s)"))
                with ui_tab_contact:
                    with gr.Row():
                        with gr.Column(scale=1, min_width=300, elem_id="contact_sheet_controls"):
                            # === SOURCE & ACTIONS PRINCIPALES ===
                            contact_source_mode = gr.Radio(
                                _contact_source_choices(default_lang),
                                value=_valid_choice_value(contact_settings_init["source_mode"], CONTACT_SHEET_SOURCE_CHOICES, CONTACT_SHEET_DEFAULTS["source_mode"]),
                                label=t_init.get("contact_source_label", "📸 Images à compiler"),
                            )

                            with gr.Row():
                                contact_btn_preview = gr.Button(t_init.get("contact_btn_preview", "👁️ Aperçu"), variant="secondary", scale=1)
                                contact_btn_export = gr.Button(t_init.get("contact_btn_export", "🚀 Exporter"), variant="primary", scale=1)

                            # === PARAMÈTRES EN ACCORDÉONS (fermés par défaut pour compacité) ===
                            contact_layout_acc = gr.Accordion(t_init.get("contact_layout_acc", "📐 Mise en page"), open=False)
                            with contact_layout_acc:
                                contact_output_width = gr.Number(value=contact_settings_init["output_width"], label=t_init.get("contact_output_width", "Largeur finale (px)"), precision=0)
                                with gr.Row():
                                    contact_flexible_cols = gr.Checkbox(value=False, label=t_init.get("contact_flexible", "🔄 Flexible (auto-colonnes)"), scale=2)
                                    contact_images_per_row = gr.Slider(1, 24, value=contact_settings_init["images_per_row"], step=1, label=t_init.get("contact_images_per_row", "Colonnes"), scale=1)
                                contact_spacing = gr.Slider(0, 100, value=contact_settings_init["spacing"], step=5, label=t_init.get("contact_spacing", "Espacement (px)"))
                                contact_margin = gr.Slider(0, 200, value=contact_settings_init["margin"], step=10, label=t_init.get("contact_margin", "Marge (px)"))
                                contact_background = gr.ColorPicker(value=contact_settings_init["background"], label=t_init.get("contact_background", "Couleur fond"))

                            contact_format_acc = gr.Accordion(t_init.get("contact_format_acc", "🖼️ Format images"), open=False)
                            with contact_format_acc:
                                contact_ratio_mode = gr.Radio(
                                    _contact_ratio_mode_choices(default_lang),
                                    value=_contact_ratio_mode_from_setting(contact_settings_init["ratio"]),
                                    label=t_init.get("contact_ratio_label", "Rapport d'aspect")
                                )
                                contact_fit_mode = gr.Dropdown(
                                    _contact_fit_choices(default_lang),
                                    value=_valid_choice_value(contact_settings_init["fit_mode"], CONTACT_SHEET_FIT_CHOICES, CONTACT_SHEET_DEFAULTS["fit_mode"]),
                                    label=t_init.get("contact_fit_mode", "Remplissage"),
                                )
                                contact_sort_alpha = gr.Checkbox(value=contact_settings_init["sort_alpha"], label=t_init.get("contact_sort_alpha", "↪️ Ignorer le tri de la galerie"))

                            contact_text_acc = gr.Accordion(t_init.get("contact_text_acc", "🔤 Texte & Labels"), open=False)
                            with contact_text_acc:
                                contact_label_mode = gr.Dropdown(
                                    _contact_label_choices(default_lang),
                                    value=_valid_choice_value(contact_settings_init["label_mode"], CONTACT_SHEET_LABEL_CHOICES, CONTACT_SHEET_DEFAULTS["label_mode"]),
                                    label=t_init.get("contact_label_mode", "Type de label"),
                                )
                                contact_font_size = gr.Slider(8, 200, value=contact_settings_init["font_size"], step=5, label=t_init.get("contact_font_size", "Taille police (px)"))
                                contact_label_opacity = gr.Slider(0, 100, value=contact_settings_init["label_opacity"], step=10, label=t_init.get("contact_label_opacity", "Opacité fond (%)"))

                            contact_export_acc = gr.Accordion(t_init.get("contact_export_acc", "⚙️ Export avancé"), open=False)
                            with contact_export_acc:
                                contact_limit_enabled = gr.Checkbox(value=contact_settings_init["limit_enabled"], label=t_init.get("contact_multi_sheets", "📚 Multiples planches"))
                                contact_images_per_sheet = gr.Number(value=contact_settings_init["images_per_sheet"], label=t_init.get("contact_images_per_sheet", "Images par planche"), precision=0)
                                contact_continue_numbering = gr.Checkbox(value=contact_settings_init["continue_numbering"], label=t_init.get("contact_continue_numbering", "↪️ Continuer numérotation"))
                                contact_output_dir = gr.Textbox(value=contact_settings_init["output_dir"], label=t_init.get("contact_output_dir", "Dossier sortie"), placeholder=t_init.get("contact_output_dir_ph", "= dataset/planches_compilation"))
                                contact_filename_prefix = gr.Textbox(value=contact_settings_init["filename_prefix"], label=t_init.get("contact_filename_prefix", "Préfixe fichier"))
                                with gr.Row():
                                    contact_export_format = gr.Dropdown(
                                        _contact_format_choices(default_lang),
                                        value=_valid_choice_value(contact_settings_init["export_format"], CONTACT_SHEET_FORMAT_CHOICES, CONTACT_SHEET_DEFAULTS["export_format"]),
                                        label=t_init.get("contact_export_format", "Format"),
                                        scale=1,
                                    )
                                    contact_quality = gr.Slider(1, 100, value=contact_settings_init["quality"], step=5, label=t_init.get("contact_quality", "Qualité"), scale=1)
                                contact_resize_final = gr.Slider(25, 200, value=100, step=25, label=t_init.get("contact_resize_final", "🔍 Resize final (%)"))

                            contact_btn_save_settings = gr.Button(t_init.get("contact_btn_save", "💾 Sauvegarder"), variant="secondary", size="sm")
                            contact_status = gr.Markdown(t_init.get("contact_status_loading", "⏳ Chargement..."))

                        with gr.Column(scale=2, elem_id="contact_sheet_preview_panel"):
                            with gr.Row():
                                with gr.Column(scale=2):
                                    contact_preview_title = gr.Markdown(f"### {t_init.get('contact_preview_title', '👁️ Aperçu live')}")
                                with gr.Column(scale=1):
                                    contact_btn_back_to_live = gr.Button(t_init.get("contact_preview_back", "🔄 Planche témoin"), variant="secondary", size="sm")
                            contact_preview_gallery = gr.Gallery(label="", columns=1, rows=1, height="auto", object_fit="contain", allow_preview=False, elem_id="contact_preview_live")
                            contact_export_files = gr.File(label=t_init.get("contact_preview_exported", "📥 Fichiers exportés"), file_count="multiple", interactive=False)

        with gr.Column(scale=0, elem_id="right_panel") as right_panel:
            ui_lib_title = gr.HTML(t_init.get("lib_title", ""))
            
            ui_lib_mode = gr.Radio(t_init.get("lib_mode_choices", []), label=t_init.get("lib_mode", ""), value=t_init.get("lib_mode_choices", [""])[0] if t_init.get("lib_mode_choices") else "")
            ui_lib_target = gr.Textbox(label=t_init.get("lib_target_rem", ""), placeholder="Ex: 1girl", visible=False)
            
            ui_btn_apply_lib = gr.Button(t_init.get("btn_apply_lib_add", ""), variant="primary")
            
            gr.Markdown("---")
            ui_lib_add_text = gr.Textbox(show_label=False, lines=3, placeholder=t_init.get("lib_add_text_ph", ""))
            ui_btn_add_to_lib = gr.Button(t_init.get("btn_add_to_lib", ""), size="sm")
            
            with gr.Row():
                ui_btn_uncheck_all = gr.Button(t_init.get("btn_uncheck_all", ""), size="sm")
                ui_btn_clear_lib = gr.Button(t_init.get("btn_clear_lib", ""), variant="stop", size="sm")
            
            gr.Markdown("---")
            ui_lib_list_title = gr.Markdown(t_init.get("lib_list_title", ""))
            
            ui_lib_html = gr.HTML(render_lib_html(initial_library, default_lang))

# ==========================================
# CÂBLAGE DES ÉVÉNEMENTS
# ==========================================

    lang_radio.change(
        fn=change_language, 
        inputs=[
            lang_radio, ui_stats_table, ui_export_config_df, lib_state, ui_strategy_radio, include_subfolders_state,
            contact_source_mode, contact_ratio_mode, contact_fit_mode, contact_label_mode, contact_export_format,
        ],
        outputs=[
            ui_title, ui_settings_acc, ui_guide_acc, ui_guide_text, ui_dataset_drop_zone, ui_browse_btn, ui_load_btn, ui_include_subfolders, ui_status_text,
            ui_recipe_global, ui_recipes_dropdown, ui_recipe_name, ui_save_recipe_btn, ui_tracked_words, ui_ai_recipe_count, ui_btn_ai_recipe, ui_btn_analyze_recipe,
            ui_gallery_title, ui_search_box, ui_multi_select_cb, ui_select_all_btn, ui_clear_sel_btn, ui_gallery_cols,
            ui_toggle_panel_btn, ui_tab_view, ui_btn_prev, ui_btn_next, ui_btn_delete_current, ui_viewer_shortcuts, ui_toggle_tag_btn,
            ui_live_translation_output, ui_save_single_btn,
            ui_trans_module_title, ui_trans_engine, ui_trans_source, ui_trans_target,
            ui_btn_translate_entire_caption, ui_trans_insert_title, ui_trans_input, ui_btn_insert_trans,
            ui_tab_batch, ui_btn_undo, ui_btn_clean_com, ui_btn_clean_dup, ui_preview_table,
            ui_tab_prep, ui_dup_title, prep_hash_algo, ui_hash_tol, ui_hash_tol_help, btn_scan_dups, dup_dropdown, dup_caption_A, dup_caption_B, btn_del_A, btn_skip_dup, btn_del_B, btn_delete_all_b,
            ui_rename_title, ui_rename_prefix, btn_rename, ui_resize_title, prep_size, prep_format, prep_crop, prep_alpha, prep_dest, btn_prep, prep_min_res, btn_detect_low_res, btn_move_low_res,
            ui_tab_ai, ui_ai_conf_title, api_backend, vlm_model, llm_model, ui_ai_adv_acc, api_url_input, ai_temp, ai_ctx, api_timeout, ai_sys,
            ui_ai_act_title, ai_format_preset, ai_action_dropdown, ai_template_dd, ai_template_name, btn_save_template, custom_prompt_input, use_vision_for_custom, injection_mode, ai_injection_note, btn_run_ai, btn_test_ai, btn_select_no_caption, btn_undo_ai,
            ui_bias_title, btn_bias, txt_bias,
            ui_tab_export, ui_exp_edit, ui_btn_up, ui_btn_down, ui_btn_del, ui_quick_prio, ui_quick_target, ui_export_config_df, ui_strategy_radio, ui_max_img_input, ui_export_dir, ui_export_suffix, ui_btn_simul, ui_btn_exp, export_pie, ui_exp_gal,
            ui_tab_stats, ui_stats_table, ui_btn_civitai, ui_btn_export_stats_csv, ui_btn_export_stats_md, ui_btn_top20, ui_btn_orph, ui_txt_orph, pie_chart, bar_chart,
            ui_adv_stats_title, ui_adv_stats_help, btn_calc_adv, plot_heatmap, ui_heatmap_help, plot_bucket, ui_bucket_help,
            txt_anti, ui_anti_help, txt_contra, ui_contra_help,
            ui_lib_title, ui_lib_mode, ui_lib_target, ui_btn_apply_lib, ui_lib_add_text, ui_btn_add_to_lib, ui_btn_uncheck_all, ui_btn_clear_lib, ui_lib_list_title, ui_lib_html,
            # Composants persistants et réglages avancés
            ui_fav_section_title, ui_fav_dropdown, ui_btn_add_fav, ui_btn_remove_fav,
            ui_lang_import_acc, ui_lang_import_info, ui_lang_import_file, ui_lang_import_btn,
            ui_btn_delete_recipe, ui_sort_order, api_key_input,
            ui_lm_studio_acc, ui_lm_studio_list_btn, ui_lm_studio_vlm_dd, ui_lm_studio_llm_dd, ui_lm_studio_shared_dd,
            ui_lm_studio_load_vlm, ui_lm_studio_load_llm, ui_lm_studio_load_shared,
            ui_lm_studio_unload_vlm, ui_lm_studio_unload_llm, ui_lm_studio_unload_shared, ui_lm_studio_save_choices,
            # Nouveaux v4.4
            ui_recent_paths_dd, ui_csv_acc, ui_csv_hint, ui_btn_export_csv_captions, ui_btn_import_csv_captions,
            ui_csv_import_file, ui_btn_export_md_captions, ui_btn_import_md_captions, ui_csv_contact_hint, ui_btn_open_contact_sheet,
            # Planche(s) compilation(s)
            ui_tab_contact, contact_source_mode, contact_btn_preview, contact_btn_export,
            contact_layout_acc, contact_output_width, contact_flexible_cols, contact_images_per_row,
            contact_spacing, contact_margin, contact_background, contact_format_acc,
            contact_ratio_mode, contact_fit_mode, contact_sort_alpha, contact_text_acc,
            contact_label_mode, contact_font_size, contact_label_opacity, contact_export_acc,
            contact_limit_enabled, contact_images_per_sheet, contact_continue_numbering,
            contact_output_dir, contact_filename_prefix, contact_export_format, contact_quality,
            contact_resize_final, contact_btn_save_settings, contact_status, contact_preview_title,
            contact_btn_back_to_live, contact_export_files,
        ]
    )

    # Note: contact_flexible_cols et contact_sort_alpha sont maintenant des Radios (pas des Checkboxes)
    # Les convertir en booléens pour la fonction
    contact_sheet_inputs = [
        contact_source_mode, contact_output_width, contact_flexible_cols, contact_images_per_row, contact_spacing, contact_margin,
        contact_background, contact_ratio_mode, contact_fit_mode, contact_sort_alpha, contact_label_mode,
        contact_font_size, contact_label_opacity, contact_limit_enabled, contact_images_per_sheet,
        contact_continue_numbering, contact_output_dir, contact_filename_prefix, contact_export_format,
        contact_quality, contact_resize_final, lang_radio,
    ]
    contact_btn_save_settings.click(
        fn=save_contact_sheet_settings,
        inputs=contact_sheet_inputs,
        outputs=[contact_status],
    )
    contact_btn_preview.click(
        fn=preview_contact_sheets,
        inputs=[filtered_state, selected_indices_state] + contact_sheet_inputs,
        outputs=[contact_preview_gallery, contact_status],
        show_progress="full",
    )
    contact_btn_export.click(
        fn=export_contact_sheets,
        inputs=[filtered_state, selected_indices_state, dir_input] + contact_sheet_inputs,
        outputs=[contact_export_files, contact_status],
        show_progress="full",
    )

    def wire_contact_live_preview(component, event_name="input"):
        getattr(component, event_name)(
            fn=preview_contact_sheet_live,
            inputs=[filtered_state, selected_indices_state] + contact_sheet_inputs,
            outputs=[contact_preview_gallery, contact_status],
            show_progress=False,
            trigger_mode="always_last",
            concurrency_limit=1,
            concurrency_id="contact_sheet_live_preview",
        )

    # Live preview : utiliser input/release plutôt que change évite l'attente Gradio perceptible avant rafraîchissement.
    for component in [
        contact_source_mode, contact_output_width, contact_flexible_cols, contact_images_per_row,
        contact_spacing, contact_margin, contact_background, contact_ratio_mode, contact_fit_mode,
        contact_sort_alpha, contact_label_mode, contact_font_size, contact_label_opacity,
        contact_resize_final,
    ]:
        wire_contact_live_preview(component, "input")

    for component in [contact_images_per_row, contact_spacing, contact_margin, contact_font_size, contact_label_opacity, contact_resize_final, contact_background]:
        wire_contact_live_preview(component, "release")

    # Événement pour le bouton "Créer planche(s)" du CSV - déclenche le live preview automatiquement
    ui_btn_open_contact_sheet.click(
        fn=preview_contact_sheet_live,
        inputs=[filtered_state, selected_indices_state] + contact_sheet_inputs,
        outputs=[contact_preview_gallery, contact_status],
        show_progress=False,
        trigger_mode="always_last",
        concurrency_limit=1,
        concurrency_id="contact_sheet_live_preview",
    )

    # Événement pour le bouton "Revenir à la planche témoin" - revient au live preview
    contact_btn_back_to_live.click(
        fn=preview_contact_sheet_live,
        inputs=[filtered_state, selected_indices_state] + contact_sheet_inputs,
        outputs=[contact_preview_gallery, contact_status],
        show_progress=False,
        trigger_mode="always_last",
        concurrency_limit=1,
        concurrency_id="contact_sheet_live_preview",
    )

    def update_lib_ui(mode, lang):
        t = UI_T.get(lang, UI_T.get("FR", {}))
        m_add = t.get("lib_mode_choices", ["Ajouter", "Retirer", "Remplacer"])[0]
        m_rem = t.get("lib_mode_choices", ["Ajouter", "Retirer", "Remplacer"])[1]
        m_rep = t.get("lib_mode_choices", ["Ajouter", "Retirer", "Remplacer"])[2]

        if mode == m_add:
            return gr.update(visible=False), gr.update(value=t.get("btn_apply_lib_add", ""))
        elif mode == m_rem:
            return gr.update(visible=True, label=t.get("lib_target_rem", "")), gr.update(value=t.get("btn_apply_lib_rem", ""))
        else:
            return gr.update(visible=True, label=t.get("lib_target_rep", "")), gr.update(value=t.get("btn_apply_lib_rep", ""))

    ui_lib_mode.change(fn=update_lib_ui, inputs=[ui_lib_mode, lang_radio], outputs=[ui_lib_target, ui_btn_apply_lib])

    ui_multi_select_cb.change(fn=lambda x: x, inputs=[ui_multi_select_cb], outputs=[])
    js_toggle = "function() { const p = document.getElementById('left_panel'); const b = document.getElementById('toggle_gallery_btn'); if (p.classList.contains('collapsed')) { p.classList.remove('collapsed'); b.innerText = '◀'; } else { p.classList.add('collapsed'); b.innerText = '▶'; } return []; }"
    ui_toggle_panel_btn.click(fn=None, js=js_toggle)
    js_toggle_right = "function() { const p = document.getElementById('right_panel'); const b = document.getElementById('toggle_right_btn'); if (p.classList.contains('collapsed')) { p.classList.remove('collapsed'); b.innerText = '▶'; } else { p.classList.add('collapsed'); b.innerText = '◀'; } return []; }"
    ui_toggle_right_btn.click(fn=None, js=js_toggle_right)
    js_open_contact_sheet = """
    function(){
        const matches = t => {
            const text = t.textContent || '';
            return text.includes('Planche') || text.includes('Contact sheet');
        };
        // 1. Onglet visible (exclure le conteneur de mesure caché)
        let tab = Array.from(document.querySelectorAll('.tab-container:not(.visually-hidden) button[role="tab"]')).find(matches);
        if (tab) { tab.click(); return []; }
        // 2. Sinon l'onglet est dans le menu overflow "..." : l'ouvrir puis cliquer l'item
        const ov = document.querySelector('.overflow-menu > button');
        if (ov) {
            ov.click();
            setTimeout(function(){
                const item = Array.from(document.querySelectorAll('.overflow-dropdown button')).find(matches);
                if (item) item.click();
            }, 80);
            return [];
        }
        // 3. Fallback : n'importe quel bouton role=tab
        tab = Array.from(document.querySelectorAll('button[role="tab"]')).find(matches);
        if (tab) tab.click();
        return [];
    }
    """
    ui_btn_open_contact_sheet.click(fn=None, js=js_open_contact_sheet)
    ui_browse_btn.click(fn=browse_folder, inputs=[], outputs=[dir_input])
    ui_hidden_dataset_path_btn.click(
        fn=set_dataset_path_from_drop,
        inputs=[ui_hidden_dataset_path_input, lang_radio],
        outputs=[dir_input, ui_status_text, ui_hidden_dataset_path_input],
    ).success(
        fn=None,
        js="function(){ const w=document.getElementById('hidden_dataset_path_input'); const v=w?.querySelector('textarea,input')?.value || ''; if(v.startsWith('__RESOLVED_PATH__')) setTimeout(()=>document.getElementById('dataset_load_btn')?.click(), 120); }",
    )
    ui_gallery_cols.change(fn=update_gallery_columns, inputs=[ui_gallery_cols], outputs=[gallery]).success(fn=None, js="function(){ setTimeout(()=>window.renderGalleryFolderSeparators && window.renderGalleryFolderSeparators(), 80); return []; }")
    ui_gallery_cols.release(fn=update_gallery_columns, inputs=[ui_gallery_cols], outputs=[gallery]).success(fn=None, js="function(){ setTimeout(()=>window.renderGalleryFolderSeparators && window.renderGalleryFolderSeparators(), 80); return []; }")

    ui_recent_paths_dd.change(fn=lambda p: gr.update(value=p) if p else gr.update(), inputs=[ui_recent_paths_dd], outputs=[dir_input])
    ui_include_subfolders.click(
        fn=toggle_include_subfolders,
        inputs=[include_subfolders_state, lang_radio],
        outputs=[include_subfolders_state, ui_include_subfolders],
    )
    ui_load_btn.click(fn=load_dataset, inputs=[dir_input, ui_sort_order, lang_radio, include_subfolders_state], outputs=[dataset_state, filtered_state, history_state, ui_status_text, gallery, selected_indices_state, ui_selection_status, ui_hidden_sync_input, ui_hidden_tags_input, current_idx_state]).success(
        fn=show_first_after_dataset_load,
        inputs=[filtered_state, ui_tracked_words, lang_radio],
        outputs=[current_img, highlight_preview, current_caption, word_counter, current_idx_state, ui_viewer_status],
    ).success(fn=lambda p: gr.update(choices=load_recent_paths(), value=None), inputs=[dir_input], outputs=[ui_recent_paths_dd])
    ui_search_box.change(fn=filter_gallery, inputs=[dataset_state, ui_search_box, ui_sort_order, lang_radio], outputs=[filtered_state, gallery, selected_indices_state, ui_selection_status, ui_hidden_sync_input, current_idx_state])
    ui_sort_order.change(fn=filter_gallery, inputs=[dataset_state, ui_search_box, ui_sort_order, lang_radio], outputs=[filtered_state, gallery, selected_indices_state, ui_selection_status, ui_hidden_sync_input, current_idx_state])
    
    live_translation_inputs = [current_caption, ui_trans_engine, ui_trans_target, api_backend, api_url_input, llm_model, lang_radio, api_key_input, api_timeout]

    ui_hidden_sync_btn.click(
        fn=handle_sync,
        inputs=[ui_hidden_sync_input, dataset_state, filtered_state, current_idx_state, current_caption, ui_tracked_words, lang_radio],
        outputs=[dataset_state, filtered_state, selected_indices_state, ui_selection_status, current_img, highlight_preview, current_caption, word_counter, current_idx_state, ui_viewer_status, ui_hidden_tags_input],
    ).success(
        fn=do_live_translation,
        inputs=live_translation_inputs,
        outputs=[ui_live_translation_output],
        show_progress="hidden",
    )
    ui_btn_prev.click(
        fn=nav_prev,
        inputs=[dataset_state, filtered_state, current_idx_state, current_caption, ui_tracked_words, lang_radio],
        outputs=[dataset_state, filtered_state, current_img, highlight_preview, current_caption, word_counter, current_idx_state, ui_viewer_status],
    ).success(
        fn=do_live_translation,
        inputs=live_translation_inputs,
        outputs=[ui_live_translation_output],
        show_progress="hidden",
    )
    ui_btn_next.click(
        fn=nav_next,
        inputs=[dataset_state, filtered_state, current_idx_state, current_caption, ui_tracked_words, lang_radio],
        outputs=[dataset_state, filtered_state, current_img, highlight_preview, current_caption, word_counter, current_idx_state, ui_viewer_status],
    ).success(
        fn=do_live_translation,
        inputs=live_translation_inputs,
        outputs=[ui_live_translation_output],
        show_progress="hidden",
    )
    js_confirm_delete_current = "(...args) => { if (!confirm('⚠️ Supprimer cette image définitivement ? / Delete this image permanently?')) throw new Error('Annulé.'); return args; }"
    delete_current_outputs = [
        dataset_state, filtered_state, gallery, current_img, highlight_preview, current_caption,
        word_counter, ui_viewer_status, current_idx_state, selected_indices_state,
        ui_selection_status, ui_hidden_sync_input, ui_hidden_tags_input,
    ]
    ui_btn_delete_current.click(
        fn=delete_current_image,
        js=js_confirm_delete_current,
        inputs=[dataset_state, filtered_state, current_idx_state, ui_tracked_words, lang_radio],
        outputs=delete_current_outputs,
    ).success(fn=bias_stale_note, inputs=[lang_radio], outputs=[bias_stale_notice])
    ui_hidden_delete_current_btn.click(
        fn=delete_current_image,
        inputs=[dataset_state, filtered_state, current_idx_state, ui_tracked_words, lang_radio],
        outputs=delete_current_outputs,
    ).success(fn=bias_stale_note, inputs=[lang_radio], outputs=[bias_stale_notice])
    ui_save_single_btn.click(fn=save_single_caption, inputs=[dataset_state, filtered_state, current_idx_state, current_caption, lang_radio], outputs=[dataset_state, filtered_state, ui_single_save_status]).success(fn=bias_stale_note, inputs=[lang_radio], outputs=[bias_stale_notice])
    ui_clear_sel_btn.click(
        fn=clear_selection,
        js="function(...args){ if(window.clearGallerySelection) window.clearGallerySelection(); return args; }",
        inputs=[dataset_state, filtered_state, lang_radio],
        outputs=[selected_indices_state, ui_selection_status, ui_hidden_sync_input],
    )
    ui_select_all_btn.click(fn=None, js="function(){ if(window.selectAllGallery) window.selectAllGallery(); return []; }")

    ui_hidden_live_translation_btn.click(
        fn=do_live_translation,
        inputs=live_translation_inputs,
        outputs=[ui_live_translation_output],
        show_progress="hidden",
        trigger_mode="always_last",
        concurrency_limit=1,
        concurrency_id="live_translation",
    )
    ui_hidden_reverse_translation_btn.click(
        fn=reverse_live_translation,
        inputs=[ui_live_translation_output, ui_trans_engine, ui_trans_target, api_backend, api_url_input, llm_model, ui_tracked_words, lang_radio, api_key_input, api_timeout],
        outputs=[current_caption, highlight_preview, word_counter],
        show_progress="hidden",
        trigger_mode="always_last",
        concurrency_limit=1,
        concurrency_id="reverse_live_translation",
    )
    
    ui_btn_translate_entire_caption.click(
        fn=translate_entire_caption_action, 
        inputs=[dataset_state, filtered_state, current_idx_state, current_caption, ui_trans_engine, ui_trans_source, api_backend, api_url_input, llm_model, ui_tracked_words, lang_radio, api_key_input, api_timeout],
        outputs=[dataset_state, filtered_state, current_caption, highlight_preview, word_counter, ui_single_save_status]
    ).success(
        fn=do_live_translation,
        inputs=live_translation_inputs,
        outputs=[ui_live_translation_output],
        show_progress="hidden",
    ).success(fn=bias_stale_note, inputs=[lang_radio], outputs=[bias_stale_notice])
    ui_btn_insert_trans.click(fn=trans_insert, inputs=[ui_trans_input, current_caption, ui_trans_engine, ui_trans_source, api_backend, api_url_input, llm_model, lang_radio, api_key_input, api_timeout], outputs=[current_caption]).success(fn=lambda: "", outputs=[ui_trans_input]).success(
        fn=do_live_translation,
        inputs=live_translation_inputs,
        outputs=[ui_live_translation_output],
        show_progress="hidden",
    )

    js_confirm_batch = "(...args) => { if (!confirm('⚠️ Appliquer cette modification en masse sur la sélection ? / Apply this mass modification to the selection?')) throw new Error('Annulé.'); return args; }"
    js_confirm_undo = "(...args) => { if (!confirm('⚠️ Annuler la dernière action ? / Undo the last action?')) throw new Error('Annulé.'); return args; }"
    js_confirm_dup = "(...args) => { if (!confirm('⚠️ Supprimer ce fichier définitivement ? / Delete this file permanently?')) throw new Error('Annulé.'); return args; }"
    js_confirm_all_b = "(...args) => { if (!confirm('⚠️ Supprimer automatiquement tous les fichiers B détectés ? / Automatically delete every detected B file?')) throw new Error('Annulé.'); return args; }"
    
    ui_btn_add_to_lib.click(fn=add_to_lib_html, inputs=[ui_lib_add_text, lib_state, lang_radio], outputs=[ui_lib_html, lib_state, ui_lib_add_text])
    ui_hidden_lib_toggle_btn.click(fn=toggle_lib_item, inputs=[ui_hidden_lib_toggle_input, lib_state, lang_radio], outputs=[ui_lib_html, lib_state])
    ui_hidden_lib_delete_btn.click(fn=delete_lib_item, inputs=[ui_hidden_lib_delete_input, lib_state, lang_radio], outputs=[ui_lib_html, lib_state])
    ui_btn_uncheck_all.click(fn=uncheck_all_lib, inputs=[lib_state, lang_radio], outputs=[ui_lib_html, lib_state])
    ui_btn_clear_lib.click(fn=clear_lib, inputs=[lang_radio], outputs=[ui_lib_html, lib_state])
    
    ui_btn_apply_lib.click(fn=batch_library_cb, js=js_confirm_batch, inputs=[dataset_state, lib_state, ui_lib_mode, ui_lib_target, selected_indices_state, ui_search_box, current_idx_state, ui_tracked_words, lang_radio], outputs=[dataset_state, filtered_state, history_state, ui_batch_status, ui_preview_table, current_caption, highlight_preview, word_counter, gallery]).success(
        fn=do_live_translation,
        inputs=live_translation_inputs,
        outputs=[ui_live_translation_output],
        show_progress="hidden",
    ).success(fn=bias_stale_note, inputs=[lang_radio], outputs=[bias_stale_notice])

    js_get_sel = "function(tracker, dummy) { let sel = window.getSelection().toString().trim(); if(!sel) { let ae = document.activeElement; if(ae && (ae.tagName === 'TEXTAREA' || ae.tagName === 'INPUT')) sel = ae.value.substring(ae.selectionStart, ae.selectionEnd).trim(); } return [tracker, sel || \"\"]; }"
    ui_hidden_calc_btn.click(fn=analyze_dataset, inputs=[dataset_state, ui_tracked_words, lang_radio], outputs=[pie_chart, bar_chart, ui_stats_table, stats_df_state, ui_export_config_df, config_df_state, ui_stats_status])
    ui_tracked_words.change(fn=update_viewer, inputs=[filtered_state, current_idx_state, ui_tracked_words, lang_radio], outputs=[current_img, highlight_preview, current_caption, word_counter, current_idx_state, ui_viewer_status])
    ui_toggle_tag_btn.click(fn=toggle_tracked_word, inputs=[ui_tracked_words, dummy_selection], outputs=[ui_tracked_words], js=js_get_sel).success(fn=None, js="function(){ setTimeout(()=>document.getElementById('hidden_calc_btn')?.click(), 100); }")
    current_caption.change(fn=update_word_count, inputs=[current_caption, lang_radio], outputs=[word_counter])
    ui_recipes_dropdown.change(fn=apply_recipe, inputs=[ui_recipes_dropdown], outputs=[ui_tracked_words])
    ui_save_recipe_btn.click(fn=save_recipe, inputs=[ui_recipe_name, ui_tracked_words], outputs=[ui_recipes_dropdown, ui_status_text])
    ui_btn_ai_recipe.click(
        fn=auto_fill_recipe_from_ai,
        inputs=[dataset_state, ui_ai_recipe_count, api_backend, api_url_input, llm_model, ai_temp, ai_ctx, ai_sys, lang_radio, api_key_input, api_timeout],
        outputs=[ui_tracked_words, ui_status_text],
    ).success(
        fn=None,
        js="function(){ setTimeout(()=>document.getElementById('hidden_calc_btn')?.click(), 80); }",
    )
    ui_btn_analyze_recipe.click(fn=None, js="function(){ setTimeout(()=>document.getElementById('hidden_calc_btn')?.click(), 30); }")

    ui_btn_undo.click(fn=undo_last_action, js=js_confirm_undo, inputs=[dataset_state, history_state, current_idx_state, ui_tracked_words, lang_radio], outputs=[dataset_state, filtered_state, ui_batch_status, current_caption, highlight_preview, word_counter]).success(
        fn=do_live_translation,
        inputs=live_translation_inputs,
        outputs=[ui_live_translation_output],
        show_progress="hidden",
    ).success(fn=bias_stale_note, inputs=[lang_radio], outputs=[bias_stale_notice])
    ui_btn_clean_com.click(fn=batch_clean_commas, js=js_confirm_batch, inputs=[dataset_state, selected_indices_state, ui_search_box, current_idx_state, ui_tracked_words, lang_radio], outputs=[dataset_state, filtered_state, history_state, ui_batch_status, ui_preview_table, current_caption, highlight_preview, word_counter]).success(
        fn=do_live_translation,
        inputs=live_translation_inputs,
        outputs=[ui_live_translation_output],
        show_progress="hidden",
    ).success(fn=bias_stale_note, inputs=[lang_radio], outputs=[bias_stale_notice])
    ui_btn_clean_dup.click(fn=batch_remove_duplicates, js=js_confirm_batch, inputs=[dataset_state, selected_indices_state, ui_search_box, current_idx_state, ui_tracked_words, lang_radio], outputs=[dataset_state, filtered_state, history_state, ui_batch_status, ui_preview_table, current_caption, highlight_preview, word_counter]).success(
        fn=do_live_translation,
        inputs=live_translation_inputs,
        outputs=[ui_live_translation_output],
        show_progress="hidden",
    ).success(fn=bias_stale_note, inputs=[lang_radio], outputs=[bias_stale_notice])

    ui_export_config_df.select(fn=get_row_index, inputs=[config_df_state], outputs=[recipe_selected_row, ui_quick_prio, ui_quick_target])
    ui_quick_prio.change(fn=apply_quick_prio, inputs=[ui_quick_prio, recipe_selected_row, config_df_state], outputs=[ui_export_config_df, config_df_state, ui_tracked_words, recipe_selected_row])
    ui_quick_target.change(fn=apply_quick_target, inputs=[ui_quick_target, recipe_selected_row, config_df_state], outputs=[ui_export_config_df, config_df_state, ui_tracked_words])
    ui_btn_up.click(fn=df_move_up, inputs=[ui_export_config_df, recipe_selected_row], outputs=[ui_export_config_df, recipe_selected_row, ui_tracked_words])
    ui_btn_down.click(fn=df_move_down, inputs=[ui_export_config_df, recipe_selected_row], outputs=[ui_export_config_df, recipe_selected_row, ui_tracked_words])
    ui_btn_del.click(fn=df_delete_row, inputs=[ui_export_config_df, recipe_selected_row], outputs=[ui_export_config_df, recipe_selected_row, ui_tracked_words])
    ui_hidden_dnd_btn.click(fn=handle_drag_and_drop, inputs=[ui_hidden_dnd_input, ui_export_config_df], outputs=[ui_export_config_df, config_df_state, ui_tracked_words])
    ui_export_config_df.change(fn=handle_recipe_df_safe, inputs=[ui_export_config_df, config_df_state, ui_tracked_words], outputs=[ui_export_config_df, config_df_state, ui_tracked_words])

    ui_btn_civitai.click(fn=generate_civitai_format, inputs=[ui_stats_table], outputs=[ui_civitai_output])
    ui_btn_export_stats_csv.click(fn=export_stats_csv, inputs=[ui_stats_table, lang_radio], outputs=[ui_stats_export_file, ui_stats_status])
    ui_btn_export_stats_md.click(fn=export_stats_md, inputs=[ui_stats_table, lang_radio], outputs=[ui_stats_export_file, ui_stats_status])
    ui_btn_top20.click(fn=auto_fill_top_tags, inputs=[dataset_state], outputs=[ui_tracked_words]).success(fn=None, js="function(){ setTimeout(()=>document.getElementById('hidden_calc_btn')?.click(), 100); }")
    ui_btn_orph.click(fn=find_orphans, inputs=[dataset_state, lang_radio], outputs=[ui_txt_orph])
    ui_stats_table.select(
        fn=filter_gallery_from_stats_row,
        inputs=[ui_stats_table, dataset_state, ui_sort_order, lang_radio],
        outputs=[ui_search_box, filtered_state, gallery, selected_indices_state, ui_selection_status, ui_hidden_sync_input, current_idx_state],
    )
    ui_stats_table.change(fn=handle_stats_df_safe, inputs=[ui_stats_table, stats_df_state, ui_tracked_words], outputs=[ui_stats_table, stats_df_state, ui_tracked_words]).success(fn=None, js="function(){ setTimeout(()=>document.getElementById('hidden_calc_btn')?.click(), 100); }")
    btn_calc_adv.click(fn=update_advanced_stats, inputs=[dataset_state], outputs=[plot_heatmap, plot_bucket, txt_anti, txt_contra])

    ui_btn_simul.click(
        fn=simulate_and_clear_selection,
        inputs=[dataset_state, ui_export_dir, ui_export_suffix, ui_export_config_df, selected_indices_state, ui_strategy_radio, ui_max_img_input, lang_radio],
        outputs=[ui_export_status, export_gallery, export_pie, bar_chart, selected_indices_state, ui_selection_status, ui_hidden_sync_input],
    )
    ui_btn_exp.click(fn=simulate_and_export, inputs=[dataset_state, ui_export_dir, ui_export_suffix, ui_export_config_df, gr.State(False), selected_indices_state, ui_strategy_radio, ui_max_img_input, lang_radio], outputs=[ui_export_status, export_gallery, export_pie, bar_chart])
    selected_indices_state.change(fn=update_prep_button_label, inputs=[selected_indices_state, lang_radio], outputs=[btn_prep])
    prep_summary_inputs = [dataset_state, selected_indices_state, prep_dest, prep_size, prep_format, prep_crop, prep_alpha, lang_radio]
    for prep_summary_component in [selected_indices_state, dataset_state, prep_dest, prep_size, prep_format, prep_crop, prep_alpha, lang_radio]:
        prep_summary_component.change(fn=prep_workflow_summary, inputs=prep_summary_inputs, outputs=[prep_quick_summary])
    prep_preset.change(
        fn=apply_prep_workflow_preset,
        inputs=[prep_preset],
        outputs=[prep_size, prep_format, prep_crop, prep_alpha, prep_dest],
    ).success(fn=prep_workflow_summary, inputs=prep_summary_inputs, outputs=[prep_quick_summary])
    btn_apply_prep_preset.click(
        fn=apply_prep_workflow_preset,
        inputs=[prep_preset],
        outputs=[prep_size, prep_format, prep_crop, prep_alpha, prep_dest],
    ).success(fn=prep_workflow_summary, inputs=prep_summary_inputs, outputs=[prep_quick_summary])
    duplicate_pair_outputs = [dup_img_A, dup_img_B, dup_idA, dup_idB, dup_caption_A, dup_caption_B, dup_recommendation]
    btn_scan_dups.click(fn=scan_duplicates_advanced, inputs=[dataset_state, ui_hash_tol, prep_hash_algo], outputs=[dup_dropdown, dup_mapping_state]).success(
        fn=load_duplicate_pair, inputs=[dup_dropdown, dup_mapping_state, dataset_state, lang_radio], outputs=duplicate_pair_outputs
    )
    dup_dropdown.change(fn=load_duplicate_pair, inputs=[dup_dropdown, dup_mapping_state, dataset_state, lang_radio], outputs=duplicate_pair_outputs)
    btn_skip_dup.click(fn=skip_duplicate, inputs=[dup_dropdown, dup_mapping_state], outputs=[dup_dropdown, dup_mapping_state, dup_status]).success(
        fn=load_duplicate_pair, inputs=[dup_dropdown, dup_mapping_state, dataset_state, lang_radio], outputs=duplicate_pair_outputs
    )
    btn_del_A.click(fn=delete_duplicate, js=js_confirm_dup, inputs=[dataset_state, filtered_state, dup_idA, dup_dropdown, dup_mapping_state, lang_radio], outputs=[dataset_state, filtered_state, gallery, dup_dropdown, dup_mapping_state, dup_status]).success(
        fn=load_duplicate_pair, inputs=[dup_dropdown, dup_mapping_state, dataset_state, lang_radio], outputs=duplicate_pair_outputs
    ).success(fn=bias_stale_note, inputs=[lang_radio], outputs=[bias_stale_notice])
    btn_del_B.click(fn=delete_duplicate, js=js_confirm_dup, inputs=[dataset_state, filtered_state, dup_idB, dup_dropdown, dup_mapping_state, lang_radio], outputs=[dataset_state, filtered_state, gallery, dup_dropdown, dup_mapping_state, dup_status]).success(
        fn=load_duplicate_pair, inputs=[dup_dropdown, dup_mapping_state, dataset_state, lang_radio], outputs=duplicate_pair_outputs
    ).success(fn=bias_stale_note, inputs=[lang_radio], outputs=[bias_stale_notice])
    btn_delete_recommended_dup.click(fn=delete_recommended_duplicate, js=js_confirm_dup, inputs=[dataset_state, filtered_state, dup_dropdown, dup_mapping_state, lang_radio], outputs=[dataset_state, filtered_state, gallery, dup_dropdown, dup_mapping_state, dup_status]).success(
        fn=load_duplicate_pair, inputs=[dup_dropdown, dup_mapping_state, dataset_state, lang_radio], outputs=duplicate_pair_outputs
    ).success(fn=bias_stale_note, inputs=[lang_radio], outputs=[bias_stale_notice])
    btn_delete_all_b.click(fn=delete_all_duplicates_b, js=js_confirm_all_b, inputs=[dataset_state, filtered_state, dup_mapping_state, lang_radio], outputs=[dataset_state, filtered_state, gallery, dup_dropdown, dup_mapping_state, dup_status]).success(
        fn=load_duplicate_pair, inputs=[dup_dropdown, dup_mapping_state, dataset_state, lang_radio], outputs=duplicate_pair_outputs
    ).success(fn=bias_stale_note, inputs=[lang_radio], outputs=[bias_stale_notice])
    btn_rename.click(fn=batch_rename_dataset, inputs=[dataset_state, ui_rename_prefix], outputs=[dataset_state, prep_status]).success(fn=bias_stale_note, inputs=[lang_radio], outputs=[bias_stale_notice])
    btn_prep.click(fn=batch_process_images, inputs=[dataset_state, selected_indices_state, prep_dest, prep_size, prep_format, prep_crop, prep_alpha], outputs=[prep_status], show_progress="full")
    btn_load_manual_crop.click(fn=load_manual_crop_image, inputs=[filtered_state, current_idx_state, lang_radio], outputs=[manual_crop_editor, manual_crop_status]).success(
        fn=None,
        js="function(){ requestAnimationFrame(()=>window.idrManualCropLoadFromEditor && window.idrManualCropLoadFromEditor()); return []; }",
    )
    btn_save_manual_crop.click(
        fn=save_manual_crop_image,
        inputs=[manual_crop_editor, filtered_state, current_idx_state, prep_dest, prep_size, prep_format, prep_alpha, lang_radio],
        outputs=[manual_crop_status],
        show_progress="full",
    )
    manual_crop_nav_outputs = [manual_crop_editor, current_img, highlight_preview, current_caption, word_counter, current_idx_state, ui_viewer_status, manual_crop_status]
    btn_manual_crop_prev.click(
        fn=manual_crop_jump,
        inputs=[filtered_state, current_idx_state, gr.State("prev"), ui_tracked_words, lang_radio],
        outputs=manual_crop_nav_outputs,
    ).success(fn=None, js="function(){ requestAnimationFrame(()=>window.idrManualCropLoadFromEditor && window.idrManualCropLoadFromEditor()); return []; }")
    btn_manual_crop_next.click(
        fn=manual_crop_jump,
        inputs=[filtered_state, current_idx_state, gr.State("next"), ui_tracked_words, lang_radio],
        outputs=manual_crop_nav_outputs,
    ).success(fn=None, js="function(){ requestAnimationFrame(()=>window.idrManualCropLoadFromEditor && window.idrManualCropLoadFromEditor()); return []; }")
    btn_save_manual_crop_next.click(
        fn=save_manual_crop_and_next,
        inputs=[manual_crop_editor, filtered_state, current_idx_state, prep_dest, prep_size, prep_format, prep_alpha, ui_tracked_words, lang_radio],
        outputs=[manual_crop_editor, manual_crop_status, current_img, highlight_preview, current_caption, word_counter, current_idx_state, ui_viewer_status],
        show_progress="full",
    ).success(fn=None, js="function(){ requestAnimationFrame(()=>window.idrManualCropLoadFromEditor && window.idrManualCropLoadFromEditor()); return []; }")
    ui_hidden_manual_crop_btn.click(
        fn=overwrite_manual_crop_from_payload,
        inputs=[ui_hidden_manual_crop_payload, dataset_state, filtered_state, current_idx_state, ui_tracked_words, lang_radio],
        outputs=[dataset_state, filtered_state, gallery, current_img, highlight_preview, current_caption, word_counter, current_idx_state, manual_crop_status],
    ).success(
        fn=None,
        js="function(){ requestAnimationFrame(()=>window.idrManualCropLoadFromEditor && window.idrManualCropLoadFromEditor()); return []; }",
    ).success(fn=bias_stale_note, inputs=[lang_radio], outputs=[bias_stale_notice])
    btn_detect_low_res.click(fn=detect_low_resolution_images, inputs=[dataset_state, prep_min_res, lang_radio], outputs=[low_res_df, prep_status])
    btn_move_low_res.click(fn=move_low_resolution_images, inputs=[dataset_state, filtered_state, prep_min_res, lang_radio], outputs=[dataset_state, filtered_state, gallery, low_res_df, prep_status, selected_indices_state, ui_selection_status, ui_hidden_sync_input]).success(fn=bias_stale_note, inputs=[lang_radio], outputs=[bias_stale_notice])

    ai_action_dropdown.change(fn=update_ai_action_desc, inputs=[ai_action_dropdown], outputs=[ai_action_desc, custom_prompt_group, injection_group]).success(
        fn=load_ai_action_for_edit,
        inputs=[ai_action_dropdown],
        outputs=[ai_action_edit_name, ai_action_edit_prompt, ai_action_edit_desc, ai_action_edit_vision, ai_action_edit_injection, ai_actions_manage_status],
    )
    ai_format_preset.change(
        fn=apply_ai_format_preset,
        inputs=[ai_format_preset],
        outputs=[ai_action_dropdown, custom_prompt_input, injection_mode, use_vision_for_custom],
    ).success(fn=update_ai_action_desc, inputs=[ai_action_dropdown], outputs=[ai_action_desc, custom_prompt_group, injection_group]).success(
        fn=load_ai_action_for_edit,
        inputs=[ai_action_dropdown],
        outputs=[ai_action_edit_name, ai_action_edit_prompt, ai_action_edit_desc, ai_action_edit_vision, ai_action_edit_injection, ai_actions_manage_status],
    )
    btn_save_ai_action.click(
        fn=save_custom_ai_action,
        inputs=[ai_action_edit_name, ai_action_edit_prompt, ai_action_edit_desc, ai_action_edit_vision, ai_action_edit_injection],
        outputs=[ai_action_dropdown, ai_actions_manage_status],
    ).success(fn=update_ai_action_desc, inputs=[ai_action_dropdown], outputs=[ai_action_desc, custom_prompt_group, injection_group]).success(
        fn=load_ai_action_for_edit,
        inputs=[ai_action_dropdown],
        outputs=[ai_action_edit_name, ai_action_edit_prompt, ai_action_edit_desc, ai_action_edit_vision, ai_action_edit_injection, ai_actions_manage_status],
    )
    btn_delete_ai_action.click(
        fn=delete_custom_ai_action,
        inputs=[ai_action_edit_name],
        outputs=[ai_action_dropdown, ai_actions_manage_status],
    ).success(fn=update_ai_action_desc, inputs=[ai_action_dropdown], outputs=[ai_action_desc, custom_prompt_group, injection_group]).success(
        fn=load_ai_action_for_edit,
        inputs=[ai_action_dropdown],
        outputs=[ai_action_edit_name, ai_action_edit_prompt, ai_action_edit_desc, ai_action_edit_vision, ai_action_edit_injection, ai_actions_manage_status],
    )
    btn_import_ai_actions.click(
        fn=import_ai_actions_json,
        inputs=[ai_actions_import_file],
        outputs=[ai_action_dropdown, ai_actions_manage_status],
    )
    btn_export_ai_actions.click(fn=export_ai_actions_json, inputs=[], outputs=[ai_actions_export_file, ai_actions_manage_status])

    def _switch_backend_url(backend):
        """Bascule l'URL par défaut quand on change de backend.
        Ollama → 11434, LM Studio/OpenAI → 1234, Anthropic/Gemini → URL cloud."""
        kind = _backend_kind(backend)
        if kind == "ollama":
            return gr.update(value=DEFAULT_OLLAMA_URL)
        if kind == "anthropic":
            return gr.update(value=DEFAULT_ANTHROPIC_URL)
        if kind == "gemini":
            return gr.update(value=DEFAULT_GEMINI_URL)
        return gr.update(value=DEFAULT_LM_STUDIO_URL)

    ai_settings_inputs = [api_backend, vlm_model, llm_model, api_url_input, api_key_input, ai_temp, ai_ctx, api_timeout, ai_sys]
    api_backend.change(fn=_switch_backend_url, inputs=[api_backend], outputs=[api_url_input]).success(
        fn=save_ai_settings, inputs=ai_settings_inputs, outputs=None,
    )
    for ai_setting_component in [vlm_model, llm_model, api_url_input, api_key_input, ai_temp, ai_ctx, api_timeout, ai_sys]:
        ai_setting_component.change(fn=save_ai_settings, inputs=ai_settings_inputs, outputs=None)
    ai_template_dd.change(fn=apply_ai_recipe, inputs=[ai_template_dd], outputs=[custom_prompt_input])
    btn_save_template.click(fn=save_ai_recipe, inputs=[ai_template_name, custom_prompt_input], outputs=[ai_template_dd])
    ai_action_inputs = [
        dataset_state, selected_indices_state, ui_search_box, ai_action_dropdown,
        custom_prompt_input, injection_mode, use_vision_for_custom, vlm_model, llm_model,
        api_backend, api_url_input, ai_temp, ai_ctx, ai_sys, current_idx_state,
        ui_tracked_words, lang_radio, api_key_input, api_timeout,
    ]
    ai_action_outputs = [dataset_state, filtered_state, history_state, ai_status, ui_hidden_tags_input, current_caption, highlight_preview, word_counter]
    btn_run_ai.click(
        fn=process_ai_action,
        inputs=ai_action_inputs,
        outputs=ai_action_outputs,
        show_progress="full",
    ).success(fn=bias_stale_note, inputs=[lang_radio], outputs=[bias_stale_notice])
    btn_test_ai.click(
        fn=process_ai_current_image,
        inputs=[
            dataset_state, filtered_state, ui_search_box, ai_action_dropdown,
            custom_prompt_input, injection_mode, use_vision_for_custom, vlm_model, llm_model,
            api_backend, api_url_input, ai_temp, ai_ctx, ai_sys, current_idx_state,
            ui_tracked_words, lang_radio, api_key_input, api_timeout,
        ],
        outputs=ai_action_outputs,
        show_progress="full",
    ).success(fn=bias_stale_note, inputs=[lang_radio], outputs=[bias_stale_notice])
    btn_select_no_caption.click(
        fn=select_images_without_caption,
        inputs=[dataset_state, filtered_state, lang_radio],
        outputs=[selected_indices_state, ui_selection_status, ui_hidden_sync_input],
    )
    btn_bias.click(
        fn=analyze_bias,
        inputs=[dataset_state, llm_model, api_backend, api_url_input, ai_temp, ai_ctx, ai_sys, lang_radio, api_key_input, api_timeout],
        outputs=[txt_bias],
    ).success(fn=lambda: "", outputs=[bias_stale_notice])

    # 🎯 LM Studio : Rafraîchissement et chargement
    ui_lm_studio_list_btn.click(
        fn=refresh_lm_studio_models,
        inputs=[api_url_input, lang_radio],
        outputs=[ui_lm_studio_vlm_dd, ui_lm_studio_llm_dd, ui_lm_studio_shared_dd, ui_lm_studio_status],
    )
    lm_studio_choice_inputs = [
        ui_lm_studio_vlm_dd, ui_lm_studio_llm_dd, ui_lm_studio_shared_dd,
        api_backend, api_url_input, api_key_input, ai_temp, ai_ctx, api_timeout, ai_sys, lang_radio,
    ]
    ui_lm_studio_load_vlm.click(
        fn=lm_studio_load_model,
        inputs=[ui_lm_studio_vlm_dd, api_url_input, lang_radio],
        outputs=[ui_lm_studio_status],
    ).success(
        # Synchronise le champ "Modèle Vision" avec le modèle chargé
        fn=lambda x: gr.update(value=x or ""), inputs=[ui_lm_studio_vlm_dd], outputs=[vlm_model],
    ).success(
        fn=save_ai_settings, inputs=ai_settings_inputs, outputs=None,
    )
    ui_lm_studio_load_llm.click(
        fn=lm_studio_load_model,
        inputs=[ui_lm_studio_llm_dd, api_url_input, lang_radio],
        outputs=[ui_lm_studio_status],
    ).success(
        fn=lambda x: gr.update(value=x or ""), inputs=[ui_lm_studio_llm_dd], outputs=[llm_model],
    ).success(
        fn=save_ai_settings, inputs=ai_settings_inputs, outputs=None,
    )
    ui_lm_studio_load_shared.click(
        fn=lm_studio_load_model,
        inputs=[ui_lm_studio_shared_dd, api_url_input, lang_radio],
        outputs=[ui_lm_studio_status],
    ).success(
        fn=lambda x: (gr.update(value=x or ""), gr.update(value=x or "")),
        inputs=[ui_lm_studio_shared_dd],
        outputs=[vlm_model, llm_model],
    ).success(
        fn=save_lm_studio_model_choices,
        inputs=lm_studio_choice_inputs,
        outputs=[vlm_model, llm_model, ui_lm_studio_status],
    )
    ui_lm_studio_unload_vlm.click(
        fn=lm_studio_unload_model,
        inputs=[ui_lm_studio_vlm_dd, api_url_input, lang_radio],
        outputs=[ui_lm_studio_status],
    )
    ui_lm_studio_unload_llm.click(
        fn=lm_studio_unload_model,
        inputs=[ui_lm_studio_llm_dd, api_url_input, lang_radio],
        outputs=[ui_lm_studio_status],
    )
    ui_lm_studio_unload_shared.click(
        fn=lm_studio_unload_model,
        inputs=[ui_lm_studio_shared_dd, api_url_input, lang_radio],
        outputs=[ui_lm_studio_status],
    )
    ui_lm_studio_save_choices.click(
        fn=save_lm_studio_model_choices,
        inputs=lm_studio_choice_inputs,
        outputs=[vlm_model, llm_model, ui_lm_studio_status],
    )

    # ⭐ Favoris : ajout, retrait, sélection
    ui_btn_add_fav.click(fn=add_favorite, inputs=[dir_input, lang_radio], outputs=[ui_fav_dropdown, ui_status_text])
    ui_btn_remove_fav.click(fn=remove_favorite, inputs=[ui_fav_dropdown, lang_radio], outputs=[ui_fav_dropdown, ui_status_text])
    ui_fav_dropdown.change(
        fn=load_favorite_dataset,
        inputs=[ui_fav_dropdown, ui_sort_order, lang_radio, include_subfolders_state],
        outputs=[dir_input, dataset_state, filtered_state, history_state, ui_status_text, gallery, selected_indices_state, ui_selection_status, ui_hidden_sync_input, ui_hidden_tags_input, current_idx_state],
    ).success(
        fn=show_first_after_dataset_load,
        inputs=[filtered_state, ui_tracked_words, lang_radio],
        outputs=[current_img, highlight_preview, current_caption, word_counter, current_idx_state, ui_viewer_status],
    )

    # 🗑️ Suppression de recette
    ui_btn_delete_recipe.click(
        fn=delete_recipe,
        js="(name, lang) => { if (name && !confirm('⚠️ Supprimer la recette \"' + name + '\" ? / Delete recipe?')) throw new Error('Annulé.'); return [name, lang]; }",
        inputs=[ui_recipes_dropdown, lang_radio],
        outputs=[ui_recipes_dropdown, ui_status_text],
    )

    # 🌐 Import d'un fichier de langue personnalisé
    ui_lang_import_btn.click(
        fn=import_language_file,
        inputs=[ui_lang_import_file, lang_radio],
        outputs=[ui_lang_import_status],
    )

    # 📋 Export / Import CSV captions
    ui_btn_export_csv_captions.click(
        fn=export_captions_csv,
        js="function(...args){ document.getElementById('gallery_csv_acc')?.classList.remove('csv-import-open'); return args; }",
        inputs=[dataset_state, lang_radio],
        outputs=[ui_csv_status],
    )
    ui_btn_export_md_captions.click(
        fn=export_captions_md,
        js="function(...args){ document.getElementById('gallery_csv_acc')?.classList.remove('csv-import-open'); return args; }",
        inputs=[dataset_state, lang_radio],
        outputs=[ui_csv_status],
    )
    ui_btn_import_csv_captions.click(
        fn=None,
        js="function(){ const acc = document.getElementById('gallery_csv_acc'); acc?.classList.add('csv-import-open'); return []; }",
    )
    ui_btn_import_md_captions.click(
        fn=None,
        js="function(){ const acc = document.getElementById('gallery_csv_acc'); acc?.classList.add('csv-import-open'); return []; }",
    )
    ui_csv_import_file.upload(
        fn=import_captions_file_refresh,
        inputs=[ui_csv_import_file, dataset_state, filtered_state, current_idx_state, ui_tracked_words, lang_radio],
        outputs=[dataset_state, filtered_state, gallery, current_img, highlight_preview, current_caption, word_counter, current_idx_state, ui_viewer_status, ui_hidden_tags_input, ui_csv_status],
    ).success(fn=bias_stale_note, inputs=[lang_radio], outputs=[bias_stale_notice])

    # Ctrl+D : copier la caption vers l'image suivante
    copy_next_outputs = [dataset_state, filtered_state, current_img, highlight_preview, current_caption, word_counter, current_idx_state, ui_viewer_status]
    ui_hidden_copy_next_btn.click(
        fn=copy_caption_to_next,
        inputs=[dataset_state, filtered_state, current_idx_state, current_caption, ui_tracked_words, lang_radio],
        outputs=copy_next_outputs,
    ).success(fn=do_live_translation, inputs=live_translation_inputs, outputs=[ui_live_translation_output], show_progress="hidden")

    app.load(fn=None, inputs=None, outputs=None, js=custom_js)

if __name__ == "__main__":
    launch_kwargs = {
        "inbrowser": True,
        "server_name": "127.0.0.1",
        "allowed_paths": get_gradio_allowed_paths(),
    }
    if get_gradio_major_version() >= 6:
        launch_kwargs["css"] = css_code
        launch_kwargs["js"] = f"({custom_js})();"
    try:
        app.launch(**launch_kwargs)
    except TypeError:
        launch_kwargs.pop("css", None)
        try:
            app.launch(**launch_kwargs)
        except TypeError:
            launch_kwargs.pop("allowed_paths", None)
            app.launch(**launch_kwargs)
