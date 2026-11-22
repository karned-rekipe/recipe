# Déploiement

L'image `ghcr.io/karned-rekipe/recipe` est multiarchitecture et publiée par tag
Git. GitOps crée deux Deployments : `rekipe-recipe-api` et
`rekipe-recipe-mcp`. Le chart injecte les URLs Keycloak et Media, ainsi que
l'URI MongoDB issue d'un Secret alimenté par Vault.

Les images sont sélectionnées par version et digest dans
`amazone-gitops-karned/applications/rekipe/helm/values.yaml`. Le namespace cible
est `rekipe`; la base partagée vit dans le namespace `database`.

Les NetworkPolicies autorisent MongoDB, Keycloak et Media, et limitent les
appels entrants interservices à l'agent et à l'Ingress.
