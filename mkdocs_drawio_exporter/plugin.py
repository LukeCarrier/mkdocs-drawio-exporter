import os.path
import sys

import mkdocs
from mkdocs.config import config_options
import mkdocs.plugins
from mkdocs.structure.files import Files
from mkdocs.utils import copy_file

from .exporter import ConfigurationError, DrawIoExporter, Source


log = mkdocs.plugins.log.getChild('drawio-exporter')


class DrawIoExporterPlugin(mkdocs.plugins.BasePlugin):
    """Draw.io Exporter MkDocs plugin.

    Contains only the bindings to MkDocs events, as it's difficult to isolate
    this module from MkDocs for testing.
    """

    config_scheme = (
        ('cache_dir', config_options.Type(str)),
        ('drawio_executable', config_options.Type(str)),
        ('drawio_args', config_options.Type(list, default=[])),
        ('format', config_options.Type(str, default='svg')),
        ('embed_format', config_options.Type(str, default='{img_open}{img_src}{img_close}')),
        ('sources', config_options.Type(str, default='*.drawio')),
    )

    exporter = None

    sources = []

    def on_config(self, config):
        self.exporter = DrawIoExporter(log)

        self.config['cache_dir'] = self.exporter.prepare_cache_dir(
                self.config['cache_dir'], config['docs_dir'])
        try:
            self.config['drawio_executable'] = self.exporter.prepare_drawio_executable(
                    self.config['drawio_executable'],
                    DrawIoExporter.DRAWIO_EXECUTABLE_NAMES,
                    self.exporter.drawio_executable_paths(sys.platform))
        except ConfigurationError as e:
            raise mkdocs.exceptions.ConfigurationError(str(e))

        os.makedirs(self.config['cache_dir'], exist_ok=True)

        log.debug('Using Draw.io executable "{}", arguments {} and cache directory "{}"'.format(
                self.config['drawio_executable'], self.config['drawio_args'],
                self.config['cache_dir']))

    def on_post_page(self, output_content, page, **kwargs):
        output_content, content_sources = self.exporter.rewrite_image_embeds(
                output_content, self.config['sources'],
                self.config['format'], self.config['embed_format'])

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
            cache_filename, exit_status = self.exporter.ensure_file_cached(
                    abs_src_path, source.source_rel, source.page_index,
                    self.config['drawio_executable'], self.config['drawio_args'],
                    self.config['cache_dir'], self.config['format'])

            if exit_status not in (None, 0):
                log.error('Export failed with exit status {}; skipping copy'.format(exit_status))
                continue

            try:
                copy_file(cache_filename, abs_dest_path)
            except FileNotFoundError:
                log.warn('Export successful, but wrote no output file')
