from http.server import executable
from logging import Logger
import os.path
import sys

import mkdocs
import mkdocs.plugins

from mkdocs.plugins import BasePlugin, log
from mkdocs.config.config_options import Type
from mkdocs.structure.files import Files
from mkdocs.utils import copy_file
from mkdocs.config import Config

from .exporter import ConfigurationError, DrawIoExporter, Source


logger: Logger = log.getChild('drawio-exporter')


class DrawIoExporterPlugin(BasePlugin):
    """Draw.io Exporter MkDocs plugin.

    Contains only the bindings to MkDocs events, as it's difficult to isolate
    this module from MkDocs for testing.
    """

    config_scheme = (
        ('cache_dir', Type(str)),
        ('drawio_executable', Type(str)),
        ('drawio_args', Type(list, default=[])),
        ('format', Type(str, default='svg')),
        ('embed_format', Type(str, default='{img_open}{img_src}{img_close}')),
        ('sources', Type(str, default='*.drawio')),
    )

    exporter = None

    def on_config(self, config: Config):

        try:

            self.exporter = DrawIoExporter(config={**self.config, **config, **{'logger': logger}})

            os.makedirs(self.exporter.cache_dir, exist_ok=True)

            logger.debug(
                'Using Draw.io executable "{}", arguments {} and cache directory "{}"'
                    .format(
                        self.exporter.drawio_executable, 
                        self.exporter.drawio_args,
                        self.exporter.cache_dir
                    )
            )

            self.sources = []

        except ConfigurationError as e:
            raise mkdocs.exceptions.ConfigurationError(str(e))

    def on_post_page(self, content: str, page, **kwargs):

        sources = self.exporter.get_sources_from(content, content_path=page.file.dest_path)

        for source in sources:

            cache_filename, exit_status = self.exporter.ensure_file_cached(
                source=os.path.join(self.exporter.docs_dir, source.source_rel), 
                source_rel=source.source_rel, 
                page_index=source.page_index
            )

            if exit_status not in (None, 0):
                logger.error('Export failed with exit status {}; skipping copy'.format(exit_status))
                continue

            try:
                
                output_path = os.path.join(self.exporter.site_dir,  '{}-{}.{}'.format(
                    source.source_rel, 
                    source.page_index, 
                    self.exporter.format
                ))

                copy_file(source_path=cache_filename, output_path=output_path)

            except FileNotFoundError:
                logger.warn('Export successful, but wrote no output file')

        return self.exporter.rewrite_image_embeds(content, content_path=page.file.dest_path)

    def on_files(self, files, **kwargs):
        keep = self.exporter.filter_cache_files(files)
        logger.debug('{} files left after excluding cache'.format(len(keep)))
        return Files(keep)
