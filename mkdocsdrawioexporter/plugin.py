import os.path
import re
import sys

import mkdocs
from mkdocs.config import config_options
import mkdocs.plugins
from mkdocs.structure.files import Files
from mkdocs.utils import copy_file, string_types

from .exporter import DrawIoExporter, Source


log = mkdocs.plugins.log.getChild('drawio-exporter')


class DrawIoExporterPlugin(mkdocs.plugins.BasePlugin):
    """Draw.io Exporter MkDocs plugin.

    Contains only the bindings to MkDocs events, as it's difficult to isolate
    this module from MkDocs for testing.
    """

    config_scheme = (
        ('cache_dir', config_options.Type(string_types)),
        ('drawio_executable', config_options.Type(string_types)),
        ('format', config_options.Type(string_types, default='svg')),
        ('image_re', config_options.Type(string_types, default='(<img[^>]+src=")([^">]+)("\s*\/?>)')),
        ('sources', config_options.Type(string_types, default='*.drawio')),
    )

    exporter = None

    sources = []
    image_re = None

    def on_config(self, config):
        self.exporter = DrawIoExporter(log)

        self.config['cache_dir'] = self.exporter.prepare_cache_dir(
                self.config['cache_dir'], config['docs_dir'])
        self.config['drawio_executable'] = self.exporter.prepare_drawio_executable(
                self.config['drawio_executable'], DrawIoExporter.DRAWIO_EXECUTABLE_NAMES,
                self.exporter.drawio_executable_paths(sys.platform))

        os.makedirs(self.config['cache_dir'], exist_ok=True)
        self.image_re = re.compile(self.config['image_re'])

        log.debug('Using Draw.io executable "{}", cache directory "{}" and image regular expression "{}"'.format(
                self.config['drawio_executable'], self.config['cache_dir'], self.config['image_re']))

    def on_post_page(self, output_content, page, **kwargs):
        output_content, content_sources = self.exporter.rewrite_image_embeds(
                output_content, self.image_re, self.config['sources'],
                self.config['format'])

        for source in content_sources:
            source.resolve_rel_path(page.file.dest_path)
        self.sources += content_sources

        return output_content

    def on_files(self, files, config):
        keep = self.exporter.filter_cache_files(files, self.config['cache_dir'])
        log.debug('{} files left after excluding cache'.format(len(keep)))

        return Files(keep)

    def on_post_build(self, config):
        sources = set(self.sources)
        log.debug('Found {} unique sources in {} total embeds'.format(len(sources), len(self.sources)))
        self.sources = []

        for source in sources:
            dest_rel_path = '{}-{}.{}'.format(
                    source.source_rel, source.page_index, self.config['format'])
            abs_src_path = os.path.join(config['docs_dir'], source.source_rel)
            abs_dest_path = os.path.join(config['site_dir'], dest_rel_path)
            cache_filename = self.exporter.ensure_file_cached(
                    abs_src_path, source.source_rel, source.page_index,
                    self.config['drawio_executable'], self.config['cache_dir'],
                    self.config['format'])

            try:
                copy_file(cache_filename, abs_dest_path)
            except FileNotFoundError:
                log.exception('Output file not created in cache')
