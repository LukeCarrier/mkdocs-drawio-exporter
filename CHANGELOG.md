# Changelog

## 0.9.0: maintainer guilt

* Migrate to Poetry for dependency management
* Update all of our ailing dependencies
* Use `Logger.warning` over `Logger.warn` to fix deprecation warnings
* Document `--embed-svg-images` for shape libraries
* Support inlining SVG content with `embed_format: '{content}'`; props @herberton
* Fix handling of diagram filenames containing spaces

## 0.8.0: embed modes for SVG

* Allow embedding SVGs inline or with `<object>`
* Update dependencies

## 0.7.0: clean up configuration handling

* Handle missing executable by exiting
* Honour a passed `drawio_executable`
* Correctly handle Program Files (x86) on 64-bit Windows
* Update dependencies

## 0.6.1: fix handling of cached files

* Fix handling of cached files

## 0.6.0: ease containerisation

* New `drawio_args` option allows passing additional args to the Draw.io CLI
* Improve handling of cases where Draw.io reports a successful export but doesn't write an output file

## 0.5.0: support MkDocs 1.1

* Make dependency upgrades a little easier
* Drop Python 2.7 support

## 0.4.0: Merry Christmas

* Locate `draw.io` binary on `PATH` based on platform
* Better handle missing `draw.io` binary
* Added support for multi-page documents
* Clean up the code and write some unit tests

## 0.3.1: fix some more stuff

* Actually copy the cached file when we say we will

## 0.3.0: fix some stuff

* Tighten up error handling around Draw.io execution

## 0.2.0: make it work everywhere

* Locate `drawio` executable for non-Windows platforms

## 0.1.0: initial release

* Locate `draw.io` executable on `PATH`
* Render to specified format
* Cache rendered artifacts for quicker builds
