# Diagrams.net (Draw.io) Exporter for MkDocs

Exports your Draw.io diagrams at build time for easier embedding into your documentation.

---

## Quick start

First install the package:

```
$ pip install mkdocs-drawio-exporter
```

Then enable it:

```yaml
plugins:
    - drawio-exporter
```

## Configuration

For the default configuration, just add the plugin to the `plugins` key:

```yaml
plugins:
    - drawio-exporter
```

You can override the default configuration; values shown are defaults:

```yaml
plugins:
    - drawio-exporter:
        # Diagrams are cached to speed up site generation. The default path is
        # drawio-exporter, relative to the documentation directory.
        cache_dir: 'drawio-exporter'
        # Path to the Draw.io executable:
        #   * drawio on Linux
        #   * draw.io on macOS
        #   * or draw.io.exe on Windows
        # We'll look for it on your system's PATH, then default installation
        # paths. If we can't find it we'll warn you.
        drawio_executable: null
        # Additional Draw.io CLI args
        drawio_args: []
        # Output format (see draw.io --help | grep format)
        format: svg
        # Embed format
        #   * The default is to embed via the <img> tag, only rewriting the
        #     value of the src attribute.
        #   * Consider <object type="image/svg+xml" data="{img_src}"></object>
        #     to enable interactive elements (like hyperlinks) in SVGs.
        #   * Consider {content} to inline SVGs into documents directly, useful
        #     for styling with CSS, preserving interactivity, and improving
        #     search by indexing diagram text.
        embed_format: '{img_open}{img_src}{img_close}'
        # Glob pattern for matching source files
        sources: '*.drawio'
```

## Usage

With the plugin configured, you can now proceed to embed images by simply embedding the `*.drawio` diagram file as you would with any image file:

```markdown
![My alt text](my-diagram.drawio)
```

If you're working with multi-page documents, append the index of the page as an anchor in the URL:

```markdown
![Page 1](my-diagram.drawio#0)
```

The plugin will export the diagram to the `format` specified in your configuration and will rewrite the `<img>` tag in the generated page to match. To speed up your documentation rebuilds, the generated output will be placed into `cache_dir` and then copied to the desired destination. The cached images will only be updated if the source diagram's modification date is newer than the cached export. Thus, bear in mind caching works per file - with large multi-page documents a change to one page will rebuild all pages, which will be slower than separate files per page.

### GitHub Actions

See [this guide](./docs/github-actions.md).

### Headless usage

In addition to the above, if you're running in a headless environment (e.g. in integration, or inside a Docker container), you may need to ensure a display server is running and that the necessary dependencies are installed.

On Debian and Ubuntu, the following should install the dependencies:

```console
sudo apt install libasound2 xvfb
```

To run MkDocs with an automatically assigned X display, wrap the command as follows:

```console
xvfb-run -a mkdocs build
```

### Running without the sandbox

If you're seeing messages like the following it's likely that you're running MkDocs as root:

```text
[22:0418/231827.169035:FATAL:electron_main_delegate.cc(211)] Running as root without --no-sandbox is not supported. See https://crbug.com/638180.
```

If possible, consider running MkDocs as a non-privileged user. Depending on the circumstances (e.g. running within an unprivileged container) it may be appropriate to disable the Chrome sandbox by adding the following option to `mkdocs.yml`:

```yaml
plugins:
    - drawio-exporter:
        drawio_args:
            - --no-sandbox
```

## Hacking

To get completion working in your editor, set up a virtual environment in the root of this repository and install MkDocs:

```
$ pip3 install --user --upgrade wheel
$ pipx install twine
$ poetry install
```

To install the plugin onto a local MkDocs site in editable form:

```
$ poetry add --editable /path/to/mkdocs-drawio-exporter
```

Note that you'll need to repeat this step if you make any changes to the `[tool.poetry.plugins.*]` sections listed in `pyproject.toml`.

Run the tests with the `test` script:

```
$ poetry run test
```

## Upgrading dependencies

To upgrade the dependencies, first make any necessary changes to the constraints expressed in the `[tool.poetry.dependencies]` section of `pyproject.toml`, then have Poetry update them:

```
$ poetry update
```

## Releasing

Build the distributable package:

```
$ poetry build
```

Push it to the PyPI test instance:

```
$ twine upload --repository-url https://test.pypi.org/legacy/ dist/*
```

Test it inside a virtual environment:

```
$ pip install --index-url https://test.pypi.org/simple/ --no-deps mkdocs-drawio-exporter
```

Let's go live:

```
$ twine upload dist/*
```
