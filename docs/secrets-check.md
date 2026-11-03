# Secrets check

Done before the first public release (2026-11-02).

| Check | Result |
|---|---|
| Tracked files named like `.env`, `secret`, `token`, `.pem`, `.key` | Only `.env.example`, which holds empty `HA_URL=` and `HA_TOKEN=` |
| Hard-coded keys, passwords, bearer tokens, `sk-`/`ghp_`/JWT patterns in tracked files | None. Matches are `secrets.GITHUB_TOKEN` in the release workflow, the `.gitignore` entries, and a test string `invalid x-api-key` |
| Private addresses or hostnames (`192.168.`, `.local`, `duckdns`, `nabu.casa`) | None in the code or docs |
| Git history: secret-like files ever added, JWT-looking strings | None |
| Environment variables read by the code | Only `npm_package_version` in `frontend/vite.config.ts`, with a `"dev"` fallback |

The workflows use only the automatic `GITHUB_TOKEN`. No repository secrets need to be set up.
`.env` and `secrets.yaml` are git-ignored.
