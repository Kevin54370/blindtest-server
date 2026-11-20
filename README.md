# BlindTestPro V3.1.2 — Serveur Render

## Nouveautés
- Wake Lock du navigateur pour empêcher la mise en veille de l'écran pendant la partie, si le navigateur et le téléphone le prennent en charge.
- Reconnexion WebSocket automatique avec délai progressif.
- Conservation locale du pseudo et de l'identifiant joueur (`localStorage`).
- Le serveur reprend l'inscription existante grâce à l'identifiant joueur.
- Une coupure temporaire ne supprime plus immédiatement le joueur : son inscription est conservée 2 heures.
- Les joueurs déconnectés restent visibles comme « Déconnecté » dans l'interface animateur.

## Déploiement Render
1. Décompresser cette archive.
2. Remplacer les fichiers du dépôt GitHub `blindtest-server` par le contenu du dossier.
3. Commit / push sur la branche suivie par Render.
4. Attendre le redéploiement puis vérifier `https://VOTRE-SERVEUR/health`.

## Limites à connaître
- Wake Lock fonctionne surtout sur les navigateurs mobiles récents en HTTPS. Le téléphone peut malgré tout suspendre une page si le système l'impose.
- Dans ce cas, la reconnexion automatique reprend la même identité au retour dans la page.
- Les salons et les identifiants sont stockés en mémoire sur le processus Render. Un redémarrage complet du serveur efface les salons en cours ; pour une persistance après redémarrage, il faudrait ajouter une base de données.
- L'identité locale est conservée sur le même navigateur et le même téléphone. Effacer les données du navigateur ou changer d'appareil fait perdre ce jeton local.
