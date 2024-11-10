# FIXME: drop once we upgrade to Python 3.9
from __future__ import annotations

import fnmatch
import hashlib
import os.path
import re
import shutil
import subprocess
import sys
from typing import TypedDict
import urllib.parse


IMAGE_RE = re.compile(r'!\[(?P<alt>[^\]]*)\]\((?P<filename>[^\)]*)\)')


class Configuration(TypedDict):
    """Draw.io Exporter MkDocs plugin configuration.

    Contains the resolved configuration values, including defaults and any
    computed values (such as paths to binaries).

    Seems ugly to shadow BasePlugin.config_scheme, but improves type hints and
    allows us to more easily pass configuration around."""

    cache_dir: str
    drawio_executable: str
    drawio_args: list[str]
    format: str
    embed_format: str
    sources: str


class ConfigurationError(Exception):
    """Configuration exception.

    Used to signal that MkDocs should exit, as the plugin configuration is
    invalid and we'll be unable to export diagrams.
    """

    key = None
    """Configuration key.

    :type str:"""

    value = None
    """Configuration value.

    :type mixed:"""

    message = None
    """Explanatory message describing the problem.

    :type str:"""

    def __init__(self, key, value, message):
        """Initialise a ConfigurationError.

        :param str key: Configuration key.
        :param mixed value: Configuration value.
        :param str message: Explanatory message describing the problem.
        """
        self.key = key
        self.value = value
        self.message = message
        Exception.__init__(self, self.message)

    def __str__(self):
        return f'drawio-exporter: value "{self.value}" for key "{self.key}" is invalid: {self.message}'

    def drawio_executable(value, message):
        """Raise an error for a misconfigured Draw.io path.

        :param str value: Configured Draw.io executable path.
        :param str message: Explanatory message describing the problem.
        """
        return ConfigurationError('drawio_executable', value, message)


class Source:
    """Diagram source.

    Sources are pairs of filenames and page indices which can be exported to
    produce a static image. The relative path of the source within the
    documentation directory must be resolved after instantiation due to MkDocs's
    design.
    """

    source_embed = None
    """Path of the embedded resource, relative to parent page.

    :type: str
    """

    source_rel = None
    """Path of the source, relative to the documentation directory.

    :type: str
    """

    page_index = None
    """Page index within the document.

    :type: int"""

    def __init__(self, source_embed, page_index):
        """Initialise a Source.

        :param str source_embed: Path of the embedded resource.
        :param int page_index: Page index within the document.
        """
        self.source_embed = source_embed
        self.page_index = page_index

    def __eq__(self, other):
        return self.source_rel == other.source_rel \
                and self.page_index == other.page_index

    def __hash__(self):
        return hash((
            'source_rel', self.source_rel,
            'page_index', self.page_index,
        ))

    def __repr__(self):
        return f"Source({self.source_embed}, {self.page_index}, {self.source_rel})"

    def resolve_rel_path(self, page_src_path):
        """Resolve the path of the source, relative to the documentation directory.

        :param str page_src_path: The source path of the parent page.
        """
        unescaped_source_embed = urllib.parse.unquote(self.source_embed)
        self.source_rel = os.path.normpath(os.path.join(
                os.path.dirname(page_src_path),
                unescaped_source_embed))


class DrawIoExporter:
    """Draw.io Exporter.

    The logic for the export process lives here. The bindings to the MkDocs
    plugin events is kept separate to ease testing.
    """

    log = None
    """Log.

    :type: logging.Logger
    """

    docs_dir = None
    """Draw.io docs_dir.

    :type str:
    """

    def __init__(self, log, docs_dir):
        """Initialise.

        :param logging.Logger log: Where to log.
        :param str docs_dir: MkDocs docs_dir.
        """
        self.log = log
        self.docs_dir = docs_dir

    DRAWIO_EXECUTABLE_NAMES = ['drawio', 'draw.io']
    """Draw.io executable names."""

    def drawio_executable_paths(self, platform):
        """Get the Draw.io executable paths for the platform.

        Declared as a function to allow us to use API/environment information
        available only when running under the specified platform.

        :param str platform: sys.platform.
        :return list(str): All known paths.
        """
        if platform == 'darwin':
            applications = [
                os.path.expanduser('~/Applications'),
                '/Applications',
            ]
            drawio_path = os.path.join('draw.io.app', 'Contents', 'MacOS', 'draw.io')
            return [os.path.join(dir, drawio_path) for dir in applications]
        elif platform.startswith('linux'):
            return ['/opt/draw.io/drawio']
        elif platform == 'win32':
            program_files = [os.environ['ProgramFiles']]
            if 'ProgramFiles(x86)' in os.environ:
                program_files.append(os.environ['ProgramFiles(x86)'])
            return [os.path.join(dir, 'draw.io', 'draw.io.exe') for dir in program_files]
        else:
            self.log.warning(f'Draw.io executable paths not known for platform "{platform}"')

    def prepare_cache_dir(self, cache_dir):
        """Ensure the cache path is set, absolute and exists.

        :param str cache_dir: Configured cache directory.
        :param str docs_dir: Docs directory, in which to base relative cache directories.
        :return str: Final cache directory.
        """
        if not cache_dir:
           cache_dir = 'drawio-exporter'
        if not os.path.isabs(cache_dir):
            cache_dir = os.path.join(self.docs_dir, cache_dir)
        return cache_dir

    def prepare_drawio_executable(self, executable, executable_names, platform_executable_paths):
        """Ensure the Draw.io executable path is configured, or guess it.

        :param str executable: Configured Draw.io executable.
        :param list(str) executable_names: Candidate executable names to seek on PATH.
        :param list(str) platform_executable_paths: Candidate platform-specific executable paths.
        :return str: Final Draw.io executable.
        """
        if executable:
            if not os.path.isfile(executable):
                raise ConfigurationError.drawio_executable(
                        executable, "executable didn't exist")
            return executable

        for name in executable_names:
            executable = shutil.which(name)
            if executable:
                self.log.debug(f'Found Draw.io executable "{name}" at "{executable}"')
                return executable

        candidates = platform_executable_paths
        self.log.debug(f'Trying paths {candidates} for platform "{sys.platform}"')
        for candidate in candidates:
            if os.path.isfile(candidate):
                self.log.debug(f'Found Draw.io executable for platform "{sys.platform}" at "{candidate}"')
                return candidate

        raise ConfigurationError.drawio_executable(
                None, 'Unable to find Draw.io executable; ensure it\'s on PATH or set drawio_executable option')

    def validate_config(self, config: Configuration):
        """Validate the configuration.

        :param dict config: Configuration.
        :return bool: True if configuration is valid.
        """
        if '{content}' in config['embed_format'] and config['format'] != 'svg':
            raise ConfigurationError(
                    'embed_format', config['embed_format'],
                    'cannot inline content of non-SVG format')

    def rewrite_image_embeds(self, page_src_path, output_content, config: Configuration):
        """Rewrite image embeds.

        :param str page_dest_path: Destination path.
        :param str output_content: Content to rewrite.
        :param str sources: Glob to match Draw.io diagram filenames.
        :param str format: Desired export format.
        :param str embed_format: Format string to rewrite <img> tags with.
        :return str: Rewritten content.
        """
        content_sources = []

        def replace(match):
            try:
                filename, page_index = match.group('filename').rsplit('#', 1)
            except ValueError:
                filename = match.group('filename')
                page_index = 0
            img_alt = match.group('alt')

            if fnmatch.fnmatch(filename, config['sources']):
                source = Source(filename, page_index)
                source.resolve_rel_path(page_src_path)
                content_sources.append(source)
                img_src = f"{filename}-{page_index}.{config['format']}"

                # Cache the file on-demand and read file content only if we
                # need to inline the file's content.
                content = None
                if '{content}' in config['embed_format']:
                    img_path = self.make_cache_filename(
                            source.source_rel, page_index, config['cache_dir'])

                    abs_src_path = os.path.join(self.docs_dir, source.source_rel)
                    _, exit_status = self.ensure_file_cached(
                            abs_src_path, source.source_rel, source.page_index,
                            config)

                    if exit_status not in (None, 0):
                        self.log.error(f'Export failed with exit status {exit_status}; skipping rewrite')
                        return match.group(0)

                    with open(img_path, 'r') as f:
                        content = f.read()

                return config['embed_format'].format(
                        img_alt=img_alt, img_src=img_src, content=content)
            else:
                return match.group(0)
        output_content = IMAGE_RE.sub(replace, output_content)

        return (output_content, content_sources)

    def filter_cache_files(self, files, cache_dir):
        """Remove cache files from the generated output.

        :param list(mkdocs.structure.File): Files to filter.
        :param str cache_dir: Cache directory.
        :return list(mkdocs.structure.File): Filtered files.
        """
        return [f for f in files if not f.abs_src_path.startswith(cache_dir)]

    def ensure_file_cached(self, source, source_rel, page_index, config: Configuration):
        """Ensure cached copy of output exists.

        :param str source: Source path, absolute.
        :param str source_rel: Source path, relative to docs directory.
        :param int page_index: Page index, numbered from zero.
        :param str drawio_executable: Path to the configured Draw.io executable.
        :param list(str) drawio_args: Additional arguments to append to the Draw.io export command.
        :param str cache_dir: Export cache directory.
        :param str format: Desired export format.
        :return tuple(str, int): Cached export filename.
        """
        cache_filename = self.make_cache_filename(source_rel, page_index, config['cache_dir'])
        exit_status = None

        if self.use_cached_file(source, cache_filename):
            self.log.debug(f'Source file appears unchanged; using cached copy from "{cache_filename}"')
        else:
            if not config['drawio_executable']:
                self.log.warning(f'Skipping export of "{source}" as Draw.io executable not available')
                return (None, exit_status)

            self.log.debug(f'Exporting "{source}" to "{cache_filename}"')
            exit_status = self.export_file(
                    source, page_index, cache_filename, config)

        return (cache_filename, exit_status)

    def make_cache_filename(self, source, page_index, cache_dir):
        """Make the cached filename.

        :param str source: Source path, relative to the docs directory.
        :param int page_index: Page index, numbered from zero.
        :param str cache_dir: Export cache directory.
        :return str: Resulting filename.
        """
        filename_hash = hashlib.sha1(source.encode('utf-8')).hexdigest()
        basename = f'{filename_hash}-{page_index}'
        return os.path.join(cache_dir, basename)

    def use_cached_file(self, source, cache_filename):
        """Is the cached copy up to date?

        :param str source: Source path, relative to the docs directory.
        :param str cache_filename: Export cache filename.
        :return bool: True if cache is up to date, else False.
        """
        return os.path.exists(cache_filename) \
                and os.path.getmtime(cache_filename) >= os.path.getmtime(source)

    def export_file(self, source, page_index, dest, config: Configuration):
        """Export an individual file.

        :param str source: Source path, absolute.
        :param int page_index: Page index, numbered from zero.
        :param str dest: Destination path, within cache.
        :param str drawio_executable: Path to the configured Draw.io executable.
        :param list(str) drawio_args: Additional arguments to append to the Draw.io export command.
        :param str format: Desired export format.
        :return int: The Draw.io exit status.
        """
        cmd = [
            config['drawio_executable'],
            '--export', source,
            '--page-index', str(page_index),
            '--output', dest,
            '--format', config['format'],
        ]
        cmd += config['drawio_args']

        try:
            self.log.debug(f'Using export command {cmd}')
            return subprocess.call(cmd)
        except (OSError, subprocess.CalledProcessError):
            self.log.exception('Subprocess raised exception')
