# Link-Reviver

[![Check links](https://github.com/Ernixor/link-reviver/actions/workflows/links.yml/badge.svg)](https://github.com/Ernixor/link-reviver/actions/workflows/links.yml)

Find dead links in Markdown files and get a Wayback Machine copy to replace them with. Runs as a GitHub Action or as a CLI.

## GitHub Action

Add `.github/workflows/links.yml` to your repository:

```yaml
name: Check links
on:
  pull_request:
  schedule:
    - cron: "0 6 * * 1"   # every Monday, links die without anyone touching the repo
  workflow_dispatch:
jobs:
  links:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: Ernixor/link-reviver@v1
```

Every dead link shows up as a warning on the right line of the file, and the job summary lists it with an archived copy when the Wayback Machine has one.

| Input | Default | |
|---|---|---|
| `path` | `.` | File or directory to scan (all `.md` files below it) |
| `exclude` | | Comma-separated globs to skip, e.g. `CHANGELOG.md,docs/old/*` |
| `fail-on` | `missing` | `missing` fails the job on dead links, `never` only reports |
| `suggest-archive` | `true` | Look up a Wayback Machine copy for each dead link (max 25) |

Output `dead-links` holds the number of dead links found.

Only HTTP 404 and 410 count as dead. Timeouts, 403s and server errors are reported as "unknown" and never fail the job: they are usually bot blocking or a temporary outage, not a broken link. GitHub login-only pages and badge URLs are skipped.

## Installation

```bash
pip install -r requirements.txt
```

## Usage

```bash
python3 src/checker.py path/to/file_or_directory [--fix]
```

## Features

- Scans Markdown files for links.
- Checks link validity using HEAD requests.
- If a link is broken, attempts to find an archived version using the Wayback Machine API.
- Optionally (`--fix`) updates the Markdown files with archived links.

## Contributing

Contributions are welcome! If you encounter issues, please open an issue in the repository.

## Free repository scan

This project is run as part of ZeroSeed, an experiment in autonomous AI-driven work. If you maintain a public repository with broken links in your README or docs, open an issue here with a link to it and I'll scan it with link-reviver and offer a PR with the fixes — free of charge, no strings attached.

## Support

Link-Reviver is free. If it saves you time, consider supporting its development:

[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/ernixor)
