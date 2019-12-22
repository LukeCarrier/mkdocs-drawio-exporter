import fnmatch
import hashlib
import os.path
import re
import shutil
import subprocess

import mkdocs
import mkdocs.plugins
import mkdocs.utils


log = mkdocs.plugins.log.getChild('drawio-exporter')


class DrawIoExporter(mkdocs.plugins.BasePlugin):
    drawio_executable_names = ['drawio', 'draw.io']

    source_files = []

    config_scheme = (
        ('cache_dir', mkdocs.config.config_options.Type(mkdocs.utils.string_types)),
        ('drawio_executable', mkdocs.config.config_options.Type(mkdocs.utils.string_types)),
        ('format', mkdocs.config.config_options.Type(mkdocs.utils.string_types, default='svg')),
        ('sources', mkdocs.config.config_options.Type(mkdocs.utils.string_types, default='*.drawio')),
    )

    image_re = None

    def prepare_cache_dir(self, cache_dir, docs_dir):
        """Ensure the cache path is set, absolute and exists.

        :param str cache_dir: Configured cache directory.
        :param str docs_dir: Docs directory, in which to base relative cache directories.
        :return str: Final cache directory.
        """
        if not cache_dir:
           cache_dir = 'drawio-exporter'
        if not os.path.isabs(cache_dir):
            cache_dir = os.path.join(docs_dir, cache_dir)
        os.makedirs(cache_dir, exist_ok=True)
        return cache_dir

    def prepare_drawio_executable(self, executable):
        """Ensure the Draw.io executable path is configured, or guess it.

        :param str executable: Configured Draw.io executable.
        :return str: Final Draw.io executable.
        """
        if executable and not os.path.isfile(executable):
            log.error('Configured Draw.io executable "{}" doesn\'t exist', executable)
            return

        for name in self.drawio_executable_names:
            executable = shutil.which(name)
            if executable:
                log.debug('Found Draw.io executable "{}" at "{}"'.format(name, executable))
                return executable

        log.error('Unable to find Draw.io executable; ensure it\'s on PATH or set drawio_executable option')

    def on_config(self, config):
        self.config['cache_dir'] = self.prepare_cache_dir(
                self.config['cache_dir'], config['docs_dir'])
        self.config['drawio_executable'] = self.prepare_drawio_executable(
                self.config['drawio_executable'])

        self.image_re = re.compile('(<img[^>]+src=")([^">]+)("\s*\/?>)')

        log.debug('Using Draw.io executable "{}" and cache directory "{}"'.format(
                self.config['drawio_executable'], self.config['cache_dir']))

    def on_post_page(self, output_content, **kwargs):
        def replace(match):
            if fnmatch.fnmatch(match.group(2), self.config['sources']):
                return '{}{}.{}{}'.format(match.group(1), match.group(2), self.config['format'], match.group(3))
            else:
                return match.group(0)
        return self.image_re.sub(replace, output_content)

    def on_files(self, files, config):
        self.source_files = [f for f in files if fnmatch.fnmatch(f.src_path, self.config['sources'])]
        log.debug('Found {} source files matching glob {}'.format(len(self.source_files), self.config['sources']))

        keep = [f for f in files if not f.abs_src_path.startswith(self.config['cache_dir'])]
        log.debug('{} files left after excluding cache'.format(len(keep)))
        return mkdocs.structure.files.Files(keep)

    def on_post_build(self, config):
        for f in self.source_files:
            abs_dest_path = f.abs_dest_path + '.' + self.config['format']
            log.debug('Exporting {} to {}'.format(f.src_path, abs_dest_path))

            cache_filename = os.path.join(self.config['cache_dir'], hashlib.sha1(f.src_path.encode('utf-8')).hexdigest())
            if os.path.exists(cache_filename) and os.path.getmtime(cache_filename) >= os.path.getmtime(f.abs_src_path):
                log.debug('Source file appears unchanged; using cached copy from {}'.format(cache_filename))
                mkdocs.utils.copy_file(cache_filename, abs_dest_path)
            elif not self.config['drawio_executable']:
                log.warn('Skipping build of "{}" as Draw.io executable not on path'.format(f.src_path))
            else:
                try:
                    cmd = [
                        self.config['drawio_executable'],
                        '--export', f.abs_src_path,
                        '--output', cache_filename,
                        '--format', self.config['format'],
                    ]
                    log.debug('Using export command {}'.format(cmd))
                    exit_status = subprocess.call(cmd)
                    if exit_status == 0:
                        try:
                            mkdocs.utils.copy_file(cache_filename, abs_dest_path)
                        except FileNotFoundError:
                            log.exception('Output file not created in cache')
                    else:
                        log.error('Export failed with exit status {}'.format(exit_status))
                except:
                    log.exception('Subprocess raised exception')
