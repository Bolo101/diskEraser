# e-Broyeur - Outil d’effacement sécurisé et de formatage de disques 💽

<div style="display: flex; align-items: center;">
  <img src="./img/background" alt="Logo" width="120" style="margin-right: 20px;">
  <p>
    <b>e-Broyeur</b> est un outil permettant d’effacer de manière sécurisée les données des supports de stockage, tout en offrant la possibilité de formater avec le système de fichiers de votre choix (EXT4, NTFS ou VFAT). Il prend en charge l’effacement parallèle de plusieurs disques avec un nombre configurable de passes d’écrasement pour une sanitisation approfondie des données.
  </p>
</div>

## Méthodes d’effacement sécurisé

### Pour les HDD : plusieurs passes d’écrasement
- Recommandé pour les disques durs mécaniques traditionnels.
- Utilise plusieurs passes de données aléatoires suivies d’une passe de zéros.
- Empêche la récupération des données via l’analyse physique des résidus magnétiques.

### Pour les SSD : effacement cryptographique
- Recommandé pour les SSD et les supports flash.
- Les options incluent :
  - **Remplissage par données aléatoires** : écrasement avec des données aléatoires cryptographiquement sûres.
  - **Remplissage par zéros** : effacement rapide en écrivant des zéros sur toutes les zones adressables.
- Fonctionne avec ATA Secure Erase pour les périphériques compatibles.

⚠️ **AVERTISSEMENT DE COMPATIBILITÉ SSD**

Bien que cet outil puisse détecter et traiter les SSD, veuillez noter que :

- **Wear leveling SSD** : rend les méthodes d’écrasement classiques moins efficaces.
- **Sur-provisionnement** : de l’espace réservé caché peut conserver des données.
- **Durée de vie du périphérique** : plusieurs passes peuvent réduire la longévité d’un SSD.

Pour les SSD, les méthodes d’effacement cryptographique sont recommandées à la place de plusieurs passes d’écrasement.

⚠️ **AVERTISSEMENT DE PERFORMANCE POUR CLÉS USB**

Le noyau Linux marque souvent à tort les clés USB comme des périphériques rotatifs, ce qui peut fortement impacter les performances pendant les opérations d’effacement. Il s’agit d’un problème connu affectant les périphériques de stockage USB.

**Pour corriger ce problème lorsque vous n’utilisez PAS l’ISO personnalisé**, créez la règle udev suivante :

Cette règle est disponible sur Stack Exchange : [Solution sur Stack Exchange](https://unix.stackexchange.com/questions/439109/set-usb-flash-drive-as-non-rotational-drive)

1. Créez le fichier `/etc/udev/rules.d/usb-flash.rules` avec les privilèges root :
```bash
sudo nano /etc/udev/rules.d/usb-flash.rules
```

2. Ajoutez le contenu suivant :

```bash
# Essayer de détecter les clés USB et les définir comme non rotatives
# cf. https://mpdesouza.com/blog/kernel-adventures-are-usb-sticks-rotational-devices/

# Le périphérique est déjà marqué comme non rotatif, on l’ignore
ATTR{queue/rotational}=="0", GOTO="skip"

# Le périphérique a une certaine prise en charge de la file d’attente, il s’agit probablement d’un HDD
ATTRS{queue_type}!="none", GOTO="skip"

# Basculer le bit rotatif sur ce périphérique amovible et signaler la correspondance
ATTR{removable}=="1", SUBSYSTEM=="block", SUBSYSTEMS=="usb", ACTION=="add", ATTR{queue/rotational}="0"
ATTR{removable}=="1", SUBSYSTEM=="block", SUBSYSTEMS=="usb", ACTION=="add", RUN+="/bin/beep -f 70 -r 2"

LABEL="skip"
```

3. Rechargez les règles udev et redémarrez le service udev :
```bash
sudo udevadm control --reload-rules
sudo systemctl restart systemd-udevd
```

4. Rebranchez vos clés USB pour appliquer les nouvelles règles.

**Remarque** : les images ISO personnalisées incluent déjà ces règles d’optimisation.

---

## Fonctionnalités ✨

- **Double interface** : modes CLI et GUI pour plus de flexibilité.
- **Détection intelligente des périphériques** : identifie automatiquement les périphériques électroniques et mécaniques.
- **Prise en charge de LVM** : gère l’administration des disques LVM.
- **Méthodes d’effacement sécurisé** :
  - Plusieurs passes d’écrasement pour les HDD.
  - Effacement cryptographique pour les SSD (remplissage aléatoire ou par zéros).
- **Fonctions de sécurité** : détecte les disques système actifs et demande confirmation.
- **Traitement parallèle** : efface plusieurs disques simultanément.
- **Configuration après effacement** : partitionnement et formatage automatiques.
- **Formats flexibles** : prise en charge des systèmes de fichiers NTFS, EXT4 et VFAT.
- **Formatage seul** : formater uniquement le disque dans le format choisi, sans effacement des données.
- **Plusieurs options de déploiement** : exécution en Python, en commande Linux ou via ISO amorçable.
- **Présentation améliorée de la liste des disques en mode GUI** : affiche des informations utiles sur les disques détectés.
- **Système de journalisation complet** :
  - **Suivi de progression en temps réel** : surveille l’état des opérations avec un journal détaillé des étapes.
  - **Gestion des erreurs et récupération** : détection avancée des erreurs.
  - **Journaux de session** : suit les sessions individuelles avec horodatage.
  - **Historique complet des opérations** : conserve une trace d’audit complète de toutes les opérations sur les disques.
  - **Export PDF** : exporte les journaux au format PDF pour impression ou archivage.

---

## Mode Live vs mode Installateur

L’ISO 64 bits précompilée intègre deux modes de démarrage.

### Mode Live
Le mode Live est conseillé lorsqu’on virtualise une machine en démarrant directement sur le système cible via une clé USB bootable contenant l’ISO. Le processus de virtualisation s’exécute entièrement depuis l’environnement Live, sans installation requise sur la machine hôte.

Les utilisateurs ont accès à toutes les fonctionnalités, y compris la possibilité d’exporter les journaux vers un support externe avant d’éteindre la session.

<div style="display: flex; align-items: center;">
  <img src="./img/gui.png" alt="GUI" width="600" style="margin-right: 20px;">
</div>

### Mode Installateur
Le mode Installateur est conçu pour une **station fixe de sanitisation**, où les disques physiques retirés de leurs machines d’origine, ou des périphériques externes, sont directement connectés à la station pour être nettoyés. Ce mode vise une configuration permanente et dédiée, plutôt qu’une intervention sur site.

Toutes les fonctionnalités sont disponibles pour l’utilisateur, à l’exception des opérations suivantes, qui sont **réservées à l’accès administrateur (protégé par mot de passe)** :

| Action protégée | Raison |
|---|---|
| Export des journaux depuis la station | Prévenir l’extraction non autorisée de données |
| Purge des journaux | Préserver l’intégrité de la trace d’audit |
| Redémarrage et arrêt du système | Assurer la disponibilité de la station |
| Quitter le mode kiosque | Maintenir un environnement contrôlé |

<div style="display: flex; align-items: center;">
  <img src="./img/gui_installer.png" alt="GUI" width="600" style="margin-right: 20px;">
</div>

### Comparaison rapide

| | Mode Live | Mode Installateur |
|---|---|---|
| **Cas d’usage** | Intervention sur site, démarrage sur la machine cible | Station fixe, connexion de disques externes |
| **Installation requise** | Non | Oui |
| **Export des journaux** | ✅ Utilisateur | 🔒 Administrateur uniquement |
| **Purge des journaux** | ✅ Utilisateur | 🔒 Administrateur uniquement |
| **Redémarrage / arrêt** | ✅ Utilisateur | 🔒 Administrateur uniquement |
| **Quitter le mode kiosque** | ✅ Utilisateur | 🔒 Administrateur uniquement |
| **Effacement de disques externes** | ✅ Utilisateur | ✅ Utilisateur |
| **Formatage de disques externes** | ✅ Utilisateur | ✅ Utilisateur |

## Prérequis 📋

- **Privilèges root** (nécessaires pour l’accès aux disques).
- **Python 3** avec **Tkinter** (pour le mode GUI).
- **Connaissances de base en gestion de disques** : cet outil **efface définitivement** les données ⚠️.

## Installation et utilisation 🚀

### Utilisation du code Python 🐍
⚠️ **Si vous souhaitez installer le système avec un panneau d’administration, utilisez le dossier *code_installer* au lieu du dossier *code*.**

```bash
git clone https://github.com/Bolo101/e-broyeur.git
cd e-broyeur/code/python
sudo python3 main.py         # Mode GUI (par défaut)
sudo python3 main.py --cli   # Mode ligne de commande
```

### Installation en tant que commande Linux 💻

```bash
sudo mkdir -p /usr/local/bin/e-broyeur
sudo cp e-broyeur/code/python/*.py /usr/local/bin/e-broyeur
sudo chmod +x /usr/local/bin/e-broyeur/main.py
sudo ln -s /usr/local/bin/e-broyeur/main.py /usr/local/bin/e-broyeur

# Puis exécuter :
sudo e-broyeur           # Mode GUI
sudo e-broyeur --cli     # Mode CLI
```

### Utilisation via ISO amorçable 💿

1. **Créer ou télécharger l’ISO** :

    - **Créer l’ISO** :

    Choisissez la version ISO souhaitée, 32 bits ou 64 bits, XFCE (plus léger) ou KDE.

    ```bash
    cd iso/
    make
    make 32      # environnement 32 bits (sans mode installateur)
    make all-iso # génère les 4 ISO
    make clean   # nettoie les fichiers de build
    make help    # affiche le message d’aide
    ```

    - **ISO précompilée**

    Télécharger la version précompilée : [e-Broyeur ISO v7.0](https://archive.org/details/e-Broyeur-v7.0)

    ```txt
    - e-Broyeur-v7.0-64bits.iso : 0d740a6205b3790a7780284814b7cc94a83b16767f0aa40c2ffdaa1e15c99aac
    - e-Broyeur-v7.0-32bits.iso : c7210c53b7b78f35a5c5bcbaa3af71a275b05559b099ea4331816a7ccbc77ba6
    ```

2. **Flasher sur une clé USB** :
   ```bash
   sudo dd if=e-Broyeur*.iso of=/dev/sdX bs=4M status=progress
   ```

3. **Démarrer depuis la clé USB** et suivre les instructions à l’écran.

## Options de ligne de commande ⌨️

```bash
# Options de formatage
-f ext4|ntfs|vfat, --filesystem ext4|ntfs|vfat

# Nombre de passes d’effacement
-p NUMBER, --passes NUMBER

# Mode d’interface
--cli           # Utiliser l’interface en ligne de commande

# Exemples :
python3 main.py -f ext4 -p 3      # GUI, EXT4, 3 passes
python3 main.py --cli -f ntfs     # CLI, NTFS, passes par défaut
```

## Structure du projet 🏗

```text
project/
├── README.md               # Documentation
├── code/                   # Scripts Python
│   ├── disk_erase.py       # Module d’effacement
│   ├── disk_format.py      # Module de formatage
│   ├── disk_operations.py  # Opérations sur les disques
│   ├── disk_partition.py   # Module de partitionnement
│   ├── gui_interface.py    # Interface graphique
│   ├── cli_interface.py    # Interface en ligne de commande
│   ├── log_handler.py      # Fonctionnalité de journalisation
│   ├── main.py             # Logique principale du programme
│   └── utils.py            # Fonctions utilitaires
├── code_installer
│   ├── admin_interface.py  # Administration pannel
│   ├── cli_interface.py
│   ├── config_manager.py
│   ├── disk_erase.py
│   ├── disk_format.py
│   ├── disk_operations.py
│   ├── disk_partition.py
│   ├── export_manager.py
│   ├── gui_interface.py
│   ├── log_handler.py
│   ├── main.py
│   ├── stats_manager.py
│   └── utils.py
├── img
│   ├── background
│   ├── gui_installer.png
│   └── gui.png
├── iso
│   ├── iso-32-bits
│   │   └── forgeIso32.sh  # Générateur d’ISO
│   ├── iso-64-bits        # Automatisation du build
│   │   └── forgeIso64.sh  # Générateur d’ISO
│   └── makefile
├── setup.sh                # Installateur de dépendances
└── LICENSE                 # Licence CC 4.0
```

## Notes de sécurité ⚠️

- **Perte de données** : cet outil **efface définitivement** les données. Sauvegardez d’abord les informations importantes.
- **Accès root** : exécutez-le avec les privilèges appropriés (root/sudo).
- **Types de stockage** : différentes méthodes d’effacement sont optimisées selon la technologie de stockage :
  - Pour les HDD : plusieurs passes d’écrasement.
  - Pour les SSD : effacement cryptographique (remplissage aléatoire ou par zéros).
- **Protection du système** : l’outil détecte et signale les disques système actifs.
- **Trace d’audit** : conservez les fichiers journaux pour la conformité et le dépannage.

## Licence ⚖️

Ce projet est sous licence [Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International](https://creativecommons.org/licenses/by-nc-sa/4.0/).

![Creative Commons License](https://i.creativecommons.org/l/by-nc-sa/4.0/88x31.png)

Vous êtes libre de :
- **Partager** : copier et redistribuer le matériel.
- **Adapter** : remixer, transformer et construire à partir du matériel.

Sous les conditions suivantes :
- **Attribution** : fournir une attribution appropriée.
- **NonCommercial** : usage commercial interdit.
- **ShareAlike** : distribuer les modifications sous la même licence.