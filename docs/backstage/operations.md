# Exploitation

Les probes `/health` et `/ready` sont servies sur le port d'administration
`9000`. Une validation fonctionnelle doit aussi lire une recette par l'Ingress,
car une probe verte ne valide ni MongoDB ni l'hydratation complète du catalogue.

Avant une migration, sauvegarder MongoDB et les originaux Media. Les imports de
préproduction sont additifs et idempotents sur `_id`; les domaines planning et
shopping ne font pas partie d'une restauration du catalogue recettes.

Pour revenir en arrière, restaurer le tag et le digest précédents dans GitOps,
attendre Argo et vérifier séparément l'API, le MCP OAuth et les images. Ne jamais
supprimer une collection ou réimporter un dump sans sauvegarde et inventaire.
