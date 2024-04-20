# Use with GitHub Actions

How to configure publishing to GitHub Pages using a GitHub Actions workflow, running on Ubuntu. `mkdocs` and any needed plugins are installed using Poetry.

## Poetry configuration

Ensure your Poetry configuration (`pyproject.toml`) contains all of the dependencies you need. For example:

```toml
[tool.poetry]
name = "my-docs"
version = "0.1.0"
description = ""
authors = ["Luke Carrier <luke@carrier.im>"]

[tool.poetry.dependencies]
python = "^3.10"
mkdocs = "^1.3.0"
mkdocs-drawio-exporter = "^0.9.0"

[tool.poetry.dev-dependencies]

[build-system]
requires = ["poetry-core>=1.0.0"]
build-backend = "poetry.core.masonry.api"
```

If any are missing, add them as follows:

```console
poetry add mkdocs-plugin-redirects
```

## Create the workflow

Create `.github/workflows/publish.yml`:

```yaml
name: publish

on:
  push:
    branches:
      - master

permissions:
  contents: read
  pages: write
  id-token: write

concurrency:
  group: pages
  cancel-in-progress: true

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4
      - name: Configure Pages
        uses: actions/configure-pages@v5
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: 3.x
      - name: Setup Poetry
        uses: abatilo/actions-poetry@v2
      - name: Install Draw.io Desktop
        run: |
          set -euo pipefail

          drawio_arch=amd64
          drawio_version=18.1.3
          drawio_sha256sum=39a50f25ad52d6909c5c18d89a7cfc193e8e31fb98458a390c0a0709d22e9e10

          drawio_deb="drawio-${drawio_arch}-${drawio_version}.deb"
          drawio_url="https://github.com/jgraph/drawio-desktop/releases/download/v${drawio_version}/${drawio_deb}"

          curl -L -o "$drawio_deb" "$drawio_url"
          sha256sum --check <<<"${drawio_sha256sum}  $drawio_deb"
          sudo apt-get install -y libasound2 xvfb ./"$drawio_deb"
      - name: Install Python dependencies
        run: poetry install
      - name: Build
        run: xvfb-run -a poetry run mkdocs build
      - name: Upload Pages artifact
        uses: actions/upload-pages-artifact@v3
        with:
          path: site
  deploy:
    needs: build
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - name: Deploy GitHub Pages
        id: deployment
        uses: actions/deploy-pages@v4
```
