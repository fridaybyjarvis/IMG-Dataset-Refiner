# Prompt de reprise - IMG Dataset Refiner v4.3 Pro

Copie ce document dans une nouvelle conversation IA si tu veux reprendre le développement de **IMG Dataset Refiner** dans plusieurs semaines ou plusieurs mois.

## Rôle attendu

Agis comme un développeur expert en **Python**, **Gradio 4+/6**, interfaces locales, JavaScript natif injecté, outils Stable Diffusion / Flux / LoRA, et intégration d'APIs IA locales.

Tu dois analyser le code avant de modifier quoi que ce soit. Le fichier principal contient beaucoup de contournements Gradio/Svelte sensibles : il ne faut pas refactorer brutalement ni remplacer le JavaScript custom sans comprendre ses effets.

## Fichiers essentiels à fournir à l'IA

À joindre en priorité :

1. `lora_manager.py`
2. `languages/fr.json`
3. `languages/en.json`
4. `requirements.txt`
5. `Changelog.md`
6. `Prompt_system.md`

À joindre si la demande concerne la configuration ou l'état utilisateur :

7. `ai_settings.json`
8. `ui_settings.json`
9. `lora_recipes.json`
10. `ai_recipes.json` si présent
11. `favorites.json` si présent
12. `SUGGESTIONS.md` si présent

À joindre si la demande concerne la documentation ou la publication GitHub :

13. `readme.md`
14. `start.bat`
15. `install.bat`

## Contexte du projet

Nous avons développé un outil local nommé **IMG Dataset Refiner v4.3 Pro**.

C'est un gestionnaire complet de datasets image + captions `.txt` pour :

- visualiser des images;
- éditer et traduire des captions;
- appliquer des opérations batch;
- gérer une bibliothèque custom de mots;
- détecter les doublons visuels;
- pré-traiter et redimensionner les images;
- analyser les biais de tags;
- créer une recette globale;
- simuler et exporter un dataset équilibré;
- utiliser des modèles LLM/VLM locaux ou cloud.

## Technologies principales

- Python
- Gradio 4+ / Gradio 6
- JavaScript natif injecté via `custom_js`
- Pandas
- Plotly
- Pillow
- requests
- deep-translator
- imagehash
- opencv-python / cv2
- Ollama
- LM Studio
- APIs OpenAI-compatible
- Anthropic Claude
- Google Gemini

## Architecture à comprendre avant modification

Le fichier `lora_manager.py` contient :

- constantes globales;
- chargement dynamique des langues;
- CSS global;
- `custom_js`, très sensible;
- fonctions de chargement de dataset;
- fonctions de synchronisation galerie/backend;
- fonctions batch;
- fonctions de traduction;
- fonctions d'export;
- fonctions IA;
- construction Gradio complète;
- câblage des événements.

Les fichiers `fr.json` et `en.json` pilotent presque tous les textes d'interface. Toute nouvelle UI visible doit idéalement ajouter ses clés dans les deux fichiers.

## Points sensibles Gradio / JavaScript

L'application contourne plusieurs limites de Gradio :

1. **Bibliothèque custom HTML**
   - Gradio/Svelte supprime les `onclick`.
   - Le code utilise donc `document.addEventListener` + `data-idx` + horodatage pour synchroniser les clics avec Python.

2. **Galerie multi-sélection**
   - La galerie visuelle est synchronisée avec Python via un champ caché et un bouton caché.
   - La sélection est stockée côté JS dans `window.gallerySelectedIndices`.

3. **Composants cachés**
   - Certains composants doivent rester dans le DOM.
   - Ne pas se contenter de `visible=False` si le JS doit les trouver.
   - Le CSS masque plusieurs composants via `display: none !important`.

4. **Raccourcis clavier**
   - Flèches, `PageUp/PageDown`, `Ctrl+S`, `Alt+S`, etc.
   - Ne pas casser le focus de l'éditeur de caption.

5. **Drag & Drop dataset**
   - Le navigateur peut masquer les chemins absolus.
   - Le JS envoie une signature de dossier.
   - Python tente de retrouver le dossier via favoris, chemins probables, dossier utilisateur et lecteurs locaux.

6. **Drag & Drop DataFrame**
   - Le tableau d'export possède un drag/drop simple des lignes.
   - Ne pas introduire de listener global agressif sur tous les clics de la page.
   - La multi-sélection avancée du tableur a déjà causé des régressions et doit être réintroduite seulement avec un design isolé et testé.

## Règles critiques de stabilité

Ces règles sont très importantes :

- Ne pas passer `custom_js` via `launch(js=...)`.
- Garder l'injection du JS via `app.load(..., js=custom_js)`.
- Ne pas combiner `custom_js` avec des outputs Gradio dans le même `app.load`.
- Ne pas faire `app.load(... outputs=[gallery])` pour mettre à jour `Gallery` au chargement.
- Ne pas mettre à jour `Gallery` au chargement de page pour restaurer les colonnes : cela peut provoquer une boucle Gradio/Svelte `flush` et bloquer les onglets.
- Pour les préférences UI comme les colonnes galerie, lire le fichier au démarrage Python et initialiser les composants avec la bonne valeur.
- Tester les onglets après toute modification liée à `app.load`, `Gallery`, `Tabs`, `Dataframe` ou `custom_js`.
- Si la console affiche une boucle `index-*.js: Uncaught ... flush`, suspecter une mise à jour frontend Gradio répétée ou un listener JS global trop large.
- Les messages navigateur `Tracking Prevention blocked access to storage for cdnjs iframe-resizer` sont généralement du bruit, pas la cause principale du gel.

## Préférences et fichiers de configuration

- `ai_settings.json`
  - backend IA;
  - modèles VLM/LLM;
  - modèle partagé LM Studio;
  - URL API;
  - clé API;
  - température;
  - contexte;
  - prompt système.

- `ui_settings.json`
  - préférences UI, notamment `gallery_columns`.
  - Le chemin doit être résolu depuis le dossier réel de `lora_manager.py`, pas depuis le répertoire courant.

- `lora_recipes.json`
  - recettes globales / règles d'export.

- `favorites.json`
  - favoris de dossiers datasets.

## Fonctionnalités actuelles importantes

- Chargement dataset par chemin, Browse, favoris, drag/drop.
- Galerie avec nombre de colonnes persistant.
- Éditeur de caption avec sauvegarde.
- Traduction live et traduction globale.
- Bibliothèque custom de mots.
- Batch cleaning.
- Pré-traitement d'images.
- Détection doublons visuels.
- Assistant IA local/cloud.
- LM Studio : refresh, modèles VLM/LLM, modèle partagé, load/unload, sauvegarde.
- Recette globale générée par IA depuis les captions.
- Profiling IA du dataset avec résumé compact.
- Statistiques générales et analytiques avancées.
- Export versionné avec simulation.

## Historique récent à ne pas oublier

Un bug critique a été corrigé :

- Symptôme : les onglets **Visualiseur & Édition**, **Édition en Batch**, **Pré-traitement & Doublons**, etc. ne répondaient plus, même sans dataset chargé.
- Console : répétition d'erreurs Gradio/Svelte `index-*.js: Uncaught ... flush`.
- Cause probable : mise à jour frontend de `Gallery` depuis `app.load(... outputs=[gallery])`.
- Correction : retirer l'update frontend de la galerie au chargement. La préférence des colonnes est appliquée au démarrage Python, pas via un événement frontend.

Un autre point important :

- Le drag/drop multi-sélection du tableur d'export a été tenté puis retiré.
- Le drag/drop simple reste actif.
- Si cette fonctionnalité est redemandée, proposer d'abord une approche prudente :
  - limiter strictement les listeners au conteneur `#export_recipe_df`;
  - ne pas utiliser de capture globale;
  - ne pas intercepter les boutons d'onglets;
  - tester les onglets avant de conclure.

## Mission lors d'une reprise

Quand tu reprends :

1. Lire `lora_manager.py` autour de :
   - `custom_js`;
   - `load_ui_settings`;
   - `update_gallery_columns`;
   - `handle_drag_and_drop`;
   - `call_ai_api`;
   - construction Gradio;
   - `app.load`;
   - `launch_kwargs`.

2. Lire `fr.json` et `en.json` si tu ajoutes une UI visible.

3. Ne pas supprimer les contournements JS sans comprendre pourquoi ils existent.

4. Après modification, vérifier au minimum :
   - `python -m py_compile lora_manager.py`;
   - `import lora_manager`;
   - démarrage Gradio;
   - clics sur tous les onglets;
   - galerie sans dataset chargé;
   - galerie après chargement d'un dataset;
   - console navigateur si possible.

5. Mettre à jour :
   - `Changelog.md`;
   - `readme.md` si la fonctionnalité est visible utilisateur;
   - `Prompt_system.md` si une nouvelle règle de stabilité est découverte.

## Style de développement souhaité

- Privilégier les petites corrections ciblées.
- Ne pas réécrire l'application entière.
- Garder la compatibilité Windows.
- Garder les chemins externes compatibles avec `allowed_paths`.
- Ne pas ajouter de dépendance lourde sans raison.
- Documenter toute contrainte Gradio/Svelte découverte.
- En cas de doute, préserver la stabilité de l'interface avant d'ajouter une fonctionnalité avancée.
