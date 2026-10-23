# News fragments

Every change that users should know about adds **one file** to this directory.
At release time `make cl-build VERSION=X.Y.Z` collates them into a new
`CHANGELOG.md` section and deletes them.

## Filename

```
<issue>.<type>.md
```

- `<issue>`: the GitHub issue or PR number (e.g. `42`). If there is none, a
  short slug prefixed with `+` (e.g. `+slots`); the `+` keeps it out of the
  issue numbering.
- `<type>`: one of `added`, `changed`, `deprecated`, `removed`, `fixed`,
  `security` (Keep a Changelog categories), or `misc` for an internal change
  users need not know about (agent rules, CI, test refactoring). A `misc`
  fragment may be empty: it satisfies `make cl-check`, and its text never
  reaches `CHANGELOG.md`.

Examples: `42.added.md`, `57.fixed.md`, `+slots.added.md`, `+ci.misc.md`.

## Content

One entry, in the past tense, as it should read in the changelog. Markdown is
fine.

## Commands

```
make cl-preview VERSION=X.Y.Z   # preview the collated result
make cl-check                   # what CI runs on your PR (part of `make check`)
make cl-build VERSION=X.Y.Z     # write CHANGELOG.md and remove the fragments
```

This `README.md` and `_template.md` are ignored by towncrier (`ignore` in
`pyproject.toml`).
