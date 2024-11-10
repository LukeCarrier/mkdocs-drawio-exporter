import unittest
from unittest.mock import MagicMock, patch

import logging
import os
from os.path import join, sep

from ..exporter import Configuration, ConfigurationError, DrawIoExporter, Source


class FileMock:
    src_path = None
    abs_src_path = None

    def __init__(self, **kwargs):
        for attr, value in kwargs.items():
            setattr(self, attr, value)


class SourceTests(unittest.TestCase):
    def test_resolve_rel_path(self):
        cases = [
            ("dir/diagram.drawio", ("diagram.drawio", 0), "dir/page.md"),
            ("dir1/dir2/diagram.drawio", ("diagram.drawio", 0), "dir1/dir2/index.md"),
            ("dir1/dir2/dir3/diagram.drawio", ("diagram.drawio", 0), "dir1/dir2/dir3/index.md"),
        ]
        for expect, source_args, page_src_path in cases:
            with self.subTest(expect, source_args, page_src_path):
                source = Source(*source_args)
                result = source.resolve_rel_path(page_src_path)
                self.assertEqual(expect, result)


class ExporterTests(unittest.TestCase):
    log = None

    def setUp(self):
        self.log = logging.getLogger(__name__)
    def make_exporter(self, docs_dir=None):
        if not docs_dir:
            docs_dir = sep + 'docs'
        return DrawIoExporter(self.log, docs_dir)

    def make_config(self, **kwargs):
        defaults = {
            'cache_dir': 'drawio-exporter',
            'drawio_executable': 'drawio',
            'drawio_args': [],
            'format': 'svg',
            'embed_format': '<img alt="{img_alt}" src="{img_src}">',
            'sources': '*.drawio',
        }
        # FIXME: when dropping support for Python 3.8, replace with the merge
        # operator (|).
        values = {**defaults, **kwargs}
        return Configuration(**values)

    def test_drawio_executable_paths_warns_on_unknown_platform(self):
        self.log.warning = MagicMock()
        exporter = self.make_exporter()
        exporter.drawio_executable_paths('win32-but-stable')
        self.log.warning.assert_called_once()

    def test_prepare_cache_dir_defaults(self):
        exporter = self.make_exporter()
        assert len(exporter.prepare_cache_dir(sep + 'docs'))

    def test_prepare_cache_dir_resolves_relative_path(self):
        exporter = self.make_exporter()

        result = exporter.prepare_cache_dir('temp')
        assert os.path.isabs(result)
        assert result.startswith(sep + 'docs' + sep)

    def test_prepare_drawio_executable_aborts_on_missing_executable(self):
        exporter = self.make_exporter()
        with self.assertRaises(ConfigurationError):
            exporter.prepare_drawio_executable(
                    sep + join('does', 'not', 'exist'), [], [])

    def test_prepare_drawio_executable_uses_valid_specified_exectuable(self):
        exporter = self.make_exporter()
        # We need something that exists, and right now we're not verifying that
        # it's executable. This will do.
        expected = os.path.abspath(__file__)
        actual = exporter.prepare_drawio_executable(
                expected, exporter.DRAWIO_EXECUTABLE_NAMES, [])
        assert expected == actual

    @patch('shutil.which')
    @patch.dict(os.environ, {'PATH': sep + join('does', 'not', 'exist')})
    def test_prepare_drawio_executable_on_path(self, mock_which):
        exporter = self.make_exporter()
        mock_which.return_value = sep + join('does', 'not', 'exist', 'drawio')
        result = exporter.prepare_drawio_executable(None, exporter.DRAWIO_EXECUTABLE_NAMES, [])
        assert result == mock_which.return_value

    @patch('os.path.isfile')
    def test_prepare_drawio_executable_platform_specific(self, mock_isfile):
        expect = sep + join('does', 'not', 'exist', 'someotherdrawio')
        mock_isfile.side_effect = lambda p: p == expect

        exporter = self.make_exporter()

        result = exporter.prepare_drawio_executable(None, [], [
            sep + join('does', 'not', 'exist', 'drawio'),
            expect,
        ])
        assert result == expect

    def test_prepare_drawio_executable_raises_on_failure(self):
        exporter = self.make_exporter()

        with self.assertRaises(ConfigurationError):
            exporter.prepare_drawio_executable(None, [], [])

    def test_rewrite_image_embeds(self):
        page_dest_path = "index.html"
        source = '''# Example text

![Some text](../some-diagram.drawio)'''
        object_embed_format = '<object type="image/svg+xml" data="{img_src}"></object>'

        exporter = self.make_exporter()

        config = self.make_config(sources='*.nomatch')
        output_content, sources = exporter.rewrite_image_embeds(
                page_dest_path, source, config)
        assert output_content == source
        assert sources == []

        config = self.make_config()
        output_content, sources = exporter.rewrite_image_embeds(
                page_dest_path, source, config)
        assert output_content != source
        assert 'src="../some-diagram.drawio-0.svg"' in output_content
        assert len(sources) == 1

        config = self.make_config(embed_format=object_embed_format)
        output_content, sources = exporter.rewrite_image_embeds(
                page_dest_path, source, config)
        assert output_content != source
        assert '<object type="image/svg+xml" data="../some-diagram.drawio-0.svg"></object>' in output_content
        assert len(sources) == 1

    def test_filter_cache_files(self):
        files = [
            sep + join('docs', 'drawio-exporter', '0000000000000000000000000000000000000000-0'),
            sep + join('docs', 'index.md'),
        ]
        files = [FileMock(**{'abs_src_path': f}) for f in files]

        exporter = self.make_exporter()

        result = exporter.filter_cache_files(files, sep + join('docs', 'nomatch'))
        assert len(result) == 2

        result = exporter.filter_cache_files(files, sep + join('docs', 'drawio-exporter'))
        assert len(result) == 1
        assert files[0] not in result

    def test_ensure_file_cached(self):
        source = sep + join('docs', 'diagram.drawio')
        source_rel = 'diagram.drawio'
        drawio_executable = sep + join('bin', 'drawio')
        cache_dir = sep + join('docs', 'drawio-exporter')

        exporter = self.make_exporter()
        config = self.make_config(
            cache_dir=cache_dir,
            drawio_executable=drawio_executable,
        )

        exporter.make_cache_filename = MagicMock()
        exporter.make_cache_filename.return_value = join(cache_dir, '0000000000000000000000000000000000000000-0')

        exporter.export_file = MagicMock()
        exporter.export_file.return_value = 0

        cache_filename, exit_status = exporter.ensure_file_cached(
                source, source_rel, 0, config)
        assert cache_filename == exporter.make_cache_filename.return_value
        assert exit_status == 0

    def test_ensure_file_cached_aborts_if_drawio_executable_unavailable(self):
        source = sep + join('docs', 'diagram.drawio')
        source_rel = 'diagram.drawio'
        drawio_executable = None
        cache_dir = sep + join('docs', 'drawio-exporter')

        exporter = self.make_exporter()
        config = self.make_config(
            cache_dir=cache_dir,
            drawio_executable=drawio_executable,
        )

        exporter.export_file = MagicMock()
        exporter.export_file.return_value = 0

        self.log.warning = MagicMock()

        _, exit_status = exporter.ensure_file_cached(
                source, source_rel, 0, config)

        assert exit_status is None
        self.log.warning.assert_called_once()

    def test_ensure_file_cached_skips_export_if_cache_fresh(self):
        source = sep + join('docs', 'diagram.drawio')
        source_rel = 'diagram.drawio'
        drawio_executable = sep + join('bin', 'drawio')
        cache_dir = sep + join('docs', 'drawio-exporter')

        exporter = self.make_exporter()
        config = self.make_config(
            cache_dir=cache_dir,
            drawio_executable=drawio_executable,
        )

        exporter.make_cache_filename = MagicMock()
        exporter.make_cache_filename.return_value = join(cache_dir, '0000000000000000000000000000000000000000-0')

        exporter.use_cached_file = MagicMock()
        exporter.use_cached_file.return_value = True

        exporter.export_file = MagicMock()
        exporter.export_file.return_value = 0

        cache_filename, exit_status = exporter.ensure_file_cached(
                source, source_rel, 0, config)

        assert cache_filename == exporter.make_cache_filename.return_value
        assert exit_status is None
        exporter.use_cached_file.assert_called_once()
        assert not exporter.export_file.called

    def test_ensure_file_cached_returns_exit_status_if_non_zero(self):
        source = sep + join('docs', 'diagram.drawio')
        source_rel = 'diagram.drawio'
        drawio_executable = sep + join('bin', 'drawio')
        cache_dir = sep + join('docs', 'drawio-exporter')

        exporter = self.make_exporter()
        config = self.make_config(
            cache_dir=cache_dir,
            drawio_executable=drawio_executable,
        )

        exporter.make_cache_filename = MagicMock()
        exporter.make_cache_filename.return_value = join(cache_dir, '0000000000000000000000000000000000000000-0')

        exporter.use_cached_file = MagicMock()
        exporter.use_cached_file.return_value = False

        exporter.export_file = MagicMock()
        exporter.export_file.return_value = 1

        self.log.error = MagicMock()

        cache_filename, exit_status = exporter.ensure_file_cached(
                source, source_rel, 0, config)

        assert exit_status == 1

    def test_make_cache_filename(self):
        cache_dir = sep + 'docs'

        exporter = self.make_exporter()

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

        exporter = self.make_exporter()

        def getmtime_return_value(path):
            if path == cache_filename:
                return 1577043612.1444612
            elif path == source:
                return 1577133635.3318102
            else:
                raise ValueError(f'didn\'t expect path "{path}"')
        getmtime_mock.side_effect = getmtime_return_value

        result = exporter.use_cached_file(source, cache_filename)
        assert not result

    @patch('subprocess.call')
    def test_export_file(self, call_mock):
        source = sep + join('docs', 'diagram.drawio')
        dest = sep + join('docs', 'diagram.drawio-0.svg')
        drawio_executable = sep + join('bin', 'drawio')

        exporter = self.make_exporter()
        config = self.make_config(
            drawio_executable=drawio_executable,
        )

        call_mock.return_value = 0

        result = exporter.export_file(
                source, 0, dest, config)

        assert result == 0
        call_mock.assert_called_once()

    @patch('subprocess.call')
    def test_export_file_logs_exc_on_raise(self, call_mock):
        source = sep + join('docs', 'diagram.drawio')
        dest = sep + join('docs', 'diagram.drawio-0.svg')
        drawio_executable = sep + join('bin', 'drawio')

        exporter = self.make_exporter()
        config = self.make_config(
            drawio_executable=drawio_executable,
        )

        call_mock.side_effect = OSError()

        self.log.exception = MagicMock()

        result = exporter.export_file(
                source, 0, dest, config)

        assert result is None
        self.log.exception.assert_called_once()
        call_mock.assert_called_once()

    @patch('subprocess.call')
    def test_export_file_honours_drawio_args(self, call_mock):
        source = sep + join('docs', 'diagram.drawio')
        page_index = 0
        dest = sep + join('docs', 'diagram.drawio-0.svg')
        drawio_executable = sep + join('bin', 'drawio')

        exporter = self.make_exporter()
        config = self.make_config(
            drawio_executable=drawio_executable,
            format='svg'
        )

        def test_drawio_args(config: Configuration, drawio_args):
            test_config = {**config, 'drawio_args': drawio_args}
            exporter.export_file(
                    source, page_index, dest, test_config)
            call_mock.assert_called_with([
                config['drawio_executable'],
                '--export', source,
                '--page-index', str(page_index),
                '--output', dest,
                '--format', config['format'],
            ] + drawio_args)

        test_drawio_args(config, [])
        test_drawio_args(config, ['--no-sandbox'])


if __name__ == '__main__':
    unittest.main()
