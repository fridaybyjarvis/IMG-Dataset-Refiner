"""Frontend CSS and custom JS string literals for IMG Dataset Refiner.

Extracted verbatim from lora_manager.py to keep that main module
shorter and let the Gradio launch code pull these by import.
"""

css_code = """
/* ======================================================
   IMG Dataset Refiner — Premium control-room theme
   Layout IDs and hidden bridge components are intentionally
   preserved for Gradio/Svelte stability.
   ====================================================== */

:root {
    --idr-bg: #090d12;
    --idr-bg-2: #0d131a;
    --idr-surface: #121922;
    --idr-surface-2: #17212b;
    --idr-surface-3: #1c2834;
    --idr-border: #2a3746;
    --idr-border-soft: rgba(148, 163, 184, 0.18);
    --idr-text: #e7edf5;
    --idr-muted: #9aa8b7;
    --idr-muted-2: #738295;
    --idr-teal: #2dd4bf;
    --idr-amber: #f2b84b;
    --idr-green: #65d46e;
    --idr-blue: #60a5fa;
    --idr-coral: #fb7185;
    --idr-red: #f87171;
    --idr-shadow: 0 18px 48px rgba(0, 0, 0, 0.36);
    --idr-shadow-soft: 0 8px 28px rgba(0, 0, 0, 0.26);
    --idr-radius: 8px;
}

* { box-sizing: border-box !important; }
.gradio-container header, .gradio-container-4-26-0 header, header { display: none !important; }
footer { display: none !important; }

html, body, gradio-app {
    margin: 0 !important;
    padding: 0 !important;
    min-height: 100% !important;
    background:
        linear-gradient(180deg, #090d12 0%, #0d131a 46%, #090d12 100%) !important;
    color: var(--idr-text) !important;
}

body,
.gradio-container {
    font-family: "Inter", "Segoe UI", system-ui, -apple-system, BlinkMacSystemFont, sans-serif !important;
    letter-spacing: 0 !important;
}

.gradio-container, .contain, main, .wrap {
    max-width: none !important;
    width: 100% !important;
    margin: 0 !important;
}

.gradio-container {
    padding: 14px 18px 18px 18px !important;
    min-height: 100vh !important;
    background: transparent !important;
}

.gradio-container .main.fillable,
.gradio-container > .main,
.gradio-container > main {
    max-width: none !important;
    padding: 0 !important;
    background: transparent !important;
}

.gradio-container * {
    scrollbar-width: thin;
    scrollbar-color: #3b4a5c #101720;
}

.gradio-container ::-webkit-scrollbar { width: 10px; height: 10px; }
.gradio-container ::-webkit-scrollbar-track { background: #101720; }
.gradio-container ::-webkit-scrollbar-thumb {
    background: #3b4a5c;
    border: 2px solid #101720;
    border-radius: 8px;
}

#top_workspace {
    gap: 14px !important;
    align-items: stretch !important;
    flex-wrap: nowrap !important;
    margin-bottom: 14px !important;
}

#workbench_row {
    display: flex !important;
    flex-direction: row !important;
    flex-wrap: nowrap !important;
    gap: 14px !important;
    align-items: flex-start !important;
    min-height: calc(100vh - 24px) !important;
}

#workbench_row > div,
#top_workspace > div {
    min-width: 0 !important;
}

#center_panel {
    min-width: 480px !important;
    flex: 1 1 0 !important;
    width: auto !important;
}

#dataset_header,
#recipe_header,
#left_panel,
#right_panel,
.panel-purple {
    position: relative !important;
    border-radius: var(--idr-radius) !important;
    border: 1px solid var(--idr-border-soft) !important;
    background:
        linear-gradient(180deg, rgba(255, 255, 255, 0.045), rgba(255, 255, 255, 0.015)),
        var(--idr-surface) !important;
    box-shadow: var(--idr-shadow-soft) !important;
    overflow: visible !important;
}

#dataset_header,
#recipe_header {
    padding: 12px !important;
    max-height: min(410px, 58vh) !important;
    flex-wrap: nowrap !important;
    overflow-x: hidden !important;
    overflow-y: auto !important;
}

#dataset_header > *,
#recipe_header > * {
    flex-shrink: 0 !important;
}

#dataset_header::before,
#recipe_header::before,
#left_panel::before,
#right_panel::before,
.panel-purple::before {
    content: "";
    position: absolute;
    left: 0;
    right: 0;
    top: 0;
    height: 2px;
    background: linear-gradient(90deg, var(--idr-teal), var(--idr-amber), var(--idr-blue));
    opacity: 0.9;
    pointer-events: none;
}

#recipe_header::before {
    background: linear-gradient(90deg, var(--idr-amber), var(--idr-teal), var(--idr-green));
}

#left_panel::before {
    background: linear-gradient(90deg, var(--idr-green), var(--idr-teal));
}

#right_panel::before {
    background: linear-gradient(90deg, var(--idr-blue), var(--idr-teal));
}

#app_title h1 {
    font-size: 1.34rem !important;
    line-height: 1.08 !important;
    margin: 0 0 4px 0 !important;
    color: #f6f8fb !important;
    font-weight: 780 !important;
    letter-spacing: 0 !important;
}

#app_title p {
    margin: 0 0 4px 0 !important;
    color: var(--idr-muted) !important;
    font-size: 0.92rem !important;
}

#dataset_title_row {
    gap: 10px !important;
    align-items: flex-start !important;
    flex-wrap: nowrap !important;
}

#dataset_title_row > div {
    min-width: 0 !important;
}

#dataset_settings_col {
    flex: 0 0 150px !important;
    position: relative !important;
    z-index: 30 !important;
}

#dataset_settings_col > .block:has(> .label-wrap.open) {
    position: absolute !important;
    right: 0 !important;
    top: 0 !important;
    width: min(390px, calc(100vw - 44px)) !important;
    max-height: min(72vh, 560px) !important;
    overflow: auto !important;
    padding: 14px !important;
    border: 1px solid rgba(45, 212, 191, 0.42) !important;
    border-radius: var(--idr-radius) !important;
    background:
        linear-gradient(180deg, rgba(28, 39, 55, 0.98), rgba(14, 21, 30, 0.98)),
        var(--idr-surface) !important;
    box-shadow: 0 24px 60px rgba(0, 0, 0, 0.48) !important;
}

#dataset_settings_col > .block:has(> .label-wrap.open)::after {
    content: "Cliquez sur Paramètres pour fermer";
    display: block;
    margin-top: 8px;
    color: var(--idr-muted);
    font-size: 0.72rem;
}

#left_panel {
    position: sticky !important;
    top: 0 !important;
    resize: horizontal;
    overflow-x: hidden !important;
    overflow-y: auto !important;
    flex-wrap: nowrap !important;
    width: clamp(330px, 24vw, 500px);
    min-width: 295px;
    max-width: 44vw;
    flex: none !important;
    padding: 14px !important;
    height: 100vh !important;
    max-height: 100vh;
    transition: min-width 0.25s ease, width 0.25s ease, padding 0.25s ease, opacity 0.25s ease !important;
}

#left_panel > * {
    flex: 0 0 auto !important;
    flex-shrink: 0 !important;
}

#right_panel {
    width: clamp(315px, 22vw, 460px);
    min-width: 295px;
    max-width: 38vw;
    flex: none !important;
    padding: 14px !important;
    overflow-x: hidden !important;
    overflow-y: auto !important;
    max-height: 100vh;
    transition: min-width 0.25s ease, width 0.25s ease, padding 0.25s ease, opacity 0.25s ease !important;
}

#left_panel.collapsed,
#right_panel.collapsed {
    width: 0px !important;
    min-width: 0px !important;
    padding: 0px !important;
    margin: 0px !important;
    border: none !important;
    opacity: 0 !important;
    pointer-events: none !important;
    overflow: hidden !important;
}

#panel_toggles_row {
    gap: 8px !important;
    margin-bottom: 10px !important;
}

#panel_toggles_row > div {
    flex: 1 1 0 !important;
    min-width: 0 !important;
}

#center_panel > .tabs,
#center_panel div:has(> .tab-nav) {
    border-radius: var(--idr-radius) !important;
    background: var(--idr-surface) !important;
    border: 1px solid var(--idr-border-soft) !important;
    box-shadow: var(--idr-shadow) !important;
    overflow: visible !important;
}

.gradio-container button[role="tab"] {
    background: transparent !important;
    color: var(--idr-muted) !important;
    border: 0 !important;
    border-radius: 0 !important;
    min-height: 42px !important;
    font-weight: 680 !important;
}

.gradio-container button[role="tab"][aria-selected="true"],
.gradio-container button[role="tab"].selected {
    color: #f8fafc !important;
    background: linear-gradient(180deg, rgba(45, 212, 191, 0.16), rgba(242, 184, 75, 0.06)) !important;
    box-shadow: inset 0 -2px 0 var(--idr-teal) !important;
}

.gradio-container label,
.gradio-container .label-wrap,
.gradio-container .block-label {
    color: var(--idr-muted) !important;
    font-size: 0.82rem !important;
    font-weight: 650 !important;
}

.gradio-container h1,
.gradio-container h2,
.gradio-container h3,
.gradio-container strong {
    color: var(--idr-text) !important;
}

.gradio-container p,
.gradio-container li,
.gradio-container markdown,
.gradio-container .prose {
    color: var(--idr-muted) !important;
}

.gradio-container input,
.gradio-container textarea,
.gradio-container select {
    background: #0f151d !important;
    color: var(--idr-text) !important;
    border: 1px solid var(--idr-border) !important;
    border-radius: var(--idr-radius) !important;
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.03) !important;
}

.gradio-container input::placeholder,
.gradio-container textarea::placeholder {
    color: var(--idr-muted-2) !important;
}

.gradio-container input:focus,
.gradio-container textarea:focus,
.gradio-container select:focus {
    border-color: var(--idr-teal) !important;
    box-shadow: 0 0 0 3px rgba(45, 212, 191, 0.16) !important;
    outline: none !important;
}

.gradio-container button {
    min-height: 34px !important;
    border-radius: var(--idr-radius) !important;
    border: 1px solid var(--idr-border) !important;
    background: linear-gradient(180deg, #223041, #182231) !important;
    color: var(--idr-text) !important;
    font-weight: 720 !important;
    letter-spacing: 0 !important;
    padding: 0 12px !important;
    font-size: 0.9rem !important;
    box-shadow: 0 8px 18px rgba(0, 0, 0, 0.22) !important;
    transition: transform 0.12s ease, border-color 0.12s ease, background 0.12s ease, box-shadow 0.12s ease !important;
}

.gradio-container button:hover {
    transform: translateY(-1px);
    border-color: rgba(45, 212, 191, 0.52) !important;
    box-shadow: 0 12px 24px rgba(0, 0, 0, 0.28) !important;
}

.gradio-container button:active {
    transform: translateY(0);
}

.gradio-container button.primary {
    background: linear-gradient(135deg, #2dd4bf 0%, #f2b84b 100%) !important;
    color: #081017 !important;
    border-color: rgba(242, 184, 75, 0.72) !important;
}

.gradio-container button.secondary {
    background: linear-gradient(180deg, #1f2d3a, #151f2a) !important;
    color: #dbeafe !important;
}

.gradio-container button.stop {
    background: linear-gradient(180deg, rgba(248, 113, 113, 0.92), rgba(190, 64, 78, 0.92)) !important;
    color: #fff7f7 !important;
    border-color: rgba(248, 113, 113, 0.58) !important;
}

#dataset_load_btn,
#save_single_btn,
#btn_prep,
#btn_run_ai,
#btn_calc_adv,
#ui_btn_exp {
    box-shadow: 0 12px 28px rgba(45, 212, 191, 0.14) !important;
}

#dataset_quick_row {
    gap: 12px !important;
    align-items: stretch !important;
    flex-wrap: nowrap !important;
}

#recipe_save_row,
#recipe_ai_row,
#gallery_sort_select_row,
#selection_buttons_row,
#csv_actions_row,
#md_actions_row {
    gap: 8px !important;
    align-items: center !important;
}

#recipe_save_row,
#recipe_ai_row,
#gallery_sort_select_row,
#selection_buttons_row,
#csv_actions_row,
#md_actions_row {
    flex-wrap: nowrap !important;
}

#dataset_quick_row > div,
#recipe_save_row > div,
#recipe_ai_row > div,
#gallery_sort_select_row > div,
#selection_buttons_row > div,
#csv_actions_row > div,
#md_actions_row > div {
    min-width: 0 !important;
}

#dataset_path_col {
    flex: 1.15 1 0 !important;
    gap: 8px !important;
}

#dataset_drop_col {
    flex: 1 1 0 !important;
    gap: 8px !important;
    justify-content: flex-start !important;
}

#dataset_path_row {
    flex-wrap: nowrap !important;
    gap: 8px !important;
    align-items: stretch !important;
}

#dataset_path_row textarea,
#dataset_path_row input {
    min-height: 76px !important;
    height: 76px !important;
    max-height: 76px !important;
    resize: none !important;
    overflow: auto !important;
    line-height: 1.25 !important;
    padding: 10px 12px !important;
}

#dataset_path_row button {
    flex: 0 0 104px !important;
    width: 104px !important;
    height: 76px !important;
    min-width: 0 !important;
    padding: 0 10px !important;
    align-self: stretch !important;
}

#dataset_header .block,
#recipe_header .block,
#left_panel .block {
    margin-top: 3px !important;
    margin-bottom: 3px !important;
}

#dataset_header textarea,
#dataset_header input,
#recipe_header textarea,
#recipe_header input,
#left_panel textarea,
#left_panel input {
    min-height: 34px !important;
}

#dataset_header .block.padded,
#recipe_header .block.padded {
    padding: 6px 8px !important;
}

#dataset_header .form,
#recipe_header .form {
    gap: 6px !important;
}

#recipe_save_row .block.padded,
#recipe_ai_row .block.padded {
    min-height: 68px !important;
}

#recipe_save_row > .form,
#recipe_ai_row > .form {
    min-height: 72px !important;
}

#tracked_words_input textarea {
    min-height: 42px !important;
    max-height: 220px !important;
    resize: vertical !important;
    overflow: auto !important;
}

#dataset_drop_col .dataset-drop-zone {
    min-height: 84px;
    height: 84px;
    margin-top: 0;
    display: flex;
    flex-direction: column;
    justify-content: center;
    font-size: 11.2px !important;
    line-height: 1.22 !important;
    padding: 12px 14px !important;
}

#dataset_status_text {
    min-height: 0 !important;
    height: auto !important;
    padding: 0 !important;
    margin: 2px 0 0 0 !important;
}

#dataset_status_text p {
    margin: 0 !important;
    font-size: 0.78rem !important;
    line-height: 1.25 !important;
}

#dataset_load_btn {
    width: 100% !important;
    min-height: 34px !important;
    height: 34px !important;
    margin-top: 0 !important;
}

#dataset_header #dataset_dir_input textarea {
    font-size: 0.82rem !important;
}

#dataset_header .wrap:has(#dataset_dir_input),
#dataset_header .wrap:has(#dataset_dir_input) > .block {
    height: 76px !important;
}

#dataset_header .wrap:has(#dataset_load_btn),
#dataset_header .wrap:has(#dataset_load_btn) > .block {
    min-height: 34px !important;
}

#include_subfolders_btn {
    width: 100% !important;
    min-height: 34px !important;
    height: 34px !important;
    justify-content: flex-start !important;
}

#include_subfolders_btn.include-subfolders-on,
#include_subfolders_btn[aria-pressed="true"] {
    border-color: rgba(45, 212, 191, 0.72) !important;
    background: linear-gradient(135deg, rgba(45, 212, 191, 0.9), rgba(101, 212, 110, 0.72)) !important;
    color: #061017 !important;
}

#dataset_header .wrap:has(#dataset_status_text) {
    margin-top: 0 !important;
}

#recipe_save_row > div:has(button),
#recipe_ai_row > div:has(#ai_recipe_btn) {
    flex: 0 1 220px !important;
}

#recipe_ai_row #ai_recipe_btn {
    flex: 0 0 min(280px, 48%) !important;
    width: min(280px, 48%) !important;
    min-width: 0 !important;
}

#recipe_save_row button,
#recipe_ai_row button {
    max-width: 260px !important;
    width: 100% !important;
}

#analyze_recipe_btn {
    max-width: 260px !important;
    width: 100% !important;
    align-self: auto !important;
}

#recipe_save_row button,
#recipe_ai_row button,
#ai_recipe_btn {
    height: 34px !important;
    min-height: 34px !important;
}

#ai_recipe_btn,
#analyze_recipe_btn {
    min-height: 34px !important;
}

#gallery_search_box {
    position: relative !important;
    min-height: 43px !important;
    height: 43px !important;
    padding: 6px 8px !important;
    margin-bottom: 5px !important;
    overflow: hidden !important;
}

#gallery_search_box .wrap,
#gallery_search_box .block,
#gallery_search_box .form,
#gallery_sort_radio .wrap,
#multi_cb .wrap {
    background: transparent !important;
    box-shadow: none !important;
}

#gallery_search_box label,
#gallery_sort_radio label,
#multi_cb label {
    font-size: 0.77rem !important;
    line-height: 1.1 !important;
}

#gallery_search_box label.container {
    display: block !important;
    min-height: 31px !important;
    height: 31px !important;
}

#gallery_search_box span[data-testid="block-info"] {
    display: none !important;
}

#gallery_search_box::before {
    content: "🔍";
    position: absolute;
    left: 18px;
    top: 50%;
    z-index: 3;
    transform: translateY(-50%);
    opacity: 0.82;
    pointer-events: none;
    font-size: 0.82rem;
}

#gallery_search_box .input-container {
    margin: 0 !important;
}

#gallery_search_box textarea {
    min-height: 31px !important;
    height: 31px !important;
    padding: 6px 10px 6px 31px !important;
}

#gallery_sort_select_row {
    align-items: center !important;
    gap: 4px !important;
    margin: 4px 0 6px !important;
    padding: 6px !important;
    border: 1px solid rgba(148, 163, 184, 0.16) !important;
    border-radius: var(--idr-radius) !important;
    background: rgba(8, 13, 20, 0.36) !important;
}

#gallery_sort_select_row .block,
#gallery_sort_select_row .form {
    margin: 0 !important;
    min-width: 0 !important;
}

#gallery_sort_select_row > .form {
    display: grid !important;
    grid-template-columns: minmax(66px, 0.72fr) minmax(96px, 1fr) !important;
    gap: 4px !important;
    align-items: center !important;
    flex: 1 1 168px !important;
    width: auto !important;
}

#gallery_sort_select_row > .form > * {
    min-width: 0 !important;
}

#gallery_sort_select_row > button {
    flex: 0 1 52px !important;
}

#gallery_sort_radio,
#multi_cb {
    min-height: 30px !important;
    height: 30px !important;
    padding: 0 !important;
    border: 0 !important;
    background: transparent !important;
    overflow: hidden !important;
}

#gallery_sort_radio > span[data-testid="block-info"] {
    display: none !important;
}

#gallery_sort_radio .wrap,
#gallery_sort_radio [role="radiogroup"] {
    display: flex !important;
    flex-direction: row !important;
    gap: 4px !important;
    align-items: center !important;
    height: 30px !important;
    min-height: 30px !important;
}

#gallery_sort_radio .wrap label,
#gallery_sort_radio [role="radiogroup"] label {
    flex: 1 1 0 !important;
    min-width: 0 !important;
}

#gallery_sort_radio input[type="radio"] {
    display: none !important;
}

#gallery_sort_radio .wrap label,
#multi_cb label {
    min-height: 28px !important;
    height: 28px !important;
    align-items: center !important;
}

#gallery_sort_radio .wrap label {
    justify-content: center !important;
    padding: 0 5px !important;
    border: 1px solid rgba(148, 163, 184, 0.16) !important;
    border-radius: 6px !important;
    background: rgba(18, 28, 40, 0.72) !important;
    color: #b9c8da !important;
}

#gallery_sort_radio .wrap label.selected {
    border-color: rgba(45, 212, 191, 0.45) !important;
    background: rgba(45, 212, 191, 0.14) !important;
    color: #eff6ff !important;
}

#multi_cb label {
    display: flex !important;
    white-space: nowrap !important;
}

/* ======================================================
   Checkboxes — état coché clairement visible (coche blanche)
   ====================================================== */
.gradio-container input[type="checkbox"] {
    -webkit-appearance: none !important;
    appearance: none !important;
    width: 20px !important;
    height: 20px !important;
    flex-shrink: 0 !important;
    cursor: pointer !important;
    border: 2px solid var(--idr-border, #2a3746) !important;
    border-radius: 5px !important;
    background-color: var(--idr-surface-2, #17212b) !important;
    background-image: none !important;
    position: relative !important;
    transition: background-color 0.15s ease, border-color 0.15s ease !important;
}

.gradio-container input[type="checkbox"]:hover {
    border-color: var(--idr-teal, #2dd4bf) !important;
}

.gradio-container input[type="checkbox"]:checked {
    background-color: var(--idr-teal, #2dd4bf) !important;
    border-color: var(--idr-teal, #2dd4bf) !important;
}

/* Coche blanche dessinée par-dessus le fond coloré */
.gradio-container input[type="checkbox"]:checked::after {
    content: "" !important;
    position: absolute !important;
    left: 5px !important;
    top: 1px !important;
    width: 5px !important;
    height: 10px !important;
    border: solid #0b1016 !important;
    border-width: 0 2.5px 2.5px 0 !important;
    transform: rotate(45deg) !important;
}

#select_all_btn,
#clear_sel_btn {
    width: 100% !important;
    min-width: 0 !important;
    min-height: 29px !important;
    height: 29px !important;
    padding: 0 6px !important;
    font-size: 0.72rem !important;
    white-space: nowrap !important;
}

#ui_selection_status {
    margin-top: 0 !important;
}

.selection-status-pill {
    display: inline-flex;
    align-items: center;
    width: auto;
    min-height: 25px;
    padding: 4px 9px;
    border-left: 3px solid #22c55e;
    border-radius: 6px;
    background: rgba(34, 197, 94, 0.095);
    color: #d7fbe7;
    font-size: 0.79rem;
    font-weight: 700;
    line-height: 1.1;
}

#gallery_csv_acc {
    margin-top: 8px !important;
    max-height: 280px !important;
    overflow: auto !important;
}

#caption_import_dropzone {
    display: none !important;
}

#gallery_csv_acc.csv-import-open #caption_import_dropzone {
    display: block !important;
}

#caption_import_dropzone label,
#caption_import_dropzone [data-testid="block-info"] {
    font-size: 0.8rem !important;
}

#gallery_csv_acc > div:last-child,
#gallery_csv_acc > div:not(.wrap):not(.label-wrap) {
    padding: 8px !important;
    max-height: 210px !important;
    overflow: auto !important;
}

#gallery_csv_acc .block {
    margin-top: 3px !important;
    margin-bottom: 3px !important;
}

#gallery_csv_acc .prose p,
#gallery_csv_acc .md p {
    margin: 0 !important;
    font-size: 0.78rem !important;
    line-height: 1.35 !important;
    color: var(--idr-muted) !important;
}

#gallery_csv_acc input {
    min-height: 34px !important;
}

#main_gallery {
    min-height: 520px !important;
    background: #0f151d !important;
    border: 1px solid var(--idr-border) !important;
    border-radius: var(--idr-radius) !important;
    padding: 0 !important;
}

#main_gallery button {
    position: relative !important;
    width: 100% !important;
    min-width: 0 !important;
    border-radius: 7px !important;
    overflow: hidden !important;
    border: 1px solid rgba(148, 163, 184, 0.16) !important;
    background: #0b1118 !important;
    box-shadow: none !important;
    padding: 0 !important;
    aspect-ratio: 1 / 1 !important;
}

#main_gallery img {
    width: 100% !important;
    height: 100% !important;
    object-fit: cover !important;
}

#main_gallery button figcaption,
#main_gallery button .caption,
#main_gallery button [class*="caption"],
#main_gallery button [class*="label"] {
    display: none !important;
}

#main_gallery .grid-wrap,
#main_gallery .grid-container,
#main_gallery [class*="grid"] {
    gap: 6px !important;
    padding: 6px !important;
}

#main_gallery .idr-manual-gallery-grid {
    --idr-manual-gallery-gap: 6px;
    display: flex !important;
    flex-wrap: wrap !important;
    gap: 6px !important;
    align-items: start !important;
    align-content: flex-start !important;
}

#main_gallery .idr-manual-gallery-grid > * {
    min-width: 0 !important;
}

#main_gallery .idr-manual-gallery-grid > *:not(.gallery-folder-separator) {
    flex: 0 0 calc((100% - (var(--idr-manual-gallery-cols, 4) - 1) * var(--idr-manual-gallery-gap)) / var(--idr-manual-gallery-cols, 4)) !important;
    max-width: calc((100% - (var(--idr-manual-gallery-cols, 4) - 1) * var(--idr-manual-gallery-gap)) / var(--idr-manual-gallery-cols, 4)) !important;
}

#main_gallery button:hover {
    border-color: rgba(45, 212, 191, 0.55) !important;
    transform: translateY(-1px);
}

#main_gallery .gallery-folder-separator {
    position: static !important;
    grid-column: 1 / -1 !important;
    width: 100% !important;
    height: auto !important;
    min-height: 0 !important;
    max-height: 22px !important;
    align-self: start !important;
    aspect-ratio: auto !important;
    flex: 0 0 100% !important;
    max-width: 100% !important;
    z-index: 5;
    display: flex;
    align-items: center;
    justify-content: flex-start;
    margin: 0 0 -2px 0;
    padding: 2px 9px;
    background:
        linear-gradient(90deg, rgba(45, 212, 191, 0.18), rgba(242, 184, 75, 0.10), rgba(45, 212, 191, 0.02)),
        #101923;
    color: #dffcf8;
    border-bottom: 1px solid rgba(45, 212, 191, 0.38);
    font-size: 0.73rem;
    font-weight: 850;
    line-height: 1.1;
    text-align: left;
    text-shadow: none;
    pointer-events: none;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    box-sizing: border-box;
}

#main_gallery .gallery-folder-separator::after {
    content: "";
    height: 1px;
    flex: 1 1 auto;
    margin-left: 10px;
    background: linear-gradient(90deg, rgba(45, 212, 191, 0.75), rgba(242, 184, 75, 0.45), transparent);
}

#main_gallery .gallery-folder-separator + * {
    margin-top: 0 !important;
}

.custom-selected {
    outline: 3px solid var(--idr-amber) !important;
    outline-offset: -3px !important;
    box-shadow: inset 0 0 0 2px rgba(8, 16, 23, 0.9), 0 0 0 2px rgba(242, 184, 75, 0.34) !important;
    border-radius: 8px !important;
}

.custom-selected img {
    filter: saturate(1.16) contrast(1.04) brightness(0.95) !important;
    opacity: 0.96 !important;
}

#viewer_area,
#viewer_caption_area,
#live_translation_preview {
    border-radius: var(--idr-radius) !important;
}

#viewer_area {
    min-height: 300px !important;
}

#viewer_area img,
#viewer_area canvas {
    border-radius: var(--idr-radius) !important;
}

#viewer_area_text {
    gap: 8px !important;
}

#viewer_area_text .html-container,
#viewer_area_text .html-container *,
#viewer_area_text .prose,
#viewer_area_text .prose *,
#viewer_area_text .md,
#viewer_area_text .md * {
    font-size: 0.82rem !important;
    line-height: 1.34 !important;
}

#viewer_area_text .html-container {
    padding: 10px 12px !important;
}

#viewer_area_text [style*="green"] {
    font-size: 0.82rem !important;
    margin: 4px 0 !important;
}

#viewer_shortcuts_acc {
    margin: 2px 0 !important;
    max-height: 180px !important;
    overflow: auto !important;
}

#viewer_shortcuts_acc > button {
    min-height: 30px !important;
    padding: 0 10px !important;
    font-size: 0.82rem !important;
}

#viewer_shortcuts_acc .prose,
#viewer_shortcuts_acc .md {
    font-size: 0.78rem !important;
    line-height: 1.35 !important;
}

#viewer_caption_area textarea {
    min-height: 110px !important;
    font-size: 0.86rem !important;
    line-height: 1.38 !important;
}

.caption-label {
    font-size: 14px !important;
    font-weight: bold !important;
    color: var(--idr-green) !important;
    display: none !important;
}

#hidden_sync_input, #hidden_sync_btn, #hidden_calc_btn, #hidden_dnd_input, #hidden_dnd_btn, #hidden_tags_input,
#hidden_live_translation_btn, #hidden_reverse_translation_btn,
#hidden_dataset_path_input, #hidden_dataset_path_btn, #hidden_manual_crop_payload, #hidden_manual_crop_btn { display: none !important; }
#hidden_delete_current_btn { display: none !important; }
#hidden_lib_toggle_input, #hidden_lib_toggle_btn, #hidden_lib_delete_input, #hidden_lib_delete_btn { display: none !important; }
#hidden_copy_next_btn { display: none !important; }
.form:has(#hidden_sync_input), .form:has(#hidden_dnd_input), .form:has(#hidden_tags_input), .form:has(#hidden_live_translation_btn), .form:has(#hidden_reverse_translation_btn),
.form:has(#hidden_dataset_path_input), .form:has(#hidden_delete_current_btn), .form:has(#hidden_lib_toggle_input), .form:has(#hidden_lib_delete_input), .form:has(#hidden_copy_next_btn), .form:has(#hidden_manual_crop_payload) {
    display: none !important;
    height: 0 !important;
    margin: 0 !important;
    padding: 0 !important;
}

.gradio-container .block,
.gradio-container .form,
.gradio-container .panel,
.gradio-container .compact {
    background: transparent !important;
    border-color: var(--idr-border-soft) !important;
}

.gradio-container .accordion,
.gradio-container details {
    background: rgba(23, 33, 43, 0.68) !important;
    border: 1px solid var(--idr-border-soft) !important;
    border-radius: var(--idr-radius) !important;
}

.gradio-container .accordion > button,
.gradio-container details > summary {
    color: var(--idr-text) !important;
    border-radius: var(--idr-radius) !important;
}

.gradio-dataframe {
    border-radius: var(--idr-radius) !important;
    overflow: hidden !important;
    border: 1px solid var(--idr-border) !important;
}

.gradio-dataframe table,
.gradio-dataframe thead,
.gradio-dataframe tbody {
    background: #0f151d !important;
    color: var(--idr-text) !important;
}

.gradio-dataframe th {
    background: #1a2430 !important;
    color: #dbeafe !important;
    font-weight: 740 !important;
    border-color: var(--idr-border) !important;
}

.gradio-dataframe td {
    border-color: rgba(148, 163, 184, 0.14) !important;
}

.gradio-dataframe tbody tr {
    transition: background-color 0.2s, opacity 0.2s;
}

.gradio-dataframe tbody tr:hover {
    background-color: rgba(45, 212, 191, 0.08) !important;
}

.gradio-dataframe tbody tr[draggable="true"] { cursor: grab !important; }
.gradio-dataframe tbody tr.dragging {
    opacity: 0.45;
    background-color: rgba(242, 184, 75, 0.22) !important;
    outline: 2px dashed var(--idr-amber);
    outline-offset: -2px;
}

.gradio-container .plot-container,
.gradio-container .js-plotly-plot {
    border-radius: var(--idr-radius) !important;
}

#autocomplete-list {
    position: absolute;
    border: 1px solid var(--idr-border);
    background-color: #111923;
    z-index: 9999;
    max-height: 180px;
    overflow-y: auto;
    border-radius: var(--idr-radius);
    box-shadow: var(--idr-shadow);
}

#autocomplete-list div {
    padding: 9px 10px;
    cursor: pointer;
    color: var(--idr-text);
    font-size: 14px;
}

#autocomplete-list div:hover,
#autocomplete-list div.autocomplete-active {
    background-color: rgba(45, 212, 191, 0.18);
    color: #f8fafc;
}

.info-box,
.ai-desc-box {
    background: rgba(45, 212, 191, 0.08) !important;
    border: 1px solid rgba(45, 212, 191, 0.22) !important;
    border-left: 3px solid var(--idr-teal) !important;
    padding: 10px 12px !important;
    margin-bottom: 12px !important;
    border-radius: var(--idr-radius) !important;
    color: #d9fff8 !important;
}

.lib-title-panel {
    padding: 10px 12px;
    border-radius: var(--idr-radius);
    border: 1px solid rgba(45, 212, 191, 0.34);
    background:
        linear-gradient(135deg, rgba(45, 212, 191, 0.18), rgba(96, 165, 250, 0.11)),
        rgba(16, 24, 34, 0.92);
    color: #e8fbff;
    font-weight: 780;
    text-align: center;
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04);
}

#prep_workspace {
    gap: 12px !important;
    align-items: flex-start !important;
}

#prep_workspace > div {
    min-width: 0 !important;
}

#prep_duplicate_panel,
#prep_transform_panel {
    gap: 8px !important;
}

#prep_preset_row {
    gap: 8px !important;
    align-items: flex-end !important;
    flex-wrap: nowrap !important;
}

#prep_preset_row > div {
    min-width: 0 !important;
}

.prep-summary-box {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 6px 10px;
    padding: 10px 12px;
    border-radius: var(--idr-radius);
    border: 1px solid rgba(45, 212, 191, 0.28);
    background: rgba(45, 212, 191, 0.07);
    color: var(--idr-text);
    font-size: 0.82rem;
    line-height: 1.3;
}

.prep-summary-box strong {
    grid-column: 1 / -1;
    color: #bffcf3 !important;
}

.prep-summary-path {
    grid-column: 1 / -1;
    color: var(--idr-muted);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

#dup_recommendation {
    margin: 4px 0 !important;
    padding: 8px 10px !important;
    border-radius: var(--idr-radius) !important;
    border: 1px solid rgba(242, 184, 75, 0.25) !important;
    background: rgba(242, 184, 75, 0.065) !important;
}

#dup_recommendation p {
    margin: 0 !important;
    font-size: 0.8rem !important;
    line-height: 1.35 !important;
}

#prep_duplicate_panel .block.padded,
#prep_transform_panel .block.padded,
#prep_low_res_panel {
    padding: 9px 10px !important;
    margin: 4px 0 !important;
}

#prep_duplicate_panel textarea,
#prep_transform_panel textarea,
#ai_action_manager textarea {
    font-size: 0.84rem !important;
    line-height: 1.35 !important;
}

#prep_duplicate_panel img,
#manual_crop_editor img,
#manual_crop_editor canvas {
    object-fit: contain !important;
    border-radius: var(--idr-radius) !important;
}

#manual_crop_acc {
    margin-top: 8px !important;
}

#manual_crop_canvas_tool {
    border: 1px solid rgba(45, 212, 191, 0.26);
    border-radius: var(--idr-radius);
    background: rgba(8, 13, 19, 0.86);
    padding: 10px;
    margin-bottom: 8px;
}

.manual-crop-toolbar {
    display: flex;
    gap: 6px;
    align-items: center;
    flex-wrap: wrap;
    margin-bottom: 8px;
}

.manual-crop-toolbar button {
    min-height: 30px !important;
    padding: 0 9px !important;
    font-size: 0.78rem !important;
}

.manual-crop-toolbar button.active {
    border-color: rgba(45, 212, 191, 0.85) !important;
    background: linear-gradient(135deg, rgba(45, 212, 191, 0.28), rgba(96, 165, 250, 0.20)) !important;
    color: #f8fafc !important;
}

#manual_crop_canvas_wrap {
    position: relative;
    width: 100%;
    aspect-ratio: 16 / 10;
    min-height: 300px;
    max-height: 520px;
    border-radius: var(--idr-radius);
    overflow: hidden;
    border: 1px solid rgba(148, 163, 184, 0.18);
    background:
        linear-gradient(45deg, rgba(255,255,255,0.03) 25%, transparent 25%),
        linear-gradient(-45deg, rgba(255,255,255,0.03) 25%, transparent 25%),
        #070b10;
    background-size: 24px 24px;
}

#manual_crop_canvas {
    display: block;
    width: 100%;
    height: 100%;
    cursor: grab;
    touch-action: none;
}

#manual_crop_canvas.dragging {
    cursor: grabbing;
}

.manual-crop-help {
    margin-top: 7px;
    color: var(--idr-muted);
    font-size: 0.76rem;
    line-height: 1.35;
}

.manual-crop-status {
    color: #bffcf3;
    font-size: 0.76rem;
    margin-left: auto;
}

#manual_crop_editor {
    height: 1px !important;
    min-height: 1px !important;
    max-height: 1px !important;
    opacity: 0.01 !important;
    overflow: hidden !important;
    pointer-events: none !important;
    margin: 0 !important;
}

#manual_crop_acc > button,
#ai_action_manager > button {
    min-height: 32px !important;
    font-size: 0.84rem !important;
}

#manual_crop_acc .prose p,
#manual_crop_acc .md p {
    margin: 0 0 6px 0 !important;
    font-size: 0.78rem !important;
    line-height: 1.35 !important;
}

#manual_crop_nav,
#manual_crop_actions,
#ai_action_manager_buttons,
#ai_action_json_buttons {
    gap: 8px !important;
    flex-wrap: nowrap !important;
}

#manual_crop_nav > div,
#manual_crop_actions > div,
#ai_action_manager_buttons > div,
#ai_action_json_buttons > div {
    min-width: 0 !important;
}

#manual_crop_nav button,
#manual_crop_actions button,
#ai_action_manager_buttons button,
#ai_action_json_buttons button {
    width: 100% !important;
    min-height: 32px !important;
    font-size: 0.82rem !important;
}

#ai_action_manager {
    margin: 8px 0 10px 0 !important;
    border-color: rgba(96, 165, 250, 0.26) !important;
    background: rgba(96, 165, 250, 0.055) !important;
}

#ai_action_manager .block {
    margin-top: 4px !important;
    margin-bottom: 4px !important;
}

#ai_action_manager input,
#ai_action_manager textarea {
    min-height: 34px !important;
}

#btn_translate_entire {
    background: linear-gradient(135deg, var(--idr-green), var(--idr-teal)) !important;
    color: #06120f !important;
    font-weight: 760 !important;
    border: none !important;
}

#btn_translate_entire:hover {
    box-shadow: 0 12px 24px rgba(45, 212, 191, 0.18) !important;
}

#live_translation_preview textarea {
    background-color: rgba(45, 212, 191, 0.07) !important;
    color: #9ff7e9 !important;
    border: 1px dashed rgba(45, 212, 191, 0.55) !important;
    font-style: italic !important;
    opacity: 1 !important;
    -webkit-text-fill-color: #9ff7e9 !important;
}

.dataset-drop-zone {
    border: 1px dashed rgba(148, 163, 184, 0.38);
    border-radius: var(--idr-radius);
    padding: 11px 12px;
    margin: 8px 0 10px 0;
    background: rgba(45, 212, 191, 0.055);
    color: var(--idr-muted);
    font-size: 12.5px;
    line-height: 1.35;
    transition: border-color 0.15s ease, background-color 0.15s ease, color 0.15s ease, transform 0.15s ease;
}

.dataset-drop-zone strong {
    display: block;
    color: #bffcf3;
    margin-bottom: 3px;
    font-weight: 760;
}

.dataset-drop-zone.dragover {
    border-color: var(--idr-teal);
    background: rgba(45, 212, 191, 0.14);
    color: #fff;
    transform: translateY(-1px);
}

.lib-item-custom {
    transition: border-color 0.16s ease, background-color 0.16s ease, transform 0.16s ease !important;
    border-radius: var(--idr-radius) !important;
    margin-bottom: 7px !important;
}

.lib-item-custom:hover {
    transform: translateY(-1px);
    border-color: rgba(45, 212, 191, 0.62) !important;
}

.lib-item-delete {
    color: #fecdd3 !important;
    background-color: rgba(248, 113, 113, 0.13) !important;
}

.panel-purple {
    padding: 14px !important;
    margin-bottom: 10px !important;
}

.panel-purple::before {
    background: linear-gradient(90deg, var(--idr-blue), var(--idr-teal), var(--idr-amber));
}

.panel-translate {
    border: 1px solid rgba(251, 113, 133, 0.22) !important;
    border-radius: var(--idr-radius) !important;
    background: rgba(251, 113, 133, 0.045) !important;
}

.panel-translate > .label-wrap,
.panel-translate > button {
    background: rgba(251, 113, 133, 0.075) !important;
    border-left: 3px solid var(--idr-coral) !important;
    border-radius: var(--idr-radius) !important;
}

#dataset_status_text,
#ui_selection_status,
#ui_single_save_status,
#prep_status,
#ai_status,
#ui_export_status,
#ui_stats_status {
    color: var(--idr-muted) !important;
}

@media (max-width: 1050px) {
    .gradio-container { padding: 10px !important; }
    #top_workspace, #workbench_row { flex-wrap: wrap !important; }
    #dataset_header,
    #recipe_header {
        width: 100% !important;
        max-width: none !important;
        max-height: none !important;
        flex: 1 1 100% !important;
        overflow: visible !important;
    }
    #dataset_header > *,
    #recipe_header > * {
        flex-shrink: 1 !important;
    }
    #dataset_quick_row,
    #dataset_title_row,
    #recipe_save_row,
    #recipe_ai_row {
        flex-wrap: wrap !important;
        align-items: stretch !important;
    }
    #selection_buttons_row,
    #gallery_sort_select_row,
    #csv_actions_row,
    #md_actions_row {
        flex-wrap: wrap !important;
    }
    #selection_buttons_row > div,
    #gallery_sort_select_row > div,
    #csv_actions_row > div,
    #md_actions_row > div {
        flex: 1 1 calc(50% - 4px) !important;
        min-width: 0 !important;
    }
    #selection_tools_group > .form {
        grid-template-columns: 1fr !important;
    }
    #dataset_settings_col {
        flex: 1 1 100% !important;
    }
    #dataset_path_col,
    #dataset_drop_col,
    #recipe_save_row > .form,
    #recipe_ai_row > .form {
        flex: 1 1 100% !important;
        width: 100% !important;
        min-width: 0 !important;
    }
    #recipe_save_row button,
    #recipe_ai_row button,
    #ai_recipe_btn,
    #analyze_recipe_btn {
        flex: 1 1 calc(50% - 4px) !important;
        width: auto !important;
        max-width: none !important;
        min-width: 0 !important;
    }
    #left_panel, #right_panel, #center_panel {
        position: relative !important;
        top: auto !important;
        width: 100% !important;
        max-width: none !important;
        min-width: 0 !important;
        height: auto !important;
        max-height: none !important;
    }
    #dataset_header,
    #recipe_header,
    #left_panel,
    #right_panel,
    .panel-purple {
        padding: 10px !important;
    }
    #app_title h1 { font-size: 1.32rem !important; }
    .gradio-container button { min-height: 36px !important; }
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

    function getGalleryFolderLabels() {
        return Array.from(document.querySelectorAll('#main_gallery button')).map(btn => {
            const marker = "__IDR_FOLDER__";
            const endMarker = "__IDR_END__";
            const text = btn.textContent || "";
            const pos = text.indexOf(marker);
            if (pos < 0) return "";
            const end = text.indexOf(endMarker, pos + marker.length);
            const raw = end >= 0 ? text.slice(pos + marker.length, end) : text.slice(pos + marker.length);
            return raw.trim();
        });
    }

    function hideGalleryFolderMarkers(btn) {
        const marker = "__IDR_FOLDER__";
        if (!btn || !(btn.textContent || "").includes(marker)) return;
        btn.querySelectorAll('figcaption, .caption, [class*="caption"], [class*="label"], span, p, div').forEach(el => {
            if ((el.textContent || "").includes(marker)) {
                el.style.display = 'none';
                el.setAttribute('aria-hidden', 'true');
            }
        });
    }

    function directGalleryItems(parent) {
        if (!parent || !parent.children) return [];
        return Array.from(parent.children).filter(child => {
            if (!child || !child.matches) return false;
            if (child.classList.contains('gallery-folder-separator')) return true;
            return child.matches('button') || !!child.querySelector?.('button');
        });
    }

    function galleryTileForButton(btn) {
        const gallery = document.getElementById('main_gallery');
        let node = btn;
        while (node && node.parentElement && node.parentElement !== gallery) {
            const parent = node.parentElement;
            const itemCount = directGalleryItems(parent).length;
            if (itemCount >= 2) return node;
            node = parent;
        }
        return btn;
    }

    function getManualGalleryColumnCount() {
        const wrapper = document.getElementById('gallery_cols_slider');
        const input = wrapper ? wrapper.querySelector('input[type="number"], input[type="range"], input') : null;
        let value = parseInt(input?.value || "", 10);
        if (!Number.isFinite(value)) {
            const txt = wrapper?.innerText || "";
            const match = txt.match(/\b([1-6])\b/g);
            value = match && match.length ? parseInt(match[match.length - 1], 10) : 4;
        }
        return Math.max(1, Math.min(6, value || 4));
    }

    function applyManualGalleryColumns(btns) {
        const cols = getManualGalleryColumnCount();
        const containers = new Set();
        btns.forEach(btn => {
            const tile = galleryTileForButton(btn);
            if (tile?.parentElement) containers.add(tile.parentElement);
        });
        containers.forEach(container => {
            container.classList.add('idr-manual-gallery-grid');
            container.style.setProperty('--idr-manual-gallery-cols', String(cols));
        });
    }

    function renderGalleryFolderSeparators() {
        const gallery = document.getElementById('main_gallery');
        const btns = Array.from(document.querySelectorAll('#main_gallery button'));
        if (!gallery || !btns.length) return;
        applyManualGalleryColumns(btns);
        const labels = getGalleryFolderLabels();
        gallery.querySelectorAll('.gallery-folder-separator').forEach(row => {
            const idx = Number(row.dataset.galleryFolderIndex);
            const tile = Number.isInteger(idx) && btns[idx] ? galleryTileForButton(btns[idx]) : null;
            if (!tile || !labels[idx] || row.nextElementSibling !== tile) {
                row.remove();
            }
        });
        btns.forEach((btn, idx) => {
            btn.querySelectorAll('.gallery-folder-separator').forEach(el => el.remove());
            btn.classList.remove('has-folder-separator');
            hideGalleryFolderMarkers(btn);
            const labelText = labels[idx] || "";
            if (!labelText) return;
            const tile = galleryTileForButton(btn);
            let sep = tile.previousElementSibling;
            if (!sep || !sep.classList || !sep.classList.contains('gallery-folder-separator')) {
                sep = document.createElement('div');
                sep.className = 'gallery-folder-separator';
                tile.parentNode.insertBefore(sep, tile);
            }
            sep.dataset.galleryFolderIndex = String(idx);
            if (sep.textContent !== labelText) sep.textContent = labelText;
        });
    }
    window.renderGalleryFolderSeparators = renderGalleryFolderSeparators;

    let gallerySeparatorTimer = null;
    function scheduleGalleryFolderSeparators() {
        if (gallerySeparatorTimer) clearTimeout(gallerySeparatorTimer);
        gallerySeparatorTimer = setTimeout(renderGalleryFolderSeparators, 120);
    }

    function updateGalleryVisuals() {
        document.querySelectorAll('#main_gallery button').forEach((btn, idx) => {
            btn.classList.toggle('custom-selected', window.gallerySelectedIndices.has(idx));
        });
        scheduleGalleryFolderSeparators();
    }
    window.updateGalleryVisuals = updateGalleryVisuals;
    function syncWithPython(viewIndex) {
        const payload = { selected: Array.from(window.gallerySelectedIndices), viewIndex: viewIndex };
        const wrapper = document.getElementById('hidden_sync_input');
        const inputEl = wrapper ? wrapper.querySelector('textarea, input') : null;
        if (inputEl) {
            setNativeValue(inputEl, JSON.stringify(payload));
            setTimeout(() => { const btn = document.getElementById('hidden_sync_btn'); if (btn) btn.click(); }, 30);
        }
    }
    window.syncWithPython = syncWithPython;
    window.selectAllGallery = function() {
        const btns = document.querySelectorAll('#main_gallery button');
        window.gallerySelectedIndices = new Set();
        btns.forEach((b, i) => window.gallerySelectedIndices.add(i));
        updateGalleryVisuals();
        if (btns.length > 0) syncWithPython(window.lastClickedIndex !== -1 ? window.lastClickedIndex : 0);
    };
    window.clearGallerySelection = function() {
        window.gallerySelectedIndices = new Set();
        updateGalleryVisuals();
    };

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

    function setupLiveTranslationBridge() {
        const wrapper = document.getElementById('viewer_caption_area');
        const inp = wrapper ? wrapper.querySelector('textarea') : null;
        if (!inp || inp.dataset.liveTranslationBridge) return;
        inp.dataset.liveTranslationBridge = "true";
        let timer = null;
        inp.addEventListener("input", function() {
            if (window.__idrReverseTranslationUpdating) return;
            clearTimeout(timer);
            timer = setTimeout(() => {
                window.__idrLiveTranslationUpdating = true;
                const btn = document.getElementById('hidden_live_translation_btn');
                if (btn) btn.click();
                setTimeout(() => { window.__idrLiveTranslationUpdating = false; }, 900);
            }, 140);
        });
    }

    function setupReverseTranslationBridge() {
        const wrapper = document.getElementById('live_translation_preview');
        const inp = wrapper ? wrapper.querySelector('textarea') : null;
        if (!inp || inp.dataset.reverseTranslationBridge) return;
        inp.dataset.reverseTranslationBridge = "true";
        let timer = null;
        inp.addEventListener("input", function() {
            if (window.__idrLiveTranslationUpdating) return;
            clearTimeout(timer);
            timer = setTimeout(() => {
                window.__idrReverseTranslationUpdating = true;
                const btn = document.getElementById('hidden_reverse_translation_btn');
                if (btn) btn.click();
                setTimeout(() => { window.__idrReverseTranslationUpdating = false; }, 900);
            }, 180);
        });
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

    function installLanguageAutodetect() {
        const langKey = "idr_language_initialized";
        const radios = Array.from(document.querySelectorAll('#language_selector input[type="radio"]'));
        if (!radios.length) return;
        radios.forEach(radio => {
            if (!radio.dataset.langPersistReady) {
                radio.dataset.langPersistReady = "true";
                radio.addEventListener("change", () => {
                    if (radio.checked) localStorage.setItem(langKey, "manual");
                });
            }
        });
        if (localStorage.getItem(langKey)) return;
        const browserLang = (navigator.language || (navigator.languages && navigator.languages[0]) || "en").toLowerCase();
        const desired = browserLang.startsWith("fr") ? "FR" : "EN";
        const target = radios.find(r => (r.value || "").toUpperCase() === desired);
        if (target && !target.checked) {
            target.click();
        }
        localStorage.setItem(langKey, "auto");
    }

    window.__idrManualCropState = window.__idrManualCropState || {
        img: null,
        ratio: "1:1",
        frame: null,
        scale: 1,
        panX: 0,
        panY: 0,
        dragging: false,
        dragMode: "pan",
        lastX: 0,
        lastY: 0,
        activeHandle: null
    };

    function manualCropEls() {
        return {
            tool: document.getElementById('manual_crop_canvas_tool'),
            canvas: document.getElementById('manual_crop_canvas'),
            status: document.getElementById('manual_crop_canvas_status'),
            payloadWrap: document.getElementById('hidden_manual_crop_payload'),
            payloadInput: document.querySelector('#hidden_manual_crop_payload textarea, #hidden_manual_crop_payload input'),
            payloadBtn: document.getElementById('hidden_manual_crop_btn')
        };
    }

    function manualCropSetStatus(text, warn=false) {
        const { status } = manualCropEls();
        if (!status) return;
        status.textContent = text;
        status.style.color = warn ? '#fbbf24' : '#bffcf3';
    }

    function manualCropCanvasSize(canvas) {
        const rect = canvas.getBoundingClientRect();
        const dpr = window.devicePixelRatio || 1;
        const width = Math.max(420, Math.round(rect.width * dpr));
        const height = Math.max(280, Math.round(rect.height * dpr));
        if (canvas.width !== width || canvas.height !== height) {
            canvas.width = width;
            canvas.height = height;
        }
        return { width, height, dpr };
    }

    function manualCropRatioValue(ratio) {
        if (!ratio || ratio === "free") return null;
        const parts = ratio.split(':').map(Number);
        if (parts.length !== 2 || !parts[0] || !parts[1]) return 1;
        return parts[0] / parts[1];
    }

    function manualCropStatusText(prefix="") {
        const st = window.__idrManualCropState;
        const ratio = st.ratio && st.ratio !== "free" ? st.ratio : (st.ratio === "free" ? "Free" : "");
        const size = st.img ? `${st.img.naturalWidth}x${st.img.naturalHeight}` : "";
        return [prefix, size, ratio ? `ratio ${ratio}` : ""].filter(Boolean).join(" · ");
    }

    function manualCropSyncRatioButtons() {
        const { tool } = manualCropEls();
        if (!tool) return;
        const st = window.__idrManualCropState;
        tool.querySelectorAll('.manual-ratio-btn').forEach(btn => {
            btn.classList.toggle('active', (btn.dataset.ratio || "") === st.ratio);
        });
    }

    function manualCropApplyRatio(ratio) {
        const st = window.__idrManualCropState;
        st.ratio = ratio || "1:1";
        st.frame = null;
        manualCropSyncRatioButtons();
        if (st.img) manualCropResetImage();
        else manualCropDraw();
        manualCropSetStatus(manualCropStatusText());
    }

    function manualCropInvertRatio() {
        const st = window.__idrManualCropState;
        const parts = (st.ratio || "").split(':').map(Number);
        if (st.ratio === "free" || parts.length !== 2 || !parts[0] || !parts[1]) {
            manualCropSetStatus(manualCropStatusText('Free ratio has no orientation'), true);
            return;
        }
        if (parts[0] === parts[1]) {
            manualCropSetStatus(manualCropStatusText('Square ratio unchanged'));
            return;
        }
        manualCropApplyRatio(`${parts[1]}:${parts[0]}`);
    }

    function manualCropComputeFrame(width, height) {
        const st = window.__idrManualCropState;
        const margin = Math.round(Math.min(width, height) * 0.11);
        const maxW = width - margin * 2;
        const maxH = height - margin * 2;
        const ratio = manualCropRatioValue(st.ratio);
        if (!ratio) {
            if (!st.frame) {
                st.frame = { x: margin, y: margin, w: maxW, h: maxH };
            } else {
                st.frame.x = Math.max(8, Math.min(st.frame.x, width - 64));
                st.frame.y = Math.max(8, Math.min(st.frame.y, height - 64));
                st.frame.w = Math.max(64, Math.min(st.frame.w, width - st.frame.x - 8));
                st.frame.h = Math.max(64, Math.min(st.frame.h, height - st.frame.y - 8));
            }
            return st.frame;
        }
        let w = maxW;
        let h = w / ratio;
        if (h > maxH) {
            h = maxH;
            w = h * ratio;
        }
        st.frame = { x: (width - w) / 2, y: (height - h) / 2, w, h };
        return st.frame;
    }

    function manualCropDraw() {
        const { canvas, tool } = manualCropEls();
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        const { width, height } = manualCropCanvasSize(canvas);
        const st = window.__idrManualCropState;
        ctx.clearRect(0, 0, width, height);
        ctx.fillStyle = '#071019';
        ctx.fillRect(0, 0, width, height);
        const frame = manualCropComputeFrame(width, height);
        if (!st.img) {
            ctx.fillStyle = '#93a4b7';
            ctx.font = `${Math.round(14 * (window.devicePixelRatio || 1))}px system-ui, sans-serif`;
            ctx.textAlign = 'center';
            ctx.fillText(tool?.dataset?.empty || 'Load the current image to begin.', width / 2, height / 2);
            return;
        }
        const drawW = st.img.naturalWidth * st.scale;
        const drawH = st.img.naturalHeight * st.scale;
        const drawX = frame.x + frame.w / 2 - drawW / 2 + st.panX;
        const drawY = frame.y + frame.h / 2 - drawH / 2 + st.panY;
        ctx.imageSmoothingQuality = 'high';
        ctx.drawImage(st.img, drawX, drawY, drawW, drawH);

        ctx.save();
        ctx.fillStyle = 'rgba(0, 0, 0, 0.62)';
        ctx.fillRect(0, 0, width, frame.y);
        ctx.fillRect(0, frame.y + frame.h, width, height - frame.y - frame.h);
        ctx.fillRect(0, frame.y, frame.x, frame.h);
        ctx.fillRect(frame.x + frame.w, frame.y, width - frame.x - frame.w, frame.h);
        ctx.strokeStyle = 'rgba(45, 212, 191, 0.95)';
        ctx.lineWidth = 2 * (window.devicePixelRatio || 1);
        ctx.strokeRect(frame.x, frame.y, frame.w, frame.h);
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.28)';
        ctx.lineWidth = 1 * (window.devicePixelRatio || 1);
        for (let i = 1; i < 3; i++) {
            ctx.beginPath();
            ctx.moveTo(frame.x + frame.w * i / 3, frame.y);
            ctx.lineTo(frame.x + frame.w * i / 3, frame.y + frame.h);
            ctx.moveTo(frame.x, frame.y + frame.h * i / 3);
            ctx.lineTo(frame.x + frame.w, frame.y + frame.h * i / 3);
            ctx.stroke();
        }
        if (st.ratio === "free") {
            const hs = 10 * (window.devicePixelRatio || 1);
            ctx.fillStyle = '#2dd4bf';
            [[frame.x, frame.y], [frame.x + frame.w, frame.y], [frame.x, frame.y + frame.h], [frame.x + frame.w, frame.y + frame.h]].forEach(([x, y]) => {
                ctx.fillRect(x - hs / 2, y - hs / 2, hs, hs);
            });
        }
        ctx.restore();
    }

    function manualCropClampPan() {
        const { canvas } = manualCropEls();
        const st = window.__idrManualCropState;
        if (!canvas || !st.img) return;
        const { width, height } = manualCropCanvasSize(canvas);
        const frame = manualCropComputeFrame(width, height);
        const minScale = Math.max(frame.w / st.img.naturalWidth, frame.h / st.img.naturalHeight);
        st.scale = Math.max(minScale, Math.min(st.scale, minScale * 8));
        const drawW = st.img.naturalWidth * st.scale;
        const drawH = st.img.naturalHeight * st.scale;
        const maxX = Math.max(0, (drawW - frame.w) / 2);
        const maxY = Math.max(0, (drawH - frame.h) / 2);
        st.panX = Math.max(-maxX, Math.min(maxX, st.panX));
        st.panY = Math.max(-maxY, Math.min(maxY, st.panY));
    }

    function manualCropResetImage() {
        const { canvas } = manualCropEls();
        const st = window.__idrManualCropState;
        if (!canvas || !st.img) return;
        const { width, height } = manualCropCanvasSize(canvas);
        const frame = manualCropComputeFrame(width, height);
        st.scale = Math.max(frame.w / st.img.naturalWidth, frame.h / st.img.naturalHeight);
        st.panX = 0;
        st.panY = 0;
        manualCropClampPan();
        manualCropDraw();
    }

    function manualCropSourceImage() {
        const sources = [
            document.getElementById('viewer_area'),
            document.getElementById('manual_crop_editor'),
            document.getElementById('main_gallery')
        ].filter(Boolean);
        for (const source of sources) {
            const imgs = Array.from(source.querySelectorAll('img')).filter(img => {
                const src = img.currentSrc || img.src || '';
                return src && !src.startsWith('data:image/svg') && img.naturalWidth > 0;
            });
            if (imgs.length) return imgs[0];
        }
        return null;
    }

    window.idrManualCropLoadFromEditor = function() {
        const source = manualCropSourceImage();
        if (!source) {
            manualCropSetStatus('Current viewer image not ready yet.', true);
            return;
        }
        const img = new Image();
        img.crossOrigin = 'anonymous';
        img.onload = () => {
            const st = window.__idrManualCropState;
            st.img = img;
            st.frame = null;
            manualCropResetImage();
            manualCropSetStatus(manualCropStatusText());
        };
        img.onerror = () => manualCropSetStatus('Could not load source image.', true);
        img.src = source.src + (source.src.includes('?') ? '&' : '?') + 'cropcache=' + Date.now();
    };

    function manualCropHandleAt(x, y) {
        const st = window.__idrManualCropState;
        if (st.ratio !== "free" || !st.frame) return null;
        const dpr = window.devicePixelRatio || 1;
        const hit = 18 * dpr;
        const f = st.frame;
        const handles = [
            ['nw', f.x, f.y], ['ne', f.x + f.w, f.y],
            ['sw', f.x, f.y + f.h], ['se', f.x + f.w, f.y + f.h]
        ];
        for (const [name, hx, hy] of handles) {
            if (Math.abs(x - hx) <= hit && Math.abs(y - hy) <= hit) return name;
        }
        return null;
    }

    function manualCropPointerPos(e) {
        const { canvas } = manualCropEls();
        const rect = canvas.getBoundingClientRect();
        const dpr = window.devicePixelRatio || 1;
        return { x: (e.clientX - rect.left) * dpr, y: (e.clientY - rect.top) * dpr };
    }

    function manualCropResizeFrame(handle, dx, dy) {
        const { canvas } = manualCropEls();
        const st = window.__idrManualCropState;
        if (st.ratio !== "free" || !st.frame || !canvas) return;
        const { width, height } = manualCropCanvasSize(canvas);
        const f = st.frame;
        if (handle.includes('w')) { f.x += dx; f.w -= dx; }
        if (handle.includes('e')) { f.w += dx; }
        if (handle.includes('n')) { f.y += dy; f.h -= dy; }
        if (handle.includes('s')) { f.h += dy; }
        if (f.w < 64) f.w = 64;
        if (f.h < 64) f.h = 64;
        if (f.x < 8) { f.w += f.x - 8; f.x = 8; }
        if (f.y < 8) { f.h += f.y - 8; f.y = 8; }
        if (f.x + f.w > width - 8) f.w = width - 8 - f.x;
        if (f.y + f.h > height - 8) f.h = height - 8 - f.y;
    }

    function manualCropPayload() {
        const { canvas } = manualCropEls();
        const st = window.__idrManualCropState;
        if (!canvas || !st.img || !st.frame) return null;
        const { width, height } = manualCropCanvasSize(canvas);
        const frame = manualCropComputeFrame(width, height);
        manualCropClampPan();
        const drawW = st.img.naturalWidth * st.scale;
        const drawH = st.img.naturalHeight * st.scale;
        const drawX = frame.x + frame.w / 2 - drawW / 2 + st.panX;
        const drawY = frame.y + frame.h / 2 - drawH / 2 + st.panY;
        let x = (frame.x - drawX) / st.scale;
        let y = (frame.y - drawY) / st.scale;
        let w = frame.w / st.scale;
        let h = frame.h / st.scale;
        x = Math.max(0, Math.min(st.img.naturalWidth - 1, x));
        y = Math.max(0, Math.min(st.img.naturalHeight - 1, y));
        w = Math.max(1, Math.min(st.img.naturalWidth - x, w));
        h = Math.max(1, Math.min(st.img.naturalHeight - y, h));
        return { ratio: st.ratio, crop: { x, y, w, h }, sourceSize: { w: st.img.naturalWidth, h: st.img.naturalHeight } };
    }

    function manualCropCommit(goNext=false) {
        const { payloadInput, payloadBtn } = manualCropEls();
        const payload = manualCropPayload();
        if (!payload) {
            manualCropSetStatus('Load an image first.', true);
            return;
        }
        payload.goNext = !!goNext;
        window.__idrManualCropGoNext = false;
        if (payloadInput && payloadBtn) {
            setNativeValue(payloadInput, JSON.stringify(payload));
            manualCropSetStatus(goNext ? 'Saving crop and moving next...' : 'Saving crop...');
            payloadBtn.click();
        }
    }

    function manualCropIsUsable() {
        const { tool, canvas } = manualCropEls();
        if (!tool || !canvas) return false;
        const r = tool.getBoundingClientRect();
        const visible = !!(r.width || r.height || tool.getClientRects().length);
        if (!visible) return false;
        const intersectsViewport = r.bottom > 0 && r.top < window.innerHeight;
        const focusInside = tool.contains(document.activeElement);
        return intersectsViewport || focusInside;
    }

    function setupManualCropTool() {
        const { canvas } = manualCropEls();
        const tool = document.getElementById('manual_crop_canvas_tool');
        if (!canvas || !tool || tool.dataset.cropReady) return;
        tool.dataset.cropReady = "true";
        const st = window.__idrManualCropState;
        tool.querySelectorAll('.manual-ratio-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                manualCropApplyRatio(btn.dataset.ratio || "1:1");
            });
        });
        document.getElementById('manual_crop_use_loaded')?.addEventListener('click', () => window.idrManualCropLoadFromEditor());
        document.getElementById('manual_crop_overwrite')?.addEventListener('click', () => manualCropCommit(false));
        canvas.addEventListener('pointerdown', e => {
            if (!st.img) return;
            const pos = manualCropPointerPos(e);
            st.dragging = true;
            st.activeHandle = manualCropHandleAt(pos.x, pos.y);
            st.dragMode = st.activeHandle ? 'resize' : 'pan';
            st.lastX = pos.x;
            st.lastY = pos.y;
            canvas.classList.add('dragging');
            canvas.setPointerCapture(e.pointerId);
        });
        canvas.addEventListener('pointermove', e => {
            if (!st.dragging) return;
            const pos = manualCropPointerPos(e);
            const dx = pos.x - st.lastX;
            const dy = pos.y - st.lastY;
            if (st.dragMode === 'resize') {
                manualCropResizeFrame(st.activeHandle, dx, dy);
            } else {
                st.panX += dx;
                st.panY += dy;
                manualCropClampPan();
            }
            st.lastX = pos.x;
            st.lastY = pos.y;
            manualCropDraw();
        });
        canvas.addEventListener('pointerup', e => {
            st.dragging = false;
            st.activeHandle = null;
            canvas.classList.remove('dragging');
            try { canvas.releasePointerCapture(e.pointerId); } catch(err) {}
        });
        canvas.addEventListener('wheel', e => {
            if (!st.img) return;
            e.preventDefault();
            const factor = e.deltaY < 0 ? 1.08 : 0.925;
            st.scale *= factor;
            manualCropClampPan();
            manualCropDraw();
        }, { passive: false });
        window.addEventListener('resize', () => setTimeout(manualCropDraw, 80));
        manualCropDraw();
    }

    if (!window.__idrManualCropKeyboardReady) {
        window.__idrManualCropKeyboardReady = true;
        document.addEventListener('keydown', function(e) {
            if (!manualCropIsUsable()) return;
            const target = e.target;
            const isInput = target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable);
            if (isInput) return;
            if (e.code === 'ArrowLeft') {
                e.preventDefault();
                e.stopPropagation();
                document.getElementById('manual_crop_prev_btn')?.click();
                return;
            }
            if (e.code === 'ArrowRight') {
                e.preventDefault();
                e.stopPropagation();
                document.getElementById('manual_crop_next_btn')?.click();
                return;
            }
            if (e.code === 'ArrowUp' || e.code === 'ArrowDown') {
                e.preventDefault();
                e.stopPropagation();
                manualCropInvertRatio();
                return;
            }
            if (e.code === 'Enter') {
                e.preventDefault();
                e.stopPropagation();
                manualCropCommit(true);
            }
        }, true);
    }

    setupDatasetPathDropZone();
    installStaticTooltips();
    installLanguageAutodetect();
    setupManualCropTool();
    setupLiveTranslationBridge();
    setupReverseTranslationBridge();

    const observer = new MutationObserver(() => { 
        updateGalleryVisuals(); setupAutocomplete(); setupLiveTranslationBridge(); setupReverseTranslationBridge(); setupDatasetPathDropZone(); installStaticTooltips(); installLanguageAutodetect(); setupManualCropTool();
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
        if (e.code === 'Escape') {
            const searchBox = document.querySelector('input[placeholder*="mot"], input[placeholder*="word"]');
            if (searchBox && document.activeElement === searchBox) {
                e.preventDefault(); e.stopPropagation();
                setNativeValue(searchBox, '');
                searchBox.dispatchEvent(new Event('input', { bubbles: true }));
                return;
            }
        }
        if ((e.ctrlKey || e.metaKey) && e.shiftKey && (e.code === 'KeyC' || e.key.toLowerCase() === 'c')) {
            e.preventDefault(); e.stopPropagation();
            const capArea = document.querySelector('#viewer_caption_area textarea');
            if (capArea && capArea.value) navigator.clipboard.writeText(capArea.value);
            return;
        }
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

        if ((e.ctrlKey || e.metaKey) && !e.shiftKey && (e.code === 'KeyD' || e.key.toLowerCase() === 'd')) {
            if (isInput) return;
            e.preventDefault(); e.stopPropagation();
            document.getElementById('hidden_copy_next_btn')?.click();
            return;
        }
        if ((e.ctrlKey || e.metaKey) && (e.code === 'KeyZ' || e.key.toLowerCase() === 'z') && !e.shiftKey) {
            if (isInput) return;
            e.preventDefault(); e.stopPropagation();
            document.getElementById('btn_undo')?.click();
            return;
        }
        if ((e.ctrlKey || e.metaKey) && !e.shiftKey && !e.altKey && e.key >= '1' && e.key <= '6') {
            if (isInput) return;
            e.preventDefault(); e.stopPropagation();
            const tabIdx = parseInt(e.key) - 1;
            const allTabLabels = Array.from(document.querySelectorAll('.tab-container.visually-hidden button'));
            const targetLabel = allTabLabels[tabIdx]?.textContent?.trim();
            if (!targetLabel) {
                const tabs = document.querySelectorAll('button[role="tab"]');
                if (tabs[tabIdx]) tabs[tabIdx].click();
                return;
            }
            const visibleTab = Array.from(document.querySelectorAll('button[role="tab"]')).find(btn => btn.textContent.trim() === targetLabel);
            if (visibleTab) {
                visibleTab.click();
                return;
            }
            const overflowItem = Array.from(document.querySelectorAll('.overflow-dropdown button')).find(btn => btn.textContent.trim() === targetLabel);
            if (overflowItem) {
                if (overflowItem.closest('.overflow-dropdown')?.classList.contains('hide')) {
                    document.querySelector('.overflow-menu > button')?.click();
                }
                setTimeout(() => overflowItem.click(), 30);
            }
            return;
        }
        if ((e.ctrlKey || e.metaKey) && (e.code === 'KeyF' || e.key.toLowerCase() === 'f')) { e.preventDefault(); e.stopPropagation(); const searchBox = document.querySelector('input[placeholder*="mot"], input[placeholder*="word"]'); if (searchBox) { searchBox.focus(); searchBox.select(); } return; }
        if (e.altKey && (e.code === 'KeyS' || e.key.toLowerCase() === 's')) { e.preventDefault(); e.stopPropagation(); document.getElementById('toggle_tag_btn')?.click(); return; }
        if ((e.ctrlKey || e.metaKey) && (e.code === 'KeyS' || e.key.toLowerCase() === 's')) { e.preventDefault(); e.stopPropagation(); document.getElementById('save_single_btn')?.click(); return; }
        if (e.altKey && (e.code === 'KeyC' || e.key.toLowerCase() === 'c')) { e.preventDefault(); e.stopPropagation(); document.getElementById('clear_sel_btn')?.click(); return; }
        
        if (e.code === 'PageUp') { e.preventDefault(); document.getElementById('prev_btn')?.click(); return; }
        if (e.code === 'PageDown') { e.preventDefault(); document.getElementById('next_btn')?.click(); return; }
        if (isInput) return;
        if (e.code === 'Delete') {
            e.preventDefault(); e.stopPropagation();
            if (confirm('⚠️ Supprimer cette image définitivement ? / Delete this image permanently?')) {
                document.getElementById('hidden_delete_current_btn')?.click();
            }
            return;
        }
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
        if (selInput && selInput.value && selInput.value.startsWith('__SET_SELECTION__')) {
            try {
                const payload = JSON.parse(selInput.value.substring('__SET_SELECTION__'.length));
                window.gallerySelectedIndices = new Set((payload.selected || []).map(Number));
                window.lastClickedIndex = Number.isInteger(payload.viewIndex) ? payload.viewIndex : window.lastClickedIndex;
                updateGalleryVisuals();
                selInput.value = '__SELECTION_APPLIED__';
            } catch(err) {
                selInput.value = '__SELECTION_ERROR__';
            }
        }
        if (selInput && selInput.value === '{}' && window.gallerySelectedIndices.size > 0) {
            window.gallerySelectedIndices.clear();
            updateGalleryVisuals();
        }
    }, 150);
}
"""

