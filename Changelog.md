# **📝 Changelog \- IMG Dataset Refiner (v3.0 Pro)**

Cette mise à jour majeure transforme l'outil en une véritable suite professionnelle d'ingénierie de données (Data Engineering) pour les modèles IA. Elle apporte des capacités d'analyse visuelle, de traitement d'images automatisé et d'assistance par Intelligence Artificielle locale.

## **🤖 Nouveautés IA (Assistant Local via API)**

* **Intégration Ollama / LM Studio :** Support natif pour exécuter des modèles de langage (LLM) et de vision (VLM) directement sur le dataset via API locale.  
* **Auto-Taggage / Super OCR (VLM) :** Génération complète de captions ou extraction précise de textes incrustés dans l'image.  
* **Reality Check & Chasseur d'Hallucinations (VLM) :** L'IA compare le texte à l'image et supprime automatiquement les tags qui décrivent des éléments invisibles.  
* **Concept Isolator (VLM) :** L'IA décrit l'environnement et ignore le sujet central, idéal pour préparer les données d'entraînement de LoRAs de personnages.  
* **Traducteur Visuel (Booru ↔ Naturel) :** Conversion intelligente des listes de tags en phrases complètes fluides (optimisé pour Flux et SD3).  
* **Tag Sorting & Standardisation :** Restructuration des tags par ordre d'importance et correction automatique des erreurs sémantiques.  
* **Prompt Personnalisé & Templates :** Possibilité de créer ses propres requêtes IA (avec la variable {tags}), de choisir le mode d'injection (Remplacer, Ajouter) et de sauvegarder ses propres recettes IA.  
* **Gestion Avancée des Erreurs :** L'outil ignore silencieusement les plantages/timeouts de l'API sur certaines images pour continuer le traitement par lots, et génère un rapport final détaillé.  
* **Analyse de Biais Sémantique :** Génération d'un rapport détaillé par un LLM sur la qualité et les potentiels biais de votre dataset.

## **🖼️ Nouveautés Pré-traitement & Image**

* **Traque aux Doublons Visuels (Perceptual Hashing) :** Nouveau scanner propulsé par ImageHash capable de détecter les images quasi-identiques (même si elles sont recadrées ou redimensionnées). Interface côte à côte pour suppression facile.  
* **Redimensionnement & Formatage en Masse :** Conversion rapide d'un dossier entier (ex: vers 1024x1024 en WebP) via Pillow.  
* **Smart Face Crop (OpenCV) :** Option de recadrage intelligent qui détecte les visages pour centrer automatiquement la coupe autour du sujet principal.  
* **Gestion Automatique de l'Alpha :** Conversion automatique des fonds transparents (PNG) en fonds blancs purs, un standard requis pour l'entraînement.  
* **Renommage par Lot (Batch Renaming) :** Outil intégré pour renommer toutes les images et leurs fichiers .txt associés avec un préfixe commun.

## **🧬 Nouveautés Analytiques & UX**

* **Changement de nom :** "Datasets Images EditSelect" devient officiellement **"IMG Dataset Refiner"**.  
* **Intellisense (Autocomplétion) :** Injection d'un script JavaScript natif dans le visualiseur. L'outil suggère désormais automatiquement des mots-clés existants de votre dataset pendant la frappe \!  
* **Matrice de Co-occurrence (Concept Bleeding) :** Nouveau graphique Plotly interactif pour repérer si deux tags (ex: un personnage et un vêtement) apparaissent trop souvent ensemble.  
* **Analyseur de Résolutions (Bucketing) :** Nouveau graphique en nuage de points (Scatter Plot) pour vérifier la distribution des dimensions de vos images par rapport aux "buckets" standards de l'entraînement.  
* **Matrice d'Exclusion (Anti-Heatmap) :** Liste des tags ultra-fréquents qui ne sont *jamais* associés, pour détecter des lacunes dans le dataset.  
* **Chasseur de Contradictions Logiques :** Script de vérification hors-ligne qui signale les incohérences flagrantes (ex: day et night sur la même image).  
* **Onboarding & Outils Contextuels :** Ajout de menus déroulants de guides de démarrage rapide et de bulles d'aide interactives pour guider les nouveaux utilisateurs.

# **📝 Changelog \- v2.0**

Cette mise à jour majeure se concentre sur l'ergonomie, la rapidité d'exécution (workflow) et la compatibilité totale avec les nouvelles versions de Gradio (v4+). L'application passe d'un outil cliquable classique à un véritable logiciel "desktop-like" ultra-réactif.

## **🚀 Nouveautés Majeures**

* **Refonte du système de Sélection (Façon Windows) :** \* La sélection d'images ne fait plus clignoter la galerie (traitement 100% JavaScript).  
  * Support du \[Ctrl \+ Clic\] pour ajouter/retirer des images individuelles.  
  * Support du \[Maj \+ Clic\] pour sélectionner une plage complète d'images d'un coup.  
  * Support du \[Ctrl \+ A\] pour tout sélectionner instantanément.  
  * **Correction :** Un clic simple affiche désormais l'image instantanément dans le visualiseur tout en réinitialisant la sélection.  
* **Menu Contextuel (Clic Droit) :** \* Ajout d'un menu volant natif sur les images de la galerie pour des actions rapides sans déplacer la souris : Sauvegarder, Ajouter aux stats, Vider la sélection.  
* **Sauvegarde Silencieuse (Auto-Save) :** \* Fini l'obligation de cliquer sur "Sauvegarder". Lors de la navigation vers une autre image (via flèches ou clic), l'outil détecte les modifications de la caption et sauvegarde le fichier automatiquement en arrière-plan (en créant un .bak de sécurité).

## **⚡ Ergonomie & Tableaux ("Excel-like")**

* **Glisser-Déposer (Drag & Drop) Indestructible :** Réécriture du système de Drag & Drop dans les tableaux de la recette pour résister aux rechargements dynamiques de Gradio 4\.  
* **Édition "Excel-like" :** Un simple clic sur une case du tableau simule un double-clic et sélectionne tout le texte instantanément. Taper un nouveau chiffre écrase l'ancien sans avoir besoin d'utiliser la touche Retour arrière.  
* **Smart Swap 2.0 (Inversion Intelligente) :** Si la priorité d'un tag est modifiée vers un numéro déjà occupé, l'ancien tag prend la place vacante automatiquement (zéro doublon). Protection ajoutée contre les index hors-limites.  
* **Panneau de Saisie Rapide :** Ajout de menus déroulants sous le tableau de recette pour changer les priorités et cibles instantanément.  
* **Boutons de déplacement :** Ajout des boutons ⬆️ Monter, ⬇️ Descendre et 🗑️ Supprimer pour réorganiser le tableau sans la souris.

## **⌨️ Raccourcis Claviers (Sécurisés)**

* **Indépendance AZERTY/QWERTY :** Les raccourcis utilisent désormais e.code pour garantir leur fonctionnement quelle que soit la langue du clavier.  
* **Nouveaux raccourcis :** \* \[Alt \+ Flèche Haut/Bas\] : Déplacer la ligne sélectionnée dans le tableau.  
  * \[Ctrl \+ F\] : Placer le curseur directement dans la barre de recherche.  
* **Légende dynamique :** Ajout d'un encart rappelant les raccourcis sous le visualiseur d'image, mis à jour selon la langue choisie (FR/EN).

## **🐛 Corrections de Bugs (Gradio 4+ fixes)**

* **Boucle infinie des mots-clés :** Le calcul des statistiques ne se déclenche plus à chaque lettre tapée, mais uniquement lors de la frappe d'une virgule ,, de la touche Entrée, ou en quittant la case. Fin des effacements intempestifs \!  
* **Bug de surlignage HTML ("Background") :** Correction d'une faille où les mots-clés (comme "background" ou "color") corrompaient la balise HTML \<mark\> utilisée pour le surlignage. Le moteur Regex traite désormais les mots les plus longs en premier et en une seule passe.  
* **Boutons fantômes (Gradio 4\) :** Remplacement de visible=False par du CSS display: none \!important pour les boutons de synchronisation Python/JS, car Gradio 4 détruisait complètement les éléments du DOM, rendant les scripts inopérants.  
* **Bouton de copie CivitAI :** Suppression du paramètre obsolète show\_copy\_button=True qui causait des crashs au lancement, et génération d'un tableau purement Markdown formaté.  
* **Avertissement col\_count :** Mise à jour du paramètre déprécié col\_count vers column\_count pour un terminal propre.  
* **Bug de démarrage :** Sécurisation des fonctions d'interface (MSG\[lang\].get) pour éviter les crashs KeyError: None si l'initialisation de Gradio se fait avant le chargement complet des langues.

## **🌍 Internationalisation**

* Mise à jour complète des fichiers fr.json et en.json pour intégrer les instructions liées au Drag & Drop, aux nouveaux raccourcis clavier, et à la sauvegarde automatique.