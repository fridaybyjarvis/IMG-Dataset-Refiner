"""Internationalization helpers for IMG Dataset Refiner.

Loads and manages UI language dictionaries (MSG / UI_T) from
languages/*.json and provides import helpers for new languages.
"""

import os
import json
import shutil

try:
    import gradio as gr
except ImportError:
    gr = None

APP_DIR = os.path.dirname(os.path.abspath(__file__))
LANGUAGES_DIR = os.path.join(APP_DIR, "languages")

# Global language dictionaries populated by load_languages().
# Keys are uppercase ISO codes ("FR", "EN", ...); values are dicts
# with keys "MSG" and "UI_T".
MSG = {"FR": {}, "EN": {}}
UI_T = {"FR": {}, "EN": {}}


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


def get_available_languages():
    """Renvoie les codes de langue disponibles (au moins FR et EN)."""
    return sorted(set(["FR", "EN"]) | set(MSG.keys()))


def import_language_file(uploaded_file, lang="FR"):
    """Importe un fichier JSON de langue dans le dossier languages/.
    Le fichier doit contenir MSG et UI_T comme fr.json."""
    m = MSG.get(lang, MSG.get("FR", {}))
    if not uploaded_file:
        return "⚠️ Aucun fichier sélectionné."
    try:
        src_path = uploaded_file.name if hasattr(uploaded_file, "name") else str(uploaded_file)
        with open(src_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if "MSG" not in data or "UI_T" not in data:
            return "❌ Le fichier doit contenir les clés 'MSG' et 'UI_T'."
        os.makedirs(LANGUAGES_DIR, exist_ok=True)
        base_name = os.path.basename(src_path).lower()
        if not base_name.endswith(".json"):
            base_name += ".json"
        dest_path = os.path.join(LANGUAGES_DIR, base_name)
        shutil.copy2(src_path, dest_path)
        lang_code = os.path.splitext(base_name)[0].upper()
        load_languages()
        msg = m.get("lang_imported", "✅ Langue '{name}' importée avec succès. Redémarrez l'application pour la voir.").format(name=lang_code)
        if gr is not None:
            gr.Info(msg)
        return msg
    except json.JSONDecodeError:
        return "❌ Fichier JSON invalide."
    except Exception as e:
        return f"❌ Erreur d'import : {e}"


# Populate dictionaries on first import so MSG/UI_T are ready before
# the main module's UI build runs.
load_languages()