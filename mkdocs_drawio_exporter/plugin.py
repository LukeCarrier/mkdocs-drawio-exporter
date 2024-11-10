import os.path
import sys

import mkdocs
from mkdocs.config import config_options
import mkdocs.plugins
from mkdocs.structure.files import Files
from mkdocs.utils import copy_file

from .exporter import ConfigurationError, DrawIoExporter


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
        ('embed_format', config_options.Type(str, default='<img alt="{img_alt}" src="{img_src}">')),
        ('sources', config_options.Type(str, default='*.drawio')),
    )

    exporter = None

    sources = []

    def on_config(self, config, **kwargs):
        self.exporter = DrawIoExporter(log, config['docs_dir'])

        self.config['cache_dir'] = self.exporter.prepare_cache_dir(
                self.config['cache_dir'])
        try:
            self.config['drawio_executable'] = self.exporter.prepare_drawio_executable(
                    self.config['drawio_executable'],
                    DrawIoExporter.DRAWIO_EXECUTABLE_NAMES,
                    self.exporter.drawio_executable_paths(sys.platform))
            self.exporter.validate_config(self.config)
        except ConfigurationError as e:
            raise mkdocs.exceptions.ConfigurationError(str(e))

        os.makedirs(self.config['cache_dir'], exist_ok=True)

        log.debug(f'Using Draw.io executable "{self.config["drawio_executable"]}", '
                f'arguments {self.config["drawio_args"]} and '
                f'cache directory "{self.config["cache_dir"]}"')

    def on_page_markdown(self, markdown, page, **kwargs):
        output_content, content_sources = self.exporter.rewrite_image_embeds(
                page.file.src_path, markdown, self.config)

        self.sources += content_sources

        return output_content

    def on_files(self, files, config, **kwargs):
        keep = self.exporter.filter_cache_files(files, self.config['cache_dir'])
        log.debug(f'{len(keep)} files left after excluding cache')

        return Files(keep)

    def on_post_build(self, config, **kwargs):
        sources = set(self.sources)
        log.debug(f'Found {len(sources)} unique sources in {len(self.sources)} total embeds')
        self.sources = []

        for source in sources:
            dest_rel_path = f'{source.source_rel}-{source.page_index}.{self.config["format"]}'
            abs_src_path = os.path.join(config['docs_dir'], source.source_rel)
            abs_dest_path = os.path.join(config['site_dir'], dest_rel_path)
            cache_filename, exit_status = self.exporter.ensure_file_cached(
                    abs_src_path, source.source_rel, source.page_index,
                    self.config)

            if exit_status not in (None, 0):
                log.error(f'Export failed with exit status {exit_status}; skipping copy')
                continue

            try:
                copy_file(cache_filename, abs_dest_path)
            except FileNotFoundError:
                log.warning('Export successful, but wrote no output file')
