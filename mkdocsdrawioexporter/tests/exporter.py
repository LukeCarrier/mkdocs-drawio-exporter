import unittest
from unittest.mock import MagicMock, patch

import logging
import os
from os.path import isabs, join, sep
import re

from ..exporter import DrawIoExporter


class FileMock:
    src_path = None
    abs_src_path = None

    def __init__(self, **kwargs):
        for attr, value in kwargs.items():
            setattr(self, attr, value)


class ExporterTests(unittest.TestCase):
    log = None
    exporter = None

    def setUp(self):
        self.log = logging.getLogger(__name__)
        self.exporter = DrawIoExporter(self.log)

    def test_drawio_executable_paths_warns_on_unknown_platform(self):
        self.log.warn = MagicMock()
        self.exporter.drawio_executable_paths('win32-but-stable')
        self.log.warn.assert_called_once()

    def test_prepare_cache_dir_defaults(self):
        assert len(self.exporter.prepare_cache_dir(None, sep + 'docs'))

    def test_prepare_cache_dir_resolves_relative_path(self):
        result = self.exporter.prepare_cache_dir('temp', sep + 'docs')
        assert os.path.isabs(result)
        assert result.startswith(sep + 'docs' + sep)

    def test_prepare_drawio_executable_aborts_on_missing_executable(self):
        self.log.error = MagicMock()
        assert self.exporter.prepare_drawio_executable(sep + join('does', 'not', 'exist'), [], []) == None
        self.log.error.assert_called_once()

    @patch('shutil.which')
    @patch.dict(os.environ, {'PATH': sep + join('does', 'not', 'exist')})
    def test_prepare_drawio_executable_on_path(self, mock_which):
        mock_which.return_value = sep + join('does', 'not', 'exist', 'drawio')
        result = self.exporter.prepare_drawio_executable(None, self.exporter.DRAWIO_EXECUTABLE_NAMES, [])
        assert result == mock_which.return_value

    @patch('os.path.isfile')
    def test_prepare_drawio_executable_platform_specific(self, mock_isfile):
        expect = sep + join('does', 'not', 'exist', 'someotherdrawio')
        mock_isfile.side_effect = lambda p: p == expect

        result = self.exporter.prepare_drawio_executable(None, [], [
            sep + join('does', 'not', 'exist', 'drawio'),
            expect,
        ])
        assert result == expect

    def test_prepare_drawio_executable_logs_error_on_failure(self):
        self.log.error = MagicMock()
        assert self.exporter.prepare_drawio_executable(None, [], []) == None
        self.log.error.assert_called_once()

    def test_rewrite_image_embeds(self):
        source = '''<h1>Example text</h1>
<img alt="Some text" src="../some-diagram.drawio" />'''
        image_re = re.compile('(<img[^>]+src=")([^">]+)("\s*\/?>)')

        unmodified = self.exporter.rewrite_image_embeds(
                source, image_re, '*.nomatch', 'svg')
        assert unmodified == source

        modified = self.exporter.rewrite_image_embeds(
                source, image_re, '*.drawio', 'svg')
        assert modified != source
        assert 'src="../some-diagram.drawio.svg"' in modified

    def test_match_source_files(self):
        files = [
            join('some', 'diagram.drawio'),
            join('some', 'index.md'),
            join('some', 'page.md'),
        ]
        files = [FileMock(**{'src_path': f}) for f in files]

        result = self.exporter.match_source_files(files, '*.nomatch')
        assert len(result) == 0

        result = self.exporter.match_source_files(files, '*.drawio')
        assert len(result) == 1
        assert files[0] in result

    def test_filter_cache_files(self):
        files = [
            sep + join('docs', 'drawio-exporter', '0000000000000000000000000000000000000000'),
            sep + join('docs', 'index.md'),
        ]
        files = [FileMock(**{'abs_src_path': f}) for f in files]

        result = self.exporter.filter_cache_files(files, sep + join('docs', 'nomatch'))
        assert len(result) == 2

        result = self.exporter.filter_cache_files(files, sep + join('docs', 'drawio-exporter'))
        assert len(result) == 1
        assert files[0] not in result

    def test_ensure_file_cached(self):
        source = sep + join('docs', 'diagram.drawio')
        source_rel = 'diagram.drawio'
        drawio_executable = sep + join('bin', 'drawio')
        cache_dir = sep + join('docs', 'drawio-exporter')

        self.exporter.make_cache_filename = MagicMock()
        self.exporter.make_cache_filename.return_value = join(cache_dir, '0000000000000000000000000000000000000000')

        self.exporter.export_file = MagicMock()
        self.exporter.export_file.return_value = 0

        result = self.exporter.ensure_file_cached(
                source, source_rel, drawio_executable, cache_dir, 'svg')
        assert result == self.exporter.make_cache_filename.return_value

    def test_ensure_file_cached_aborts_if_drawio_executable_unavailable(self):
        source = sep + join('docs', 'diagram.drawio')
        source_rel = 'diagram.drawio'
        drawio_executable = None
        cache_dir = sep + join('docs', 'drawio-exporter')

        self.exporter.export_file = MagicMock()
        self.exporter.export_file.return_value = 0

        self.log.warn = MagicMock()

        result = self.exporter.ensure_file_cached(
                source, source_rel, drawio_executable, cache_dir, 'svg')

        assert result == None
        self.log.warn.assert_called_once()

    def test_ensure_file_cached_skips_export_if_cache_fresh(self):
        source = sep + join('docs', 'diagram.drawio')
        source_rel = 'diagram.drawio'
        drawio_executable = sep + join('bin', 'drawio')
        cache_dir = sep + join('docs', 'drawio-exporter')

        self.exporter.make_cache_filename = MagicMock()
        self.exporter.make_cache_filename.return_value = join(cache_dir, '0000000000000000000000000000000000000000')

        self.exporter.use_cached_file = MagicMock()
        self.exporter.use_cached_file.return_value = True

        self.exporter.export_file = MagicMock()
        self.exporter.export_file.return_value = 0

        result = self.exporter.ensure_file_cached(
                source, source_rel, drawio_executable, cache_dir, 'svg')

        assert result == self.exporter.make_cache_filename.return_value
        self.exporter.use_cached_file.assert_called_once()
        assert not self.exporter.export_file.called

    def test_ensure_file_cached_logs_error_if_export_fails(self):
        source = sep + join('docs', 'diagram.drawio')
        source_rel = 'diagram.drawio'
        drawio_executable = sep + join('bin', 'drawio')
        cache_dir = sep + join('docs', 'drawio-exporter')

        self.exporter.make_cache_filename = MagicMock()
        self.exporter.make_cache_filename.return_value = join(cache_dir, '0000000000000000000000000000000000000000')

        self.exporter.use_cached_file = MagicMock()
        self.exporter.use_cached_file.return_value = False

        self.exporter.export_file = MagicMock()
        self.exporter.export_file.return_value = 1

        self.log.error = MagicMock()

        result = self.exporter.ensure_file_cached(
                source, source_rel, drawio_executable, cache_dir, 'svg')

        assert result == None
        self.log.error.assert_called_once()

    def test_make_cache_filename(self):
        cache_dir = sep + 'docs'

        result1 = self.exporter.make_cache_filename('diagram.drawio', cache_dir)
        result2 = self.exporter.make_cache_filename('other-diagram.drawio', cache_dir)

        assert result1.startswith(cache_dir)
        assert result2.startswith(cache_dir)
        assert result1 != result2

    @patch('os.path.exists')
    @patch('os.path.getmtime')
    def test_use_cached_file(self, getmtime_mock, exists_mock):
        cache_filename = sep + join('docs', 'drawio-exporter', '0000000000000000000000000000000000000000')
        source = sep + join('docs', 'diagram.drawio')

        exists_mock.return_value = True

        def getmtime_return_value(path):
            if path == cache_filename:
                return 1577043612.1444612
            elif path == source:
                return 1577133635.3318102
            else:
                raise ValueError('didn\'t expect path "{}"'.format(path))
        getmtime_mock.side_effect = getmtime_return_value

        result = self.exporter.use_cached_file(source, cache_filename)
        assert result == False

    @patch('subprocess.call')
    def test_export_file(self, call_mock):
        source = sep + join('docs', 'diagram.drawio')
        dest = sep + join('docs', 'diagram.drawio.svg')
        drawio_executable = sep + join('bin', 'drawio')

        call_mock.return_value = 0

        result = self.exporter.export_file(
                source, dest, drawio_executable, 'svg')

        assert result == 0
        call_mock.assert_called_once()

    @patch('subprocess.call')
    def test_export_file_logs_exc_on_raise(self, call_mock):
        source = sep + join('docs', 'diagram.drawio')
        dest = sep + join('docs', 'diagram.drawio.svg')
        drawio_executable = sep + join('bin', 'drawio')

        call_mock.side_effect = OSError()

        self.log.exception = MagicMock()

        result = self.exporter.export_file(
                source, dest, drawio_executable, 'svg')

        assert result == None
        self.log.exception.assert_called_once()
        call_mock.assert_called_once()


if __name__ == '__main__':
    unittest.main()
