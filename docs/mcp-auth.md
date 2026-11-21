# Authentification OAuth du MCP Recipe

Le transport HTTP MCP de `recipe` est un **serveur de ressources OAuth 2.1**.
Il n'authentifie pas directement les utilisateurs et n'émet aucun jeton :
Keycloak assure la connexion, le consentement et l'émission des access tokens.

Cette séparation suit le contrat d'autorisation MCP :

1. le client appelle le MCP sans jeton ;
2. le MCP répond `401` avec un challenge `WWW-Authenticate` ;
3. le client découvre Keycloak dans les métadonnées RFC 9728 ;
4. le client obtient un jeton par un flux OAuth adapté à son identité ;
5. le MCP valide signature, algorithme, `iss`, `aud`, `exp`, `nbf`, scopes et rôle ;
6. le tool n'est exécuté qu'après ces contrôles.

## Identités prises en charge

### Personne avec Codex

Codex utilise un client Keycloak **public** pré-enregistré :

- client : `rekipe-mcp-codex` ;
- flux : Authorization Code ;
- PKCE obligatoire : `S256` ;
- callback loopback : `http://127.0.0.1/callback/tLYe0rBa72Al`, avec port
  dynamique selon RFC 8252 ;
- aucun client secret stocké dans Codex.

Le suffixe `tLYe0rBa72Al` est l'identifiant stable calculé par Codex pour l'URL
canonique de ce MCP. Keycloak enregistre ce chemin exact, sans wildcard ; sa
gestion des clients natifs accepte ensuite le port loopback éphémère. Si l'URL
publique du MCP change, ce callback et le client Keycloak doivent être mis à
jour ensemble.

L'utilisateur doit posséder le rôle realm `rekipe:mcp-access`. Retirer ce rôle
empêche l'obtention d'un accès utilisable par le MCP, même si la personne peut
encore se connecter à l'interface web Rekipe.

Le client Codex a `fullScopeAllowed=false` et ne peut projeter que ce rôle MCP
dans ses jetons. Les autres rôles éventuellement détenus par l'utilisateur ne
sont pas transmis à ce client. Ses access tokens expirent après cinq minutes ;
une révocation de rôle ou de client peut donc laisser un jeton déjà émis valide
pendant au plus cette durée.

Configuration Codex :

```bash
codex mcp add rekipe \
  --url https://rekipe.amazone.lan/api/recipe-mcp/mcp \
  --oauth-client-id rekipe-mcp-codex

codex mcp login rekipe \
  --scopes recipes:read,recipes:write,recipes:image:generate
```

Le navigateur est ouvert uniquement pour la connexion Keycloak. Codex reçoit
ensuite des access tokens courts et les renouvelle selon le protocole OAuth.

### Agent sans utilisateur

Un agent de service dispose de son propre client Keycloak **confidentiel**. Il
utilise le grant `client_credentials`, avec un secret distinct conservé dans
Vault. Le compte de service reçoit :

- le rôle realm `rekipe:mcp-access` ;
- uniquement les scopes nécessaires à son travail ;
- aucun scope `recipes:delete` ou `recipes:admin` par défaut.

Un secret d'agent ne doit jamais être partagé avec un autre agent, placé dans
un fichier versionné, passé dans une URL ou fourni comme argument de tool.
Révoquer un agent consiste à désactiver son client Keycloak ou à faire tourner
son secret dans Vault.

## Scopes

| Scope | Autorise |
|---|---|
| `recipes:read` | connexion MCP, listes, recherches, détails, resources et prompts |
| `recipes:write` | création, modification, duplication, fusion et suggestions |
| `recipes:image:generate` | génération ou remplacement de l'image principale |
| `recipes:delete` | soft-delete des recettes et ressources catalogue |
| `recipes:admin` | purge irréversible des éléments supprimés |

`recipes:read` est obligatoire pour toute connexion. Les autres scopes sont
cumulatifs et contrôlés au niveau de chaque tool. Le rôle
`rekipe:mcp-access` constitue une seconde barrière indépendante des scopes.

## Liaison du jeton à la ressource

L'identifiant canonique du serveur de ressources de préproduction est :

```text
https://rekipe.amazone.lan/api/recipe-mcp/mcp
```

Cette valeur est publiée comme `resource`, ajoutée par Keycloak dans `aud` et
comparée exactement par `recipe`. Un jeton émis pour le frontend, une autre API
ou un autre MCP est donc rejeté.

Les métadonnées publiques sont exposées sur :

```text
https://rekipe.amazone.lan/.well-known/oauth-protected-resource/api/recipe-mcp/mcp
```

Elles ne contiennent aucun secret. L'endpoint MCP, lui, refuse toute requête
anonyme avant l'initialisation d'une session MCP.

## Configuration du serveur

| Variable | Signification |
|---|---|
| `REKIPE_MCP_PUBLIC_BASE_URL` | base publique HTTPS, sans le suffixe `/mcp` |
| `REKIPE_MCP_AUTH_ISSUER_URL` | issuer public exact du realm Keycloak |
| `REKIPE_MCP_AUTH_JWKS_URI` | endpoint JWKS, éventuellement interne au cluster |
| `REKIPE_MCP_AUTH_REQUIRED_ROLE` | rôle realm exigé, défaut `rekipe:mcp-access` |
| `REKIPE_AUTH_DISABLED` | bypass réservé au développement local explicite |

Le déploiement de préproduction ne doit jamais définir
`REKIPE_AUTH_DISABLED=true`. L'issuer public et le JWKS interne peuvent être
différents : le premier lie cryptographiquement l'identité du jeton, le second
évite une boucle réseau par l'Ingress pour télécharger les clés publiques.

## Vérifications opérationnelles

Sans jeton :

```bash
curl --include \
  https://rekipe.amazone.lan/api/recipe-mcp/mcp
```

Résultat attendu : `401 Unauthorized` avec `WWW-Authenticate: Bearer` et une
URL `resource_metadata`.

Métadonnées :

```bash
curl --fail --silent --show-error \
  https://rekipe.amazone.lan/.well-known/oauth-protected-resource/api/recipe-mcp/mcp \
  | jq
```

Un test de bout en bout doit ensuite couvrir au minimum :

- jeton valide avec `recipes:read` : `list_recipes` accepté ;
- même jeton : `generate_recipe_image` refusé ;
- ajout de `recipes:image:generate` : génération acceptée ;
- mauvais issuer, mauvaise audience, jeton expiré ou rôle absent : `401` ;
- scope d'action absent : tool refusé ;
- révocation du rôle ou désactivation du client : nouvel accès impossible.

## Choix de sécurité

- L'ancienne allowlist IP n'est pas une identité et n'est pas conservée comme
  mécanisme d'autorisation MCP.
- L'enregistrement dynamique anonyme de clients Keycloak n'est pas activé. Un
  client humain ou machine est créé explicitement, puis auditable.
- TLS reste obligatoire ; aucun contournement de validation de certificat ne
  fait partie du parcours.
- Les access tokens ne sont jamais loggés ni renvoyés par un tool.
- `get_profile` expose seulement l'identifiant stable `sub` et les libellés de
  profil déjà présents dans le jeton ; il ne révèle aucun secret.
