# **📊 IMG Dataset Refiner (v3.0 Pro)**

**L'outil ultime de gestion, d'équilibrage, de pré-traitement et d'assistance IA (VLM/LLM) pour la préparation d'entraînements de modèles (LoRA, SDXL, Flux)** [Installation](#bookmark=id.mdqckzv177zk) • [Nouveautés v3](#bookmark=id.qlisdo3xd41l) • [Fonctionnalités](#bookmark=id.vzq3rz6q41py) • [Workflow](#bookmark=id.rxhnnyhrpao9)

## **🎯 À propos**

**IMG Dataset Refiner** (anciennement *Datasets Images EditSelect*) est une suite logicielle "desktop-like" conçue pour les créateurs de modèles IA. Propulsé par **Gradio** avec des injections JavaScript natives pour des performances optimales, cet outil permet de **visualiser, pré-traiter, nettoyer, analyser par l'IA et exporter** vos datasets d'images avec une précision chirurgicale.

## **🚀 Nouveautés de la v3.0 Pro**

Cette mise à jour majeure transforme l'outil en une véritable suite d'ingénierie de données (Data Engineering) avec des capacités d'analyse visuelle et sémantique :

* **🤖 Assistant IA Local (Ollama / LM Studio) :** Connectez l'outil à vos LLM et VLM locaux (Llama 3, Qwen-VL, LLaVA) pour auto-tagger, traquer les hallucinations, isoler des concepts ou traduire vos tags en langage naturel (idéal pour Flux).  
* **🖼️ Traque aux Doublons & Pré-traitement :** Scanner visuel de doublons (Perceptual Hashing), recadrage intelligent des visages (OpenCV), correction automatique de la transparence (Alpha) et redimensionnement/renommage en masse.  
* **🧬 Audits Avancés :** Matrice de co-occurrence (Heatmap) pour repérer le "Concept Bleeding", graphique de distribution des résolutions (Bucketing), et chasseur de contradictions logiques.  
* **🪄 Intellisense Natif :** Le visualiseur intègre désormais une autocomplétion intelligente ultra-rapide qui suggère les tags déjà présents dans votre dataset au fil de la frappe.  
* **Interface Pro & Onboarding :** Ajout de menus contextuels d'aide, de guides de démarrage rapide, et changement de langue à la volée (FR/EN) sur l'intégralité des modules avancés.

*(Consultez le Changelog.md pour revoir les ajouts ergonomiques de la v2.0 comme la sélection façon Windows et l'auto-save).*

## **📸 Galerie & Aperçu**

### **🎬 Interface Principale & Autocomplétion**

*(Insérez vos screenshots ici)*

### **🤖 Assistant IA Local & Profiling**

*(Insérez vos screenshots ici)*

### **📈 Graphiques Avancés (Co-occurrence & Bucketing)**

*(Insérez vos screenshots ici)*

## **🌟 Fonctionnalités Principales**

### **🤖 Assistant IA (VLM & LLM)**

| Fonctionnalité | Description |
| :---- | :---- |
| **Auto-Taggage / Super OCR** | Le VLM lit l'image de zéro, extrait les détails visuels et le texte incrusté (text: "..."). |
| **Reality Check (Anti-Hallucination)** | Le VLM vérifie vos tags existants et supprime automatiquement ceux qui ne sont pas sur l'image. |
| **Concept Isolator (Spécial LoRA)** | L'IA décrit l'environnement mais *ignore* volontairement le sujet central pour protéger votre Trigger Word. |
| **Traducteur Visuel (Flux/SD3)** | Un LLM convertit vos listes de mots-clés Booru-style en de belles phrases descriptives fluides. |
| **Prompt Custom & Templates** | Créez vos propres instructions IA et sauvegardez-les comme "Templates". |

### **🖼️ Pré-traitement Image & Doublons**

| Fonctionnalité | Description |
| :---- | :---- |
| **Scanner de Doublons Visuels** | Détecte les images quasi-identiques (recadrées, redimensionnées) via ImageHash avec un curseur de tolérance. |
| **Smart Face Crop** | Recadre automatiquement l'image autour du visage détecté par l'IA OpenCV. |
| **Standardisation de l'Alpha** | Repère les PNG transparents et remplace le fond par du blanc pour éviter le bruit lors de l'entraînement. |
| **Batch Resize & Rename** | Redimensionnement (Pillow), conversion (WebP/JPEG) et renommage global du dossier en 1 clic. |

### **👁️ Galerie, Visualiseur & Éditeur**

| Fonctionnalité | Description |
| :---- | :---- |
| **Sélection Ultra-Rapide** | \[Ctrl+Clic\], \[Maj+Clic\], \[Ctrl+A\] avec surbrillance dynamique gérée côté client. |
| **Intellisense** | Autocomplétion dynamique des tags lors de la saisie manuelle. |
| **Menu Contextuel Custom** | Clic droit sur l'image pour un accès rapide aux actions essentielles. |
| **Édition Batch** | Regex, remplacement de synonymes, nettoyage d'espaces et de virgules sur des milliers d'images à la fois. |

### **📈 Statistiques & Équilibrage**

| Fonctionnalité | Description |
| :---- | :---- |
| **Audits de Dataset** | Heatmap de co-occurrence, nuage de points de résolutions, et détection de contradictions logiques (ex: *jour* ET *nuit*). |
| **Tableau "Excel-like" & Drag/Drop** | Glissez/déposez pour réorganiser vos priorités de tags instantanément. |
| **Assistant d'Export Intelligent** | Algorithme "Greedy" pour équilibrer la distribution d'images selon des pourcentages cibles précis. |

## **🚀 Installation & Lancement**

### **Prérequis**

* **Python 3.10+**  
* Un moteur IA local (ex: **Ollama**, **LM Studio**, ou **KoboldCPP**) pour les fonctionnalités de l'Assistant IA.  
* Git

### **Étapes**

1. **Clonez le dépôt** \`\`\`bash  
   git clone [https://github.com/BC8069EA84/Datasets-Images-EditSelect.git](https://github.com/BC8069EA84/Datasets-Images-EditSelect.git)  
   cd Datasets-Images-EditSelect

2. **Installez les dépendances** *(Mises à jour pour la v3.0)* \`\`\`bash  
   pip install gradio pandas plotly imagehash opencv-python requests Pillow

3. **Lancez l'outil** \`\`\`bash  
   python lora\_manager.py

4. **Accédez à l'interface** L'interface s'ouvrira automatiquement dans votre navigateur par défaut (sur 127.0.0.1).

## **💡 Comment ça marche ? (Workflow recommandé)**

1️⃣ **Pré-traitement (Onglet 🖼️)** └─ Nettoyez les doublons visuels, renommez vos fichiers, et recadrez/redimensionnez vos images en masse.  
2️⃣ **Intelligence Artificielle (Onglet 🤖)** └─ Lancez un auto-taggage via VLM, ou convertissez vos tags en phrases via LLM si vous ciblez un modèle Flux.  
3️⃣ **Audit & Statistiques (Onglet 📈)** └─ Utilisez le *Reality Check* et générez les graphiques avancés pour vérifier qu'aucun tag indésirable ne "saigne" sur votre concept (Concept Bleeding).  
4️⃣ **Nettoyage Final & Édition (Onglet 👁️ et ⚡)** └─ Complétez vos tags manuellement grâce à l'Intellisense et utilisez le Batch Editor pour corriger les fautes restantes.  
5️⃣ **Export Stratégique (Onglet 📁)** └─ Entrez vos cibles %, simulez l'équilibre, et exportez un dataset parfait et prêt à l'entraînement \!

## **📦 Structure du Projet**

IMG-Dataset-Refiner/    
├── lora\_manager.py          \# Point d'entrée principal (Le code métier et UI)    
├── Changelog.md             \# Historique des mises à jour (v2.0 & v3.0 Pro)    
├── en.json                  \# Dictionnaire de langue Anglaise    
├── fr.json                  \# Dictionnaire de langue Française    
├── lora\_recipes.json        \# Sauvegardes de vos configurations d'export  
├── ai\_recipes.json          \# Sauvegardes de vos prompts Custom IA  
├── README.md                \# Cette documentation    
├── requirements.txt         \# Dépendances Python    
└── screenshots demo/        \# Démonstration visuelle

## **🎓 Cas d'Usage**

✅ Préparation de datasets exigeants pour **LoRA fine-tuning** (SD 1.5, SDXL, Flux)  
✅ **Auto-captioning local** respectueux de la vie privée  
✅ Équilibrage mathématique de datasets **multi-concepts** ✅ Identification et résolution de problèmes d'**overfitting** via audits visuels

## **📄 Licence**

Libre d'utilisation et de modification pour vos workflows d'IA.

## **🤝 Contribution**

Les contributions sont bienvenues \! N'hésitez pas à :

* Signaler des bugs via les Issues  
* Proposer des améliorations  
* Soumettre des Pull Requests

**Forgé avec ❤️ pour la communauté IA** [⬆️ Retour au sommet](#bookmark=id.9fk626vr5xxk)