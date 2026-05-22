import gradio as gr
import os
import re
import shutil
import json
import io
import copy
import requests
import base64
import html
import sys
import time
from urllib.parse import unquote, urlparse
import plotly.express as px
import pandas as pd
from collections import Counter, defaultdict
from PIL import Image

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

# ==========================================
# CONFIGURATION & DICTIONNAIRES DE LANGUE
# ==========================================

APP_DIR = os.path.dirname(os.path.abspath(__file__))
RECIPES_FILE = os.path.join(APP_DIR, "lora_recipes.json")
AI_RECIPES_FILE = os.path.join(APP_DIR, "ai_recipes.json")
FAVORITES_FILE = os.path.join(APP_DIR, "favorites.json")
AI_SETTINGS_FILE = os.path.join(APP_DIR, "ai_settings.json")
UI_SETTINGS_FILE = os.path.join(APP_DIR, "ui_settings.json")
LANGUAGES_DIR = os.path.join(APP_DIR, "languages")
DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"
DEFAULT_LM_STUDIO_URL = "http://127.0.0.1:1234"
DEFAULT_OPENAI_URL = "https://api.openai.com"
DEFAULT_ANTHROPIC_URL = "https://api.anthropic.com"
DEFAULT_GEMINI_URL = "https://generativelanguage.googleapis.com"
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
    "system_prompt": "",
}

MSG = {"FR": {}, "EN": {}}
UI_T = {"FR": {}, "EN": {}}
LIVE_TRANSLATION_CACHE = {}
DEFAULT_UI_SETTINGS = {
    "gallery_columns": 2,
}

CONTRADICTIONS_LOGIQUES = [
    ("day", "night"), ("daytime", "night"),
    ("solo", "multiple girls"), ("solo", "multiple boys"),
    ("indoors", "outdoors"), ("outside", "inside"),
    ("1girl", "1boy"), ("monochrome", "colorful")
]

def _resolve_lang_path(lang_code):
    """Cherche un fichier de langue dans languages/ d'abord, puis à la racine.
    Permet la rétro-compatibilité avec les anciennes installations."""
    code = lang_code.lower()
    candidate_a = os.path.join(LANGUAGES_DIR, f"{code}.json")
    candidate_b = os.path.join(APP_DIR, f"{code}.json")
    if os.path.exists(candidate_a):
        return candidate_a
    if os.path.exists(candidate_b):
        return candidate_b
    return None

def load_languages():
    """Charge les langues. Scanne le dossier languages/ ET la racine.
    Toute langue trouvée (au-delà de FR/EN) est ajoutée dynamiquement."""
    candidates = set(["FR", "EN"])
    # Détecter automatiquement les autres langues présentes dans languages/
    if os.path.isdir(LANGUAGES_DIR):
        try:
            for f in os.listdir(LANGUAGES_DIR):
                if f.lower().endswith(".json"):
                    candidates.add(os.path.splitext(f)[0].upper())
        except Exception:
            pass

    for lang in candidates:
        filepath = _resolve_lang_path(lang)
        if filepath:
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    MSG[lang] = data.get("MSG", {})
                    UI_T[lang] = data.get("UI_T", {})
            except Exception as e:
                print(f"⚠️ Erreur en lisant '{filepath}' : {e}")
        else:
            if lang in ("FR", "EN"):
                print(f"⚠️ Fichier de langue '{lang.lower()}.json' introuvable (cherché dans '{LANGUAGES_DIR}/' et à la racine).")

load_languages()

def get_available_languages():
    """Renvoie les codes de langue disponibles (au moins FR et EN)."""
    langs = sorted(set(["FR", "EN"]) | set(MSG.keys()))
    return langs

def import_language_file(uploaded_file, lang="FR"):
    """Importe un fichier JSON de langue dans le dossier languages/.
    Le fichier doit contenir MSG et UI_T comme fr.json."""
    m = MSG.get(lang, MSG.get("FR", {}))
    if not uploaded_file:
        return "⚠️ Aucun fichier sélectionné."
    try:
        # Le fichier peut être un chemin ou un objet NamedString selon Gradio
        src_path = uploaded_file.name if hasattr(uploaded_file, "name") else str(uploaded_file)
        # Valider le JSON
        with open(src_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if "MSG" not in data or "UI_T" not in data:
            return "❌ Le fichier doit contenir les clés 'MSG' et 'UI_T'."
        # Copier vers languages/ avec le nom du fichier original (en minuscules)
        os.makedirs(LANGUAGES_DIR, exist_ok=True)
        base_name = os.path.basename(src_path).lower()
        if not base_name.endswith(".json"):
            base_name += ".json"
        dest_path = os.path.join(LANGUAGES_DIR, base_name)
        shutil.copy2(src_path, dest_path)
        lang_code = os.path.splitext(base_name)[0].upper()
        # Recharger les langues pour prendre en compte la nouveauté
        load_languages()
        msg = m.get("lang_imported", "✅ Langue '{name}' importée avec succès. Redémarrez l'application pour la voir.").format(name=lang_code)
        gr.Info(msg)
        return msg
    except json.JSONDecodeError:
        return "❌ Fichier JSON invalide."
    except Exception as e:
        return f"❌ Erreur d'import : {e}"

# ==========================================
# STYLES CSS NATIFS & JAVASCRIPT GLOBAL
# ==========================================
css_code = """
/* Suppression totale des en-têtes Gradio */
.gradio-container header, .gradio-container-4-26-0 header, header { display: none !important; }
footer { display: none !important; }
html, body, gradio-app { margin: 0 !important; padding: 0 !important; background: #0b0f14 !important; }
.gradio-container, .contain, main, .wrap { max-width: none !important; width: 100% !important; margin: 0 !important; }
.gradio-container { padding: 8px 16px 16px 16px !important; min-height: 100vh !important; }
.gradio-container .main.fillable, .gradio-container > .main, .gradio-container > main { max-width: none !important; padding: 0 !important; }
#top_workspace { gap: 12px !important; align-items: flex-start !important; flex-wrap: nowrap !important; }
#workbench_row { display: flex !important; flex-direction: row !important; flex-wrap: nowrap !important; gap: 12px !important; align-items: stretch !important; }
#workbench_row > div { min-width: 0 !important; }
#center_panel { min-width: 420px !important; flex: 1 1 0 !important; width: auto !important; }
#app_title h1 { font-size: 1.35rem !important; line-height: 1.15 !important; margin: 0 0 4px 0 !important; }
#app_title p { margin: 0 0 6px 0 !important; font-size: 0.88rem !important; }
#dataset_header, #recipe_header { min-width: 0 !important; }

#left_panel { resize: horizontal; overflow-x: hidden; overflow-y: auto; width: clamp(320px, 24vw, 470px); min-width: 280px; max-width: 44vw; flex: none !important; border-right: 1px solid #374151; padding-right: 12px; transition: min-width 0.3s ease, width 0.3s ease, padding 0.3s ease, opacity 0.3s ease; }
#left_panel.collapsed { width: 0px !important; min-width: 0px !important; padding: 0px !important; margin: 0px !important; border: none !important; opacity: 0; pointer-events: none; }
#right_panel { width: clamp(300px, 22vw, 440px); min-width: 280px; max-width: 38vw; flex: none !important; border-left: 1px solid #374151; padding-left: 12px; overflow-y: auto; max-height: calc(100vh - 260px); transition: min-width 0.3s ease, width 0.3s ease, padding 0.3s ease, opacity 0.3s ease; }
#right_panel.collapsed { width: 0px !important; min-width: 0px !important; padding: 0px !important; margin: 0px !important; border: none !important; opacity: 0; pointer-events: none; overflow: hidden !important; }
/* Ligne d'en-tête du centre : aligner les deux toggles (gauche/droite) horizontalement */
#panel_toggles_row { gap: 8px !important; }
#panel_toggles_row > div { flex: 1 1 0 !important; min-width: 0 !important; }
#main_gallery { min-height: 520px !important; }
@media (max-width: 1050px) {
    #top_workspace, #workbench_row { flex-wrap: wrap !important; }
    #left_panel, #right_panel, #center_panel { width: 100% !important; max-width: none !important; min-width: 0 !important; }
}
.caption-label { font-size: 14px !important; font-weight: bold !important; color: #4ade80 !important; display: none !important; }
.custom-selected { outline: 4px solid #ff8800 !important; outline-offset: -4px !important; box-shadow: inset 0 0 20px rgba(255, 136, 0, 0.9) !important; border-radius: 8px !important; }
.custom-selected img { filter: sepia(0.8) hue-rotate(330deg) saturate(3) !important; opacity: 0.8 !important; }

#hidden_sync_input, #hidden_sync_btn, #hidden_calc_btn, #hidden_dnd_input, #hidden_dnd_btn, #hidden_tags_input,
#hidden_dataset_path_input, #hidden_dataset_path_btn { display: none !important; }
#hidden_lib_toggle_input, #hidden_lib_toggle_btn, #hidden_lib_delete_input, #hidden_lib_delete_btn { display: none !important; }
.form:has(#hidden_sync_input), .form:has(#hidden_dnd_input), .form:has(#hidden_tags_input),
.form:has(#hidden_dataset_path_input), .form:has(#hidden_lib_toggle_input), .form:has(#hidden_lib_delete_input) {
    display: none !important;
    height: 0 !important;
    margin: 0 !important;
    padding: 0 !important;
}

.gradio-dataframe tbody tr { transition: background-color 0.2s, opacity 0.2s; }
.gradio-dataframe tbody tr[draggable="true"] { cursor: grab !important; }
.gradio-dataframe tbody tr.dragging { opacity: 0.4; background-color: rgba(255, 136, 0, 0.3) !important; outline: 2px dashed #ff8800; outline-offset: -2px;}
#autocomplete-list { position: absolute; border: 1px solid #555; background-color: #1f2937; z-index: 9999; max-height: 150px; overflow-y: auto; border-radius: 4px; box-shadow: 0px 4px 6px rgba(0,0,0,0.5); }
#autocomplete-list div { padding: 8px; cursor: pointer; color: #fff; font-size: 14px; }
#autocomplete-list div:hover, #autocomplete-list div.autocomplete-active { background-color: #4ade80; color: #000; }
.info-box { background-color: rgba(74, 222, 128, 0.1); border-left: 4px solid #4ade80; padding: 10px; margin-bottom: 15px; border-radius: 4px; }

#btn_translate_entire { background: #4ade80 !important; color: #052e16 !important; font-weight: bold !important; border: none !important; transition: all 0.2s; }
#btn_translate_entire:hover { background: #22c55e !important; transform: scale(1.01); }

/* Rendu 100% Natif Gradio (Fond Vert par CSS) pour Traduction Live */
#live_translation_preview textarea { 
    background-color: rgba(34, 197, 94, 0.08) !important; 
    color: #4ade80 !important; 
    border: 1px dashed #4ade80 !important; 
    font-style: italic !important;
    opacity: 1 !important; 
    -webkit-text-fill-color: #4ade80 !important;
}

.lib-item-custom { transition: border-color 0.2s ease, background-color 0.2s ease; }
.dataset-drop-zone { border: 1px dashed #64748b; border-radius: 6px; padding: 8px 10px; margin: 6px 0 8px 0; background: rgba(74, 222, 128, 0.06); color: #cbd5e1; font-size: 12.5px; line-height: 1.3; transition: border-color 0.15s ease, background-color 0.15s ease, color 0.15s ease; }
.dataset-drop-zone strong { display: block; color: #4ade80; margin-bottom: 2px; }
.dataset-drop-zone.dragover { border-color: #4ade80; background: rgba(74, 222, 128, 0.16); color: #fff; }

/* ======================================================
   🎨 PANELS THÉMATIQUES (v4.3.2)
   Encarts colorés semi-transparents pour regrouper visuellement
   les zones fonctionnelles. Volontairement légers : on ne touche
   ni au layout flex (top_workspace / workbench_row), ni aux
   composants enfants ; on n'ajoute qu'un fond, une bordure et un
   liseré gauche.
   ====================================================== */

/* Tronc commun : tous les panels partagent le même paddding, le même radius et la même transition douce. */
#top_workspace > #dataset_header,
#top_workspace > #recipe_header,
#workbench_row > #left_panel,
#workbench_row > #right_panel,
.panel-purple {
    border-radius: 10px !important;
    padding: 10px 12px !important;
    transition: background-color 0.25s ease, box-shadow 0.25s ease, border-color 0.25s ease !important;
    position: relative !important;
}

/* 🟡 Jaune — Chargement du dataset */
#top_workspace > #dataset_header {
    background: rgba(234, 179, 8, 0.08) !important;
    border: 1px solid rgba(234, 179, 8, 0.35) !important;
    border-left: 4px solid #eab308 !important;
}
#top_workspace > #dataset_header:hover {
    background: rgba(234, 179, 8, 0.12) !important;
    box-shadow: 0 0 0 1px rgba(234, 179, 8, 0.25) inset !important;
}

/* 🔵 Bleu foncé — Recette globale */
#top_workspace > #recipe_header {
    background: rgba(59, 130, 246, 0.07) !important;
    border: 1px solid rgba(59, 130, 246, 0.30) !important;
    border-left: 4px solid #3b82f6 !important;
}
#top_workspace > #recipe_header:hover {
    background: rgba(59, 130, 246, 0.11) !important;
    box-shadow: 0 0 0 1px rgba(59, 130, 246, 0.25) inset !important;
}

/* 🟢 Vert — Galerie & Sélection */
#workbench_row > #left_panel {
    background: rgba(34, 197, 94, 0.06) !important;
    /* on conserve la border-right gérée plus haut comme guide visuel */
    border: 1px solid rgba(34, 197, 94, 0.28) !important;
    border-right: 1px solid #374151 !important;
    border-left: 4px solid #22c55e !important;
}
#workbench_row > #left_panel.collapsed {
    background: transparent !important;
    border: none !important;
}

/* 🟦 Cyan — Bibliothèque de mots (panneau droit) */
#workbench_row > #right_panel {
    background: rgba(20, 184, 166, 0.06) !important;
    border: 1px solid rgba(20, 184, 166, 0.30) !important;
    border-left: 4px solid #14b8a6 !important;
    /* on n'écrase pas le padding-left existant */
    padding-left: 12px !important;
}
#workbench_row > #right_panel.collapsed {
    background: transparent !important;
    border: none !important;
}

/* 🟣 Violet — Bloc "Serveur et Modèles Locaux" dans l'onglet IA.
   Appliqué via elem_classes="panel-purple" sur le Group Gradio. */
.panel-purple {
    background: rgba(168, 85, 247, 0.07) !important;
    border: 1px solid rgba(168, 85, 247, 0.30) !important;
    border-left: 4px solid #a855f7 !important;
    margin-bottom: 8px !important;
}
.panel-purple:hover {
    background: rgba(168, 85, 247, 0.10) !important;
}

/* Accordion "Assistant de Traduction" — léger habillage rouge
   pour rappeler la zone rouge de la maquette image2 (volet pliable). */
.panel-translate > .label-wrap,
.panel-translate > button {
    background: rgba(239, 68, 68, 0.10) !important;
    border-left: 3px solid #ef4444 !important;
    border-radius: 6px !important;
}
.panel-translate {
    border: 1px solid rgba(239, 68, 68, 0.25) !important;
    border-radius: 8px !important;
}

/* Sur écrans étroits (mobile / responsive), les liserés gauches restent
   visibles mais on assouplit le padding pour éviter les débordements. */
@media (max-width: 1050px) {
    #top_workspace > #dataset_header,
    #top_workspace > #recipe_header,
    #workbench_row > #left_panel,
    #workbench_row > #right_panel,
    .panel-purple {
        padding: 8px 10px !important;
    }
}
"""

custom_js = """
function() {
    if (window.__DIES_INJECTED) return;
    window.__DIES_INJECTED = true;
    document.body.classList.add('dark');
    window.gallerySelectedIndices = new Set();
    window.lastClickedIndex = -1;
    window.allDatasetTags = [];

    function setNativeValue(element, value) {
        const valueSetter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, "value").set;
        const prototype = Object.getPrototypeOf(element);
        const descriptor = Object.getOwnPropertyDescriptor(prototype, "value");
        const setter = descriptor ? descriptor.set : valueSetter;
        setter.call(element, value);
        element.dispatchEvent(new Event('input', { bubbles: true }));
    }

    function decodeDroppedPath(raw) {
        if (!raw) return "";
        let first = raw.split(/\\r?\\n/).map(x => x.trim()).find(x => x && !x.startsWith("#")) || "";
        first = first.replace(/^["']|["']$/g, "");
        if (!first) return "";
        try {
            if (first.toLowerCase().startsWith("file:")) {
                const u = new URL(first);
                let p = decodeURIComponent(u.pathname || "");
                if (/^\\/[A-Za-z]:\\//.test(p)) p = p.slice(1);
                return p.replace(/\\//g, "\\\\");
            }
        } catch(err) {}
        return first;
    }

    function looksLikeLocalPath(path) {
        if (!path || path === "__DROP_PATH_BLOCKED__") return false;
        return /^[A-Za-z]:[\\\\/]/.test(path) || /^\\\\\\\\/.test(path) || path.startsWith("/") || path.startsWith("~") || path.startsWith("%");
    }

    function setDatasetDropStatus(message, isWarning=true) {
        const status = document.getElementById('dataset_status_text');
        if (!status) return;
        const target = status.querySelector('.prose, .md') || status;
        const color = isWarning ? '#fbbf24' : '#4ade80';
        target.innerHTML = "<p style='color:" + color + "; margin:0; font-weight:600;'>" + message + "</p>";
    }

    function pushDatasetSignatureFromDrop(signature) {
        const wrapper = document.getElementById('hidden_dataset_path_input');
        const hiddenInput = wrapper ? wrapper.querySelector('textarea, input') : null;
        const hiddenBtn = document.getElementById('hidden_dataset_path_btn');
        const zone = document.getElementById('dataset_drop_zone');
        if (hiddenInput && hiddenBtn && signature && signature.files && signature.files.length) {
            setDatasetDropStatus(zone?.dataset?.searchingMsg || "🔎 Searching matching local folder...", false);
            setNativeValue(hiddenInput, "__DROP_SIGNATURE__" + JSON.stringify(signature));
            setTimeout(() => hiddenBtn.click(), 30);
        } else {
            setDatasetDropStatus(zone?.dataset?.blockedMsg || "⚠️ No usable local path was provided.", true);
        }
    }

    function readDirectoryEntries(reader) {
        return new Promise(resolve => {
            let entries = [];
            function readBatch() {
                reader.readEntries(batch => {
                    if (!batch || batch.length === 0) resolve(entries);
                    else { entries = entries.concat(Array.from(batch)); readBatch(); }
                }, () => resolve(entries));
            }
            readBatch();
        });
    }

    async function collectEntryFiles(entry, rootName, files, maxFiles) {
        if (!entry || files.length >= maxFiles) return;
        if (entry.isFile) {
            const full = (entry.fullPath || entry.name || "").replace(/^\\//, "");
            const prefix = rootName ? rootName.replace(/[.*+?^${}()|[\\]\\\\]/g, "\\\\$&") + "/" : "";
            const rel = full.replace(new RegExp("^" + prefix), "");
            files.push(rel || entry.name || full);
            return;
        }
        if (entry.isDirectory) {
            const children = await readDirectoryEntries(entry.createReader());
            for (const child of children) {
                if (files.length >= maxFiles) break;
                await collectEntryFiles(child, rootName || entry.name || "", files, maxFiles);
            }
        }
    }

    async function buildDropSignature(dt) {
        const items = Array.from(dt?.items || []);
        const files = [];
        let rootName = "";
        for (const item of items) {
            const entry = item.webkitGetAsEntry ? item.webkitGetAsEntry() : null;
            if (!entry) continue;
            if (!rootName) rootName = entry.name || "";
            await collectEntryFiles(entry, rootName, files, 160);
        }
        if (!files.length && dt?.files?.length) {
            Array.from(dt.files).slice(0, 160).forEach(f => files.push(f.webkitRelativePath || f.name || ""));
        }
        files.sort();
        return { rootName, files };
    }

    async function buildDropSignatureWithRetry(dt) {
        let best = { rootName: "", files: [] };
        for (let attempt = 0; attempt < 4; attempt++) {
            const sig = await buildDropSignature(dt);
            if ((sig.files?.length || 0) > (best.files?.length || 0)) best = sig;
            if (best.rootName && best.files && best.files.length >= 2) break;
            await new Promise(resolve => setTimeout(resolve, 120 + attempt * 180));
        }
        return best;
    }

    function pushDatasetPathFromDrop(raw) {
        const path = decodeDroppedPath(raw);
        const dirWrapper = document.getElementById('dataset_dir_input');
        const dirInput = dirWrapper ? dirWrapper.querySelector('textarea, input') : null;
        if (!looksLikeLocalPath(path)) {
            return false;
        }
        if (dirInput) {
            setNativeValue(dirInput, path);
            const zone = document.getElementById('dataset_drop_zone');
            setDatasetDropStatus(zone?.dataset?.loadingMsg || "✅ Path detected, loading dataset...", false);
            setTimeout(() => document.getElementById('dataset_load_btn')?.click(), 120);
            return true;
        }
        return false;
    }

    function setupDatasetPathDropZone() {
        const zone = document.getElementById('dataset_drop_zone');
        const dirWrapper = document.getElementById('dataset_dir_input');
        const targets = [zone, dirWrapper].filter(Boolean);
        targets.forEach(target => {
            if (target.dataset.datasetDropSetup) return;
            target.dataset.datasetDropSetup = "true";
            target.addEventListener('dragenter', function(e) {
                e.preventDefault(); e.stopPropagation();
                if (zone) zone.classList.add('dragover');
            });
            target.addEventListener('dragover', function(e) {
                e.preventDefault(); e.stopPropagation();
                if (zone) zone.classList.add('dragover');
            });
            target.addEventListener('dragleave', function(e) {
                if (!zone || zone.contains(e.relatedTarget)) return;
                zone.classList.remove('dragover');
            });
            target.addEventListener('drop', async function(e) {
                e.preventDefault(); e.stopPropagation();
                if (zone) zone.classList.remove('dragover');
                const dt = e.dataTransfer;
                let raw = dt.getData('text/uri-list') || dt.getData('text/plain') || "";
                if (!raw && dt.files && dt.files.length > 0 && dt.files[0].path) raw = dt.files[0].path;
                if (pushDatasetPathFromDrop(raw || "__DROP_PATH_BLOCKED__")) return;
                const signature = await buildDropSignatureWithRetry(dt);
                pushDatasetSignatureFromDrop(signature);
            });
        });
    }

    window.clickLibToggle = function(idx) {
        let inp = document.querySelector('#hidden_lib_toggle_input textarea');
        if(!inp) inp = document.querySelector('#hidden_lib_toggle_input input');
        if(inp) { setNativeValue(inp, idx.toString() + "_" + Date.now()); }
        setTimeout(() => document.getElementById('hidden_lib_toggle_btn')?.click(), 50);
    };
    
    window.clickLibDelete = function(idx, e) {
        if(e) e.stopPropagation(); 
        let inp = document.querySelector('#hidden_lib_delete_input textarea');
        if(!inp) inp = document.querySelector('#hidden_lib_delete_input input');
        if(inp) { setNativeValue(inp, idx.toString() + "_" + Date.now()); }
        setTimeout(() => document.getElementById('hidden_lib_delete_btn')?.click(), 50);
    };

    function updateGalleryVisuals() { document.querySelectorAll('#main_gallery button').forEach((btn, idx) => { btn.classList.toggle('custom-selected', window.gallerySelectedIndices.has(idx)); }); }
    function syncWithPython(viewIndex) {
        const payload = { selected: Array.from(window.gallerySelectedIndices), viewIndex: viewIndex };
        const wrapper = document.getElementById('hidden_sync_input');
        const inputEl = wrapper ? wrapper.querySelector('textarea, input') : null;
        if (inputEl) {
            setNativeValue(inputEl, JSON.stringify(payload));
            setTimeout(() => { const btn = document.getElementById('hidden_sync_btn'); if (btn) btn.click(); }, 30);
        }
    }

    function setupAutocomplete() {
        const captionWrappers = document.querySelectorAll('#viewer_caption_area textarea');
        if (captionWrappers.length === 0) return;
        const inp = captionWrappers[0];
        if(inp.dataset.acSetup) return;
        inp.dataset.acSetup = "true";
        let currentFocus;
        inp.addEventListener("input", function(e) {
            let a, b, i, val = this.value; closeAllLists(); if (!val) return false;
            let lastCommaIdx = val.lastIndexOf(','); let currentWord = val.substring(lastCommaIdx + 1).trimStart();
            let prefix = val.substring(0, lastCommaIdx + 1); if(val.length > 0 && val[lastCommaIdx+1] === ' ') prefix += ' ';
            if (currentWord.length < 2) return false;
            currentFocus = -1; a = document.createElement("DIV"); a.setAttribute("id", "autocomplete-list"); this.parentNode.appendChild(a);
            const tagsInput = document.getElementById('hidden_tags_input');
            if(tagsInput) { const rawTags = tagsInput.querySelector('textarea, input')?.value || ""; if(rawTags) window.allDatasetTags = rawTags.split('|'); }
            let matches = 0;
            for (i = 0; i < window.allDatasetTags.length; i++) {
                if (window.allDatasetTags[i].toLowerCase().includes(currentWord.toLowerCase())) {
                    matches++; if(matches > 10) break;
                    b = document.createElement("DIV");
                    let matchIdx = window.allDatasetTags[i].toLowerCase().indexOf(currentWord.toLowerCase());
                    let highlighted = window.allDatasetTags[i].substring(0, matchIdx) + "<strong>" + window.allDatasetTags[i].substring(matchIdx, matchIdx + currentWord.length) + "</strong>" + window.allDatasetTags[i].substring(matchIdx + currentWord.length);
                    b.innerHTML = highlighted; b.innerHTML += "<input type='hidden' value='" + window.allDatasetTags[i] + "'>";
                    b.addEventListener("click", function(e) { inp.value = prefix + this.getElementsByTagName("input")[0].value + ", "; inp.dispatchEvent(new Event('input', { bubbles: true })); closeAllLists(); });
                    a.appendChild(b);
                }
            }
        });
        inp.addEventListener("keydown", function(e) {
            let x = document.getElementById("autocomplete-list"); if (x) x = x.getElementsByTagName("div");
            if (e.keyCode == 40) { currentFocus++; addActive(x); } else if (e.keyCode == 38) { currentFocus--; addActive(x); }
            else if (e.keyCode == 13 || e.keyCode == 9) { if (currentFocus > -1 && x) { e.preventDefault(); x[currentFocus].click(); } }
        });
        function addActive(x) { if (!x) return false; removeActive(x); if (currentFocus >= x.length) currentFocus = 0; if (currentFocus < 0) currentFocus = (x.length - 1); x[currentFocus].classList.add("autocomplete-active"); }
        function removeActive(x) { for (var i = 0; i < x.length; i++) x[i].classList.remove("autocomplete-active"); }
        function closeAllLists(elmnt) { var x = document.getElementsByClassName("autocomplete-list"); for (var i = 0; i < x.length; i++) { if (elmnt != x[i] && elmnt != inp) x[i].parentNode.removeChild(x[i]); } let list = document.getElementById("autocomplete-list"); if(list) list.remove(); }
        document.addEventListener("click", function (e) { closeAllLists(e.target); });
    }

    function installStaticTooltips() {
        const tooltips = {
            "ai_recipe_btn": "Analyse les captions actuelles des images chargees pour proposer une recette globale de mots-cles partages. / Uses the currently loaded image captions to suggest a shared global keyword recipe."
        };
        Object.entries(tooltips).forEach(([id, text]) => {
            const wrapper = document.getElementById(id);
            if (!wrapper) return;
            const target = wrapper.matches('button') ? wrapper : wrapper.querySelector('button');
            if (!target || target.dataset.nativeTooltipReady) return;
            target.dataset.nativeTooltipReady = "true";
            target.setAttribute("title", text);
            target.setAttribute("aria-label", target.innerText ? target.innerText.trim() + " - " + text : text);
        });
    }

    setupDatasetPathDropZone();
    installStaticTooltips();

    const observer = new MutationObserver(() => { 
        updateGalleryVisuals(); setupAutocomplete(); setupDatasetPathDropZone(); installStaticTooltips();
        const trackedWrapper = document.getElementById('tracked_words_input'); const trackedInput = trackedWrapper ? trackedWrapper.querySelector('textarea') : null;
        if (trackedInput && !trackedInput.dataset.commaListener) {
            trackedInput.dataset.commaListener = "true";
            trackedInput.addEventListener('keyup', function(e) { if (e.key === ',' || e.key === 'Enter') { setTimeout(() => document.getElementById('hidden_calc_btn')?.click(), 50); } });
            trackedInput.addEventListener('blur', function(e) { setTimeout(() => document.getElementById('hidden_calc_btn')?.click(), 50); });
        }
    });
    observer.observe(document.body, { childList: true, subtree: true });

    const svelteInputObserver = new MutationObserver((mutations) => {
        mutations.forEach(m => {
            m.addedNodes.forEach(node => {
                if (node.nodeType === 1) {
                    const input = node.tagName === 'INPUT' ? node : node.querySelector('input');
                    if (input && input.closest('.gradio-dataframe')) {
                        let tries = 0;
                        const selectInterval = setInterval(() => { input.select(); if (tries++ > 15) clearInterval(selectInterval); }, 20);
                    }
                }
            });
        });
    });
    svelteInputObserver.observe(document.body, { childList: true, subtree: true });

    let dragStartIndex = -1;
    document.addEventListener('mousedown', function(e) {
        const tr = e.target.closest('.gradio-dataframe tbody tr');
        if (!tr) return;
        if (e.target.closest('input') || e.target.closest('textarea')) { tr.removeAttribute('draggable'); } 
        else { tr.setAttribute('draggable', 'true'); }
    });

    document.addEventListener('dragstart', function(e) {
        const tr = e.target.closest('tbody tr[draggable="true"]');
        if (tr) {
            dragStartIndex = Array.from(tr.parentNode.children).indexOf(tr);
            e.dataTransfer.effectAllowed = 'move';
            e.dataTransfer.setData('text/plain', dragStartIndex);
            setTimeout(() => tr.classList.add('dragging'), 0);
        }
    });

    document.addEventListener('dragover', function(e) {
        const draggingTr = document.querySelector('.dragging');
        const tr = e.target.closest('tbody tr');
        if (tr && draggingTr && tr !== draggingTr && tr.parentNode === draggingTr.parentNode) {
            e.preventDefault(); 
            const rect = tr.getBoundingClientRect();
            const mid = rect.top + rect.height / 2;
            if (e.clientY < mid) { tr.before(draggingTr); } else { tr.after(draggingTr); }
        }
    });

    document.addEventListener('dragend', function(e) {
        const tr = e.target.closest('tbody tr');
        if (tr) { tr.classList.remove('dragging'); tr.removeAttribute('draggable'); }
    });

    document.addEventListener('drop', function(e) {
        const tr = e.target.closest('tbody tr');
        if (tr) {
            e.preventDefault();
            const draggingTr = document.querySelector('.dragging');
            if(draggingTr) { draggingTr.classList.remove('dragging'); draggingTr.removeAttribute('draggable'); }
            
            const dragEndIndex = Array.from(tr.parentNode.children).indexOf(tr);
            if (dragStartIndex !== -1 && dragStartIndex !== dragEndIndex) {
                const wrapper = document.getElementById('hidden_dnd_input');
                const hiddenInput = wrapper ? wrapper.querySelector('textarea, input') : null;
                const hiddenBtn = document.getElementById('hidden_dnd_btn');
                if (hiddenInput && hiddenBtn) {
                    setNativeValue(hiddenInput, dragStartIndex + "," + dragEndIndex);
                    setTimeout(() => hiddenBtn.click(), 50);
                }
            }
        }
        dragStartIndex = -1;
    });

    window.addEventListener('keydown', function(e) {
        const tag = e.target.tagName.toLowerCase();
        const isInput = (tag === 'input' || tag === 'textarea');

        if (e.altKey && e.code === 'ArrowUp') { e.preventDefault(); e.stopPropagation(); document.getElementById('btn_move_up')?.click(); return; }
        if (e.altKey && e.code === 'ArrowDown') { e.preventDefault(); e.stopPropagation(); document.getElementById('btn_move_down')?.click(); return; }
        if (isInput && !e.altKey && !e.ctrlKey && !e.metaKey && e.code !== 'PageUp' && e.code !== 'PageDown') return;

        if ((e.ctrlKey || e.metaKey) && (e.code === 'KeyA' || e.key.toLowerCase() === 'a')) {
            if (isInput) return;
            e.preventDefault(); e.stopPropagation();
            const btns = document.querySelectorAll('#main_gallery button');
            window.gallerySelectedIndices.clear();
            btns.forEach((b, i) => window.gallerySelectedIndices.add(i));
            updateGalleryVisuals();
            syncWithPython(window.lastClickedIndex !== -1 ? window.lastClickedIndex : 0);
            return;
        }

        if ((e.ctrlKey || e.metaKey) && (e.code === 'KeyF' || e.key.toLowerCase() === 'f')) { e.preventDefault(); e.stopPropagation(); const searchBox = document.querySelector('input[placeholder*="mot"], input[placeholder*="word"]'); if (searchBox) { searchBox.focus(); searchBox.select(); } return; }
        if (e.altKey && (e.code === 'KeyS' || e.key.toLowerCase() === 's')) { e.preventDefault(); e.stopPropagation(); document.getElementById('toggle_tag_btn')?.click(); return; }
        if ((e.ctrlKey || e.metaKey) && (e.code === 'KeyS' || e.key.toLowerCase() === 's')) { e.preventDefault(); e.stopPropagation(); document.getElementById('save_single_btn')?.click(); return; }
        if (e.altKey && (e.code === 'KeyC' || e.key.toLowerCase() === 'c')) { e.preventDefault(); e.stopPropagation(); document.getElementById('clear_sel_btn')?.click(); return; }
        
        if (e.code === 'PageUp') { e.preventDefault(); document.getElementById('prev_btn')?.click(); return; }
        if (e.code === 'PageDown') { e.preventDefault(); document.getElementById('next_btn')?.click(); return; }
        if (isInput) return;
        if (e.code === 'ArrowLeft' || e.key === 'ArrowLeft') { e.preventDefault(); document.getElementById('prev_btn')?.click(); }
        if (e.code === 'ArrowRight' || e.key === 'ArrowRight') { e.preventDefault(); document.getElementById('next_btn')?.click(); }
    }, true); 

    document.addEventListener('click', function(e) {
        if (!e.target || !e.target.closest) return;
        // --- 1. ÉCOUTE DES CLICS DE LA BIBLIOTHÈQUE ---
        const delBtn = e.target.closest('.lib-item-delete');
        if (delBtn) {
            e.preventDefault(); e.stopPropagation();
            const idx = delBtn.getAttribute('data-idx');
            if (idx !== null) window.clickLibDelete(idx, e);
            return;
        }

        const libItem = e.target.closest('.lib-item-custom');
        if (libItem) {
            e.preventDefault(); e.stopPropagation();
            const idx = libItem.getAttribute('data-idx');
            if (idx !== null) window.clickLibToggle(idx);
            return;
        }

        // --- 2. ÉCOUTE DES CLICS DE LA GALERIE ---
        if (e.target.closest('label') || e.target.tagName === 'INPUT') return;
        const btn = e.target.closest('#main_gallery button');
        if (!btn) return;
        
        e.preventDefault(); e.stopPropagation();
        const btns = Array.from(document.querySelectorAll('#main_gallery button'));
        const index = btns.indexOf(btn);
        if (index === -1) return;

        const cbWrapper = document.getElementById('multi_cb');
        const isMultiChecked = cbWrapper ? (cbWrapper.querySelector('input[type="checkbox"]')?.checked || false) : false;

        if (e.shiftKey && window.lastClickedIndex !== -1) {
            const start = Math.min(window.lastClickedIndex, index);
            const end = Math.max(window.lastClickedIndex, index);
            if (!e.ctrlKey && !e.metaKey && !isMultiChecked) { window.gallerySelectedIndices.clear(); }
            for (let i = start; i <= end; i++) window.gallerySelectedIndices.add(i);
        } 
        else if (e.ctrlKey || e.metaKey || isMultiChecked) {
            if (window.gallerySelectedIndices.has(index)) window.gallerySelectedIndices.delete(index);
            else window.gallerySelectedIndices.add(index);
        } 
        else {
            window.gallerySelectedIndices.clear();
            window.gallerySelectedIndices.add(index); 
        }

        window.lastClickedIndex = index;
        updateGalleryVisuals();
        syncWithPython(index);
    }, true);

    setInterval(() => {
        const wrapper = document.getElementById('hidden_sync_input');
        const selInput = wrapper ? wrapper.querySelector('textarea, input') : null;
        if (selInput && selInput.value === '{}' && window.gallerySelectedIndices.size > 0) {
            window.gallerySelectedIndices.clear();
            updateGalleryVisuals();
        }
    }, 150);
}
"""

# ==========================================
# FONCTIONS LOGIQUES PYTHON & UTILITAIRES
# ==========================================

def get_gallery_items(filtered_dataset, lang): return [(item['img_path'], "") for item in filtered_dataset]

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
        for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            add(f"{letter}:\\")
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

def _score_drop_candidate(directory, signature_files):
    candidate_files = _candidate_file_signature(directory)
    candidate_lower = {os.path.basename(f).lower() for f in candidate_files}
    candidate_rel = {f.lower().replace("\\", "/") for f in candidate_files}
    sig_rel = {str(f).lower().replace("\\", "/") for f in signature_files if f}
    sig_names = {os.path.basename(f).lower() for f in sig_rel}
    image_names = {n for n in sig_names if n.endswith(VALID_IMAGE_EXTENSIONS)}
    if image_names and not any(n in candidate_lower for n in image_names):
        return 0
    return (len(sig_rel & candidate_rel) * 3) + len(sig_names & candidate_lower)

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

    def consider(path):
        nonlocal best_path, best_score
        if not os.path.isdir(path):
            return
        score = _score_drop_candidate(path, signature_files)
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

    focused_timeout = start + min(timeout_sec, 7)
    for likely_root in likely_roots:
        for candidate in _walk_dirs_limited(likely_root, focused_timeout, max_dirs=18000, max_depth=14):
            if expected_name and os.path.basename(candidate).lower() != expected_name:
                continue
            consider(candidate)
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

def sort_dataset(dataset, order, lang, msg_no_sel, all_tags_str=""):
    if not dataset: return [], [], [], "", "{}", -1
    reverse = (order == "Z-A")
    dataset = sorted(dataset, key=lambda x: natural_sort_key(x['img_name']), reverse=reverse)
    for idx, item in enumerate(dataset): item['id'] = idx
        
    gal_items = get_gallery_items(dataset, lang)
    success_msg = MSG[lang].get("images_loaded", "{count} images loaded.").format(count=len(dataset))
    gr.Info(success_msg)
    return dataset, dataset, [], success_msg, gal_items, [], msg_no_sel, "{}", all_tags_str or extract_all_tags(dataset), -1

def load_dataset(directory, sort_order, lang):
    msg_no_sel = MSG[lang].get("no_selection", "Aucune sélection active.")
    # Accepter aussi bien les chemins absolus que relatifs ; normaliser.
    directory = normalize_dataset_path(directory)
    if not directory or not os.path.isdir(directory):
        return [], [], [], MSG[lang].get("folder_not_found", "Dossier introuvable."), [], [], msg_no_sel, "{}", "", -1
    dataset = []
    valid_extensions = ('.png', '.jpg', '.jpeg', '.webp')
    idx = 0
    for filename in sorted(os.listdir(directory), key=natural_sort_key):
        if filename.lower().endswith(valid_extensions):
            img_path = os.path.join(directory, filename)
            txt_path = os.path.splitext(img_path)[0] + '.txt'
            caption = ""
            if os.path.exists(txt_path):
                with open(txt_path, 'r', encoding='utf-8') as f: caption = f.read().strip()
            else:
                with open(txt_path, 'w', encoding='utf-8') as f: pass
            dataset.append({'id': idx, 'img_name': filename, 'img_path': img_path, 'txt_path': txt_path, 'caption': caption})
            idx += 1
    if not dataset:
        msg = MSG[lang].get("no_images_found", "No supported images found in this folder.")
        gr.Warning(msg)
        return [], [], [], msg, [], [], msg_no_sel, "{}", "", -1
    return sort_dataset(dataset, sort_order, lang, msg_no_sel, extract_all_tags(dataset))

def filter_gallery(dataset, search_text, sort_order, lang):
    if not dataset: return [], [], [], "", "{}", -1
    filtered = dataset
    if search_text:
        filtered = [item for item in dataset if search_text.lower() in item['caption'].lower()]
    reverse = (sort_order == "Z-A")
    filtered = sorted(filtered, key=lambda x: natural_sort_key(x['img_name']), reverse=reverse)
    return filtered, get_gallery_items(filtered, lang), [], "", "{}", -1

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

def clear_selection(lang): 
    return [], MSG[lang].get("no_sel_all", "Aucune sélection (Le Batch impactera **TOUT** le dataset)."), "{}"

def handle_sync(payload_str, dataset, filtered_dataset, old_idx, old_caption, tracked_words, lang):
    silent_save(dataset, filtered_dataset, old_idx, old_caption, lang)
    try:
        data = json.loads(payload_str)
        sel_js = data.get("selected", [])
        view_idx = int(data.get("viewIndex", 0))
    except:
        sel_js = []; view_idx = 0
    real_ids = [filtered_dataset[i]['id'] for i in sel_js if 0 <= i < len(filtered_dataset)] if filtered_dataset else []
    sel_text = MSG[lang].get("selected_multi", "✅ **{count}** sélectionnée(s)").format(count=len(real_ids)) if real_ids else ""
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
        settings.get("system_prompt", DEFAULT_AI_SETTINGS["system_prompt"]),
    )

def _write_ai_settings(settings):
    try:
        with open(AI_SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ Impossible de sauver {AI_SETTINGS_FILE} : {e}")

def save_ai_settings(api_backend, vlm_model, llm_model, api_url, api_key, temperature, context, system_prompt):
    settings = load_ai_settings()
    settings.update({
        "api_backend": api_backend or DEFAULT_AI_SETTINGS["api_backend"],
        "vlm_model": vlm_model or "",
        "llm_model": llm_model or "",
        "api_url": api_url or "",
        "api_key": api_key or "",
        "temperature": float(temperature) if temperature not in (None, "") else DEFAULT_AI_SETTINGS["temperature"],
        "context": int(float(context)) if context not in (None, "") else DEFAULT_AI_SETTINGS["context"],
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

def save_lm_studio_model_choices(vlm_choice, llm_choice, shared_choice, api_backend, api_url, api_key, temperature, context, system_prompt, lang):
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
        "system_prompt": system_prompt or "",
    })
    _write_ai_settings(settings)
    msg = m.get("lm_studio_saved", "💾 LM Studio model choices saved.")
    gr.Info(msg)
    return gr.update(value=vlm), gr.update(value=llm), msg

# ==========================================
# 📚 NOUVEAU MODULE: BIBLIOTHÈQUE CUSTOM
# ==========================================

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
    return render_lib_html(new_lib, lang), new_lib, ""

def toggle_lib_item(idx_str, lib_state, lang):
    new_lib = copy.deepcopy(lib_state)
    try:
        idx = int(str(idx_str).split('_')[0])
        if 0 <= idx < len(new_lib):
            new_lib[idx]['selected'] = not new_lib[idx].get('selected', False)
    except: pass
    return render_lib_html(new_lib, lang), new_lib

def delete_lib_item(idx_str, lib_state, lang):
    new_lib = copy.deepcopy(lib_state)
    try:
        idx = int(str(idx_str).split('_')[0])
        if 0 <= idx < len(new_lib):
            new_lib.pop(idx)
    except: pass
    return render_lib_html(new_lib, lang), new_lib

def uncheck_all_lib(lib_state, lang):
    new_lib = copy.deepcopy(lib_state)
    for x in new_lib: x['selected'] = False
    return render_lib_html(new_lib, lang), new_lib

def clear_lib(lang):
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
def translate_text(text, engine, source_lang, dest_lang, api_backend, api_url, llm_model, lang="FR", api_key=""):
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
            "You are a professional translator.", api_key=api_key
        )

def do_live_translation(caption, engine, dest_lang, api_backend, api_url, llm_model, lang, api_key=""):
    if not caption: return ""
    caption = str(caption).strip()
    if len(caption) < 2: return ""
    cache_key = (caption, engine, dest_lang, api_backend, api_url, llm_model, api_key)
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
            res = translate_text(caption, engine, "auto", dest_lang, api_backend, api_url, llm_model, lang, api_key)
        if res and res.startswith("⚠️"): return res
        if len(LIVE_TRANSLATION_CACHE) > 200:
            LIVE_TRANSLATION_CACHE.clear()
        LIVE_TRANSLATION_CACHE[cache_key] = res or ""
        return res
    except Exception as e:
        return f"Erreur: {e}"

def translate_entire_caption_action(dataset, filtered_dataset, idx, caption, engine, source_lang, api_backend, api_url, llm_model, tracked_words, lang, api_key=""):
    new_dataset = copy.deepcopy(dataset)
    new_filtered = [item for item in new_dataset if item['id'] in [x['id'] for x in filtered_dataset]]
    m = MSG.get(lang, MSG["FR"])

    if not caption: 
        cap, hl_html, wc = get_updated_viewer_data(new_filtered, idx, tracked_words, lang)
        return new_dataset, new_filtered, cap, hl_html, wc, m.get("trans_no_text", "Aucun texte")
        
    res = translate_text(caption, engine, source_lang, "en", api_backend, api_url, llm_model, lang, api_key)
    
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

def trans_insert(text_to_trans, current_caption, engine, source_lang, api_backend, api_url, llm_model, lang, api_key=""):
    if not text_to_trans: return current_caption
    res = translate_text(text_to_trans, engine, source_lang, "en", api_backend, api_url, llm_model, lang, api_key)
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
    return status, gallery_preview, p_fig, b_fig, [], MSG[lang].get("no_sel_all", "Aucune sélection (Le Batch impactera **TOUT** le dataset)."), "{}"

def _caption_tags(caption):
    tags = []
    for raw in str(caption or "").split(","):
        tag = re.sub(r"\s+", " ", raw).strip(" \t\r\n\"'`")
        if tag:
            tags.append(tag)
    return tags

def _shared_caption_candidates(dataset):
    counts = Counter()
    canonical = {}
    for item in dataset or []:
        seen = set()
        for tag in _caption_tags(item.get("caption", "")):
            key = tag.lower()
            if key in seen:
                continue
            seen.add(key)
            counts[key] += 1
            canonical.setdefault(key, tag)
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], canonical.get(kv[0], kv[0])))
    return [(canonical.get(key, key), count) for key, count in ranked]

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

def auto_fill_recipe_from_ai(dataset, count, api_backend, api_url, llm_model, temp, ctx, sys_prompt, lang, api_key=""):
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

    dataset_dir = os.path.dirname(dataset[0].get("img_path", "")) if dataset else ""
    dataset_name = os.path.basename(dataset_dir) or "dataset"
    total = len(dataset)
    candidate_limit = max(limit * 4, 80)
    candidate_lines = "\n".join(
        f"- {tag} ({count}/{total} images)" for tag, count in candidates[:candidate_limit]
    )
    fallback_tags = [tag for tag, _ in candidates[:limit]]
    prompt = (
        "Tu es un assistant expert en datasets LoRA/Flux/Stable Diffusion.\n"
        f"Dataset: {dataset_name}\n"
        f"Nombre d'images/captions analysees: {total}\n"
        f"Objectif: choisir les {limit} mots-cles les plus utiles pour remplir une Recette Globale.\n"
        "Contraintes strictes:\n"
        "- Reponds uniquement par une liste separee par des virgules.\n"
        "- Utilise les mots-cles candidats ci-dessous, car ils viennent de toutes les captions du dataset.\n"
        "- Priorise les mots-cles les plus partages en commun entre les images.\n"
        "- Inclus le trigger word/concept principal si tu le reconnais dans le nom du dataset ou dans les captions.\n"
        "- Ne donne aucune explication.\n\n"
        f"Mots-cles candidats avec frequence:\n{candidate_lines}"
    )

    ai_response = call_ai_api(
        prompt, llm_model, None, api_backend, api_url, temp, ctx, sys_prompt, api_key=api_key
    )
    allowed_tags = [tag for tag, _ in candidates]
    picked = []
    if ai_response and not str(ai_response).startswith("Erreur API"):
        picked = _parse_ai_recipe_tags(ai_response, allowed_tags, limit)
    else:
        gr.Warning(str(ai_response or m.get("error", "Error.")))

    for tag in fallback_tags:
        if len(picked) >= limit:
            break
        if tag.lower() not in {x.lower() for x in picked}:
            picked.append(tag)

    recipe = ", ".join(picked[:limit])
    msg = m.get("ai_recipe_success", "✅ AI recipe generated from {count} captions: {tags} keywords.").format(
        count=total, tags=len(picked[:limit])
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

def scan_duplicates_advanced(dataset, tolerance):
    if not HAS_IMAGEHASH:
        gr.Warning("Installez imagehash: pip install imagehash")
        return gr.update(choices=[], value=""), {}
    
    hashes = {}
    dups_pairs = []
    
    for item in dataset:
        try:
            img = Image.open(item['img_path'])
            h = imagehash.average_hash(img)
            
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
        return gr.update(choices=[], value=""), {}
        
    choices = [p["name"] for p in dups_pairs]
    mapping = {p["name"]: p for p in dups_pairs}
    gr.Warning(f"{len(choices)} paires suspectes trouvées !")
    return gr.update(choices=choices, value=choices[0]), mapping

def load_duplicate_pair(pair_name, mapping):
    if not pair_name or pair_name not in mapping: return None, None, -1, -1
    data = mapping[pair_name]
    return data["imgA"], data["imgB"], data["idA"], data["idB"]

def delete_duplicate(dataset, filtered_dataset, id_to_delete, pair_name, mapping):
    if id_to_delete < 0: return dataset, filtered_dataset, gr.update(), mapping, "Erreur suppression"
    item_to_del = next((x for x in dataset if x['id'] == id_to_delete), None)
    if item_to_del:
        try:
            os.remove(item_to_del['img_path'])
            if os.path.exists(item_to_del['txt_path']): os.remove(item_to_del['txt_path'])
            dataset = [x for x in dataset if x['id'] != id_to_delete]
            filtered_dataset = [x for x in filtered_dataset if x['id'] != id_to_delete]
            gr.Info(f"Fichier {item_to_del['img_name']} supprimé.")
        except Exception as e:
            gr.Warning(f"Impossible de supprimer: {e}")
            
    if pair_name in mapping:
        del mapping[pair_name]
        
    choices = list(mapping.keys())
    val = choices[0] if choices else ""
    return dataset, filtered_dataset, gr.update(choices=choices, value=val), mapping, f"Supprimé. Reste {len(choices)} doublons."

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

def batch_process_images(dataset, dest_folder, size, format_choice, crop_mode, handle_alpha):
    if not dataset: return "Aucun dataset."
    if not dest_folder: dest_folder = os.path.join(os.getcwd(), "processed_dataset")
    os.makedirs(dest_folder, exist_ok=True)
    count = 0
    target_size = int(size)
    for item in dataset:
        try:
            img = Image.open(item['img_path'])
            if handle_alpha and (img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info)):
                bg = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P': img = img.convert('RGBA')
                bg.paste(img, (0,0), img)
                img = bg
            elif img.mode not in ('RGB', 'L'):
                img = img.convert('RGB')
                
            if crop_mode == "Smart Face Crop (OpenCV)" and HAS_CV2:
                img_cv = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
                gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
                face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
                faces = face_cascade.detectMultiScale(gray, 1.1, 4)
                if len(faces) > 0:
                    x, y, w_face, h_face = faces[0]
                    center_x, center_y = x + w_face//2, y + h_face//2
                    w, h = img.size
                    min_dim = min(w, h)
                    left = max(0, center_x - min_dim//2)
                    top = max(0, center_y - min_dim//2)
                    right = min(w, left + min_dim)
                    bottom = min(h, top + min_dim)
                    if right - left < min_dim: left = right - min_dim
                    if bottom - top < min_dim: top = bottom - min_dim
                    img = img.crop((left, top, right, bottom))
                else:
                    w, h = img.size; min_dim = min(w, h)
                    img = img.crop(((w-min_dim)/2, (h-min_dim)/2, (w+min_dim)/2, (h+min_dim)/2))
            elif crop_mode == "1:1 (Carré Centre)":
                w, h = img.size; min_dim = min(w, h)
                img = img.crop(((w-min_dim)/2, (h-min_dim)/2, (w+min_dim)/2, (h+min_dim)/2))
            
            img.thumbnail((target_size, target_size), Image.Resampling.LANCZOS)
            ext = ".webp" if format_choice == "WebP" else ".jpg"
            new_name = os.path.splitext(item['img_name'])[0] + ext
            save_path = os.path.join(dest_folder, new_name)
            img.save(save_path, format="WEBP" if format_choice=="WebP" else "JPEG", quality=95)
            new_txt_name = os.path.splitext(item['img_name'])[0] + ".txt"
            shutil.copy2(item['txt_path'], os.path.join(dest_folder, new_txt_name))
            count += 1
        except Exception as e: print(f"Erreur pré-traitement sur {item['img_name']}: {e}")
    return f"✅ {count} images traitées avec succès !"

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

def load_ai_recipes():
    if os.path.exists(AI_RECIPES_FILE):
        with open(AI_RECIPES_FILE, 'r') as f: return json.load(f)
    return {"Default Flux Style": "Réécris ces tags en une phrase naturelle parfaite pour le modèle Flux : {tags}"}

def save_ai_recipe(name, prompt):
    if not name: return gr.update()
    recipes = load_ai_recipes()
    recipes[name] = prompt
    with open(AI_RECIPES_FILE, 'w') as f: json.dump(recipes, f)
    gr.Info("Template IA sauvegardé !")
    return gr.update(choices=list(recipes.keys()), value=name)

def apply_ai_recipe(name): return load_ai_recipes().get(name, "")

AI_ACTION_DESCRIPTIONS = {
    "Auto-Taggage / Super OCR (VLM)": "**Vision :** Analyse complète de l'image et extraction du texte.",
    "Reality Check & Hallucinations (VLM)": "**Vision :** Supprime les tags inexistants dans l'image réelle.",
    "Concept Isolator (Spécial LoRA)": "**Vision :** Décrit tout SAUF le sujet central.",
    "Traducteur Visuel (Booru ↔ Phrase Naturelle)": "**Texte :** Convertit des tags bruts en une belle phrase.",
    "Tag Sorting & Standardisation": "**Texte :** Ordonne l'importance des tags et corrige l'orthographe.",
    "Traduction Automatique (Vers Anglais)": "**Texte :** Traduit proprement vers l'anglais.",
    "✨ Prompt Personnalisé (Texte/Vision)": "**Custom :** Utilisez le champ 'Prompt Personnalisé' ci-dessous."
}

def update_ai_action_desc(action):
    show_custom = action == "✨ Prompt Personnalisé (Texte/Vision)"
    desc = AI_ACTION_DESCRIPTIONS.get(action, "")
    return f"<div class='ai-desc-box'>ℹ️ {desc}</div>", gr.update(visible=show_custom), gr.update(visible=show_custom)

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

def call_ai_api(prompt, model, image_path, api_backend, api_url, temp, ctx, sys_prompt, api_key=""):
    """Appelle un backend IA. Supporte Ollama, OpenAI-compatible (LM Studio inclus),
    Anthropic Claude et Google Gemini. api_key est requis pour les services cloud."""
    kind = _backend_kind(api_backend)
    api_key = (api_key or "").strip()
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
            response = requests.post(url, json=payload, timeout=180)
            response.raise_for_status()
            return response.json().get("response", "").strip()
        except Exception as e:
            return f"Erreur API Ollama: {e}"

    # --- ANTHROPIC CLAUDE ---
    if kind == "anthropic":
        url = _normalize_api_url(api_url, DEFAULT_ANTHROPIC_URL)
        if not url.endswith("/v1/messages"):
            url = url + "/v1/messages"
        if not api_key:
            return "Erreur API Anthropic: clé API manquante (entrez-la dans Paramètres Avancés API)."
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
            response = requests.post(url, json=payload, headers=headers, timeout=180)
            response.raise_for_status()
            data = response.json()
            blocks = data.get("content", [])
            return "".join(b.get("text", "") for b in blocks if b.get("type") == "text").strip()
        except Exception as e:
            return f"Erreur API Anthropic: {e}"

    # --- GOOGLE GEMINI ---
    if kind == "gemini":
        url = _normalize_api_url(api_url, DEFAULT_GEMINI_URL)
        if not api_key:
            return "Erreur API Gemini: clé API manquante (entrez-la dans Paramètres Avancés API)."
        model_id = model or "gemini-2.5-flash"
        endpoint = f"{url}/v1beta/models/{model_id}:generateContent?key={api_key}"
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
        try:
            response = requests.post(endpoint, json=payload, timeout=180)
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
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=180)
        response.raise_for_status()
        return response.json().get("choices", [{}])[0].get("message", {}).get("content", "").strip()
    except requests.HTTPError as e:
        return _format_http_error("Erreur API OpenAI-compatible", getattr(e, "response", response), e)
    except Exception as e:
        return f"Erreur API OpenAI-compatible: {e}"

def process_ai_action(dataset, selected_ids, search_text, action, custom_prompt, injection_mode, use_vision_for_custom, vlm_model, llm_model, api_backend, api_url, temp, ctx, sys_prompt, current_idx, tracked_words, lang, api_key=""):
    if not dataset: return dataset, dataset, dataset, "Dataset vide.", extract_all_tags(dataset), "", get_highlighted_html("", tracked_words), ""
    history = copy.deepcopy(dataset)
    count = 0; errors = []
    for item in dataset:
        if selected_ids and item['id'] not in selected_ids: continue
        current_cap = item['caption']; new_cap = current_cap; res = ""
        try:
            if action == "Auto-Taggage / Super OCR (VLM)": res = call_ai_api("Décris cette image en détail (virgules). Ajoute le texte lu sous la forme text: \"le texte\".", vlm_model, item['img_path'], api_backend, api_url, temp, ctx, sys_prompt, api_key=api_key)
            elif action == "Reality Check & Hallucinations (VLM)": res = call_ai_api(f"Tags actuels: '{current_cap}'. Ne renvoie QUE les tags réellement présents.", vlm_model, item['img_path'], api_backend, api_url, temp, ctx, sys_prompt, api_key=api_key)
            elif action == "Concept Isolator (Spécial LoRA)": res = call_ai_api("Décris l'arrière-plan et le style, NE DÉCRIS PAS le sujet principal.", vlm_model, item['img_path'], api_backend, api_url, temp, ctx, sys_prompt, api_key=api_key)
            elif action == "Traducteur Visuel (Booru ↔ Phrase Naturelle)": res = call_ai_api(f"Transforme en phrase anglaise fluide pour Flux : {current_cap}", llm_model, None, api_backend, api_url, temp, ctx, sys_prompt, api_key=api_key)
            elif action == "Traduction Automatique (Vers Anglais)": res = call_ai_api(f"Translate into English, keep comma format: {current_cap}", llm_model, None, api_backend, api_url, temp, ctx, sys_prompt, api_key=api_key)
            elif action == "Tag Sorting & Standardisation": res = call_ai_api(f"Ordonne (Sujet, Vêtements, Fond) et corrige: {current_cap}", llm_model, None, api_backend, api_url, temp, ctx, sys_prompt, api_key=api_key)
            elif action == "✨ Prompt Personnalisé (Texte/Vision)":
                model_to_use = vlm_model if use_vision_for_custom else llm_model
                img_path_to_use = item['img_path'] if use_vision_for_custom else None
                res = call_ai_api(custom_prompt.replace("{tags}", current_cap), model_to_use, img_path_to_use, api_backend, api_url, temp, ctx, sys_prompt, api_key=api_key)
            
            if res.startswith("Erreur API"): errors.append(item['img_name']); gr.Warning(res); continue
            if injection_mode == "Remplacer tout" or action != "✨ Prompt Personnalisé (Texte/Vision)": new_cap = res
            elif injection_mode == "Ajouter au début": new_cap = res + ", " + current_cap if current_cap else res
            elif injection_mode == "Ajouter à la fin": new_cap = current_cap + ", " + res if current_cap else res
            
            if new_cap != current_cap: item['caption'] = new_cap; count += 1
        except: errors.append(item['img_name'])
    save_all_captions(dataset)
    msg = f"✅ IA Appliquée ({count} modifiés)."
    if errors: msg += f" ⚠️ Échecs sur {len(errors)} fichiers."
    gr.Info(msg)
    filtered_dataset = [item for item in dataset if search_text.lower() in item['caption'].lower()] if search_text else dataset
    
    cap, hl, wc = get_updated_viewer_data(filtered_dataset, current_idx, tracked_words, lang)
    return dataset, filtered_dataset, history, msg, extract_all_tags(dataset), cap, hl, wc

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

def analyze_bias(dataset, llm_model, api_backend, api_url, temp, ctx, sys_prompt, lang="FR", api_key=""):
    if not dataset:
        return MSG.get(lang, MSG.get("FR", {})).get("no_dataset", "Aucun dataset.")
    profile = _build_bias_profile(dataset)
    output_lang = "français" if lang == "FR" else "English"
    top_tags = ", ".join([f"{tag} ({count})" for tag, count in profile["top_tags"][:30]])
    rare_tags = ", ".join([tag for tag, _ in profile["rare_tags"][:25]])
    caption_samples = "\n".join([f"- {cap[:260]}" for cap in profile["caption_samples"]])
    prompt = f"""
Tu es un expert senior en préparation de datasets pour Stable Diffusion, Flux et entraînement LoRA.
Analyse ce dataset à partir de ses captions réelles. Réponds en {output_lang}, de façon concrète et actionnable.

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
{caption_samples}

Produit un rapport structuré avec ces sections:
1. Diagnostic rapide: ce que le dataset semble apprendre en priorité.
2. Biais probables: sujet, pose, cadrage, style, fond, lumière, vêtements/objets, vocabulaire répétitif.
3. Risques pour un LoRA: surapprentissage, trigger trop faible, tags contradictoires, tags trop génériques, manque de diversité.
4. Corrections prioritaires: actions concrètes à faire dans les captions ou dans le tri des images.
5. Tags à surveiller: liste courte des tags à fusionner, supprimer, renforcer ou renommer.

Ne reste pas générique: appuie chaque remarque sur les tags ou captions fournis. Si une information manque, indique comment la vérifier dans l'outil.
""".strip()
    return call_ai_api(prompt, llm_model, None, api_backend, api_url, temp, ctx, sys_prompt, api_key=api_key)

# ==========================================
# GESTION DYNAMIQUE DU CHANGEMENT DE LANGUE
# ==========================================
def change_language(lang, stats_df, config_df, lib_state):
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
        gr.update(value=t.get("status_wait", "")),
        
        gr.update(value=t.get("recipe_global", "")),
        gr.update(label=t.get("recipes_dd", "")),
        gr.update(label=t.get("recipe_name", "")),
        gr.update(value=t.get("save_recipe", "")),
        gr.update(placeholder=t.get("tracked_ph", "")),
        gr.update(label=t.get("ai_recipe_count", "Nombre de mots-clés IA")),
        gr.update(value=t.get("btn_ai_recipe", "🤖 Remplir par IA")),
        gr.update(value=t.get("btn_analyze_recipe", "📊 Lancer l'analyse des données")),
        
        gr.update(value=t.get("gallery_title", "")),
        gr.update(label=t.get("search", ""), placeholder=t.get("search_ph", "")),
        gr.update(label=t.get("multi_cb", "")),
        gr.update(value=t.get("clear_sel", "")),
        gr.update(label=t.get("cols", "")),
        
        gr.update(value=t.get("hide_gal", "")),
        gr.update(label=t.get("tab_view", "")),
        gr.update(value=t.get("btn_prev", "")),
        gr.update(value=t.get("btn_next", "")),
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
        gr.update(label=t.get("hash_tol", "")),
        gr.update(value=t.get("btn_scan_dups", "")),
        gr.update(label=t.get("dup_dd", "")),
        gr.update(value=t.get("btn_del_A", "")),
        gr.update(value=t.get("btn_del_B", "")),
        
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
        
        gr.update(label=t.get("tab_ai", "")),
        gr.update(value=t.get("ai_conf_title", "")),
        gr.update(label=t.get("api_backend", "")),
        gr.update(label=t.get("vlm_model", "")),
        gr.update(label=t.get("llm_model", "")),
        gr.update(label=t.get("ai_adv_acc", "")),
        gr.update(label=t.get("api_url_input", "")),
        gr.update(label=t.get("ai_temp", "")),
        gr.update(label=t.get("ai_ctx", "")),
        gr.update(label=t.get("ai_sys", "")),
        
        gr.update(value=t.get("ai_act_title", "")),
        gr.update(label=t.get("ai_action_dd", "")),
        gr.update(label=t.get("ai_tpl_dd", "")),
        gr.update(label=t.get("ai_tpl_name", "")),
        gr.update(value=t.get("btn_save_tpl", "")),
        gr.update(label=t.get("custom_prompt_input", "")),
        gr.update(label=t.get("use_vision_custom", "")),
        gr.update(label=t.get("injection_mode", "")),
        gr.update(value=t.get("btn_run_ai", "")),
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
        gr.update(label=t.get("strat", ""), choices=t.get("strat_choices", [])),
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
    )

# ==========================================
# INTERFACE GRADIO
# ==========================================

blocks_kwargs = {"title": "IMG Dataset Refiner v4.3 Pro"}
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
    
    # State pour la bibliothèque Custom HTML
    lib_state = gr.State([])
    
    dup_mapping_state = gr.State({})
    dup_idA = gr.State(-1)
    dup_idB = gr.State(-1)
    
    dummy_selection = gr.Textbox(visible=False, elem_id="dummy_selection")
    ui_hidden_sync_input = gr.Textbox(value="{}", elem_id="hidden_sync_input")
    ui_hidden_sync_btn = gr.Button(elem_id="hidden_sync_btn")
    ui_hidden_calc_btn = gr.Button(elem_id="hidden_calc_btn")
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
    
    t_init = UI_T.get("FR", {})
    ai_settings_init = load_ai_settings()
    ui_settings_init = load_ui_settings()

    with gr.Row(elem_id="top_workspace"):
        with gr.Column(scale=2, elem_id="dataset_header"):
            ui_title = gr.Markdown(t_init.get("title", ""), elem_id="app_title")

            ui_settings_acc = gr.Accordion(t_init.get("settings_title", "⚙️ Paramètres"), open=False)
            with ui_settings_acc:
                lang_radio = gr.Radio(get_available_languages(), value="FR", label="Language / Langue")
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
            
            with gr.Row():
                dir_input = gr.Textbox(placeholder="C:\\mon\\dataset, D:\\autre\\concept, ~/datasets/portrait, ...", show_label=False, scale=4, elem_id="dataset_dir_input")
                ui_browse_btn = gr.Button(t_init.get("browse", ""), scale=1)
            ui_dataset_drop_zone = gr.HTML(render_dataset_drop_zone("FR"))
            ui_load_btn = gr.Button(t_init.get("load", ""), variant="primary", elem_id="dataset_load_btn")
            ui_status_text = gr.Markdown(t_init.get("status_wait", ""), elem_id="dataset_status_text")
            
            # ⭐ Section Favoris — placée ici car il s'agit d'une méthode
            # d'importation de dataset (chargement rapide via favoris).
            _init_favs = load_favorites()
            ui_fav_section_title = gr.Accordion(t_init.get("fav_section_title", "⭐ Favoris"), open=False)
            with ui_fav_section_title:
                with gr.Row():
                    ui_fav_dropdown = gr.Dropdown(choices=_init_favs, value=(_init_favs[0] if _init_favs else None),
                                                   label=t_init.get("fav_dropdown", "Charger un favori"),
                                                   scale=3, interactive=True, allow_custom_value=False)
                with gr.Row():
                    ui_btn_add_fav = gr.Button(t_init.get("btn_add_fav", "⭐ Ajouter aux favoris"), size="sm", scale=1)
                    ui_btn_remove_fav = gr.Button(t_init.get("btn_remove_fav", "🗑️ Retirer ce favori"),
                                                    variant="stop", size="sm", scale=1)
            
        with gr.Column(scale=3, elem_id="recipe_header"):
            ui_recipe_global = gr.Markdown(t_init.get("recipe_global", ""))
            with gr.Row():
                ui_recipes_dropdown = gr.Dropdown(choices=list(load_recipes().keys()), label=t_init.get("recipes_dd", ""), scale=2)
                ui_recipe_name = gr.Textbox(label=t_init.get("recipe_name", ""), scale=1)
                ui_save_recipe_btn = gr.Button(t_init.get("save_recipe", ""), scale=1)
            with gr.Row():
                ui_btn_delete_recipe = gr.Button(t_init.get("btn_delete_recipe", "🗑️ Supprimer cette recette"),
                                                  variant="stop", size="sm")
            ui_tracked_words = gr.Textbox(show_label=False, placeholder=t_init.get("tracked_ph", ""), lines=2, elem_id="tracked_words_input")
            with gr.Row():
                ui_ai_recipe_count = gr.Number(
                    value=20, precision=0,
                    label=t_init.get("ai_recipe_count", "Nombre de mots-clés IA"),
                    scale=1,
                )
                ui_btn_ai_recipe = gr.Button(
                    t_init.get("btn_ai_recipe", "🤖 Remplir par IA"),
                    variant="secondary", size="sm", scale=2, elem_id="ai_recipe_btn",
                )
            ui_btn_analyze_recipe = gr.Button(t_init.get("btn_analyze_recipe", "📊 Lancer l'analyse des données"), variant="secondary", size="sm", elem_id="analyze_recipe_btn")

    with gr.Row(elem_id="workbench_row"):
        with gr.Column(scale=0, elem_id="left_panel") as left_panel:
            ui_gallery_title = gr.Markdown(t_init.get("gallery_title", ""))
            ui_search_box = gr.Textbox(label=t_init.get("search", ""), placeholder=t_init.get("search_ph", ""))
            ui_sort_order = gr.Radio(["A-Z", "Z-A"], value="A-Z", label=t_init.get("sort_label", "Trier / Sort"))
            
            with gr.Row():
                ui_multi_select_cb = gr.Checkbox(label=t_init.get("multi_cb", ""), value=False, interactive=True, elem_id="multi_cb", scale=2)
                ui_clear_sel_btn = gr.Button(t_init.get("clear_sel", ""), elem_id="clear_sel_btn", scale=1)
                
            ui_selection_status = gr.Markdown("**...**")
            initial_gallery_cols = int(ui_settings_init.get("gallery_columns", DEFAULT_UI_SETTINGS["gallery_columns"]))
            ui_gallery_cols = gr.Slider(minimum=1, maximum=6, step=1, value=initial_gallery_cols, label=t_init.get("cols", ""), interactive=True)
            gallery = gr.Gallery(label="Dataset", columns=initial_gallery_cols, rows=6, height=750, object_fit="contain", allow_preview=False, elem_id="main_gallery")
            
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
                    ui_viewer_status = gr.Markdown("**...**")
                    with gr.Row():
                        current_img = gr.Image(interactive=False, type="filepath", height=350, elem_id="viewer_area")
                        with gr.Column(elem_id="viewer_area_text"):
                            highlight_preview = gr.HTML()
                            word_counter = gr.HTML("<div style='color:green;'>0</div>")
                            ui_viewer_shortcuts = gr.Markdown(t_init.get("shortcuts", ""))
                            ui_toggle_tag_btn = gr.Button(t_init.get("toggle_stat", ""), variant="secondary", elem_id="toggle_tag_btn")
                    
                    current_caption = gr.Textbox(show_label=False, lines=4, elem_id="viewer_caption_area")
                    ui_live_translation_output = gr.Textbox(label=t_init.get("live_trans_label", ""), interactive=False, lines=3, elem_id="live_translation_preview")
                    
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
                    with gr.Row():
                        with gr.Column(scale=1):
                            ui_dup_title = gr.Markdown(t_init.get("dup_title", ""))
                            ui_hash_tol = gr.Slider(0, 20, 5, step=1, label=t_init.get("hash_tol", ""))
                            btn_scan_dups = gr.Button(t_init.get("btn_scan_dups", ""))
                            dup_dropdown = gr.Dropdown(label=t_init.get("dup_dd", ""), interactive=True)
                            with gr.Row():
                                dup_img_A = gr.Image(label="Image A", interactive=False, height=200)
                                dup_img_B = gr.Image(label="Image B", interactive=False, height=200)
                            with gr.Row():
                                btn_del_A = gr.Button(t_init.get("btn_del_A", ""), variant="stop")
                                btn_del_B = gr.Button(t_init.get("btn_del_B", ""), variant="stop")
                            dup_status = gr.Markdown()
                        with gr.Column(scale=1):
                            ui_rename_title = gr.Markdown(t_init.get("rename_title", ""))
                            ui_rename_prefix = gr.Textbox(label=t_init.get("rename_prefix", ""), placeholder="concept")
                            btn_rename = gr.Button(t_init.get("btn_rename", ""))
                            gr.Markdown("---")
                            ui_resize_title = gr.Markdown(t_init.get("resize_title", ""))
                            prep_size = gr.Dropdown(["512", "768", "1024", "1536"], value="1024", label=t_init.get("prep_size", ""))
                            prep_format = gr.Dropdown(["WebP", "JPEG"], value="WebP", label=t_init.get("prep_format", ""))
                            prep_crop = gr.Dropdown(["Conserver Ratio", "1:1 (Carré Centre)", "Smart Face Crop (OpenCV)"], value="Conserver Ratio", label=t_init.get("prep_crop", ""))
                            prep_alpha = gr.Checkbox(value=True, label=t_init.get("prep_alpha", ""))
                            prep_dest = gr.Textbox(label=t_init.get("prep_dest", ""), placeholder="...")
                            btn_prep = gr.Button(t_init.get("btn_prep", ""), variant="primary")
                            prep_status = gr.Markdown()

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
                            ai_action_dropdown = gr.Dropdown([
                                "Auto-Taggage / Super OCR (VLM)",
                                "Reality Check & Hallucinations (VLM)",
                                "Concept Isolator (Spécial LoRA)",
                                "Traducteur Visuel (Booru ↔ Phrase Naturelle)",
                                "Tag Sorting & Standardisation",
                                "Traduction Automatique (Vers Anglais)",
                                "✨ Prompt Personnalisé (Texte/Vision)"
                            ], label=t_init.get("ai_action_dd", ""), value="Auto-Taggage / Super OCR (VLM)")
                            ai_action_desc = gr.HTML()
                            with gr.Group(visible=False) as custom_prompt_group:
                                with gr.Row():
                                    ai_template_dd = gr.Dropdown(choices=list(load_ai_recipes().keys()), label=t_init.get("ai_tpl_dd", ""))
                                    ai_template_name = gr.Textbox(label=t_init.get("ai_tpl_name", ""))
                                    btn_save_template = gr.Button(t_init.get("btn_save_tpl", ""))
                                custom_prompt_input = gr.Textbox(label=t_init.get("custom_prompt_input", ""), placeholder="...", lines=3)
                                use_vision_for_custom = gr.Checkbox(label=t_init.get("use_vision_custom", ""))
                            with gr.Group(visible=False) as injection_group:
                                injection_mode = gr.Radio(["Remplacer tout", "Ajouter au début", "Ajouter à la fin"], label=t_init.get("injection_mode", ""), value="Remplacer tout")
                            with gr.Row():
                                btn_run_ai = gr.Button(t_init.get("btn_run_ai", ""), variant="primary")
                                btn_undo_ai = gr.Button(t_init.get("btn_undo_ai", ""), variant="stop")
                            ai_status = gr.Markdown()
                    gr.Markdown("---")
                    ui_bias_title = gr.Markdown(t_init.get("bias_title", ""))
                    btn_bias = gr.Button(t_init.get("btn_bias", ""), variant="secondary")
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
            
            ui_lib_html = gr.HTML(render_lib_html([], "FR"))

# ==========================================
# CÂBLAGE DES ÉVÉNEMENTS
# ==========================================

    lang_radio.change(
        fn=change_language, 
        inputs=[lang_radio, ui_stats_table, ui_export_config_df, lib_state],
        outputs=[
            ui_title, ui_settings_acc, ui_guide_acc, ui_guide_text, ui_dataset_drop_zone, ui_browse_btn, ui_load_btn, ui_status_text,
            ui_recipe_global, ui_recipes_dropdown, ui_recipe_name, ui_save_recipe_btn, ui_tracked_words, ui_ai_recipe_count, ui_btn_ai_recipe, ui_btn_analyze_recipe,
            ui_gallery_title, ui_search_box, ui_multi_select_cb, ui_clear_sel_btn, ui_gallery_cols,
            ui_toggle_panel_btn, ui_tab_view, ui_btn_prev, ui_btn_next, ui_viewer_shortcuts, ui_toggle_tag_btn,
            ui_live_translation_output, ui_save_single_btn,
            ui_trans_module_title, ui_trans_engine, ui_trans_source, ui_trans_target,
            ui_btn_translate_entire_caption, ui_trans_insert_title, ui_trans_input, ui_btn_insert_trans,
            ui_tab_batch, ui_btn_undo, ui_btn_clean_com, ui_btn_clean_dup, ui_preview_table,
            ui_tab_prep, ui_dup_title, ui_hash_tol, btn_scan_dups, dup_dropdown, btn_del_A, btn_del_B,
            ui_rename_title, ui_rename_prefix, btn_rename, ui_resize_title, prep_size, prep_format, prep_crop, prep_alpha, prep_dest, btn_prep,
            ui_tab_ai, ui_ai_conf_title, api_backend, vlm_model, llm_model, ui_ai_adv_acc, api_url_input, ai_temp, ai_ctx, ai_sys,
            ui_ai_act_title, ai_action_dropdown, ai_template_dd, ai_template_name, btn_save_template, custom_prompt_input, use_vision_for_custom, injection_mode, btn_run_ai, btn_undo_ai,
            ui_bias_title, btn_bias, txt_bias,
            ui_tab_export, ui_exp_edit, ui_btn_up, ui_btn_down, ui_btn_del, ui_quick_prio, ui_quick_target, ui_export_config_df, ui_strategy_radio, ui_max_img_input, ui_export_dir, ui_export_suffix, ui_btn_simul, ui_btn_exp, export_pie, ui_exp_gal,
            ui_tab_stats, ui_stats_table, ui_btn_civitai, ui_btn_top20, ui_btn_orph, ui_txt_orph, pie_chart, bar_chart,
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
        ]
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
    ui_browse_btn.click(fn=browse_folder, inputs=[], outputs=[dir_input])
    ui_hidden_dataset_path_btn.click(
        fn=set_dataset_path_from_drop,
        inputs=[ui_hidden_dataset_path_input, lang_radio],
        outputs=[dir_input, ui_status_text, ui_hidden_dataset_path_input],
    ).success(
        fn=None,
        js="function(){ const w=document.getElementById('hidden_dataset_path_input'); const v=w?.querySelector('textarea,input')?.value || ''; if(v.startsWith('__RESOLVED_PATH__')) setTimeout(()=>document.getElementById('dataset_load_btn')?.click(), 120); }",
    )
    ui_gallery_cols.change(fn=update_gallery_columns, inputs=[ui_gallery_cols], outputs=[gallery])
    ui_gallery_cols.release(fn=update_gallery_columns, inputs=[ui_gallery_cols], outputs=[gallery])

    ui_load_btn.click(fn=load_dataset, inputs=[dir_input, ui_sort_order, lang_radio], outputs=[dataset_state, filtered_state, history_state, ui_status_text, gallery, selected_indices_state, ui_selection_status, ui_hidden_sync_input, ui_hidden_tags_input, current_idx_state])
    ui_search_box.change(fn=filter_gallery, inputs=[dataset_state, ui_search_box, ui_sort_order, lang_radio], outputs=[filtered_state, gallery, selected_indices_state, ui_selection_status, ui_hidden_sync_input, current_idx_state])
    ui_sort_order.change(fn=filter_gallery, inputs=[dataset_state, ui_search_box, ui_sort_order, lang_radio], outputs=[filtered_state, gallery, selected_indices_state, ui_selection_status, ui_hidden_sync_input, current_idx_state])
    
    live_translation_inputs = [current_caption, ui_trans_engine, ui_trans_target, api_backend, api_url_input, llm_model, lang_radio, api_key_input]

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
    ui_save_single_btn.click(fn=save_single_caption, inputs=[dataset_state, filtered_state, current_idx_state, current_caption, lang_radio], outputs=[dataset_state, filtered_state, ui_single_save_status])
    ui_clear_sel_btn.click(fn=clear_selection, inputs=[lang_radio], outputs=[selected_indices_state, ui_selection_status, ui_hidden_sync_input])

    current_caption.input(
        fn=do_live_translation,
        inputs=live_translation_inputs,
        outputs=[ui_live_translation_output],
        show_progress="hidden",
        trigger_mode="always_last",
        concurrency_limit=1,
        concurrency_id="live_translation",
    )
    
    ui_btn_translate_entire_caption.click(
        fn=translate_entire_caption_action, 
        inputs=[dataset_state, filtered_state, current_idx_state, current_caption, ui_trans_engine, ui_trans_source, api_backend, api_url_input, llm_model, ui_tracked_words, lang_radio, api_key_input], 
        outputs=[dataset_state, filtered_state, current_caption, highlight_preview, word_counter, ui_single_save_status]
    ).success(
        fn=do_live_translation,
        inputs=live_translation_inputs,
        outputs=[ui_live_translation_output],
        show_progress="hidden",
    )
    ui_btn_insert_trans.click(fn=trans_insert, inputs=[ui_trans_input, current_caption, ui_trans_engine, ui_trans_source, api_backend, api_url_input, llm_model, lang_radio, api_key_input], outputs=[current_caption]).success(fn=lambda: "", outputs=[ui_trans_input]).success(
        fn=do_live_translation,
        inputs=live_translation_inputs,
        outputs=[ui_live_translation_output],
        show_progress="hidden",
    )

    js_confirm_batch = "(...args) => { if (!confirm('⚠️ Appliquer cette modification en masse sur la sélection ? / Apply this mass modification to the selection?')) throw new Error('Annulé.'); return args; }"
    js_confirm_undo = "(...args) => { if (!confirm('⚠️ Annuler la dernière action ? / Undo the last action?')) throw new Error('Annulé.'); return args; }"
    
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
    )

    js_get_sel = "function(tracker, dummy) { let sel = window.getSelection().toString().trim(); if(!sel) { let ae = document.activeElement; if(ae && (ae.tagName === 'TEXTAREA' || ae.tagName === 'INPUT')) sel = ae.value.substring(ae.selectionStart, ae.selectionEnd).trim(); } return [tracker, sel || \"\"]; }"
    ui_hidden_calc_btn.click(fn=analyze_dataset, inputs=[dataset_state, ui_tracked_words, lang_radio], outputs=[pie_chart, bar_chart, ui_stats_table, stats_df_state, ui_export_config_df, config_df_state, ui_stats_status])
    ui_tracked_words.change(fn=update_viewer, inputs=[filtered_state, current_idx_state, ui_tracked_words, lang_radio], outputs=[current_img, highlight_preview, current_caption, word_counter, current_idx_state, ui_viewer_status])
    ui_toggle_tag_btn.click(fn=toggle_tracked_word, inputs=[ui_tracked_words, dummy_selection], outputs=[ui_tracked_words], js=js_get_sel).success(fn=None, js="function(){ setTimeout(()=>document.getElementById('hidden_calc_btn')?.click(), 100); }")
    current_caption.change(fn=update_word_count, inputs=[current_caption, lang_radio], outputs=[word_counter])
    ui_recipes_dropdown.change(fn=apply_recipe, inputs=[ui_recipes_dropdown], outputs=[ui_tracked_words])
    ui_save_recipe_btn.click(fn=save_recipe, inputs=[ui_recipe_name, ui_tracked_words], outputs=[ui_recipes_dropdown, ui_status_text])
    ui_btn_ai_recipe.click(
        fn=auto_fill_recipe_from_ai,
        inputs=[dataset_state, ui_ai_recipe_count, api_backend, api_url_input, llm_model, ai_temp, ai_ctx, ai_sys, lang_radio, api_key_input],
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
    )
    ui_btn_clean_com.click(fn=batch_clean_commas, js=js_confirm_batch, inputs=[dataset_state, selected_indices_state, ui_search_box, current_idx_state, ui_tracked_words, lang_radio], outputs=[dataset_state, filtered_state, history_state, ui_batch_status, ui_preview_table, current_caption, highlight_preview, word_counter]).success(
        fn=do_live_translation,
        inputs=live_translation_inputs,
        outputs=[ui_live_translation_output],
        show_progress="hidden",
    )
    ui_btn_clean_dup.click(fn=batch_remove_duplicates, js=js_confirm_batch, inputs=[dataset_state, selected_indices_state, ui_search_box, current_idx_state, ui_tracked_words, lang_radio], outputs=[dataset_state, filtered_state, history_state, ui_batch_status, ui_preview_table, current_caption, highlight_preview, word_counter]).success(
        fn=do_live_translation,
        inputs=live_translation_inputs,
        outputs=[ui_live_translation_output],
        show_progress="hidden",
    )

    ui_export_config_df.select(fn=get_row_index, inputs=[config_df_state], outputs=[recipe_selected_row, ui_quick_prio, ui_quick_target])
    ui_quick_prio.change(fn=apply_quick_prio, inputs=[ui_quick_prio, recipe_selected_row, config_df_state], outputs=[ui_export_config_df, config_df_state, ui_tracked_words, recipe_selected_row])
    ui_quick_target.change(fn=apply_quick_target, inputs=[ui_quick_target, recipe_selected_row, config_df_state], outputs=[ui_export_config_df, config_df_state, ui_tracked_words])
    ui_btn_up.click(fn=df_move_up, inputs=[ui_export_config_df, recipe_selected_row], outputs=[ui_export_config_df, recipe_selected_row, ui_tracked_words])
    ui_btn_down.click(fn=df_move_down, inputs=[ui_export_config_df, recipe_selected_row], outputs=[ui_export_config_df, recipe_selected_row, ui_tracked_words])
    ui_btn_del.click(fn=df_delete_row, inputs=[ui_export_config_df, recipe_selected_row], outputs=[ui_export_config_df, recipe_selected_row, ui_tracked_words])
    ui_hidden_dnd_btn.click(fn=handle_drag_and_drop, inputs=[ui_hidden_dnd_input, ui_export_config_df], outputs=[ui_export_config_df, config_df_state, ui_tracked_words])
    ui_export_config_df.change(fn=handle_recipe_df_safe, inputs=[ui_export_config_df, config_df_state, ui_tracked_words], outputs=[ui_export_config_df, config_df_state, ui_tracked_words])

    ui_btn_civitai.click(fn=generate_civitai_format, inputs=[ui_stats_table], outputs=[ui_civitai_output])
    ui_btn_top20.click(fn=auto_fill_top_tags, inputs=[dataset_state], outputs=[ui_tracked_words]).success(fn=None, js="function(){ setTimeout(()=>document.getElementById('hidden_calc_btn')?.click(), 100); }")
    ui_btn_orph.click(fn=find_orphans, inputs=[dataset_state, lang_radio], outputs=[ui_txt_orph])
    ui_stats_table.change(fn=handle_stats_df_safe, inputs=[ui_stats_table, stats_df_state, ui_tracked_words], outputs=[ui_stats_table, stats_df_state, ui_tracked_words]).success(fn=None, js="function(){ setTimeout(()=>document.getElementById('hidden_calc_btn')?.click(), 100); }")
    btn_calc_adv.click(fn=update_advanced_stats, inputs=[dataset_state], outputs=[plot_heatmap, plot_bucket, txt_anti, txt_contra])

    ui_btn_simul.click(
        fn=simulate_and_clear_selection,
        inputs=[dataset_state, ui_export_dir, ui_export_suffix, ui_export_config_df, selected_indices_state, ui_strategy_radio, ui_max_img_input, lang_radio],
        outputs=[ui_export_status, export_gallery, export_pie, bar_chart, selected_indices_state, ui_selection_status, ui_hidden_sync_input],
    )
    ui_btn_exp.click(fn=simulate_and_export, inputs=[dataset_state, ui_export_dir, ui_export_suffix, ui_export_config_df, gr.State(False), selected_indices_state, ui_strategy_radio, ui_max_img_input, lang_radio], outputs=[ui_export_status, export_gallery, export_pie, bar_chart])
    btn_scan_dups.click(fn=scan_duplicates_advanced, inputs=[dataset_state, ui_hash_tol], outputs=[dup_dropdown, dup_mapping_state])
    dup_dropdown.change(fn=load_duplicate_pair, inputs=[dup_dropdown, dup_mapping_state], outputs=[dup_img_A, dup_img_B, dup_idA, dup_idB])
    btn_del_A.click(fn=delete_duplicate, inputs=[dataset_state, filtered_state, dup_idA, dup_dropdown, dup_mapping_state], outputs=[dataset_state, filtered_state, dup_dropdown, dup_mapping_state, dup_status])
    btn_del_B.click(fn=delete_duplicate, inputs=[dataset_state, filtered_state, dup_idB, dup_dropdown, dup_mapping_state], outputs=[dataset_state, filtered_state, dup_dropdown, dup_mapping_state, dup_status])
    btn_rename.click(fn=batch_rename_dataset, inputs=[dataset_state, ui_rename_prefix], outputs=[dataset_state, prep_status])
    btn_prep.click(fn=batch_process_images, inputs=[dataset_state, prep_dest, prep_size, prep_format, prep_crop, prep_alpha], outputs=[prep_status])

    ai_action_dropdown.change(fn=update_ai_action_desc, inputs=[ai_action_dropdown], outputs=[ai_action_desc, custom_prompt_group, injection_group])

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

    ai_settings_inputs = [api_backend, vlm_model, llm_model, api_url_input, api_key_input, ai_temp, ai_ctx, ai_sys]
    api_backend.change(fn=_switch_backend_url, inputs=[api_backend], outputs=[api_url_input]).success(
        fn=save_ai_settings, inputs=ai_settings_inputs, outputs=None,
    )
    for ai_setting_component in [vlm_model, llm_model, api_url_input, api_key_input, ai_temp, ai_ctx, ai_sys]:
        ai_setting_component.change(fn=save_ai_settings, inputs=ai_settings_inputs, outputs=None)
    ai_template_dd.change(fn=apply_ai_recipe, inputs=[ai_template_dd], outputs=[custom_prompt_input])
    btn_save_template.click(fn=save_ai_recipe, inputs=[ai_template_name, custom_prompt_input], outputs=[ai_template_dd])
    btn_run_ai.click(
        fn=process_ai_action,
        inputs=[
            dataset_state, selected_indices_state, ui_search_box, ai_action_dropdown,
            custom_prompt_input, injection_mode, use_vision_for_custom, vlm_model, llm_model,
            api_backend, api_url_input, ai_temp, ai_ctx, ai_sys, current_idx_state,
            ui_tracked_words, lang_radio, api_key_input,
        ],
        outputs=[dataset_state, filtered_state, history_state, ai_status, ui_hidden_tags_input, current_caption, highlight_preview, word_counter],
    )
    btn_bias.click(
        fn=analyze_bias,
        inputs=[dataset_state, llm_model, api_backend, api_url_input, ai_temp, ai_ctx, ai_sys, lang_radio, api_key_input],
        outputs=[txt_bias],
    )

    # 🎯 LM Studio : Rafraîchissement et chargement
    ui_lm_studio_list_btn.click(
        fn=refresh_lm_studio_models,
        inputs=[api_url_input, lang_radio],
        outputs=[ui_lm_studio_vlm_dd, ui_lm_studio_llm_dd, ui_lm_studio_shared_dd, ui_lm_studio_status],
    )
    lm_studio_choice_inputs = [
        ui_lm_studio_vlm_dd, ui_lm_studio_llm_dd, ui_lm_studio_shared_dd,
        api_backend, api_url_input, api_key_input, ai_temp, ai_ctx, ai_sys, lang_radio,
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
    ui_fav_dropdown.change(fn=pick_favorite, inputs=[ui_fav_dropdown, lang_radio], outputs=[dir_input])

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

    app.load(fn=lambda: None, inputs=None, outputs=None, js=custom_js)

if __name__ == "__main__":
    launch_kwargs = {
        "inbrowser": True,
        "server_name": "127.0.0.1",
        "allowed_paths": get_gradio_allowed_paths(),
    }
    if get_gradio_major_version() >= 6:
        launch_kwargs["css"] = css_code
    try:
        app.launch(**launch_kwargs)
    except TypeError:
        launch_kwargs.pop("css", None)
        try:
            app.launch(**launch_kwargs)
        except TypeError:
            launch_kwargs.pop("allowed_paths", None)
            app.launch(**launch_kwargs)
