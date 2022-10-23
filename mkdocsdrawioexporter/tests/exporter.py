import shutil
import unittest
from unittest.mock import MagicMock, patch

import logging
import os
from os.path import isabs, join, sep
import re

# from symbol import return_stmt

from ..exporter import ConfigurationError, DrawIoExporter


class FileMock:
    src_path = None
    abs_src_path = None

    def __init__(self, **kwargs):
        for attr, value in kwargs.items():
            setattr(self, attr, value)


class ExporterTests(unittest.TestCase):
    logger = None

    def setUp(self):
        self.logger = logging.getLogger(__name__)

    def test_drawio_executable_paths_warns_on_unknown_platform(self):

        self.logger.warn = MagicMock()
        
        exporter = DrawIoExporter(
            config={
                'logger': self.logger,
                'platform': 'win32-but-stable'
            }
        )
        exporter.get_executable_paths()
        
        self.logger.warn.assert_called_once()

    def test_prepare_cache_dir_defaults(self):

        exporter = DrawIoExporter(
            config={
                'logger': self.logger,
                'cache_dir': None,
                'docs_dir': sep + 'docs'
            }
        )
        
        assert len(exporter.cache_dir)

    def test_prepare_cache_dir_resolves_relative_path(self):

        exporter = DrawIoExporter(
            config={
                'logger': self.logger,
                'cache_dir': 'temp',
                'docs_dir': sep + 'docs'
            }
        )
        
        assert os.path.isabs(exporter.cache_dir)
        assert exporter.cache_dir.startswith(sep + 'docs' + sep)

    def test_prepare_drawio_executable_aborts_on_missing_executable(self):
        
        with self.assertRaises(ConfigurationError):
        
            exporter = DrawIoExporter(
                config={
                    'logger': self.logger,
                    'executable_names': [],
                    'drawio_executable': sep + join('does', 'not', 'exist')
                }
            )    
            exporter.get_executable_paths = MagicMock()
            exporter.get_executable_paths.return_value = []

    def test_prepare_drawio_executable_uses_valid_specified_exectuable(self):
        
        # We need something that exists, and right now we're not verifying that
        # it's executable. This will do.
        exporter = DrawIoExporter(
            config={
                'logger': self.logger,
                'drawio_executable': os.path.abspath(__file__)
            }
        )
        exporter.get_executable_paths = MagicMock()
        exporter.get_executable_paths.return_value = []

        assert os.path.abspath(__file__) == exporter.drawio_executable

    @patch('shutil.which')
    @patch.dict(os.environ, {'PATH': sep + join('does', 'not', 'exist')})
    def test_prepare_drawio_executable_on_path(self, mock_which):
        
        mock_which.return_value = sep + join('does', 'not', 'exist', 'drawio')

        exporter = DrawIoExporter(
            config={
                'logger': self.logger,
                'drawio_executable': None
            }
        )
        exporter.get_executable_paths = MagicMock()
        exporter.get_executable_paths.return_value = []

        assert exporter.drawio_executable == sep + join('does', 'not', 'exist', 'drawio')

    @patch('os.path.isfile')
    def test_prepare_drawio_executable_platform_specific(self, mock_isfile):

        expect = sep + join('does', 'not', 'exist', 'someotherdrawio')
        mock_isfile.side_effect = lambda p: p == expect

        exporter = DrawIoExporter(
            config={
                'logger': self.logger,
                'executable_names': [],
                'drawio_executable': expect
            }
        )
        
        exporter.get_executable_paths = MagicMock()
        exporter.get_executable_paths.return_value = [
            sep + join('does', 'not', 'exist', 'drawio'),
            expect,
        ]

        assert exporter.drawio_executable == expect

    
    def test_prepare_drawio_executable_raises_on_failure(self):
        with self.assertRaises(ConfigurationError):
            exporter = DrawIoExporter(
                config={
                    'logger': self.logger,
                    'executable_names': [],
                    'drawio_executable': None
                }
            )
            exporter.get_executable_paths = MagicMock()
            exporter.get_executable_paths.return_value = []

    def test_rewrite_image_embeds(self):
        
        source = '''<h1>Example text</h1>
<img alt="Some text" src="../some-diagram.drawio" />'''

        default_embed_format = '{img_open}{img_src}{img_close}'
        object_embed_format = '<object type="image/svg+xml" data="{img_src}"></object>'

        exporter = DrawIoExporter(
            config={
                'logger': self.logger,
                'sources': '*.nomatch',
                'format': 'svg',
                'embed_format': default_embed_format
            }
        )
        output_content = exporter.rewrite_image_embeds(source, os.path.abspath('.'))
        assert output_content == source

        exporter = DrawIoExporter(
            config={
                'logger': self.logger,
                'sources': '*.drawio',
                'format': 'svg',
                'embed_format': default_embed_format
            }
        )
        output_content = exporter.rewrite_image_embeds(source, os.path.abspath('.'))
        assert output_content != source
        assert 'src="../some-diagram.drawio-0.svg"' in output_content

        exporter = DrawIoExporter(
            config={
                'logger': self.logger,
                'sources': '*.drawio',
                'format': 'svg',
                'embed_format': object_embed_format
            }
        )
        output_content = exporter.rewrite_image_embeds(source, os.path.abspath('.'))
        assert output_content != source
        assert '<object type="image/svg+xml" data="../some-diagram.drawio-0.svg"></object>' in output_content

    def test_filter_cache_files(self):
        
        files = [
            sep + join('docs', 'drawio-exporter', '0000000000000000000000000000000000000000-0'),
            sep + join('docs', 'index.md'),
        ]
        files = [FileMock(**{'abs_src_path': f}) for f in files]

        exporter = DrawIoExporter(
            config={
                'logger': self.logger,
                'cache_dir': sep + join('docs', 'nomatch')
            }
        )
        result = exporter.filter_cache_files(files)
        assert len(result) == 2

        exporter = DrawIoExporter(
            config={
                'logger': self.logger,
                'cache_dir': sep + join('docs', 'drawio-exporter')
            }
        )
        result = exporter.filter_cache_files(files)
        assert len(result) == 1
        assert files[0] not in result

    def test_ensure_file_cached(self):

        source = sep + join('docs', 'diagram.drawio')
        source_rel = 'diagram.drawio'
        cache_dir = sep + join('docs', 'drawio-exporter')

        exporter = DrawIoExporter(
            config={
                'logger': self.logger,
                'cache_dir': cache_dir,
                'format': 'svg'
            }
        )
        exporter.make_cache_filename = MagicMock()
        exporter.make_cache_filename.return_value = join(cache_dir, '0000000000000000000000000000000000000000-0')
        exporter.export_file = MagicMock()
        exporter.export_file.return_value = 0

        cache_filename, exit_status = exporter.ensure_file_cached(source, source_rel, 0)
        assert cache_filename == exporter.make_cache_filename.return_value
        assert exit_status == 0

    def test_ensure_file_cached_aborts_if_drawio_executable_unavailable(self):

        self.logger.warn = MagicMock()
        
        with self.assertRaises(ConfigurationError):
            exporter = DrawIoExporter(
                config={
                    'logger': self.logger,
                    'executable_names': [],
                    'drawio_executable': None,
                    'cache_dir': sep + join('docs', 'drawio-exporter'),
                    'format': 'svg'
                }
            )
            self.logger.warn.assert_called_once()
            

    def test_ensure_file_cached_skips_export_if_cache_fresh(self):

        source = sep + join('docs', 'diagram.drawio')
        source_rel = 'diagram.drawio'
        cache_dir = sep + join('docs', 'drawio-exporter')

        exporter = DrawIoExporter(
            config={
                'logger': self.logger,
                'cache_dir': cache_dir,
                'format': 'svg'
            }
        )
        exporter.make_cache_filename = MagicMock()
        exporter.make_cache_filename.return_value = join(cache_dir, '0000000000000000000000000000000000000000-0')
        exporter.use_cached_file = MagicMock()
        exporter.use_cached_file.return_value = True
        exporter.export_file = MagicMock()
        exporter.export_file.return_value = 0

        cache_filename, exit_status = exporter.ensure_file_cached(source, source_rel, 0)
        assert cache_filename == exporter.make_cache_filename.return_value
        assert exit_status == None

        exporter.use_cached_file.assert_called_once()
        assert not exporter.export_file.called

    def test_ensure_file_cached_returns_exit_status_if_non_zero(self):
        
        source = sep + join('docs', 'diagram.drawio')
        source_rel = 'diagram.drawio'
        cache_dir = sep + join('docs', 'drawio-exporter')

        exporter = DrawIoExporter(
            config={
                'logger': self.logger,
                'cache_dir': cache_dir,
                'format': 'svg'
            }
        )
        exporter.make_cache_filename = MagicMock()
        exporter.make_cache_filename.return_value = join(cache_dir, '0000000000000000000000000000000000000000-0')
        exporter.use_cached_file = MagicMock()
        exporter.use_cached_file.return_value = False
        exporter.export_file = MagicMock()
        exporter.export_file.return_value = 1

        self.logger.error = MagicMock()

        cache_filename, exit_status = exporter.ensure_file_cached(source, source_rel, 0)
        assert exit_status == 1

    def test_make_cache_filename(self):

        cache_dir = sep + 'docs'

        exporter = DrawIoExporter(
            config={
                'logger': self.logger
            }
        )

        results = [
            exporter.make_cache_filename('diagram.drawio', 0, cache_dir),
            exporter.make_cache_filename('other-diagram.drawio', 0, cache_dir),
            exporter.make_cache_filename('other-diagram.drawio', 1, cache_dir),
        ]

        for result in results:
            assert result.startswith(cache_dir)
        assert len(set(results)) == 3

    @patch('os.path.exists')
    @patch('os.path.getmtime')
    def test_use_cached_file(self, getmtime_mock, exists_mock):

        cache_filename = sep + join('docs', 'drawio-exporter', '0000000000000000000000000000000000000000-0')
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

        exporter = DrawIoExporter(
            config={
                'logger': self.logger
            }
        )
        result = exporter.use_cached_file(source, cache_filename)
        assert result == False

    @patch('subprocess.call')
    def test_export_file(self, call_mock):

        source = sep + join('docs', 'diagram.drawio')
        dest = sep + join('docs', 'diagram.drawio-0.svg')
        drawio_executable = sep + join('bin', 'drawio')

        call_mock.return_value = 0

        exporter = DrawIoExporter(
            config={
                'logger': self.logger
            }
        )

        result = exporter.export_file(source, 0, dest, drawio_executable, [], 'svg')

        assert result == 0
        call_mock.assert_called_once()

    @patch('subprocess.call')
    def test_export_file_logs_exc_on_raise(self, call_mock):

        source = sep + join('docs', 'diagram.drawio')
        dest = sep + join('docs', 'diagram.drawio-0.svg')
        drawio_executable = sep + join('bin', 'drawio')

        call_mock.side_effect = OSError()

        self.logger.exception = MagicMock()

        exporter = DrawIoExporter(
            config={
                'logger': self.logger
            }
        )

        result = exporter.export_file(source, 0, dest, drawio_executable, [], 'svg')

        assert result == None
        self.logger.exception.assert_called_once()
        call_mock.assert_called_once()

    @patch('subprocess.call')
    def test_export_file_honours_drawio_args(self, call_mock):
        source = sep + join('docs', 'diagram.drawio')
        page_index = 0
        dest = sep + join('docs', 'diagram.drawio-0.svg')
        drawio_executable = sep + join('bin', 'drawio')
        format = 'svg'

        exporter = DrawIoExporter(
            config={
                'logger': self.logger
            }
        )

        def test_drawio_args(drawio_args):
            exporter.export_file(source, page_index, dest, drawio_executable, drawio_args, format)
            call_mock.assert_called_with([
                drawio_executable,
                '--export', source,
                '--page-index', str(page_index),
                '--output', dest,
                '--format', format,
            ] + drawio_args)

        test_drawio_args([])
        test_drawio_args(['--no-sandbox'])


if __name__ == '__main__':
    unittest.main()
