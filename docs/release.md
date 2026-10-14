# Releasing Inköp

HACS installs Inköp from a GitHub **release**: the release carries `inkop.zip` (the integration with the built card), which HACS unpacks into `custom_components/inkop/`. The zip is built by the release workflow, so the built card (`custom_components/inkop/www/inkop-card.js`) is **not** committed to git.

## Versions

- Releases are tagged `vMAJOR.MINOR.PATCH` (a suffix such as `-beta1` is accepted). The first public release is `v0.1.0`; mark it as a *pre-release* in GitHub until the manual checks in `docs/dev.md` have all passed on a real Home Assistant (HACS only offers pre-releases to users who enable beta versions).
- The workflow stamps the tag's version into the packaged `manifest.json` and into the card (it shows in the browser console). The versions in the repository (`custom_components/inkop/manifest.json`, `frontend/package.json`) are placeholders and need no bump; a test only checks that they agree with each other.
- `ha-ica-todo` is a separate release in its own repository. The minimum version Inköp needs (`MIN_ICA_VERSION` in `custom_components/inkop/const.py`, currently 0.10.0) must have been released first.

## Checklist for a release

1. `main` is green in CI (Python, frontend, *Release package builds*, hassfest). The HACS validation job needs the repository license, description and topics (see "Before the public release").
2. The manual checks in `docs/dev.md` for the changes in this release have been done and noted in `plan.md`.
3. `ha-ica-todo` at the required version has a published GitHub release (HACS installs it from its release zip).
4. On GitHub: *Releases → Draft a new release*, create the tag `vX.Y.Z` on `main`, write short notes (what is new, anything users must do), tick *pre-release* if it is one, **Publish**.
5. The *Release* workflow runs: it lints and tests the card, builds it with the release version, packages `dist/inkop.zip` with `scripts/package-release.sh` and attaches it to the release. Check that the asset `inkop.zip` is there (about 50 KB).
6. Verify the install path on a Home Assistant: HACS → custom repository → *Inköp* → download the new release → restart → the integration loads, the card appears, and the version in the browser console matches. Then run the core checklist (features 1 to 6).

## What the workflow does, and how to try it locally

`.github/workflows/release.yaml` is small on purpose and uses only first-party actions. The same packaging runs on every pull request (the *Release package builds* job), so a broken release is found early. Locally:

```bash
./scripts/node.sh sh -c 'npm ci && npm pkg set version=0.1.0 && npm run build'
./scripts/package-release.sh v0.1.0      # writes dist/inkop.zip
unzip -l dist/inkop.zip
```

(`npm pkg set version=...` changes `frontend/package.json`: use the version that is already there, or undo with `git checkout frontend/package.json`.)

## If a release is wrong

Delete the GitHub release and its tag (people who already installed it keep it), fix the problem, and publish a new patch version. Do not re-use a tag.

## Before the public release

- **License:** HACS validation requires a `LICENSE` file; the maintainer has not chosen one yet. Without a license others have no right to use or change the code.
- **Repository description and topics:** set on GitHub (e.g. `home-assistant`, `hacs`, `ica`, `shopping-list`, `todo`); HACS validation checks both.
- **Screenshots:** `docs/images/*.png` come from the preview page with sample data. Replace them with screenshots from a real Home Assistant after the manual checks.
- **Brand assets:** an icon for Home Assistant's brand store (optional; the HACS job currently ignores this check).
