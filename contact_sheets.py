"""Contact sheet generation and preview for IMG Dataset Refiner.

Moved from lora_manager.py to keep the main module focused on UI and
event handlers.  This module is self-contained: it only needs PIL for
image composition and the UI_T dictionary from i18n.py for labels.
"""

import os
import io
import math

try:
    import gradio as gr
except ImportError:
    gr = None

from PIL import Image, ImageDraw, ImageFont

from i18n import UI_T

CONTACT_SHEET_PREVIEW_IMAGE_CACHE = {}
CONTACT_SHEET_PREVIEW_IMAGE_CACHE_MAX = 160
CONTACT_SHEET_DEFAULTS = {
    "source_mode": "Galerie filtrée",
    "output_width": 3048,
    "images_per_row": 8,
    "spacing": 16,
    "margin": 0,
    "background": "#00ff00",
    "ratio": "Hauteur variable (Original)",
    "fit_mode": "Ajuster avec bandes (Pad)",
    "sort_alpha": False,
    "label_mode": "Numérotation (1, 2, 3...)",
    "font_size": 70,
    "label_opacity": 70,
    "limit_enabled": True,
    "images_per_sheet": 35,
    "continue_numbering": True,
    "output_dir": "",
    "filename_prefix": "Planche_compilee",
    "export_format": "JPEG",
    "quality": 95,
}
CONTACT_SHEET_SOURCE_CHOICES = ["Galerie filtrée", "Sélection multi"]
CONTACT_SHEET_RATIO_CHOICES = [
    "Hauteur variable (Original)",
    "Carré (1:1)",
    "Paysage (4:3)",
    "Paysage (16:9)",
    "Portrait (3:4)",
    "Portrait (9:16)",
]
CONTACT_SHEET_FIT_CHOICES = ["Remplir et Couper (Crop)", "Ajuster avec bandes (Pad)"]
CONTACT_SHEET_LABEL_CHOICES = ["Aucun", "Numérotation (1, 2, 3...)", "Nom du fichier", "Captions (1ère ligne)"]
CONTACT_SHEET_FORMAT_CHOICES = ["JPEG", "PNG", "WEBP"]
CONTACT_SHEET_RATIO_MODE_CHOICES = ["Original (mélange)", "Tous carrés 1:1", "Auto-fit (remplir)"]

def _safe_int(value, default, min_value=None, max_value=None):
    try:
        value = int(float(value))
    except Exception:
        value = default
    if min_value is not None:
        value = max(min_value, value)
    if max_value is not None:
        value = min(max_value, value)
    return value

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

def _contact_sheet_display_name(item):
    name = str(item.get("display_name") or item.get("rel_path") or item.get("img_name") or "")
    return os.path.splitext(os.path.basename(name.replace("\\", "/")))[0]

def _contact_sheet_sort_name(item):
    return str(item.get("sort_name") or item.get("rel_path") or item.get("display_name") or item.get("img_name") or "")

def _contact_sheet_source_items(filtered_dataset, selected_ids, source_mode, ignore_gallery_sort):
    """
    Récupère les items à compiler.
    - Respecte l'ordre de filtered_dataset (trié par galerie) par défaut
    - Si ignore_gallery_sort=True : applique un tri alphabétique local
    """
    items = list(filtered_dataset or [])
    if source_mode == "Sélection multi":
        selected = {int(x) for x in (selected_ids or []) if str(x).strip().lstrip("-").isdigit()}
        items = [item for item in items if int(item.get("id", -1)) in selected]
    if ignore_gallery_sort:
        # Forcer un tri local alphabétique, ignorant le tri de la galerie
        items = sorted(items, key=lambda item: natural_sort_key(_contact_sheet_sort_name(item)))
    return items

def _contact_sheet_batches(items, settings):
    if settings.get("limit_enabled"):
        per_sheet = max(1, int(settings.get("images_per_sheet") or 1))
        return [items[i:i + per_sheet] for i in range(0, len(items), per_sheet)]
    return [items] if items else []

def _contact_sheet_preview_cache_key(path, bg_rgb, preview_thumb_size):
    try:
        stat = os.stat(path)
        return (os.path.abspath(path), stat.st_mtime_ns, stat.st_size, tuple(bg_rgb), int(preview_thumb_size))
    except Exception:
        return None

def _remember_contact_sheet_preview(key, image):
    if not key:
        return
    CONTACT_SHEET_PREVIEW_IMAGE_CACHE[key] = image.copy()
    while len(CONTACT_SHEET_PREVIEW_IMAGE_CACHE) > CONTACT_SHEET_PREVIEW_IMAGE_CACHE_MAX:
        CONTACT_SHEET_PREVIEW_IMAGE_CACHE.pop(next(iter(CONTACT_SHEET_PREVIEW_IMAGE_CACHE)), None)

def _load_contact_sheet_image(path, bg_rgb, fast_preview=False, preview_thumb_size=900):
    preview_thumb_size = max(160, int(preview_thumb_size or 900))
    cache_key = _contact_sheet_preview_cache_key(path, bg_rgb, preview_thumb_size) if fast_preview else None
    if cache_key and cache_key in CONTACT_SHEET_PREVIEW_IMAGE_CACHE:
        return CONTACT_SHEET_PREVIEW_IMAGE_CACHE[cache_key].copy()

    img = Image.open(path)
    if fast_preview:
        img.thumbnail((preview_thumb_size, preview_thumb_size), Image.Resampling.NEAREST)
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        base = Image.new("RGB", img.size, bg_rgb)
        base.paste(img, (0, 0), img.convert("RGBA"))
        _remember_contact_sheet_preview(cache_key, base)
        return base
    converted = img.convert("RGB")
    _remember_contact_sheet_preview(cache_key, converted)
    return converted

def generate_contact_sheet_pil(items, settings, fast_preview=False, start_number=1, preview_max_width=1200, preview_thumb_size=900):
    bg_rgb = _hex_to_rgb(settings.get("background", "#00ff00"))
    output_width = int(settings["output_width"])
    spacing = int(settings["spacing"])
    margin = int(settings["margin"])
    cols = max(1, int(settings["images_per_row"]))
    font_size = int(settings["font_size"])

    if fast_preview and output_width > preview_max_width:
        preview_max_width = max(320, int(preview_max_width or 1200))
        scale_preview = preview_max_width / float(output_width)
        output_width = preview_max_width
        spacing = max(0, int(spacing * scale_preview))
        margin = max(0, int(margin * scale_preview))
        font_size = max(8, int(font_size * scale_preview))

    valid = []
    for item in items:
        path = item.get("img_path")
        if not path or not os.path.exists(path):
            continue
        try:
            # Stocker l'item complet (permet accès à caption, name, id, etc.)
            valid.append((_load_contact_sheet_image(path, bg_rgb, fast_preview, preview_thumb_size), item))
        except Exception as e:
            print(f"⚠️ Planche: impossible de charger {path}: {e}")
    if not valid:
        err = Image.new("RGB", (max(320, output_width), 220), bg_rgb)
        ImageDraw.Draw(err).text((20, 20), "Aucune image valide à afficher", fill=(255, 255, 255))
        return err

    available_width = output_width - (2 * margin) - ((cols - 1) * spacing)
    col_width = max(10, available_width // cols)
    ratio = settings["ratio"]
    fit_mode = settings["fit_mode"]
    is_variable = "variable" in ratio.lower()
    resample = Image.Resampling.BILINEAR if fast_preview else Image.Resampling.LANCZOS
    target_h = col_width
    if not is_variable:
        if "1:1" in ratio:
            target_h = col_width
        elif "4:3" in ratio:
            target_h = int(col_width * 3 / 4)
        elif "16:9" in ratio:
            target_h = int(col_width * 9 / 16)
        elif "3:4" in ratio:
            target_h = int(col_width * 4 / 3)
        elif "9:16" in ratio:
            target_h = int(col_width * 16 / 9)

    thumbs = []
    for img, item in valid:
        if is_variable:
            ratio_scale = col_width / float(max(1, img.width))
            thumb_h = max(1, int(img.height * ratio_scale))
            thumb = img.resize((col_width, thumb_h), resample)
        elif "Crop" in fit_mode:
            thumb = ImageOps.fit(img, (col_width, target_h), resample)
        else:
            thumb = ImageOps.pad(img, (col_width, target_h), method=resample, color=bg_rgb)
        thumbs.append((thumb, item))

    rows = math.ceil(len(thumbs) / cols)
    placements = []
    if is_variable:
        row_heights = []
        for row in range(rows):
            row_thumbs = thumbs[row * cols:(row + 1) * cols]
            row_heights.append(max((thumb.height for thumb, _ in row_thumbs), default=1))
        final_height = (2 * margin) + sum(row_heights) + max(0, rows - 1) * spacing
        for index, (thumb, item) in enumerate(thumbs):
            row = index // cols
            col = index % cols
            x = margin + col * (col_width + spacing)
            y_base = margin + sum(row_heights[:row]) + row * spacing
            y = y_base + (row_heights[row] - thumb.height) // 2
            placements.append((x, y, thumb, item))
    else:
        final_height = (2 * margin) + (rows * target_h) + max(0, rows - 1) * spacing
        for index, (thumb, item) in enumerate(thumbs):
            row = index // cols
            col = index % cols
            x = margin + col * (col_width + spacing)
            y = margin + row * (target_h + spacing)
            placements.append((x, y, thumb, item))

    sheet = Image.new("RGB", (output_width, max(1, final_height)), bg_rgb)
    for x, y, thumb, _ in placements:
        sheet.paste(thumb, (x, y))

    label_mode = settings["label_mode"]
    if label_mode != "Aucun":
        overlay = Image.new("RGBA", sheet.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        except IOError:
            font = ImageFont.load_default()
        alpha_bg = int((_safe_float(settings.get("label_opacity"), 70, 0, 100) / 100.0) * 255)
        for x, y, _, item in placements:
            item_id = int(item.get("id", -1))
            # Choisir le texte du label selon le mode
            if "Numérotation" in label_mode:
                text = str(item_id + 1)
            elif "Captions" in label_mode:
                # Première ligne du caption
                caption = item.get("caption", "").strip()
                text = caption.split('\n')[0][:60] if caption else ""  # Max 60 chars
            else:
                # Nom du fichier (par défaut)
                text = _contact_sheet_display_name(item)
            if not text:
                continue
            tx = x + max(5, col_width // 40)
            ty = y + max(5, col_width // 40)
            try:
                bbox = draw.textbbox((tx, ty), text, font=font)
                draw.rectangle([bbox[0] - 4, bbox[1] - 2, bbox[2] + 4, bbox[3] + 2], fill=(0, 0, 0, alpha_bg))
            except Exception:
                pass
            draw.text((tx, ty), text, fill=(255, 255, 255, 255), font=font)
        sheet = Image.alpha_composite(sheet.convert("RGBA"), overlay).convert("RGB")

    # Appliquer le resize final si spécifié
    resize_percent = int(settings.get("resize_final", 100))
    if resize_percent != 100:
        new_width = max(256, int(sheet.width * resize_percent / 100))
        new_height = int(sheet.height * resize_percent / 100)
        sheet = sheet.resize((new_width, new_height), Image.Resampling.LANCZOS)

    return sheet

def _contact_sheet_status_text(items, batches, settings, preview=False, lang="FR"):
    t = UI_T.get(lang, UI_T.get("FR", {}))
    mode = t.get("contact_status_mode_preview", "aperçu") if preview else t.get("contact_status_mode_export", "export")
    per_sheet = settings.get("images_per_sheet") if settings.get("limit_enabled") else len(items)
    template = t.get("contact_status_summary", "✅ {items} image(s) · {sheets} planche(s) · {per_sheet} image(s)/planche · {per_row} par ligne · mode {mode}.")
    return template.format(
        items=len(items),
        sheets=len(batches),
        per_sheet=per_sheet,
        per_row=settings["images_per_row"],
        mode=mode,
    )

def preview_contact_sheets(filtered_dataset, selected_ids, *values):
    values, lang = _contact_sheet_values_and_lang(values)
    t = UI_T.get(lang, UI_T.get("FR", {}))
    settings = _contact_sheet_settings_from_inputs(*values)
    items = _contact_sheet_source_items(filtered_dataset, selected_ids, settings["source_mode"], settings["sort_alpha"])
    if not items:
        return [], t.get("contact_status_no_images", "⚠️ Aucune image à compiler. Vérifie la galerie filtrée ou la sélection multi.")
    batches = _contact_sheet_batches(items, settings)
    previews = []
    offset = 0
    for batch in batches:
        start = offset + 1 if settings["continue_numbering"] else 1
        previews.append(generate_contact_sheet_pil(batch, settings, fast_preview=True, start_number=start))
        offset += len(batch)
    return previews, _contact_sheet_status_text(items, batches, settings, preview=True, lang=lang)

def preview_contact_sheet_live(filtered_dataset, selected_ids, *values):
    """Aperçu live : génère juste la 1ère planche pour vérifier la mise en forme."""
    values, lang = _contact_sheet_values_and_lang(values)
    t = UI_T.get(lang, UI_T.get("FR", {}))
    settings = _contact_sheet_settings_from_inputs(*values)
    items = _contact_sheet_source_items(filtered_dataset, selected_ids, settings["source_mode"], settings["sort_alpha"])
    if not items:
        return [], t.get("contact_status_no_images", "⚠️ Aucune image à compiler. Vérifie la galerie filtrée ou la sélection multi.")
    # Générer juste la 1ère planche (ou premier batch)
    batches = _contact_sheet_batches(items, settings)
    if batches:
        preview = generate_contact_sheet_pil(
            batches[0],
            settings,
            fast_preview=True,
            start_number=1,
            preview_max_width=900,
            preview_thumb_size=640,
        )
        status = t.get("contact_status_live", "✅ Aperçu live : {images} images · {sheets} planche(s) au total. Clic 'Générer l'aperçu' pour voir toutes.").format(images=len(batches[0]), sheets=len(batches))
        return [preview], status
    return [], t.get("contact_status_empty", "⚠️ Aucune image à compiler.")

def export_contact_sheets(filtered_dataset, selected_ids, dataset_dir, *values):
    values, lang = _contact_sheet_values_and_lang(values)
    t = UI_T.get(lang, UI_T.get("FR", {}))
    settings = _contact_sheet_settings_from_inputs(*values)
    items = _contact_sheet_source_items(filtered_dataset, selected_ids, settings["source_mode"], settings["sort_alpha"])
    if not items:
        return [], t.get("contact_status_no_export", "⚠️ Aucune image à exporter. Vérifie la galerie filtrée ou la sélection multi.")
    batches = _contact_sheet_batches(items, settings)
    dataset_dir = normalize_dataset_path(dataset_dir)
    output_dir = settings["output_dir"]
    if not output_dir:
        output_dir = os.path.join(dataset_dir, "planches_compilation") if dataset_dir else os.path.join(APP_DIR, "planches_compilation")
    output_dir = normalize_dataset_path(output_dir, allow_file_parent=False) or output_dir
    os.makedirs(output_dir, exist_ok=True)
    fmt = settings["export_format"].upper()
    ext = ".jpg" if fmt == "JPEG" else (".webp" if fmt == "WEBP" else ".png")
    save_format = "JPEG" if fmt == "JPEG" else ("WEBP" if fmt == "WEBP" else "PNG")
    paths = []
    offset = 0
    for page_idx, batch in enumerate(batches, start=1):
        start = offset + 1 if settings["continue_numbering"] else 1
        sheet = generate_contact_sheet_pil(batch, settings, fast_preview=False, start_number=start)
        path = os.path.join(output_dir, f"{settings['filename_prefix']}_{page_idx}{ext}")
        if save_format in ("JPEG", "WEBP"):
            sheet.save(path, save_format, quality=int(settings["quality"]), optimize=True)
        else:
            sheet.save(path, save_format)
        paths.append(path)
        offset += len(batch)
    msg = t.get("contact_status_exported", "✅ {count} planche(s) exportée(s) dans : {output_dir}").format(count=len(paths), output_dir=output_dir)
    gr.Info(msg)
    return paths, msg

