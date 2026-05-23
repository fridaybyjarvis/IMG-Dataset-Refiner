# **📝 Changelog \- IMG Dataset Refiner**

## **v4.3.2 Pro (UI/UX — Panels thématiques, Favoris repositionnés, double toggle latéral, Recette IA durcie)**

Cette mise à jour est principalement **esthétique et ergonomique**, plus une **correction comportementale ciblée** sur la génération de recette globale par IA. Aucune logique métier critique n'a été touchée. La structure Gradio reste fonctionnellement identique à v4.3.1, ce qui préserve la stabilité acquise sur les onglets et la galerie.

### **🤖 Recette IA : filtre strict + triggers en tête + extraction n-grams (correction comportementale)**

**Symptôme corrigé** : le bouton *🤖 Remplir par IA depuis les captions* pouvait renvoyer une recette polluée par des phrases descriptives complètes recopiées par le LLM (typiquement les sorties VLM type `"The image is a close-up portrait of a woman with..."`). Au lieu de mots-clés courts, on obtenait des pavés inutilisables comme recette globale. **Second cas non couvert au début** : pour des captions en **prose pure** (sans virgules type tag, comme les sorties brutes des VLM type `"The image shows a young man lying on the beach with his tentacles wrapped around his body. He is wearing a black wet suit..."`), aucun mot-clé n'était extrait du tout — l'IA n'avait quasiment rien à choisir.

**Causes identifiées** :

1. `_shared_caption_candidates` splittait les captions sur la virgule sans valider la longueur — une description sans virgule devenait un seul "tag" géant rejeté ensuite, donc zéro candidat exploitable.
2. Le prompt envoyé au LLM autorisait implicitement les phrases longues.
3. Le parser `_parse_ai_recipe_tags` filtrait par appartenance à `allowed_tags` mais sans contrôle de format.
4. Le trigger word/concept n'était pas explicitement placé en tête.

**Corrections apportées** :

* Nouveau filtre `_is_valid_keyword(tag)` (constantes `KEYWORD_MAX_WORDS = 6`, `KEYWORD_MAX_CHARS = 50`) appliqué à la fois côté candidats et côté parser. Rejette : phrases > 6 mots, tournures VLM (`The image`, `appears to`, `is wearing`, `il y a`, `on voit`, `porte un`, etc.), fragments terminés par un point.
* Nouvelle fonction `_detect_trigger_words(dataset, candidates)` qui repère les triggers LoRA (patterns leetspeak `D4lle`, `photosh00tsP0ses-S2`, identifiants à underscore `my_concept`, `ohwx_man`) en début de captions, et **les épingle en première position de la recette générée**, indépendamment de ce que renvoie le LLM.
* **Nouveau** : extracteur de **n-grams (1, 2 et 3 mots)** `_extract_keyword_ngrams(caption)` qui fonctionne sur les **captions en prose pure** (sorties VLM non structurées). Découpe la caption en phrases via la ponctuation, tokenise, retire les stopwords bilingues FR/EN (`the`, `is`, `a`, `on`, `le`, `la`, `est`, `dans`...) et extrait toutes les séquences continues de tokens utiles. Sur une caption comme `"The image shows a young man lying on the beach with his tentacles wrapped around his body. He is wearing a black wet suit..."`, l'extracteur produit désormais : `young man`, `beach`, `tentacles`, `black wet suit`, `wet suit`, `purple`, `cloudy sky`, `dark`, `mysterious`, etc. Avec plusieurs captions du même dataset, ces n-grams sont comptés inter-images, ce qui fait remonter naturellement les concepts vraiment partagés en tête de la liste de candidats envoyée au LLM.
* Les deux passes (split par virgule + extraction n-grams) sont **fusionnées** dans `_shared_caption_candidates`. Aucune régression sur le format `tag1, tag2, tag3` historique — il continue de fonctionner exactement comme avant, le n-gram ajoute juste de la matière quand la prose est pure.
* Prompt LLM entièrement réécrit : règles strictes numérotées, exemple de bonne réponse, exemple de mauvaise réponse, mention explicite du nombre maximum de mots par tag, interdiction des verbes conjugués de description, et injection des triggers détectés en hint.
* `candidate_limit` étendu (`max(limit * 5, 120)` au lieu de `max(limit * 4, 80)`) pour que le LLM voie davantage de contexte sur les concepts distinctifs rares.

**Résultat attendu** sur les deux scénarios problématiques :

* **Dataset Dalle (format tags)** : `D4lle, Dall-e style, AI generated, romantic atmosphere, dramatic lighting, portrait, dark background, ...` au lieu d'un pavé contenant des phrases entières recopiées.
* **Dataset tentacles (format prose VLM)** : à partir d'un ensemble de captions descriptives, l'IA reçoit maintenant les n-grams `young man`, `wet suit`, `black wet suit`, `tentacles`, `purple tentacles`, `cloudy sky`, `dark`, `mysterious` triés par fréquence inter-images, et peut produire une vraie recette globale.

Le trigger (s'il existe) est forcé en tête, les phrases descriptives sont systématiquement rejetées, et l'analyse repart automatiquement derrière comme avant grâce au `.success()` qui clique `hidden_calc_btn`.

### **🧹 Déduplication intelligente de la recette finale (anti-doublons)**

**Symptôme corrigé** : le LLM produisait parfois des recettes contenant des **variantes du même concept** ou des inclusions évidentes, par exemple `D4lle, AI, AI generated, Dall-e, Dall-e style` — 5 entrées dont 3 redondantes.

**Corrections apportées** :

* Nouvelle fonction `_normalize_tag_for_dedup(tag)` qui rapproche les variantes orthographiques : minuscules, suppression de la ponctuation interne (tirets, underscores, espaces), normalisation pluriel (`portraits` → `portrait`, `photoshoots` → `photoshoot`) et **leetspeak** (`0→o, 1→i, 3→e, 4→a, 5→s, 7→t`). Résultat : `D4lle`, `Dall-e` et `Dalle` se normalisent tous en `dalle` et sont reconnus comme identiques.
* Nouvelle fonction `_are_orthographic_variants(a, b, threshold=0.82)` qui utilise `difflib.SequenceMatcher` sur les formes normalisées. Seuil prudent (82 %) pour ne pas fusionner des concepts vraiment distincts comme `studio lighting` vs `dramatic lighting`.
* Nouvelle fonction `_deduplicate_recipe(tags, freq_lookup)` qui applique 3 passes : doublons exacts, variantes orthographiques (mergées en gardant la variante la plus fréquente sur le dataset), et **inclusion stricte d'un tag court "générique"** dans un tag plus long. La liste `_GENERIC_SHORT_TAGS` couvre les mots trop vagues pour rester seuls quand une version spécifique existe : `ai`, `art`, `photo`, `image`, `man`, `woman`, `body`, `style`, `look`, `mood`, etc. — `dark` n'y est **pas** car il garde sa valeur même à côté de `dark mysterious`.
* Règle 7 ajoutée au prompt LLM : interdiction explicite des doublons, avec exemples (`AI` + `AI generated`, `Dall-e` + `Dall-e style`, `D4lle` + `Dall-e`).
* L'assemblage final récupère un pool large (triggers + IA + fallback × 3) puis déduplique, puis coupe à `limit` — garantit que la recette demandée a bien le bon nombre de mots-clés **après** dédup, et non avant.

**Résultat démontré** sur le cas exact rapporté :
* Avant : `D4lle, AI, AI generated, Dall-e, Dall-e style`
* Après : `D4lle, AI generated, Dall-e style`

Concepts distincts préservés (testé) :
* `dark` + `dark mysterious` → tous deux gardés (`dark` n'est pas générique)
* `purple` + `purple tentacles` → tous deux gardés
* `studio lighting` + `dramatic lighting` → tous deux gardés (vraiment différents)
* `D4lle` + `Dall-e style` → tous deux gardés (similarité 67 %, sous le seuil)

### **🎨 Encarts colorés thématiques (CSS uniquement)**

Cinq zones fonctionnelles reçoivent un fond semi-transparent et un liseré gauche coloré, pour aider l'œil à comprendre instantanément à quel groupe d'usage appartient chaque bloc :

* 🟡 **Jaune** — `#dataset_header` : chargement du dataset (chemin, Parcourir, drop zone, Charger, **et désormais Favoris**).
* 🔵 **Bleu** — `#recipe_header` : recette globale (charger / sauver / supprimer recette, mots-clés, IA).
* 🟢 **Vert** — `#left_panel` : galerie & sélection.
* 🟣 **Violet** — bloc *Serveur et Modèles Locaux* dans l'onglet *Assistant IA Local* (via une nouvelle classe `panel-purple` posée sur la colonne existante).
* 🟦 **Cyan** — `#right_panel` : bibliothèque de mots (Mass Batch).

Les couleurs sont assez transparentes (6 à 12 %) pour rester confortables sur un thème sombre, et chaque panneau réagit légèrement au survol pour renforcer la lisibilité du groupe actif sans distraire.

### **⭐ Section Favoris déplacée dans la zone Chargement (jaune)**

La section **Favoris** se trouvait précédemment en bas de la colonne Recette globale (bleue), ce qui était trompeur : un favori est un **dataset** rapide à recharger, pas une recette. Le bloc *Accordion Favoris* (dropdown + boutons Ajouter / Retirer) a donc été remonté dans `#dataset_header`, juste après le bouton **Charger le Dataset**. Les variables, événements et fichier `favorites.json` sont inchangés ; seule la position visuelle change.

### **📂 Volet pliable pour l'Assistant de Traduction**

L'**Assistant de Traduction** (onglet *Visualiseur & Édition*) — l'ancien `gr.Group` devient un `gr.Accordion` **fermé par défaut**, habillé d'un liseré rouge léger pour rappeler la zone rouge de la maquette. Le contenu (moteur, langues, bouton de traduction complète, insertion rapide) reste strictement identique.

### **▶ Toggle latéral droit pour la Bibliothèque**

La précédente tentative en accordion vertical a été remplacée par un **toggle horizontal symétrique** au bouton *◀ Masquer la Galerie* déjà présent.

* Nouveau bouton `Masquer la Bibliothèque ▶` ajouté en haut du panneau central, à côté du toggle gauche, sur une même `gr.Row` (`#panel_toggles_row`).
* Mécanisme **identique** à celui de la galerie : un petit JS ajoute / retire la classe `collapsed` sur `#right_panel`, déclenchant une transition CSS de largeur vers 0 et une opacité 0.
* La zone centrale (visualiseur, captions, onglets) s'étend dynamiquement à droite, comme elle le fait déjà à gauche. Les couleurs cyan du panneau droit sont neutralisées en mode replié pour ne pas laisser de bordure résiduelle.
* Symétrie esthétique : le bouton de gauche pointe `◀ / ▶`, celui de droite pointe `▶ / ◀`.

### **🔁 Compatibilité et stabilité**

* Aucun composant Gradio existant n'a été supprimé. `ui_trans_module_title` est conservé (masqué) pour ne pas casser la liste d'outputs de `change_language`.
* Aucun nouveau câblage `app.load`, aucune mise à jour frontend de la `Gallery`, aucun listener JS global agressif — les contournements Gradio/Svelte documentés restent intacts.
* Le nouveau JS de toggle droit est **strictement local** : il agit uniquement sur deux IDs (`#right_panel`, `#toggle_right_btn`) et ne touche à aucun autre élément.
* Nouvelle clé `hide_lib` ajoutée symétriquement dans `languages/fr.json` et `languages/en.json`. La clé temporaire `lib_panel_acc` (de la version intermédiaire à accordion vertical) a été retirée. Toutes les autres clés sont inchangées (229 communes, 0 dérive).
* Tests passés : `python -m py_compile lora_manager.py` OK, AST parse OK, JSON FR/EN parseables et symétriques, tous les composants critiques toujours définis exactement une fois, filtre `_is_valid_keyword` testé contre l'exemple problématique réel et rejette correctement les phrases descriptives.

### **🧪 À vérifier après mise à jour**

* Cliquer sur chacun des onglets `Visualiseur & Édition`, `Édition en Batch`, `Pré-traitement & Doublons`, `Assistant IA Local`, `Export & Recette`, `Statistiques Générales` — ils doivent tous répondre comme avant.
* Cliquer **◀ Masquer la Galerie** : la galerie disparaît, le centre s'étend à gauche.
* Cliquer **Masquer la Bibliothèque ▶** : la bibliothèque disparaît, le centre s'étend à droite.
* Cliquer les deux : le centre occupe presque toute la largeur — utile pour les longues captions et l'édition fine.
* Déplier **Favoris** dans la zone jaune et choisir un favori : le dataset doit se charger comme avant.
* Plier / déplier l'**Assistant de Traduction** ne doit pas perturber l'éditeur de caption ni les raccourcis clavier.
* Avec un dataset chargé, cliquer **🤖 Remplir par IA depuis les captions** : la recette générée doit être une **vraie liste de mots-clés courts**, avec le trigger (s'il existe) en première position, et l'analyse des données doit se relancer derrière automatiquement.

---

## **v4.3.1 Pro (Hotfix Stabilité Gradio 6 & Préférences UI)**

Cette mise à jour stabilise l'interface après les ajustements liés à Gradio 6 et ajoute une préférence persistante pour l'affichage de la galerie.

### **🧯 Correctif critique : onglets Gradio bloqués**

* Correction d'un gel de l'interface où les onglets **Visualiseur & Édition**, **Édition en Batch**, **Pré-traitement & Doublons**, **Assistant IA**, **Export & Recette** et **Statistiques Générales** ne répondaient plus au clic.
* Cause identifiée : une mise à jour frontend de la `Gallery` via `app.load(... outputs=[gallery])` pouvait déclencher une boucle interne Gradio/Svelte (`flush`) et rendre l'interface non interactive.
* Le réglage des colonnes est maintenant appliqué au démarrage Python depuis `ui_settings.json`, sans forcer un update frontend au chargement de la page.
* Le JavaScript custom sensible reste injecté via `app.load(..., js=custom_js)` et n'est pas passé via `launch(js=...)`, afin d'éviter les incompatibilités Gradio 6.

### **🖼️ Galerie : colonnes persistantes**

* Le choix **🖼️ Galerie & Sélection / Colonnes** est sauvegardé dans `ui_settings.json`.
* Le fichier est résolu depuis le dossier réel de `lora_manager.py`, ce qui évite les pertes de réglage quand l'application est lancée depuis un autre répertoire.
* Le nombre de colonnes est restauré au redémarrage complet du logiciel.

### **📁 Export & Recette**

* Le drag & drop simple des lignes du tableau d'export est conservé.
* La tentative de multi-sélection avancée du tableau a été retirée temporairement, car elle introduisait trop de risques sur les événements globaux Gradio/Svelte.
* Toute future amélioration du déplacement multi-lignes devra être isolée du système global de clics et testée spécifiquement sur les onglets.

### **🤖 Rapport IA**

* Le profiling de dataset en mode OpenAI-compatible / LM Studio utilise désormais un plafond de sortie plus sûr pour `max_tokens`.
* Le rapport IA envoie un résumé compact du dataset (tags dominants, tags rares, captions vides, moyenne de tags, échantillons) au lieu d'un bloc brut trop long.
* Les erreurs HTTP OpenAI-compatible affichent davantage de détails serveur pour diagnostiquer LM Studio.

---

## **v4.3 Pro (Recette IA & Modèles Persistants)**

Cette mise à jour ajoute une génération automatique de Recette Globale depuis les captions existantes et aligne le titre de l'application sur la version courante.

### **🤖 Recette Globale générée par IA**

* Nouveau bouton **🤖 Remplir par IA depuis les captions** dans **Recette Globale (Synchronisée)**.
* Nouveau champ **Nombre de mots-clés IA** pour choisir combien de mots-clés doivent être proposés.
* L'analyse s'appuie sur toutes les captions du dataset : Python extrait les mots-clés les plus partagés, puis le modèle LLM chargé sélectionne une recette compacte en incluant le trigger word/concept principal quand il le détecte.
* Après génération, la recette remplit automatiquement le champ synchronisé et relance l'analyse de données.

### **🏷️ Version**

* Le titre visible de l'interface et le titre Gradio passent à **IMG Dataset Refiner v4.3 Pro**.

---

## **v4.2 Pro (Espace de Travail & Chargement Local)**

Cette mise à jour compacte l'interface et fiabilise encore le chargement de datasets situés hors du dossier de l'application.

### **⚙️ Paramètres regroupés**

* Le sélecteur **Language / Langue**, le guide de démarrage et l'import de langue personnalisée sont regroupés dans un menu **⚙️ Paramètres**.
* Les favoris de datasets sont déplacés dans la colonne de droite, sous la recette globale, pour exploiter l'espace qui restait vide.

### **🧩 Layout plus dense et adaptatif**

* Suppression de la bande vide en haut causée par les composants cachés Gradio/JS.
* La largeur de l'application utilise maintenant tout l'écran disponible au lieu de rester centrée avec de grandes marges latérales.
* Les panneaux Galerie, Vue centrale et Bibliothèque restent en ligne sur desktop, avec repli responsive seulement sur petits écrans.

### **📂 Drag & Drop de dataset**

* Quand le navigateur fournit un chemin local exploitable lors du dépôt, le champ est rempli et le dataset se charge automatiquement sans clic supplémentaire.
* Si le chemin absolu est masqué, le navigateur envoie maintenant une signature du dossier (nom + fichiers) au backend ; Python tente de retrouver le dossier correspondant sur les favoris, le dossier utilisateur et les lecteurs locaux, puis remplit le champ et charge automatiquement si la correspondance est fiable.
* La signature de dossier est relue plusieurs fois côté navigateur avant envoi, pour éviter les échecs intermittents quand Chrome/Edge fournit la liste de fichiers avec retard.
* La recherche Python priorise désormais les chemins directs, les favoris et les dossiers Pinokio/ComfyUI probables avant de lancer un scan plus large.
* Quand le navigateur masque le chemin absolu d'un dossier déposé, l'application n'ouvre plus de fenêtre Explorateur intrusive : elle affiche un message court et laisse le champ manuel / Parcourir en fallback.
* Le texte de la zone de dépôt a été clarifié pour expliquer ce comportement local.

### **📊 Analyse de données explicite**

* Ajout d'un bouton **📊 Lancer l'analyse des données** sous la Recette Globale, qui déclenche le même recalcul que la virgule / Entrée dans le champ de mots-clés.

### **💡 Traduction Live plus réactive**

* L'aperçu **Traduction Live** utilise maintenant un événement `input` avec mode `always_last` pour éviter l'empilement de traductions obsolètes pendant la frappe.
* Pour Google Translate, l'aperçu live traduit la caption en un seul bloc au lieu de déclencher un appel par tag séparé par virgule.
* Ajout d'un cache court pour éviter de retraduire immédiatement le même texte.

### **📁 Exports versionnés par dataset**

* L'export par défaut ne réutilise plus `output/dataset_final`.
* Chaque export crée un dossier propre nommé d'après le dossier source du dataset, avec suffixe auto `-S1`, `-S2`, `-S3`, etc.
* Nouveau champ **Suffixe d'export** : `-Sx` remplace `x` par le prochain numéro disponible ; `{n}` est aussi accepté pour les suffixes personnalisés.

### **⌨️ Raccourcis clarifiés**

* Le texte d'aide mentionne désormais `PageUp/PageDown` pour naviguer pendant la saisie et `Alt+S` pour suivre/retirer une sélection.

### **🔍 Simulation d'export plus prévisible**

* Le bouton **🔍 Simuler** remet automatiquement la sélection galerie à zéro et simule sur tout le dataset, comme si **🧹 Effacer** avait été cliqué avant.

### **🤖 Assistant IA persistant**

* Les réglages de **⚙️ Serveur et Modèles Locaux** sont sauvegardés dans `ai_settings.json` : backend, modèles VLM/LLM, URL API, clé API, température, contexte et prompt système.
* Au redémarrage, l'Assistant IA reprend automatiquement ces paramètres.

### **🎯 LM Studio : listes de modèles unifiées**

* Les menus **Modèle Vision favori (VLM)** et **Modèle Texte favori (LLM)** affichent maintenant la même liste complète de modèles LM Studio détectés.
* Les modèles polyvalents comme Gemma/Qwen ne sont plus masqués par une séparation VLM/LLM trop stricte.

### **🛠️ Correctifs**

* `allowed_paths` autorise Gradio à servir les images depuis les lecteurs locaux détectés (`C:\`, `D:\`, etc.).
* Les chemins collés/déposés sont normalisés plus proprement (`"..."`, `file:///`, variables d'environnement, fichier image déposé -> dossier parent).
* La sortie console Windows est forcée en UTF-8 tolérant pour éviter les crashs sur les messages contenant des emojis.

---

## **v4.1 Pro (Accessibilité & Robustesse)**

Cette mise à jour répond directement aux retours utilisateurs sur la prise en main et la flexibilité de l'outil. Aucune fonctionnalité existante n'est cassée — tout est rétro-compatible.

### **🪟 Installation simplifiée (Windows)**

* **`install.bat`** : un double-clic suffit pour créer un environnement virtuel local et installer toutes les dépendances. Plus besoin de jongler avec `pip` dans le terminal.
* **`start.bat`** : un double-clic lance l'application et ouvre automatiquement le navigateur.

### **⭐ Favoris de Datasets**

* Nouveau panneau **Favoris** sous le champ de chargement : ajoutez un chemin avec ⭐, retrouvez-le dans le dropdown, retirez-le avec 🗑️.
* Les favoris sont persistés dans `favorites.json` (créé automatiquement à la racine).
* Le chargement accepte désormais n'importe quel chemin absolu (`C:\…`, `D:\…`, `~/…`), avec expansion des variables d'environnement et résolution des chemins relatifs.

### **🌐 Internationalisation extensible**

* Les fichiers de langue sont désormais lus depuis un dossier dédié `languages/`. Le scan est dynamique : déposez un `de.json`, un `es.json`, n'importe quel code de langue, il apparaîtra dans le sélecteur de langue au prochain démarrage.
* Nouveau panneau **🌐 Importer une langue personnalisée** : importez un JSON directement depuis l'UI, sans toucher au système de fichiers.
* Le guide rappelle que Chrome et Edge peuvent aussi traduire la page entière en direct (clic-droit → "Traduire en…").

### **🔤 Tri naturel (style Windows Explorer)**

* La galerie respecte enfin l'ordre attendu : `img1.png`, `img2.png`, `img10.png` (et non plus `img1, img10, img2`). La fonction `natural_sort_key` segmente les noms en parties alphabétiques/numériques avant tri.

### **🗑️ Suppression de recettes**

* Nouveau bouton à côté du dropdown "Recette Globale" pour supprimer un preset, avec confirmation JavaScript.

### **🤖 APIs Cloud (Claude, OpenAI, Gemini)**

* Le sélecteur de backend IA propose désormais **Anthropic Claude (Cloud)** et **Google Gemini (Cloud)** en plus d'Ollama et de OpenAI/LM Studio.
* Nouveau champ **Clé API** (password masqué) dans les Paramètres Avancés.
* L'URL par défaut bascule automatiquement vers le bon endpoint à chaque changement de backend (`api.anthropic.com`, `generativelanguage.googleapis.com`, etc.).
* La fonction `call_ai_api` accepte les formats de payload de chacun (images en base64 incluses pour la Vision).

### **🎯 LM Studio : Chargement automatique du modèle favori**

* Nouvel accordion "🎯 LM Studio : Chargement Auto du Modèle" dans l'onglet IA.
* **🔄 Rafraîchir la liste** appelle `/api/v0/models` (ou `/v1/models` en fallback) et sépare automatiquement VLM (vision) et LLM (texte).
* Boutons **⚡ Charger le VLM / LLM** : envoie `POST /api/v1/models/load` (ou v0, ou fallback chat) pour mettre le modèle en mémoire avant utilisation.
* Le nom du modèle chargé est automatiquement reporté dans les champs "Modèle Vision" / "Modèle Texte" du panneau de configuration.

### **🛠️ Correctifs**

* `readme.md` nettoyé : suppression des marqueurs de conflit Git non résolus (`<<<<<<<`, `=======`, `>>>>>>>`).
* Le chargement de dataset accepte les chemins entre guillemets (copier-coller depuis l'Explorateur Windows).
* La fonction `_resolve_lang_path` cherche d'abord dans `languages/` puis à la racine pour rester compatible avec les anciennes installations.

---

## **v4.0 Pro (Mise à jour d'Ergonomie et de Productivité)**

Cette mise à jour se concentre sur l'accélération radicale du flux de travail manuel et la fiabilisation de l'interface face aux limitations strictes de Gradio 4\.

### **📚 Nouveau : Bibliothèque de mots (Mass Batch Custom)**

* **Module 100% sur mesure :** Remplacement de l'ancien tableau par une liste cliquable personnalisée (HTML/JS) immunisée contre les blocages de Gradio.  
* **Sélection visuelle :** Les mots cochés s'illuminent en orange instantanément.  
* **Édition de masse :** Nouveaux modes pour **Ajouter**, **Retirer** ou **Remplacer** des mots spécifiques sur toute une sélection d'images d'un seul clic.  
* **Mise à jour en temps réel :** L'application de la bibliothèque rafraîchit immédiatement l'éditeur de texte et la galerie visuelle.

### **🌍 Traduction Avancée & Live**

* **Aperçu Live Natif :** Le visualiseur de traduction en temps réel utilise désormais un composant natif stylisé en CSS (vert) pour une stabilité parfaite.  
* **Traduction Globale :** Nouveau bouton permettant de traduire l'intégralité du caption actuel vers l'anglais et de le sauvegarder automatiquement.  
* **Analyse contextuelle :** Le traducteur lit désormais la phrase entière au lieu de la découper mot à mot, garantissant une meilleure détection de la langue de départ (ex: *lumière* traduit correctement en *light*).

### **✨ UI, UX & Navigation**

* **Navigation "Mains sur le clavier" :** Ajout des raccourcis PageUp et PageDown pour passer à l'image précédente/suivante sans jamais perdre le focus de frappe dans la zone de texte.  
* **Tri Dynamique :** Ajout d'une option au-dessus de la galerie pour trier les images par ordre alphabétique croissant (A-Z) ou décroissant (Z-A).  
* **Interface "Desktop" :** Suppression forcée par CSS des en-têtes et pieds de page natifs de Gradio (menu hamburger) pour une interface plus propre et immersive. La barre "Recette Globale" a été rapatriée en haut de l'écran.

### **🛠️ Correctifs & Optimisations (Gradio 4\)**

* **Backups Intelligents :** Le script ne génère plus de fichiers .bak inutiles si le fichier .txt d'origine est complètement vide.  
* **Contournement de Sécurité JS :** Les événements onclick bloqués par Gradio ont été remplacés par un système global d'attributs data-idx couplé à un horodatage (Date.now()), garantissant une réactivité parfaite aux clics.  
* **Fenêtres de confirmation :** Réparation des pop-ups JavaScript de confirmation (Batch & Undo) qui faisaient perdre les données en mémoire sous Gradio 4\.  
* **Internationalisation (100%) :** Tous les nouveaux modules, alertes Javascript et messages système sont désormais liés aux fichiers fr.json et en.json pour une bascule linguistique instantanée et totale.

## **v3.0 Pro**

Cette mise à jour majeure transforme l'outil en une véritable suite professionnelle d'ingénierie de données (Data Engineering) pour les modèles IA. Elle apporte des capacités d'analyse visuelle, de traitement d'images automatisé et d'assistance par Intelligence Artificielle locale.

### **🤖 Nouveautés IA (Assistant Local via API)**

* **Intégration Ollama / LM Studio :** Support natif pour exécuter des modèles de langage (LLM) et de vision (VLM) directement sur le dataset via API locale.  
* **Auto-Taggage / Super OCR (VLM) :** Génération complète de captions ou extraction précise de textes incrustés dans l'image.  
* **Reality Check & Chasseur d'Hallucinations (VLM) :** L'IA compare le texte à l'image et supprime automatiquement les tags qui décrivent des éléments invisibles.  
* **Concept Isolator (VLM) :** L'IA décrit l'environnement et ignore le sujet central, idéal pour préparer les données d'entraînement de LoRAs de personnages.  
* **Traducteur Visuel (Booru ↔ Naturel) :** Conversion intelligente des listes de tags en phrases complètes fluides (optimisé pour Flux et SD3).  
* **Tag Sorting & Standardisation :** Restructuration des tags par ordre d'importance et correction automatique des erreurs sémantiques.  
* **Prompt Personnalisé & Templates :** Possibilité de créer ses propres requêtes IA (avec la variable {tags}), de choisir le mode d'injection (Remplacer, Ajouter) et de sauvegarder ses propres recettes IA.

### **🖼️ Pré-traitement & Gestion de Fichiers**

* **Traque aux Doublons (ImageHash) :** Scanner visuel paramétrable détectant les images similaires (clones exacts ou recadrages) avec interface de suppression rapide A/B.  
* **Smart Face Crop (OpenCV) :** Recadrage automatique centré sur les visages détectés pour optimiser les portraits.  
* **Auto-Formatage 1:1 :** Recadrage carré parfait depuis le centre.  
* **Redimensionnement de Masse :** Downscaling haute qualité (Lanczos) vers 512, 768, 1024 ou 1536px, avec conversion au format WebP ou JPEG.  
* **Gestion Alpha/Transparence :** Les images avec fond transparent (ex: PNG détourés) sont automatiquement aplaties sur fond blanc avant le redimensionnement pour éviter les artefacts noirs.  
* **Batch Renaming :** Renommage propre et incrémental (prefix\_0001.jpg) de toutes les images et de leurs .txt associés en un clic.

### **UI / UX**

* Ajout d'onglets pour une meilleure catégorisation (Vue, Batch, Pré-traitement, IA, Export, Stats).  
* Ajout de panneaux d'information "Astuce" interactifs avec encodage HTML/CSS direct.

### **Stats**

* **Matrice de Co-occurrence (Heatmap) :** Graphique interactif Plotly analysant les liens entre vos 20 tags principaux pour détecter le "Concept Bleeding".  
* **Résolution Bucketing :** Graphique en nuage de points pour visualiser la répartition des résolutions de vos images brutes.  
* **Chasseur de Contradictions :** Détection automatique d'aberrations logiques dans vos captions (ex: "day" \+ "night", ou "solo" \+ "multiple girls").  
* **Matrice d'Exclusion :** Liste les combinaisons de mots qui n'apparaissent *jamais* ensemble pour vérifier la diversité de votre concept.

### **Bugs (Gradio 4+ fixes)**

* **Boucle infinie des mots-clés :** Le calcul des statistiques ne se déclenche plus à chaque lettre tapée, mais uniquement lors de la frappe d'une virgule ,, de la touche Entrée, ou en quittant la case. Fin des effacements intempestifs \!  
* **Bug de surlignage HTML ("Background") :** Correction d'une faille où les mots-clés (comme "background" ou "color") corrompaient la balise HTML \<mark\> utilisée pour le surlignage. Le moteur Regex traite désormais les mots les plus longs en premier et en une seule passe.  
* **Boutons fantômes (Gradio 4\) :** Remplacement de visible=False par du CSS display: none \!important pour les boutons de synchronisation Python/JS, car Gradio 4 détruisait complètement les éléments du DOM, rendant les scripts inopérants.  
* **Bouton de copie CivitAI :** Suppression du paramètre obsolète show\_copy\_button=True qui causait des crashs au lancement, et génération d'un tableau purement Markdown formaté.  
* **Avertissement col\_count :** Mise à jour du paramètre déprécié col\_count vers column\_count pour un terminal propre.  
* **Bug de démarrage :** Sécurisation des fonctions d'interface (MSG\[lang\].get) pour éviter les crashs KeyError: None si l'initialisation de Gradio se fait avant le chargement complet des langues.

## **🌍 Internationalisation**

* Mise à jour complète des fichiers fr.json et en.json pour intégrer toutes les nouveautés IA, Pré-traitement, Batch Custom et UI de la version 4.0.
