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

```yaml
plugins:
    - drawio-exporter:
        # Diagrams are cached to speed up site generation. The default path is
        # drawio-exporter, relative to the documentation directory.
        cache_dir: 'drawio-exporter'
        # Path to draw.io or draw.io.exe. Will be determined from the PATH
        # environment variable if not specified.
        drawio_executable: null
        # Output format (see draw.io --help | grep format)
        format: svg
        # Glob pattern for matching source files
        sources: '*.drawio'
```

## Hacking

To get completion working in your editor, set up a virtual environment in the root of this repository and install MkDocs:

```
$ pip3 install --user --upgrade setuptools twine wheel
$ python3 -m venv venv
$ . venv/bin/activate
$ pip install -r requirements.txt
```

To install the plugin onto a local MkDocs site in editable form:

```
$ pip install --editable /path/to/mkdocs-drawio-exporter
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
