import gradio as gr
import os
import re
import shutil
import json
import copy
import plotly.express as px
import pandas as pd
from collections import Counter

# ==========================================
# CONFIGURATION & DICTIONNAIRES DE LANGUE
# ==========================================

RECIPES_FILE = "lora_recipes.json"

# Dictionnaires vides qui seront remplis au lancement
MSG = {"FR": {}, "EN": {}}
UI_T = {"FR": {}, "EN": {}}

def load_languages():
    """Charge les textes depuis les fichiers JSON externes."""
    for lang in ["FR", "EN"]:
        filepath = f"{lang.lower()}.json"
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                MSG[lang] = data.get("MSG", {})
                UI_T[lang] = data.get("UI_T", {})
        else:
            print(f"⚠️ Erreur critique: Fichier de langue '{filepath}' introuvable.")
            print(f"Veuillez vous assurer que 'fr.json' et 'en.json' sont dans le même dossier que le script.")

# Appel immédiat pour charger les langues avant de construire l'interface
load_languages()

# Injection JS pour le fonctionnement du Dark mode, des raccourcis et de la sélection visuelle
head_html = """
<script>
document.addEventListener('DOMContentLoaded', function() {
    document.body.classList.add('dark');
    
    window.addEventListener('keydown', function(e) {
        const tag = e.target.tagName.toLowerCase();
        if (e.altKey && e.key.toLowerCase() === 's') {
            e.preventDefault(); e.stopPropagation();
            const btn = document.getElementById('toggle_tag_btn');
            if(btn) btn.click();
            return;
        }
        if (tag === 'input' || tag === 'textarea') return;
        if (e.key === 'ArrowLeft') { document.getElementById('prev_btn')?.click(); }
        if (e.key === 'ArrowRight') { document.getElementById('next_btn')?.click(); }
    }, true); 

    const observer = new MutationObserver(() => {
        const galleryBtns = document.querySelectorAll('#main_gallery button');
        galleryBtns.forEach(btn => {
            const label = btn.querySelector('.caption-label');
            const img = btn.querySelector('img');
            
            if (label && (label.innerText.includes('✅') || label.innerText.includes('SELECTED'))) {
                btn.style.outline = '4px solid #ff8800';
                btn.style.outlineOffset = '-4px';
                btn.style.boxShadow = 'inset 0 0 20px rgba(255, 136, 0, 0.9)';
                btn.style.borderRadius = '8px';
                if (img) { img.style.filter = 'sepia(0.8) hue-rotate(330deg) saturate(3)'; img.style.opacity = '0.8'; }
            } else {
                btn.style.outline = 'none'; btn.style.boxShadow = 'none';
                if (img) { img.style.filter = 'none'; img.style.opacity = '1'; }
            }
        });
    });
    observer.observe(document.body, { childList: true, subtree: true });
});

function getSelectedText(tracker, dummy) {
    let sel = window.getSelection().toString().trim();
    if (!sel) {
        let activeEl = document.activeElement;
        if (activeEl && (activeEl.tagName === 'TEXTAREA' || activeEl.tagName === 'INPUT')) {
            sel = activeEl.value.substring(activeEl.selectionStart, activeEl.selectionEnd).trim();
        }
    }
    if(!sel) return [tracker, ""];
    return [tracker, sel];
}

function toggleGallery() {
    const panel = document.getElementById('left_panel');
    const btn = document.getElementById('toggle_gallery_btn');
    const isFR = btn.innerText.includes('Galerie');
    if (panel.classList.contains('collapsed')) {
        panel.classList.remove('collapsed');
        btn.innerText = isFR ? "◀ Masquer la Galerie" : "◀ Hide Gallery";
    } else {
        panel.classList.add('collapsed');
        btn.innerText = isFR ? "▶ Afficher la Galerie" : "▶ Show Gallery";
    }
    return [];
}

function confirmAction() {
    if (!confirm('⚠️ Appliquer cette modification ? / Apply this modification?')) throw new Error('Annulé. / Cancelled.');
}
</script>

<style>
    #left_panel {
        resize: horizontal; overflow-x: hidden; overflow-y: auto; width: 380px; min-width: 250px; max-width: 70vw;
        flex: none !important; border-right: 2px solid #374151; padding-right: 15px;
        transition: min-width 0.3s ease, width 0.3s ease, padding 0.3s ease, opacity 0.3s ease;
    }
    #left_panel.collapsed { width: 0px !important; min-width: 0px !important; padding: 0px !important; margin: 0px !important; border: none !important; opacity: 0; pointer-events: none; }
    .caption-label { font-size: 14px !important; font-weight: bold !important; color: #4ade80 !important; }
</style>
"""

# ==========================================
# FONCTIONS LOGIQUES 
# ==========================================

def get_gallery_items(filtered_dataset, selected_ids, lang):
    return [(item['img_path'], MSG[lang]["selected_tag"] if item['id'] in selected_ids else "") for item in filtered_dataset]

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

def load_dataset(directory, lang):
    if not os.path.isdir(directory): return [], [], [], MSG[lang]["folder_not_found"], [], [], MSG[lang]["no_sel_all"]
    dataset = []
    valid_extensions = ('.png', '.jpg', '.jpeg', '.webp')
    idx = 0
    for filename in sorted(os.listdir(directory)):
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
            
    gal_items = get_gallery_items(dataset, [], lang)
    return dataset, dataset, [], MSG[lang]["images_loaded"].format(count=len(dataset)), gal_items, [], MSG[lang]["no_sel_all"]

def filter_gallery(dataset, search_text, selected_ids, lang):
    if not dataset: return [], []
    if not search_text: return dataset, get_gallery_items(dataset, selected_ids, lang)
    filtered = [item for item in dataset if search_text.lower() in item['caption'].lower()]
    return filtered, get_gallery_items(filtered, selected_ids, lang)

def get_highlighted_html(caption, tracked_words_str):
    if not caption: return "<div style='padding:10px; background:var(--bg-color); border-radius:5px;'></div>"
    html_caption = caption
    if tracked_words_str:
        tracked_words = [w.split(':')[0].strip() for w in tracked_words_str.split(',') if w.strip()]
        for word in tracked_words:
            pattern = re.compile(r'(\b' + re.escape(word) + r'\b)', re.IGNORECASE)
            html_caption = pattern.sub(r'<mark style="background-color: #ffcc00; color: #000; font-weight: bold; padding: 2px 4px; border-radius: 4px; box-shadow: 0 0 5px rgba(255, 204, 0, 0.5);">\1</mark>', html_caption)
    return f"<div style='padding:15px; border:1px solid #555; background-color: #222; border-radius:8px; line-height:1.6; font-size:1.1em;'>{html_caption}</div>"

def update_word_count(text, lang):
    if not text: return MSG[lang]["0_words"]
    words = len(text.split())
    tokens = int(words * 1.3)
    color = "#ff4444" if tokens > 225 else "#44ff44"
    warning = MSG[lang]["truncation_risk"] if tokens > 225 else ""
    return f"<div style='color:{color}; font-weight:bold;'>{words} {MSG[lang]['word_count']} (~{tokens} {MSG[lang]['token_count']}){warning}</div>"

def update_viewer(filtered_dataset, idx, tracked_words, lang):
    if not filtered_dataset or idx < 0 or idx >= len(filtered_dataset): return None, "", "", MSG[lang]["0_words"], 0, MSG[lang]["no_img_sel"]
    item = filtered_dataset[idx]
    return item['img_path'], get_highlighted_html(item['caption'], tracked_words), item['caption'], update_word_count(item['caption'], lang), idx, MSG[lang]["viewing_img"].format(name=item['img_name'])

def gallery_click(evt: gr.SelectData, filtered_dataset, selected_indices, multi_mode, tracked_words, lang):
    idx = evt.index
    item = filtered_dataset[idx]
    real_id = item['id']
    if multi_mode:
        if real_id in selected_indices: selected_indices.remove(real_id)
        else: selected_indices.append(real_id)
    else: selected_indices = [real_id]
    
    sel_text = MSG[lang]["selected_multi"].format(count=len(selected_indices)) if selected_indices else MSG[lang]["no_sel_batch"]
    gal_items = get_gallery_items(filtered_dataset, selected_indices, lang)
    
    return item['img_path'], get_highlighted_html(item['caption'], tracked_words), item['caption'], update_word_count(item['caption'], lang), idx, MSG[lang]["viewing_img"].format(name=item['img_name']), selected_indices, sel_text, gal_items

def nav_prev(filtered_dataset, idx, tracked_words, lang):
    if not filtered_dataset: return None, "", "", MSG[lang]["0_words"], 0, ""
    idx = (idx - 1) % len(filtered_dataset)
    return update_viewer(filtered_dataset, idx, tracked_words, lang)

def nav_next(filtered_dataset, idx, tracked_words, lang):
    if not filtered_dataset: return None, "", "", MSG[lang]["0_words"], 0, ""
    idx = (idx + 1) % len(filtered_dataset)
    return update_viewer(filtered_dataset, idx, tracked_words, lang)

def save_single_caption(dataset, filtered_dataset, idx, new_caption, lang):
    if not filtered_dataset or idx < 0 or idx >= len(filtered_dataset): return dataset, filtered_dataset, MSG[lang]["error"]
    item_filtered = filtered_dataset[idx]
    real_id = item_filtered['id']
    if os.path.exists(item_filtered['txt_path']): shutil.copy2(item_filtered['txt_path'], item_filtered['txt_path'] + ".bak")
    item_filtered['caption'] = new_caption
    dataset[real_id]['caption'] = new_caption
    with open(item_filtered['txt_path'], 'w', encoding='utf-8') as f: f.write(new_caption)
    return dataset, filtered_dataset, MSG[lang]["saved"].format(name=item_filtered['img_name'])

def clear_selection(filtered_dataset, lang): 
    return [], MSG[lang]["no_sel_all"], get_gallery_items(filtered_dataset, [], lang)

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

def analyze_dataset(dataset, tracked_words_str, lang):
    if not dataset: return None, None, pd.DataFrame(), pd.DataFrame(), MSG[lang]["no_dataset"]
    if not tracked_words_str: 
        return None, None, pd.DataFrame([{MSG[lang]["df_kw"]: "", MSG[lang]["df_tgt"]: ""}]), pd.DataFrame([{MSG[lang]["df_prio"]: 1, MSG[lang]["df_kw"]: "", MSG[lang]["df_tgt"]: 0}]), MSG[lang]["enter_keywords"]
    
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
        row = {MSG[lang]["df_kw"]: word, "Count" if lang=="EN" else "Compte": count, "Current %" if lang=="EN" else "Actuel %": f"{pct:.1f}%"}
        if word in targets:
            row[MSG[lang]["df_tgt"]] = f"{targets[word]}%"
            row["Diff" if lang=="EN" else "Écart"] = f"{'+' if (pct - targets[word])>0 else ''}{pct - targets[word]:.1f}%"
        else:
            row[MSG[lang]["df_tgt"]] = "-"; row["Diff" if lang=="EN" else "Écart"] = "-"
        df_stats.append(row)
        
    df = pd.DataFrame(df_stats).sort_values(by="Count" if lang=="EN" else "Compte", ascending=False)
    
    df_config = []
    for i, word in enumerate(stats.keys()):
        cible = targets.get(word, 0)
        df_config.append({MSG[lang]["df_prio"]: i+1, MSG[lang]["df_kw"]: word, MSG[lang]["df_tgt"]: cible})
    df_conf = pd.DataFrame(df_config)

    pie_data = {k: v for k, v in stats.items() if v > 0}
    if not pie_data:
        fig_pie = px.pie(names=[MSG[lang]["none"]], values=[1], title=MSG[lang]["no_tag_found"])
        fig_bar = px.bar(x=[MSG[lang]["none"]], y=[0], title=MSG[lang]["no_tag_found"])
    else:
        fig_pie = px.pie(names=list(pie_data.keys()), values=list(pie_data.values()), title=MSG[lang]["overall_dist"])
        fig_pie.update_traces(textposition='inside', textinfo='percent+label')
        fig_bar = px.bar(x=list(pie_data.keys()), y=list(pie_data.values()), title=MSG[lang]["occ_by_keyword"])
    
    return fig_pie, fig_bar, df, df_conf, MSG[lang]["stats_updated"]

def find_orphans(dataset, lang):
    if not dataset: return MSG[lang]["no_dataset"]
    all_words = []
    for item in dataset:
        tags = [t.strip().lower() for t in item['caption'].split(',')]
        all_words.extend(tags)
    counts = Counter(all_words)
    orphans = [tag for tag, count in counts.items() if count == 1 and len(tag) > 2]
    if not orphans: return MSG[lang]["no_orphans"]
    return MSG[lang]["unique_tags"] + ", ".join(sorted(orphans))

def auto_fill_top_tags(dataset):
    if not dataset: return ""
    all_words = []
    for item in dataset:
        tags = [t.strip().lower() for t in item['caption'].split(',')]
        all_words.extend([t for t in tags if t])
    counts = Counter(all_words)
    return ", ".join([tag for tag, count in counts.most_common(20)])

def load_recipes():
    if os.path.exists(RECIPES_FILE):
        with open(RECIPES_FILE, 'r') as f: return json.load(f)
    return {"Default": "1girl, solo, looking at viewer"}

def save_recipe(name, words):
    if not name: return gr.update(), "Empty name"
    recipes = load_recipes()
    recipes[name] = words
    with open(RECIPES_FILE, 'w') as f: json.dump(recipes, f)
    return gr.update(choices=list(recipes.keys()), value=name), "✅ Saved"

def apply_recipe(name): return load_recipes().get(name, "")

# BATCH FUNCTIONS
def save_all_captions(dataset):
    for item in dataset:
        with open(item['txt_path'], 'w', encoding='utf-8') as f: f.write(item['caption'])

def undo_last_action(dataset, history, lang):
    if not history: return dataset, dataset, MSG[lang]["nothing_to_undo"]
    dataset = copy.deepcopy(history)
    save_all_captions(dataset)
    return dataset, dataset, MSG[lang]["undo_success"]

def create_preview_df(old_dataset, new_dataset, lang):
    changes = []
    for old, new in zip(old_dataset, new_dataset):
        if old['caption'] != new['caption']:
            changes.append({"File" if lang=="EN" else "Fichier": old['img_name'], "Avant" if lang=="FR" else "Before": old['caption'], "Après" if lang=="FR" else "After": new['caption']})
            if len(changes) >= 10: break
    if not changes: return pd.DataFrame([{"Message": MSG[lang]["no_changes"]}])
    return pd.DataFrame(changes)

def batch_add(dataset, text, pos, selected_ids, lang):
    if not text: return dataset, dataset, dataset, MSG[lang]["text_empty"], pd.DataFrame()
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
    return dataset, dataset, history, MSG[lang]["added_to"].format(count=count), create_preview_df(history, dataset, lang)

def batch_replace(dataset, old_text, new_text, use_regex, selected_ids, lang):
    history = copy.deepcopy(dataset)
    count = 0
    for item in dataset:
        if selected_ids and item['id'] not in selected_ids: continue
        if use_regex:
            try:
                new_cap = re.sub(old_text, new_text, item['caption'])
                if new_cap != item['caption']: item['caption'] = new_cap; count += 1
            except: return dataset, dataset, history, MSG[lang]["regex_error"], pd.DataFrame()
        else:
            if old_text in item['caption']: item['caption'] = item['caption'].replace(old_text, new_text); count += 1
    save_all_captions(dataset)
    return dataset, dataset, history, MSG[lang]["replaced_in"].format(count=count), create_preview_df(history, dataset, lang)

def batch_clean_commas(dataset, selected_ids, lang):
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
    return dataset, dataset, history, MSG[lang]["cleaned_in"].format(count=count), create_preview_df(history, dataset, lang)

def batch_remove_duplicates(dataset, selected_ids, lang):
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
    return dataset, dataset, history, MSG[lang]["dups_removed"].format(count=count), create_preview_df(history, dataset, lang)

def batch_synonyms(dataset, target_tag, synonyms_str, selected_ids, lang):
    if not target_tag: return dataset, dataset, dataset, MSG[lang]["target_empty"], pd.DataFrame()
    history = copy.deepcopy(dataset)
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
    return dataset, dataset, history, MSG[lang]["synonyms_replaced"].format(count=count), create_preview_df(history, dataset, lang)

def simulate_and_export(dataset, export_dir, config_df, is_simulation, selected_ids, strategy, max_images, filtered_dataset, lang):
    if not dataset: 
        return MSG[lang]["no_dataset"], [], None, None, selected_ids, get_gallery_items(filtered_dataset, selected_ids, lang)
        
    if config_df is None or config_df.empty: 
        config_df = pd.DataFrame([{MSG[lang]["df_prio"]: 1, MSG[lang]["df_kw"]: "", MSG[lang]["df_tgt"]: 0}])
    else:
        # Check both language keys for Priority
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

    if strategy in ["Filtre Classique (Contient au moins un tag)", "Classic Filter (Contains at least one tag)"]:
        for item in base_pool:
            if not ordered_tags or any(re.search(r'\b' + re.escape(t) + r'\b', item['caption'].lower()) for t in ordered_tags):
                to_export.append(item)
        if limit > 0: to_export = to_export[:limit]

    elif strategy in ["Priorité (Ordre du tableau)", "Priority (Table Order)"]:
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
            if sum(needs.values()) == 0:
                 to_export = relevant[:lim]
            else:
                available = relevant.copy()
                while len(to_export) < lim and available:
                    best_score = -9999; best_idx = -1
                    for i, item in enumerate(available):
                        cap = item['caption'].lower(); score = 0; has_tag = False
                        for tag in ordered_tags:
                            if re.search(r'\b' + re.escape(tag) + r'\b', cap):
                                has_tag = True
                                if tag in needs: score += (10 * needs[tag]) if needs[tag] > 0 else -5
                        if has_tag and score > best_score: best_score = score; best_idx = i
                    if best_idx == -1: break
                    chosen = available.pop(best_idx)
                    to_export.append(chosen)
                    for tag in ordered_tags:
                        if re.search(r'\b' + re.escape(tag) + r'\b', chosen['caption'].lower()) and tag in needs:
                            needs[tag] -= 1
        else:
            to_export = relevant[:lim]

    sim_stats = {t: 0 for t in ordered_tags}
    for item in to_export:
        cap = item['caption'].lower()
        for t in ordered_tags:
            if re.search(r'\b' + re.escape(t) + r'\b', cap): sim_stats[t] += 1
            
    pie_data = {k: v for k, v in sim_stats.items() if v > 0}
    if not pie_data:
        p_fig = px.pie(names=[MSG[lang]["none"]], values=[1], title=MSG[lang]["sim_no_tag"])
        b_fig = px.bar(x=[MSG[lang]["none"]], y=[0], title=MSG[lang]["sim_no_tag"])
    else:
        p_fig = px.pie(names=list(pie_data.keys()), values=list(pie_data.values()), title=MSG[lang]["sim_dist"])
        p_fig.update_traces(textposition='inside', textinfo='percent+label')
        b_fig = px.bar(x=list(pie_data.keys()), y=list(pie_data.values()), title=MSG[lang]["sim_occ"])

    gallery_preview = [item['img_path'] for item in to_export]
    new_selected_ids = [item['id'] for item in to_export]
    gal_items = get_gallery_items(filtered_dataset, new_selected_ids, lang)
    
    if is_simulation:
        rep = MSG[lang]["simul_res"].format(count=len(to_export))
        return rep, gallery_preview, p_fig, b_fig, new_selected_ids, gal_items
    else:
        if not export_dir or str(export_dir).strip() == "":
            export_dir = os.path.join(os.getcwd(), "output", "dataset_final")
            
        if not os.path.exists(export_dir): 
            os.makedirs(export_dir)
            
        for item in to_export:
            shutil.copy2(item['img_path'], os.path.join(export_dir, item['img_name']))
            shutil.copy2(item['txt_path'], os.path.join(export_dir, os.path.basename(item['txt_path'])))
            
        return MSG[lang]["export_success"].format(count=len(to_export), dest=export_dir), gallery_preview, p_fig, b_fig, new_selected_ids, gal_items

# ==========================================
# INTERFACE GRADIO
# ==========================================

def change_language(lang, stats_df, config_df, filtered_data, selected_ids):
    t = UI_T.get(lang, UI_T.get("FR", {})) # Fallback to FR if something is missing
    m = MSG.get(lang, MSG.get("FR", {}))
    
    # Traduction dynamique des tableaux (sans avoir à recalculer et sans perdre vos éditions)
    new_stats = stats_df
    new_config = config_df
    
    kw = m.get("df_kw", "Mot-clé" if lang == "FR" else "Keyword")
    tgt = m.get("df_tgt", "Cible %" if lang == "FR" else "Target %")
    prio = m.get("df_prio", "Priorité" if lang == "FR" else "Priority")
    
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
            "Priorité": prio, "Priority": prio,
            "Mot-clé": kw, "Keyword": kw,
            "Cible %": tgt, "Target %": tgt
        })

    gal_items = get_gallery_items(filtered_data, selected_ids, lang)
    
    lbl_pie = "Graphique (Répartition)" if lang == "FR" else "Chart (Distribution)"
    lbl_bar = "Graphique (Occurrences)" if lang == "FR" else "Chart (Occurrences)"
    lbl_exp = "Graphique (Export)" if lang == "FR" else "Chart (Export)"

    return (
        gr.update(value=t.get("title", "")), gr.update(value=t.get("browse", "")), gr.update(value=t.get("load", "")),
        gr.update(value=t.get("status_wait", "")), gr.update(value=t.get("recipe_global", "")), gr.update(label=t.get("recipes_dd", "")),
        gr.update(label=t.get("recipe_name", "")), gr.update(value=t.get("save_recipe", "")), gr.update(placeholder=t.get("tracked_ph", "")),
        gr.update(value=t.get("gallery_title", "")), gr.update(label=t.get("search", ""), placeholder=t.get("search_ph", "")),
        gr.update(label=t.get("multi_cb", "")), gr.update(value=t.get("clear_sel", "")), gr.update(label=t.get("cols", "")),
        gr.update(value=t.get("hide_gal", "")), gr.update(label=t.get("tab_view", "")), gr.update(value=t.get("btn_prev", "")),
        gr.update(value=t.get("btn_next", "")), gr.update(value=t.get("shortcuts", "")), gr.update(value=t.get("toggle_stat", "")),
        gr.update(value=t.get("save_cap", "")), gr.update(label=t.get("tab_batch", "")), gr.update(value=t.get("btn_undo", "")),
        gr.update(label=t.get("target_rep", "")), gr.update(label=t.get("synonyms", "")), gr.update(value=t.get("btn_rep_syn", "")),
        gr.update(label=t.get("rep_this", "")), gr.update(label=t.get("rep_that", "")), gr.update(label=t.get("use_regex", "")),
        gr.update(value=t.get("btn_apply", "")), gr.update(label=t.get("add_text", "")), 
        gr.update(choices=t.get("add_pos_choices", [""]), value=t.get("add_pos_choices", [""])[0]),
        gr.update(value=t.get("btn_add", "")), gr.update(value=t.get("btn_clean_com", "")), gr.update(value=t.get("btn_clean_dup", "")),
        gr.update(label=t.get("df_preview", "")), gr.update(label=t.get("tab_export", "")), gr.update(value=t.get("exp_desc", "")),
        gr.update(value=t.get("exp_edit", "")), gr.update(value=new_config, headers=t.get("exp_df_headers", [])), 
        gr.update(label=t.get("strat", ""), choices=t.get("strat_choices", ["", ""]), value=t.get("strat_choices", ["", ""])[1] if len(t.get("strat_choices", []))>1 else ""),
        gr.update(label=t.get("max_img", "")), gr.update(label=t.get("dest_folder", ""), placeholder=t.get("dest_ph", "")),
        gr.update(value=t.get("btn_simul", "")), gr.update(value=t.get("btn_exp", "")), gr.update(value=t.get("res_simul", "")),
        gr.update(value=t.get("exp_gal", "")), gr.update(label=t.get("tab_stats", "")), gr.update(value=t.get("btn_calc", "")),
        gr.update(value=t.get("stat_edit", "")), gr.update(value=new_stats, headers=t.get("stat_df_headers", [])), gr.update(value=t.get("btn_top20", "")),
        gr.update(value=t.get("btn_orph", "")), gr.update(label=t.get("txt_orph", "")),
        gr.update(value=gal_items), gr.update(label=lbl_pie), gr.update(label=lbl_bar), gr.update(label=lbl_exp)
    )

with gr.Blocks(title="Datasets Images EditSelect") as app:
    dataset_state = gr.State([])
    filtered_state = gr.State([])
    history_state = gr.State([])
    current_idx_state = gr.State(0)
    selected_indices_state = gr.State([]) 
    dummy_selection = gr.Textbox(visible=False, elem_id="dummy_selection")
    
    # Safe load if files were somehow missing on init
    t_init = UI_T.get("FR", {})
    if not t_init:
        gr.Markdown("# ❌ Fichiers de langue introuvables. Assurez-vous que fr.json et en.json sont dans le même dossier.")

    with gr.Row():
        with gr.Column(scale=2):
            lang_radio = gr.Radio(["FR", "EN"], value="FR", label="Language / Langue")
            ui_title = gr.Markdown(t_init.get("title", ""))
            with gr.Row():
                dir_input = gr.Textbox(placeholder="C:\\mon\\dataset", show_label=False, scale=4)
                ui_browse_btn = gr.Button(t_init.get("browse", ""), scale=1)
            ui_load_btn = gr.Button(t_init.get("load", ""), variant="primary")
            ui_status_text = gr.Markdown(t_init.get("status_wait", ""))
            
        with gr.Column(scale=3):
            ui_recipe_global = gr.Markdown(t_init.get("recipe_global", ""))
            with gr.Row():
                ui_recipes_dropdown = gr.Dropdown(choices=list(load_recipes().keys()), label=t_init.get("recipes_dd", ""), scale=2)
                ui_recipe_name = gr.Textbox(label=t_init.get("recipe_name", ""), scale=1)
                ui_save_recipe_btn = gr.Button(t_init.get("save_recipe", ""), scale=1)
            ui_tracked_words = gr.Textbox(show_label=False, placeholder=t_init.get("tracked_ph", ""), lines=2)

    gr.Markdown("---")
    
    with gr.Row():
        with gr.Column(scale=0, elem_id="left_panel") as left_panel:
            ui_gallery_title = gr.Markdown(t_init.get("gallery_title", ""))
            ui_search_box = gr.Textbox(label=t_init.get("search", ""), placeholder=t_init.get("search_ph", ""))
            with gr.Group():
                ui_multi_select_cb = gr.Checkbox(label=t_init.get("multi_cb", ""), value=False)
                ui_clear_sel_btn = gr.Button(t_init.get("clear_sel", ""))
                ui_selection_status = gr.Markdown("**...**")
            ui_gallery_cols = gr.Slider(minimum=1, maximum=6, step=1, value=2, label=t_init.get("cols", ""))
            gallery = gr.Gallery(label="Dataset", columns=2, rows=6, height=750, object_fit="contain", allow_preview=False, elem_id="main_gallery")
            
        with gr.Column(scale=1):
            ui_toggle_panel_btn = gr.Button(t_init.get("hide_gal", ""), elem_id="toggle_gallery_btn", variant="secondary", size="sm")
            
            with gr.Tabs():
                with gr.Tab(t_init.get("tab_view", "")) as ui_tab_view:
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
                    current_caption = gr.Textbox(show_label=False, lines=4)
                    ui_save_single_btn = gr.Button(t_init.get("save_cap", ""), variant="primary", elem_id="save_single_btn")
                    ui_single_save_status = gr.Markdown()

                with gr.Tab(t_init.get("tab_batch", "")) as ui_tab_batch:
                    ui_btn_undo = gr.Button(t_init.get("btn_undo", ""), variant="stop")
                    ui_batch_status = gr.Markdown()
                    with gr.Row():
                        with gr.Group():
                            ui_target_rep = gr.Textbox(label=t_init.get("target_rep", ""))
                            ui_synonyms = gr.Textbox(label=t_init.get("synonyms", ""))
                            ui_btn_rep_syn = gr.Button(t_init.get("btn_rep_syn", ""))
                        with gr.Group():
                            ui_old_text = gr.Textbox(label=t_init.get("rep_this", ""))
                            ui_new_text = gr.Textbox(label=t_init.get("rep_that", ""))
                            ui_use_regex = gr.Checkbox(label=t_init.get("use_regex", ""))
                            ui_btn_apply = gr.Button(t_init.get("btn_apply", ""))
                    with gr.Row():
                        with gr.Group():
                            ui_add_text = gr.Textbox(label=t_init.get("add_text", ""))
                            ui_add_pos = gr.Radio(t_init.get("add_pos_choices", [""]), value=t_init.get("add_pos_choices", [""])[0], show_label=False)
                            ui_btn_add = gr.Button(t_init.get("btn_add", ""))
                        with gr.Group():
                            ui_btn_clean_com = gr.Button(t_init.get("btn_clean_com", ""))
                            ui_btn_clean_dup = gr.Button(t_init.get("btn_clean_dup", ""))
                    ui_preview_table = gr.Dataframe(label=t_init.get("df_preview", ""), interactive=False)

                with gr.Tab(t_init.get("tab_export", "")) as ui_tab_export:
                    ui_exp_desc = gr.Markdown(t_init.get("exp_desc", ""))
                    with gr.Row():
                        with gr.Column(scale=1):
                            ui_exp_edit = gr.Markdown(t_init.get("exp_edit", ""))
                            ui_export_config_df = gr.Dataframe(headers=t_init.get("exp_df_headers", []), interactive=True, type="pandas")
                            ui_strategy_radio = gr.Radio(t_init.get("strat_choices", ["", ""]), value=t_init.get("strat_choices", ["", ""])[1] if len(t_init.get("strat_choices", []))>1 else "", label=t_init.get("strat", ""))
                            ui_max_img_input = gr.Number(label=t_init.get("max_img", ""), value=0, precision=0)
                            ui_export_dir = gr.Textbox(label=t_init.get("dest_folder", ""), placeholder=t_init.get("dest_ph", ""))
                            with gr.Row():
                                ui_btn_simul = gr.Button(t_init.get("btn_simul", ""), variant="secondary")
                                ui_btn_exp = gr.Button(t_init.get("btn_exp", ""), variant="primary")
                        with gr.Column(scale=1):
                            ui_res_simul = gr.Markdown(t_init.get("res_simul", ""))
                            ui_export_status = gr.Markdown()
                            export_pie = gr.Plot(label="Graphique (Export)")
                    ui_exp_gal = gr.Markdown(t_init.get("exp_gal", ""))
                    export_gallery = gr.Gallery(columns=8, rows=2, height=250, object_fit="contain", allow_preview=False)

                with gr.Tab(t_init.get("tab_stats", "")) as ui_tab_stats:
                    ui_btn_calc = gr.Button(t_init.get("btn_calc", ""), variant="primary")
                    ui_stats_status = gr.Markdown()
                    with gr.Row():
                        with gr.Column(scale=1):
                            ui_stat_edit = gr.Markdown(t_init.get("stat_edit", ""))
                            ui_stats_table = gr.Dataframe(headers=t_init.get("stat_df_headers", []), interactive=True, type="pandas")
                            ui_btn_top20 = gr.Button(t_init.get("btn_top20", ""))
                            ui_btn_orph = gr.Button(t_init.get("btn_orph", ""))
                            ui_txt_orph = gr.Textbox(label=t_init.get("txt_orph", ""), lines=4)
                        with gr.Column(scale=2):
                            pie_chart = gr.Plot(label="Graphique (Répartition)")
                            bar_chart = gr.Plot(label="Graphique (Occurrences)")

# ==========================================
# LOGIQUE D'INTERFACE ET EVENEMENTS
# ==========================================

    lang_radio.change(
        fn=change_language,
        inputs=[lang_radio, ui_stats_table, ui_export_config_df, filtered_state, selected_indices_state],
        outputs=[
            ui_title, ui_browse_btn, ui_load_btn, ui_status_text, ui_recipe_global,
            ui_recipes_dropdown, ui_recipe_name, ui_save_recipe_btn, ui_tracked_words,
            ui_gallery_title, ui_search_box, ui_multi_select_cb, ui_clear_sel_btn,
            ui_gallery_cols, ui_toggle_panel_btn, ui_tab_view, ui_btn_prev, ui_btn_next,
            ui_viewer_shortcuts, ui_toggle_tag_btn, ui_save_single_btn,
            ui_tab_batch, ui_btn_undo, ui_target_rep, ui_synonyms, ui_btn_rep_syn,
            ui_old_text, ui_new_text, ui_use_regex, ui_btn_apply, ui_add_text,
            ui_add_pos, ui_btn_add, ui_btn_clean_com, ui_btn_clean_dup, ui_preview_table,
            ui_tab_export, ui_exp_desc, ui_exp_edit, ui_export_config_df, ui_strategy_radio,
            ui_max_img_input, ui_export_dir, ui_btn_simul, ui_btn_exp, ui_res_simul,
            ui_exp_gal, ui_tab_stats, ui_btn_calc, ui_stat_edit, ui_stats_table,
            ui_btn_top20, ui_btn_orph, ui_txt_orph,
            gallery, pie_chart, bar_chart, export_pie
        ]
    )

    ui_toggle_panel_btn.click(fn=None, js="toggleGallery")
    ui_browse_btn.click(fn=browse_folder, inputs=[], outputs=[dir_input])
    ui_gallery_cols.change(fn=lambda x: gr.update(columns=x), inputs=[ui_gallery_cols], outputs=[gallery])

    ui_load_btn.click(fn=load_dataset, inputs=[dir_input, lang_radio], outputs=[dataset_state, filtered_state, history_state, ui_status_text, gallery, selected_indices_state, ui_selection_status])
    ui_search_box.change(fn=filter_gallery, inputs=[dataset_state, ui_search_box, selected_indices_state, lang_radio], outputs=[filtered_state, gallery])
    
    gallery.select(fn=gallery_click, inputs=[filtered_state, selected_indices_state, ui_multi_select_cb, ui_tracked_words, lang_radio], outputs=[current_img, highlight_preview, current_caption, word_counter, current_idx_state, ui_viewer_status, selected_indices_state, ui_selection_status, gallery])
    
    ui_btn_prev.click(fn=nav_prev, inputs=[filtered_state, current_idx_state, ui_tracked_words, lang_radio], outputs=[current_img, highlight_preview, current_caption, word_counter, current_idx_state, ui_viewer_status])
    ui_btn_next.click(fn=nav_next, inputs=[filtered_state, current_idx_state, ui_tracked_words, lang_radio], outputs=[current_img, highlight_preview, current_caption, word_counter, current_idx_state, ui_viewer_status])
    
    ui_clear_sel_btn.click(fn=clear_selection, inputs=[filtered_state, lang_radio], outputs=[selected_indices_state, ui_selection_status, gallery])
    ui_multi_select_cb.change(fn=clear_selection, inputs=[filtered_state, lang_radio], outputs=[selected_indices_state, ui_selection_status, gallery])
    
    ui_toggle_tag_btn.click(fn=toggle_tracked_word, inputs=[ui_tracked_words, dummy_selection], outputs=[ui_tracked_words], js="getSelectedText")
    ui_tracked_words.change(fn=update_viewer, inputs=[filtered_state, current_idx_state, ui_tracked_words, lang_radio], outputs=[current_img, highlight_preview, current_caption, word_counter, current_idx_state, ui_viewer_status])
    
    current_caption.change(fn=update_word_count, inputs=[current_caption, lang_radio], outputs=[word_counter])
    ui_save_single_btn.click(fn=save_single_caption, inputs=[dataset_state, filtered_state, current_idx_state, current_caption, lang_radio], outputs=[dataset_state, filtered_state, ui_single_save_status])

    ui_btn_calc.click(fn=analyze_dataset, inputs=[dataset_state, ui_tracked_words, lang_radio], outputs=[pie_chart, bar_chart, ui_stats_table, ui_export_config_df, ui_stats_status])
    ui_btn_top20.click(fn=auto_fill_top_tags, inputs=[dataset_state], outputs=[ui_tracked_words])
    ui_btn_orph.click(fn=find_orphans, inputs=[dataset_state, lang_radio], outputs=[ui_txt_orph])
    
    ui_stats_table.change(fn=df_to_tracked_words, inputs=[ui_stats_table], outputs=[ui_tracked_words])
    ui_export_config_df.change(fn=df_to_tracked_words, inputs=[ui_export_config_df], outputs=[ui_tracked_words])
    
    ui_btn_undo.click(fn=None, js="confirmAction").success(fn=undo_last_action, inputs=[dataset_state, history_state, lang_radio], outputs=[dataset_state, filtered_state, ui_batch_status])
    ui_btn_add.click(fn=None, js="confirmAction").success(fn=batch_add, inputs=[dataset_state, ui_add_text, ui_add_pos, selected_indices_state, lang_radio], outputs=[dataset_state, filtered_state, history_state, ui_batch_status, ui_preview_table])
    ui_btn_apply.click(fn=None, js="confirmAction").success(fn=batch_replace, inputs=[dataset_state, ui_old_text, ui_new_text, ui_use_regex, selected_indices_state, lang_radio], outputs=[dataset_state, filtered_state, history_state, ui_batch_status, ui_preview_table])
    ui_btn_clean_com.click(fn=None, js="confirmAction").success(fn=batch_clean_commas, inputs=[dataset_state, selected_indices_state, lang_radio], outputs=[dataset_state, filtered_state, history_state, ui_batch_status, ui_preview_table])
    ui_btn_clean_dup.click(fn=None, js="confirmAction").success(fn=batch_remove_duplicates, inputs=[dataset_state, selected_indices_state, lang_radio], outputs=[dataset_state, filtered_state, history_state, ui_batch_status, ui_preview_table])
    ui_btn_rep_syn.click(fn=None, js="confirmAction").success(fn=batch_synonyms, inputs=[dataset_state, ui_target_rep, ui_synonyms, selected_indices_state, lang_radio], outputs=[dataset_state, filtered_state, history_state, ui_batch_status, ui_preview_table])

    ui_btn_simul.click(
        fn=simulate_and_export, 
        inputs=[dataset_state, ui_export_dir, ui_export_config_df, gr.State(True), selected_indices_state, ui_strategy_radio, ui_max_img_input, filtered_state, lang_radio], 
        outputs=[ui_export_status, export_gallery, export_pie, bar_chart, selected_indices_state, gallery]
    )
    
    ui_btn_exp.click(
        fn=simulate_and_export, 
        inputs=[dataset_state, ui_export_dir, ui_export_config_df, gr.State(False), selected_indices_state, ui_strategy_radio, ui_max_img_input, filtered_state, lang_radio], 
        outputs=[ui_export_status, export_gallery, export_pie, bar_chart, selected_indices_state, gallery]
    )

if __name__ == "__main__":
    app.launch(inbrowser=True, server_name="127.0.0.1", head=head_html)