# Change requests for ha-ica-todo

`handla` never patches `ha-ica-todo`. The maintainer implements these in `per-lennartsson/ha-ica-todo` and publishes a versioned release. Mark each as done and bump the minimum version in `handla` when it ships.

## Done (v0.10.0, branch `list-events-and-metadata`, commit `c2fe1f1`)

- [x] #1 `ica_lists_changed` event after create/delete reload
- [x] #2 `offline_id`, `config_entry_id`, `comment` attributes on list entities
- [x] #3 Repo metadata points to the fork
- [x] #4 `ica_list_items_changed` event

## Done (v0.10.0, v0.11.0)

- [x] A. v0.10.0 released (13 Oct), v0.11.0 released (14 Oct)
- [x] E. Merge and name-normalisation fixes (v0.11.0: missing quantity is 1 pc, "bananas" normalises to "banana"). Verified from the release notes only, not by running the tests.
- [~] B. A Home Assistant test suite exists (flows, entities, services, coordinator, `test_utils_events.py`). Checked from the file list only; whether all six cases are covered is unverified.

## Done (v0.12.0, branch `article-group-categories`)

- [x] H. Article group (category) services for Handla's categories: `ica.get_article_groups`, `ica.get_shopping_list_items`, `ica.set_item_article_group` (with `remember`), and the option *Categorize items automatically*. Handla's minimum version is now v0.12.0. Written from the plan in `categories-plan.md`; **not checked against the released code**: confirm the service fields and answers, and that ICA keeps a category change made through `set_item_article_group` (manual check in `docs/dev.md`).

## Left (checked against `main` at v0.11.0)

### C. Make failure explicit in `ica_lists_changed` (recommended)
Still valid: a failed reload only logs and fires anyway; no `success`/`error` flag is passed.
Today a failed reload still fires the event with empty `entities`, so consumers must infer failure.

**Prompt for implementation:**
> Add `success` (bool) and `error` (string or null) to the `ica_lists_changed` payload. `success` is false when the config entry reload failed. Keep the other fields unchanged, update the README Events section and the tests.

### D. Report removed fields in `ica_list_items_changed` (minor)
Still valid: the changed-props loop runs over the new row only.
`diff_list_rows` only compares fields present in the new row, so an item that loses its quantity or unit is not reported.

**Prompt for implementation:**
> In `utils.diff_list_rows`, compare the union of keys of the old and new row (still ignoring `latestChange`), so removed fields appear in `changed_props`. Add a test.

### F. Bare numbers are split into quantity and name (minor)
`coordinator.parse_summary` turns the text `12` into quantity 1 and name `2`, and `1,5` into quantity 1 and name `,5`, because the quantity regex can backtrack inside a number. Still valid: `_SUMMARY_RE` has no lookahead after the quantity. `handla` keeps such text as a plain name, so the two parsers differ for these inputs.

**Prompt for implementation:**
> In `custom_components/ica/coordinator.py`, change `_SUMMARY_RE` so the quantity cannot be split inside a number: add `(?!\d|[.,]\d)` directly after `(?P<quantity>\d+(?:[.,]\d+)?)`. Add tests that `12` and `1,5` are kept as plain names and that `12 ägg` still parses as quantity 12.

### G. Pin the third-party action in the release workflow (recommended before more people install it)
Still valid: the workflow still uses `rogerselwyn/actions/release-asset@main`.
`.github/workflows/release.yaml` runs `rogerselwyn/actions/release-asset@main` with a token that can write to the repository. A branch reference means whatever that author pushes to `main` later runs in your releases.

**Prompt for implementation:**
> Replace the `rogerselwyn/actions/release-asset@main` step in `.github/workflows/release.yaml` with plain steps that need no third-party action: check out, write the release version into `custom_components/ica/manifest.json` (the existing `.github/scripts/update_hacs_manifest.py --version <tag without v>` does this), zip the contents of `custom_components/ica` into `ica.zip` (`cd custom_components/ica && zip -r ../../ica.zip .`), and upload it with `gh release upload "$TAG" ica.zip --clobber` using `GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}` and `permissions: contents: write`. Pass the tag through an environment variable, not directly into shell code. Test it with a pre-release.

## Dropped
- Nothing dropped. The ICA-app-only notification path (#4) is optional in `handla` (plan step 1.6).
