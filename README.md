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


## Support

If you find this tool useful, please consider supporting its development.
Once this repository is published, you can check out the GitHub Sponsors profile to support my work.
