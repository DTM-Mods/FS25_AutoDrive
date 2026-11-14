# ModHub upload: AutoDrive Overdrive

What to enter in the GIANTS ModHub upload form for this mod. Each text box below has a copy button on GitHub.

<img src="icon_512.png" alt="Mod icon" width="160">

**Mod Icon (512x512):** [`icon_512.png`](icon_512.png)

| Field | Value |
|-------|-------|
| Title English | AutoDrive Overdrive |
| Title German | AutoDrive Overdrive |
| Title French | AutoDrive Overdrive |
| Version | `3` `0` `1` `4` |
| Author | DTM Mods, Fennell (based on AutoDrive by the AutoDrive Team) |
| Manufacturer | Lizard |
| Category 1 | Gameplay |
| Category 2 | Not Set |
| Category 3 | Not Set |

## Title English
```text
AutoDrive Overdrive
```

## Title German
```text
AutoDrive Overdrive
```

## Title French
```text
AutoDrive Overdrive
```

## Description English
```text
AutoDrive Overdrive is an unofficial edition of AutoDrive by the AutoDrive Team, based on AutoDrive 3.0.1.4. Build a network of routes, and your vehicles drive themselves to any point on it, like the shop, a field or a selling point. It replaces the official AutoDrive (install one, not both); savegames, routes and settings keep working.

- Undo and redo in the route editor (Ctrl+Z / Ctrl+Y), up to 100 steps
- Drag waypoints, select several at once, and a waypoint panel
- Route check (Ctrl+Alt+N) for unreachable targets and dead ends, with fixes
- Waypoint actions (wait, horn, lights, open tension belts) and speed zones
- Fleet overview (Ctrl+Alt+I) with driver statistics, route preview (Ctrl+Alt+P)
- Best price unloading, refuelling and work times per vehicle
- Combine unloaders stay under the pipe and out of the harvester's way
- Target sub folders with 12 colours

How to use: all Overdrive settings are on their own Overdrive tab in the AutoDrive settings.

Changelog 3.0.1.4 (Overdrive build 58):
- At the end of a row, when the harvester raises its header, the unloader stops where it is and chases again once the header is working.
- Rounded headland corners harvested with the header down are followed as before.
- The wait never starts while the harvester calls for unloading and lasts at most 60 seconds.
```

## Description German
```text
AutoDrive Overdrive ist eine inoffizielle Ausgabe von AutoDrive vom AutoDrive Team, basierend auf AutoDrive 3.0.1.4. Lege ein Routennetz an, und deine Fahrzeuge fahren selbst zu jedem Punkt darauf, etwa zum Shop, zu einem Feld oder zu einer Verkaufsstelle. Ersetzt das offizielle AutoDrive (nur eins von beiden installieren); Spielstände, Routen und Einstellungen funktionieren weiter.

- Rückgängig und Wiederholen im Routen-Editor (Strg+Z / Strg+Y), bis zu 100 Schritte
- Wegpunkte verschieben, mehrere auf einmal auswählen, Wegpunkt-Panel
- Routenprüfung (Strg+Alt+N) auf unerreichbare Ziele und Sackgassen, mit Korrektur
- Wegpunkt-Aktionen (warten, hupen, Licht, Spanngurte öffnen) und Tempozonen
- Flottenübersicht (Strg+Alt+I) mit Fahrerstatistik, Routenvorschau (Strg+Alt+P)
- Entladen zum besten Preis, Tanken und Arbeitszeiten pro Fahrzeug
- Überladefahrzeuge bleiben unter dem Rohr und dem Drescher aus dem Weg
- Unterordner für Ziele mit 12 Farben

Bedienung: Alle Overdrive-Einstellungen haben einen eigenen Overdrive-Reiter in den AutoDrive-Einstellungen.

Changelog 3.0.1.4 (Overdrive Build 58):
- Am Ende einer Spur, wenn der Drescher das Schneidwerk hebt, bleibt das Überladefahrzeug stehen und folgt wieder, sobald das Schneidwerk arbeitet.
- Runde Vorgewende-Ecken mit gesenktem Schneidwerk werden wie bisher mitgefahren.
- Das Warten beginnt nie, während der Drescher zum Abtanken ruft, und dauert höchstens 60 Sekunden.
```

## Description French
```text
AutoDrive Overdrive est une édition non officielle d'AutoDrive de l'AutoDrive Team, basée sur AutoDrive 3.0.1.4. Créez un réseau de routes, et vos véhicules se rendent seuls à n'importe quel point de ce réseau, comme la boutique, un champ ou un point de vente. Remplace l'AutoDrive officiel (installez l'un ou l'autre) ; sauvegardes, routes et réglages restent valables.

- Annuler et rétablir dans l'éditeur de routes (Ctrl+Z / Ctrl+Y), jusqu'à 100 étapes
- Déplacer les points de passage, en sélectionner plusieurs, panneau de point de passage
- Vérification des routes (Ctrl+Alt+N) : destinations inaccessibles et impasses, avec corrections
- Actions aux points de passage (attendre, klaxon, phares, ouvrir les sangles) et zones de vitesse
- Vue de la flotte (Ctrl+Alt+I) avec statistiques, aperçu de route (Ctrl+Alt+P)
- Déchargement au meilleur prix, plein et horaires de travail par véhicule
- Les véhicules de déchargement restent sous la goulotte, hors du chemin de la moissonneuse
- Sous-dossiers de destinations en 12 couleurs

Utilisation : tous les réglages Overdrive sont dans leur propre onglet Overdrive des réglages AutoDrive.

Changelog 3.0.1.4 (Overdrive build 58) :
- En bout de rang, quand la moissonneuse lève sa coupe, le véhicule de déchargement s'arrête et repart dès que la coupe travaille.
- Les coins arrondis récoltés coupe baissée sont suivis comme avant.
- L'attente ne commence jamais quand la moissonneuse demande à être vidée et dure 60 secondes au plus.
```

## Before uploading

- This is a fork of AutoDrive by the AutoDrive Team, which is already on ModHub as `FS25_AutoDrive`. ModHub rejects copies of existing mods: it needs the original authors' permission (the MIT licence allows the fork, not a ModHub upload under their mod), and the zip name `FS25_AutoDrive` and version 3.0.1.4 are the same as the official mod's.
- 247 files would go into the zip; ModHub allows at most 128 (this repo's build has `max-files: 0`). All Lua files are under 0.5 MB.
- The version boxes can only take 3.0.1.4; the Overdrive build number (od.58) does not fit and is only in the changelog line.
- 71 of the mod's 733 French texts are still in English (German is complete).
