# Draw.io Exporter for MkDocs

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

The values below are the defaults -- this section is optional and can be omitted if they work for you.

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
        # Output format (see draw.io --help | grep format)
        format: svg
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

## Hacking

To get completion working in your editor, set up a virtual environment in the root of this repository and install MkDocs:

```
$ pip3 install --user --upgrade setuptools twine wheel
$ python3 -m venv venv
$ . venv/bin/activate
$ pip install -r requirements.txt
```

Install and build the Webpack assets:

```
$ python3 setup.py develop
```

To install the plugin onto a local MkDocs site in editable form:

```
$ pip install --editable /path/to/mkdocs-drawio-exporter
```

Note that you'll need to repeat this step if you make any changes to the `entry_points` listed in `setup.py`.

Run the tests with the Python `unittest` module:

```
$ python -m unittest mkdocsdrawioexporter.tests
```

## Upgrading dependencies

To upgrade the dependencies, install `pip-upgrader`:

```console
. venv/bin/activate
pip install -r requirements.dev.txt
```

Then proceed to update the dependencies:

```console
pip-upgrade requirements.dev.txt
```

## Releasing

Build the distributable package:

```
$ python3 setup.py sdist bdist_wheel
```

Push it to the PyPI test instance:

```
$ python3 -m twine upload --repository-url https://test.pypi.org/legacy/ dist/*
```

Test it inside a virtual environment:

```
$ pip install --index-url https://test.pypi.org/simple/ --no-deps mkdocs-drawio-exporter
```

Let's go live:

```
$ python3 -m twine upload dist/*
```
