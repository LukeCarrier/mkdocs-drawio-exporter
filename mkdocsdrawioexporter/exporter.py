import fnmatch
import hashlib
import os.path
import shutil
import subprocess
import sys


class DrawIoExporter:
    """Draw.io Exporter.

    The logic for the export process lives here. The bindings to the MkDocs
    plugin events is kept separate to ease testing.
    """

    log = None
    """Log.

    :type: logging.Logger
    """

    def __init__(self, log):
        """Initialise.

        :param logging.Logger log: Where to log.
        """
        self.log = log

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
                program_files.append('ProgramFiles(x86)')
            return [os.path.join(dir, 'draw.io', 'draw.io.exe') for dir in program_files]
        else:
            self.log.warn('Draw.io executable paths not known for platform "{}"'.format(platform))

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
        return cache_dir

    def prepare_drawio_executable(self, executable, executable_names, platform_executable_paths):
        """Ensure the Draw.io executable path is configured, or guess it.

        :param str executable: Configured Draw.io executable.
        :param list(str) executable_names: Candidate executable names to seek on PATH.
        :param list(str) platform_executable_paths: Candidate platform-specific executable paths.
        :return str: Final Draw.io executable.
        """
        if executable and not os.path.isfile(executable):
            self.log.error('Configured Draw.io executable "{}" doesn\'t exist', executable)
            return

        for name in executable_names:
            executable = shutil.which(name)
            if executable:
                self.log.debug('Found Draw.io executable "{}" at "{}"'.format(name, executable))
                return executable

        candidates = platform_executable_paths
        self.log.debug('Trying paths {} for platform "{}"'.format(candidates, sys.platform))
        for candidate in candidates:
            if os.path.isfile(candidate):
                self.log.debug('Found Draw.io executable for platform "{}" at "{}"'.format(
                        sys.platform, candidate))
                return candidate

        self.log.error('Unable to find Draw.io executable; ensure it\'s on PATH or set drawio_executable option')

    def rewrite_image_embeds(self, output_content, image_re, sources, format):
        """Rewrite image embeds.

        :param str output_content: Content to rewrite.
        :param re.Pattern image_re: Pattern to match HTML <img> tags.
        :param str sources: Glob to match Draw.io diagram filenames.
        :param str format: Desired export format.
        :return str: Rewritten content.
        """
        def replace(match):
            if fnmatch.fnmatch(match.group(2), sources):
                return '{}{}.{}{}'.format(match.group(1), match.group(2), format, match.group(3))
            else:
                return match.group(0)
        return image_re.sub(replace, output_content)

    def match_source_files(self, files, sources):
        """Locate files matching the source glob.

        :param list(mkdocs.structure.File) files: Files to filter.
        :param str sources: Sources glob to filter by.
        :return list(mkdocs.structure.File): Filtered files.
        """
        return [f for f in files if fnmatch.fnmatch(f.src_path, sources)]

    def filter_cache_files(self, files, cache_dir):
        """Remove cache files from the generated output.

        :param list(mkdocs.structure.File): Files to filter.
        :param str cache_dir: Cache directory.
        :return list(mkdocs.structure.File): Filtered files.
        """
        return [f for f in files if not f.abs_src_path.startswith(cache_dir)]

    def ensure_file_cached(self, source, source_rel, drawio_executable, cache_dir, format):
        """Ensure cached copy of output exists.

        :param str source: Source path, absolute.
        :param str source_rel: Source path, relative to docs directory.
        :param str drawio_executable: Path to the configured Draw.io executable.
        :param str cache_dir: Export cache directory.
        :param str format: Desired export format.
        :return str: Cached export filename.
        """
        if not drawio_executable:
            self.log.warn('Skipping build of "{}" as Draw.io executable not available'.format(source))
            return

        cache_filename = self.make_cache_filename(source_rel, cache_dir)
        if self.use_cached_file(source, cache_filename):
            self.log.debug('Source file appears unchanged; using cached copy from "{}"'.format(cache_filename))
        else:
            self.log.debug('Exporting "{}" to "{}"'.format(source, cache_filename))
            exit_status = self.export_file(source, cache_filename, drawio_executable, format)
            if exit_status != 0:
                self.log.error('Export failed with exit status {}'.format(exit_status))
                return

        return cache_filename

    def make_cache_filename(self, source, cache_dir):
        """Make the cached filename.

        :param str source: Source path, relative to the docs directory.
        :param str cache_dir: Export cache directory.
        :return str: Resulting filename.
        """
        return os.path.join(cache_dir, hashlib.sha1(source.encode('utf-8')).hexdigest())

    def use_cached_file(self, source, cache_filename):
        """Is the cached copy up to date?

        :param str source: Source path, relative to the docs directory.
        :param str cache_filename: Export cache filename.
        :return bool: True if cache is up to date, else False.
        """
        return os.path.exists(cache_filename) \
                and os.path.getmtime(cache_filename) >= os.path.getmtime(source)

    def export_file(self, source, dest, drawio_executable, format):
        """Export an individual file.

        :param str source: Source path, absolute.
        :param str dest: Destination path, within cache.
        :param str drawio_executable: Path to the configured Draw.io executable.
        :param str format: Desired export format.
        :return int: The Draw.io exit status.
        """
        cmd = [
            drawio_executable,
            '--export', source,
            '--output', dest,
            '--format', format,
        ]

        try:
            self.log.debug('Using export command {}'.format(cmd))
            return subprocess.call(cmd)
        except:
            self.log.exception('Subprocess raised exception')
