import fnmatch
import hashlib
import os.path
import re
import shutil
import subprocess
import sys
from collections import UserDict
from logging import Logger
from re import Match

IMAGE_RE = re.compile('(<img[^>]+src=")([^">]+)("\s*\/?>)')


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
        return 'drawio-exporter: value "{}" for key "{}" is invalid: {}'.format(
                self.value, self.key, self.message)

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

    def __init__(self, source_embed, page_index, page_path):
        """Initialise a Source.

        :param str source_embed: Path of the embedded resource.
        :param int page_index: Page index within the document.
        :param int page_path: Page document path.
        """
        self.source_embed = source_embed
        self.page_index = page_index
        self.source_rel = os.path.normpath(os.path.join(os.path.dirname(page_path), self.source_embed))

    def __eq__(self, other):
        return self.source_rel == other.source_rel \
                and self.page_index == other.page_index

    def __hash__(self):
        return hash((
            'source_rel', self.source_rel,
            'page_index', self.page_index,
        ))


class DrawIoExporter:
    """Draw.io Exporter.

    The logic for the export process lives here. The bindings to the MkDocs
    plugin events is kept separate to ease testing.
    """

    __config: dict
    """Configs.

    :type: dict
    """

    @property
    def logger(self) -> Logger:
        """Logger."""
        return self.__config.get('logger')
    
    @property
    def executable_names(self) -> list[str]:
        """Draw.io executable names."""
        return self.__config.get('executable_names', ['drawio', 'draw.io'])
    
    @property
    def platform(self) -> str:
        """System platform."""
        return self.__config.get('platform', sys.platform)

    @property
    def docs_dir(self) -> str:
        """Docs directory, in which to base relative cache directories."""
        return self.__config.get('docs_dir', '')

    @property
    def site_dir(self) -> str:
        """Site directory path."""
        return self.__config.get('site_dir')

    @property
    def cache_dir(self) -> str:
        """Final cache directory."""
        return self.__config.get('cache_dir')

    @property
    def drawio_executable(self) -> str:
        """Draw.io executable path."""
        return self.__config.get('drawio_executable')

    @property
    def drawio_args(self) -> list[str]:
        """Additional arguments to append to the Draw.io export command."""
        return self.__config.get('drawio_args') or []
    
    @property
    def sources(self) -> str:
        """Glob to match Draw.io diagram filenames."""
        return self.__config.get('sources')

    @property
    def format(self) -> str:
        """Desired export format."""
        return self.__config.get('format')

    @property
    def embed_format(self) -> str:
        """Format string to rewrite <img> tags with."""
        return self.__config.get('embed_format')

    def __init__(self, config: dict = {}):
        """Initialise.

        :param dict config: Configs.
        """

        self.__config = (config or {})
        self.__config['cache_dir'] = self.__get_cache_dir()
        self.__config['drawio_executable'] = self.__get_drawio_executable()

        self.__validate()

    def __get_cache_dir(self) -> str:
        """Ensure the cache path is set, absolute and exists.

        :param dict config: Configuration.
        :return str: Final cache directory.
        """

        cache_dir = self.__config.get('cache_dir') or 'drawio-exporter'
        
        if not os.path.isabs(cache_dir):
            cache_dir = os.path.join(self.docs_dir, cache_dir)
        
        return cache_dir

    def __get_drawio_executable(self):
        """Ensure the Draw.io executable path is configured, or guess it.

        :param dict config: Configuration.
        :return str: Final Draw.io executable.
        """
        
        executable = self.__config.get('drawio_executable')

        if executable:
            return executable

        for executable_name in self.executable_names:
            executable = shutil.which(executable_name)
            if executable:
                self.logger.debug('Found Draw.io executable "{}" at "{}"'.format(executable_name, executable))
                return executable

        executable_paths = self.get_executable_paths()
        self.logger.debug('Trying paths {} for platform "{}"'.format(executable_paths, sys.platform))

        for executable_path in executable_paths:
            if os.path.isfile(executable_path):
                self.logger.debug('Found Draw.io executable for platform "{}" at "{}"'.format(
                    sys.platform, 
                    executable_path
                ))
                return executable_path

        return None
    
    def __validate(self):

        if self.embed_format == 'html' and self.format != 'svg':
            raise ConfigurationError(
                'embed_format', 
                self.embed_format, 
                'you must to set "format: svg" with the "embed_format: html".'
            )

        if not self.drawio_executable:
            raise ConfigurationError.drawio_executable(
                None, 
                'Unable to find Draw.io executable; ensure it\'s on PATH or set drawio_executable option'
            )

        if not os.path.isfile(self.drawio_executable) and not shutil.which(self.drawio_executable):
            raise ConfigurationError.drawio_executable(self.drawio_executable, "executable didn't exist")

    def get_executable_paths(self) -> list[str]:
        """Get the Draw.io executable paths for the platform.

        Declared as a function to allow us to use API/environment information
        available only when running under the specified platform.
        
        :return list[str]: All known paths.
        """

        if not self.platform:
            self.logger.warn('There is no draw.io executable paths if you do not specify a platform')
        elif self.platform == 'darwin':
            applications = [os.path.expanduser('~/Applications'), '/Applications']
            drawio_path = os.path.join('draw.io.app', 'Contents', 'MacOS', 'draw.io')
            return [os.path.join(dir, drawio_path) for dir in applications]
        elif self.platform.startswith('linux'):
            return ['/opt/draw.io/drawio']
        elif self.platform == 'win32':
            program_files = [os.environ['ProgramFiles']]
            if 'ProgramFiles(x86)' in os.environ:
                program_files.append(os.environ['ProgramFiles(x86)'])
            return [os.path.join(dir, 'draw.io', 'draw.io.exe') for dir in program_files]
        else:
            self.logger.warn('Draw.io executable paths not known for platform "{}"'.format(self.platform))

    def get_source_from(self, match: Match[str], content_path: str) -> Source:
        """Get source from regex match."""
        try:
            filename, page_index = match.group(2).rsplit('#', 1)
        except ValueError:
            filename = match.group(2)
            page_index = 0
        
        return Source(filename, page_index, content_path)

    def get_sources_from(self, content: str, content_path: str) -> list[Source]:
        """Get source list from output."""
        
        sources = []
        
        matches = IMAGE_RE.finditer(content)
        
        for match in matches:
            source = self.get_source_from(match, content_path)
            if fnmatch.fnmatch(source.source_embed, self.sources):
                sources.append(source)

        return sources

    def rewrite_image_embeds(self, content: str, content_path: str):
        """Rewrite image embeds.

        :param str content: Page content to rewrite.
        :param str content_path: Path of the page content.
        :return str: Rewritten content.
        """
        
        def replace(match: Match[str]):

            source = self.get_source_from(match, content_path)

            if fnmatch.fnmatch(source.source_embed, self.sources):
                
                img_src = "{}-{}.{}".format(source.source_embed, source.page_index, self.format)

                if self.embed_format == "html":
                    
                    path = os.path.abspath(
                        os.path.join(
                            self.site_dir, 
                            "{}{}".format(
                                content_path[:content_path.rindex("/") + 1] if content_path.rfind("/") > 0 else "", 
                                img_src
                            )
                        )
                    )

                    return open(path, 'r').read()

                return self.embed_format.format(
                    img_open=match.group(1), 
                    img_close=match.group(3), 
                    img_src=img_src
                )
            else:
                return match.group(0)

        return IMAGE_RE.sub(replace, content)

    def filter_cache_files(self, files):
        """Remove cache files from the generated output.

        :param list(mkdocs.structure.File): Files to filter.
        :return list(mkdocs.structure.File): Filtered files.
        """
        return [f for f in files if not f.abs_src_path.startswith(self.cache_dir)]

    def ensure_file_cached(self, source, source_rel, page_index):
        """Ensure cached copy of output exists.

        :param str source: Source path, absolute.
        :param str source_rel: Source path, relative to docs directory.
        :param int page_index: Page index, numbered from zero.
        """
        cache_filename = self.make_cache_filename(source_rel, page_index, self.cache_dir)
        exit_status = None

        if self.use_cached_file(source, cache_filename):
            self.logger.debug('Source file appears unchanged; using cached copy from "{}"'.format(cache_filename))
        else:
            if not self.drawio_executable:
                self.logger.warn('Skipping export of "{}" as Draw.io executable not available'.format(source))
                return (None, exit_status)

            self.logger.debug('Exporting "{}" to "{}"'.format(source, cache_filename))
            exit_status = self.export_file(source, page_index, cache_filename)

        return (cache_filename, exit_status)

    def make_cache_filename(self, source, page_index, cache_dir):
        """Make the cached filename.

        :param str source: Source path, relative to the docs directory.
        :param int page_index: Page index, numbered from zero.
        :param str cache_dir: Export cache directory.
        :return str: Resulting filename.
        """
        basename = '{}-{}'.format(
                hashlib.sha1(source.encode('utf-8')).hexdigest(), page_index)
        return os.path.join(cache_dir, basename)

    def use_cached_file(self, source, cache_filename):
        """Is the cached copy up to date?

        :param str source: Source path, relative to the docs directory.
        :param str cache_filename: Export cache filename.
        :return bool: True if cache is up to date, else False.
        """
        return os.path.exists(cache_filename) \
                and os.path.getmtime(cache_filename) >= os.path.getmtime(source)

    def export_file(self, source, page_index, dest):
        """Export an individual file.

        :param str source: Source path, absolute.
        :param int page_index: Page index, numbered from zero.
        :param str dest: Destination path, within cache.
        
        :return int: The Draw.io exit status.
        """
        cmd = [
            self.drawio_executable,
            '--export', source,
            '--page-index', str(page_index),
            '--output', dest,
            '--format', self.format,
        ]
        cmd += self.drawio_args

        try:
            self.logger.debug('Using export command {}'.format(cmd))
            return subprocess.call(cmd)
        except:
            self.logger.exception('Subprocess raised exception')
