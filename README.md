# Mes bus (52 et 22) — Maison ⇄ Bureau

Petite web-app (PWA) pour les lignes de bus **52** et **22** à Paris (choix 52 / 22 dans le bandeau vert) :

- **52** : maison *La Fontaine - Radio France* (retour à *Assomption - Radio France*) ⇄ bureau *Victor Hugo - Paul Valéry* ou *Charles de Gaulle Étoile - Victor Hugo*
- **22** : maison *George Sand - La Fontaine* ⇄ bureau *Charles de Gaulle Étoile - Kléber* (direction Saint-Lazare à l'aller)
- **Tour Eiffel** : compte à rebours du prochain scintillement (5 min à chaque heure pile, de la tombée de la nuit à 23 h), puis de sa fin.


- **Horaires** : les 3 prochains bus avec compte à rebours (min / s) et heure exacte de passage
  - 🏠 Maison → Bureau : départ *La Fontaine - Radio France*
  - 💼 Bureau → Maison : départ *Victor Hugo - Paul Valéry* (par défaut) ou *Charles de Gaulle Étoile - Victor Hugo*
  - la géolocalisation choisit le bon sens toute seule (près de la maison → vers le bureau, et inversement)
  - actualisation toutes les 30 s, compte à rebours à la seconde
- **Plan** : la ligne 52 entre la maison et le bureau, avec tous les bus en circulation.
  Île-de-France Mobilités ne publie pas le GPS des bus : leur position est **estimée** à partir des heures
  de passage en temps réel (le bus est placé entre l'arrêt précédent et le prochain arrêt).

Si `CONFIG.proxyUrl` est vide, l'appli tourne en **mode démo** (bus simulés).

## Données

- Arrêts, ligne et tracé : données ouvertes IDFM (`data.iledefrance-mobilites.fr`), sans clé, chargées au premier lancement.
- Temps réel : API **PRIM** d'Île-de-France Mobilités (`stop-monitoring` et `estimated-timetable`), avec une clé gratuite.

## Mise en route (une fois)

### 1. Clé API PRIM (gratuite)
1. Créer un compte sur https://prim.iledefrance-mobilites.fr
2. Menu de son compte → **Mes jetons d'authentification** → générer une clé API.

### 2. Relais Cloudflare (gratuit, garde la clé secrète)
L'API PRIM ne s'appelle pas directement depuis une page web : le petit relais `worker/` s'en charge.
```bash
cd worker
npx wrangler login
npx wrangler secret put PRIM_API_KEY   # coller la clé PRIM
npx wrangler deploy                    # affiche l'adresse https://bus52.<compte>.workers.dev
```
Mettre ensuite cette adresse dans `CONFIG.proxyUrl` en haut du script de `index.html`
(déjà fait : `https://bus52.edumontet.workers.dev`). Le relais n'accepte que l'appli (`https://edumontet.github.io`).

### 3. Hébergement GitHub Pages
Settings → Pages → *Deploy from a branch* → `main` / `(root)`.

### 4. Sur le téléphone
Ouvrir https://edumontet.github.io/bus52/ dans Safari → Partager → **Sur l'écran d'accueil**.
Autoriser la localisation pour le choix automatique du sens.

## Horaires prévus
Le workflow `.github/workflows/horaires.yml` télécharge chaque nuit les horaires officiels (GTFS IDFM) et écrit
`data/horaires-52.json` et `data/horaires-22.json`. L'appli s'en sert pour les bus que le temps réel n'annonce pas
encore (2e/3e bus, premier bus du matin), affichés « horaire prévu ».
