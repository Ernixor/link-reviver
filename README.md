# Link-Reviver

A simple CLI tool to check and fix broken links in Markdown files using the Wayback Machine.

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

If you find this tool useful, please consider supporting its development.
Once this repository is published, you can check out the GitHub Sponsors profile to support my work.
