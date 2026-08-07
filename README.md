# BlindTest Server

Serveur Internet léger pour Blind Test Pro.

## Fonctions
- FastAPI
- WebSockets
- salons de jeu
- pseudos joueurs
- premier buzz verrouillé côté serveur
- remise à zéro par l'animateur
- page mobile joueur
- page animateur de test
- endpoint `/health`
- configuration Render incluse

## Déploiement Render

1. Créer un dépôt GitHub `blindtest-server`.
2. Envoyer tous les fichiers de ce projet à la racine du dépôt.
3. Dans Render : **New > Web Service**.
4. Connecter le dépôt GitHub.
5. Render détectera `render.yaml`, ou utiliser :
   - Build command: `pip install -r requirements.txt`
   - Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
6. Déployer.

## Test

Une fois déployé :

- `/` : accueil
- `/host` : interface animateur de test
- `/play` : interface joueur
- `/health` : état du serveur

### Exemple

1. Ouvrir `/host`.
2. Créer une partie.
3. Copier le code.
4. Sur un téléphone, ouvrir `/play?room=1234`.
5. Entrer un pseudo.
6. Buzzer.
7. Le premier buzz s'affiche sur l'écran animateur.

## API

### Créer un salon

`POST /api/rooms`

Corps optionnel :

```json
{"code":"1234"}
```

### WebSocket joueur

`/ws/player/{room}/{name}`

Le joueur envoie :

```json
{"type":"buzz"}
```

### WebSocket animateur

`/ws/host/{room}`

Commandes :

```json
{"type":"reset"}
{"type":"lock"}
{"type":"unlock"}
{"type":"ping"}
```

## Remarque

Cette version conserve les salons en mémoire. C'est adapté à un premier déploiement Render et à une soirée Blind Test. Si le service redémarre, les salons en cours sont perdus.
