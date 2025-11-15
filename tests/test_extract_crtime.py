#!/usr/bin/env python3
import unittest
import os
import sys
import tempfile
import shutil
import datetime
import logging
from unittest.mock import patch, MagicMock, mock_open
from pathlib import Path

# Add parent directory to path to import the module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import extract_crtime


class TestFiletimeToDatetime(unittest.TestCase):
    """Test the filetime_to_datetime function"""

    def test_epoch(self):
        """Test FILETIME epoch (0 should be Jan 1, 1601)"""
        result = extract_crtime.filetime_to_datetime(0)
        expected = datetime.datetime(1601, 1, 1, tzinfo=datetime.timezone.utc)
        self.assertEqual(result, expected)

    def test_known_timestamp(self):
        """Test a known FILETIME value"""
        # FILETIME for 2020-01-11 08:00:00 UTC
        filetime = 132232032000000000
        result = extract_crtime.filetime_to_datetime(filetime)
        expected = datetime.datetime(2020, 1, 11, 8, 0, 0, tzinfo=datetime.timezone.utc)
        self.assertEqual(result, expected)

    def test_with_microseconds(self):
        """Test FILETIME conversion with microseconds"""
        # 100 nanosecond ticks = 10 microseconds
        filetime = 100
        result = extract_crtime.filetime_to_datetime(filetime)
        expected = datetime.datetime(1601, 1, 1, 0, 0, 0, 10, tzinfo=datetime.timezone.utc)
        self.assertEqual(result, expected)


class TestDayWithSuffix(unittest.TestCase):
    """Test the day_with_suffix function"""

    def test_first(self):
        self.assertEqual(extract_crtime.day_with_suffix(1), "1st")
        self.assertEqual(extract_crtime.day_with_suffix(21), "21st")
        self.assertEqual(extract_crtime.day_with_suffix(31), "31st")

    def test_second(self):
        self.assertEqual(extract_crtime.day_with_suffix(2), "2nd")
        self.assertEqual(extract_crtime.day_with_suffix(22), "22nd")

    def test_third(self):
        self.assertEqual(extract_crtime.day_with_suffix(3), "3rd")
        self.assertEqual(extract_crtime.day_with_suffix(23), "23rd")

    def test_fourth_through_twentieth(self):
        for day in range(4, 21):
            self.assertEqual(extract_crtime.day_with_suffix(day), f"{day}th")

    def test_eleventh_through_thirteenth(self):
        """These are special cases that should be 'th' not 'st', 'nd', 'rd'"""
        self.assertEqual(extract_crtime.day_with_suffix(11), "11th")
        self.assertEqual(extract_crtime.day_with_suffix(12), "12th")
        self.assertEqual(extract_crtime.day_with_suffix(13), "13th")

    def test_24th_through_30th(self):
        self.assertEqual(extract_crtime.day_with_suffix(24), "24th")
        self.assertEqual(extract_crtime.day_with_suffix(25), "25th")
        self.assertEqual(extract_crtime.day_with_suffix(30), "30th")


class TestFormatTimestampLocal(unittest.TestCase):
    """Test the format_timestamp_local function"""

    def test_format_structure(self):
        """Test that the format follows the expected pattern"""
        dt = datetime.datetime(2020, 3, 2, 19, 3, 0, tzinfo=datetime.timezone.utc)
        result = extract_crtime.format_timestamp_local(dt)
        # Should contain a day with suffix (check for 'st', 'nd', 'rd', or 'th')
        has_suffix = any(suffix in result for suffix in ['st', 'nd', 'rd', 'th'])
        self.assertTrue(has_suffix)
        self.assertIn("March", result)
        self.assertIn("2020", result)
        self.assertIn("at", result)

    def test_timezone_conversion(self):
        """Test that UTC time is converted to local time"""
        dt_utc = datetime.datetime(2020, 1, 1, 12, 0, 0, tzinfo=datetime.timezone.utc)
        result = extract_crtime.format_timestamp_local(dt_utc)
        # Result should be a string (we can't test exact local time without knowing timezone)
        self.assertIsInstance(result, str)
        self.assertIn("2020", result)


class TestTruncateFilename(unittest.TestCase):
    """Test the truncate_filename function"""

    def test_short_filename_no_truncation(self):
        """Test that short filenames are not truncated"""
        result = extract_crtime.truncate_filename("test.txt", 100, "timestamp")
        self.assertEqual(result, "test.txt")

    def test_long_filename_truncation(self):
        """Test that long filenames are truncated"""
        long_path = "a" * 100
        result = extract_crtime.truncate_filename(long_path, 50, "ts")
        self.assertTrue(result.startswith("..."))
        self.assertTrue(len(result) <= 50)

    def test_very_small_terminal_width(self):
        """Test behavior with very small terminal width"""
        result = extract_crtime.truncate_filename("test.txt", 10, "timestamp")
        # With term_width=10 and ts_str="timestamp" (9 chars), max_name_chars will be negative
        # So it should return "..."
        # Actually: max_line_width = max(20, 10-20) = 20
        # max_name_chars = 20 - (9 + 4) = 7
        # "test.txt" has 8 chars, so it gets truncated to "....txt"
        self.assertTrue(result.startswith("..."))

    def test_truncation_preserves_end(self):
        """Test that truncation preserves the end of the filename"""
        path = "very_long_filename_that_needs_truncation.txt"
        result = extract_crtime.truncate_filename(path, 50, "ts")
        if result != path:  # If it was truncated
            self.assertTrue(result.startswith("..."))
            self.assertTrue(result.endswith(".txt"))


class TestGetNtfsCrtimeWithRaw(unittest.TestCase):
    """Test the get_ntfs_crtime_with_raw function"""

    def test_no_xattr(self):
        """Test when file has no NTFS creation time xattr"""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_path = f.name
        try:
            dt, raw_hex, raw_bytes = extract_crtime.get_ntfs_crtime_with_raw(temp_path)
            self.assertIsNone(dt)
            self.assertIsNone(raw_hex)
            self.assertIsNone(raw_bytes)
        finally:
            os.unlink(temp_path)

    @patch('os.getxattr')
    def test_8_byte_filetime(self, mock_getxattr):
        """Test parsing 8-byte FILETIME value"""
        # FILETIME for 2020-01-11 08:00:00 UTC
        filetime_bytes = (132232032000000000).to_bytes(8, 'little')
        mock_getxattr.return_value = filetime_bytes

        dt, raw_hex, raw_bytes = extract_crtime.get_ntfs_crtime_with_raw("/fake/path")

        self.assertIsNotNone(dt)
        self.assertEqual(dt.year, 2020)
        self.assertEqual(dt.month, 1)
        self.assertEqual(dt.day, 11)
        self.assertTrue(raw_hex.startswith("0x"))
        self.assertEqual(raw_bytes, filetime_bytes)

    @patch('os.getxattr')
    def test_hex_string_with_0x_prefix(self, mock_getxattr):
        """Test parsing hex string with 0x prefix"""
        hex_str = "0x01d5e8c5c8e00000"
        mock_getxattr.return_value = hex_str.encode('ascii')

        dt, raw_hex, raw_bytes = extract_crtime.get_ntfs_crtime_with_raw("/fake/path")

        self.assertIsNotNone(dt)
        self.assertTrue(raw_hex.startswith("0x"))
        self.assertIsNotNone(raw_bytes)

    @patch('os.getxattr')
    def test_invalid_data(self, mock_getxattr):
        """Test handling of invalid xattr data"""
        mock_getxattr.return_value = b'\xff\xff\xff'  # Invalid data

        dt, raw_hex, raw_bytes = extract_crtime.get_ntfs_crtime_with_raw("/fake/path")

        # Should not crash, should return some reasonable values
        self.assertIsInstance(dt, (datetime.datetime, type(None)))
        self.assertIsInstance(raw_hex, (str, type(None)))
        self.assertIsInstance(raw_bytes, (bytes, type(None)))


class TestBuildFileList(unittest.TestCase):
    """Test the build_file_list function"""

    def setUp(self):
        """Create a temporary directory structure"""
        self.test_dir = tempfile.mkdtemp()

        # Create some test files
        Path(self.test_dir, "file1.txt").touch()
        Path(self.test_dir, "file2.txt").touch()

        # Create a subdirectory with files
        subdir = Path(self.test_dir, "subdir")
        subdir.mkdir()
        Path(subdir, "file3.txt").touch()
        Path(subdir, "file4.txt").touch()

    def tearDown(self):
        """Clean up temporary directory"""
        shutil.rmtree(self.test_dir)

    @patch('sys.stdout')
    def test_finds_all_files(self, mock_stdout):
        """Test that all files are found recursively"""
        files = extract_crtime.build_file_list(self.test_dir)
        self.assertEqual(len(files), 4)

        # Check that all files are in the list
        file_names = [os.path.basename(f) for f in files]
        self.assertIn("file1.txt", file_names)
        self.assertIn("file2.txt", file_names)
        self.assertIn("file3.txt", file_names)
        self.assertIn("file4.txt", file_names)

    @patch('sys.stdout')
    def test_empty_directory(self, mock_stdout):
        """Test with empty directory"""
        empty_dir = tempfile.mkdtemp()
        try:
            files = extract_crtime.build_file_list(empty_dir)
            self.assertEqual(len(files), 0)
        finally:
            os.rmdir(empty_dir)


class TestUpdateProgress(unittest.TestCase):
    """Test the update_progress function"""

    @patch('sys.stdout')
    @patch('shutil.get_terminal_size')
    def test_progress_output(self, mock_term_size, mock_stdout):
        """Test that progress bar is printed"""
        mock_term_size.return_value = MagicMock(columns=80)

        # Should not raise an exception
        extract_crtime.update_progress(5, 10, "test.txt", "timestamp")

        # Verify stdout.write was called
        self.assertTrue(mock_stdout.write.called)

    @patch('sys.stdout')
    @patch('shutil.get_terminal_size')
    def test_progress_with_no_timestamp(self, mock_term_size, mock_stdout):
        """Test progress update with None timestamp"""
        mock_term_size.return_value = MagicMock(columns=80)

        # Should not raise an exception
        extract_crtime.update_progress(5, 10, "", None)

        self.assertTrue(mock_stdout.write.called)


class TestVerifyTargetCount(unittest.TestCase):
    """Test the verify_target_count function"""

    def setUp(self):
        """Create a temporary directory with files"""
        self.test_dir = tempfile.mkdtemp()
        Path(self.test_dir, "file1.txt").touch()
        Path(self.test_dir, "file2.txt").touch()
        Path(self.test_dir, "file3.txt").touch()

    def tearDown(self):
        """Clean up temporary directory"""
        shutil.rmtree(self.test_dir)

    @patch('sys.stdout')
    def test_verify_disabled(self, mock_stdout):
        """Test that verification is skipped when disabled"""
        extract_crtime.verify_target_count(self.test_dir, 5, None, False)

        # Should not write anything to stdout
        mock_stdout.write.assert_not_called()

    @patch('sys.stdout')
    def test_count_matches(self, mock_stdout):
        """Test when file count matches expected"""
        logger = MagicMock()
        extract_crtime.verify_target_count(self.test_dir, 3, logger, True)

        # Should log success
        logger.info.assert_called()

    @patch('sys.stdout')
    def test_count_mismatch(self, mock_stdout):
        """Test when file count doesn't match expected"""
        logger = MagicMock()
        extract_crtime.verify_target_count(self.test_dir, 5, logger, True)

        # Should log warning
        logger.warning.assert_called()


class TestSetupLogger(unittest.TestCase):
    """Test the setup_logger function"""

    def setUp(self):
        """Clean up log files before each test"""
        if os.path.exists("logs"):
            shutil.rmtree("logs")

    def tearDown(self):
        """Clean up log files and directory"""
        if os.path.exists("logs"):
            shutil.rmtree("logs")

    def test_logger_disabled(self):
        """Test that None is returned when logging is disabled"""
        logger = extract_crtime.setup_logger("test", False)
        self.assertIsNone(logger)

    def test_logger_enabled(self):
        """Test that a logger is created when enabled"""
        logger = extract_crtime.setup_logger("test", True)
        self.assertIsNotNone(logger)
        self.assertIsInstance(logger, logging.Logger)

        # Verify logs directory was created
        self.assertTrue(os.path.exists("logs"))

        # Verify at least one log file was created
        log_files = os.listdir("logs")
        self.assertGreater(len(log_files), 0)

    def test_logger_creates_log_file(self):
        """Test that the logger creates a timestamped log file"""
        logger = extract_crtime.setup_logger("test", True)

        # Check that log file exists and has content
        log_files = os.listdir("logs")
        self.assertEqual(len(log_files), 1)

        log_path = os.path.join("logs", log_files[0])
        self.assertTrue(os.path.isfile(log_path))

        # Verify the file has some content (header lines)
        with open(log_path, 'r') as f:
            content = f.read()
            self.assertIn("Command:", content)


class TestWalkAndCopy(unittest.TestCase):
    """Test the walk_and_copy function"""

    def setUp(self):
        """Create source and destination directories"""
        self.src_dir = tempfile.mkdtemp()
        self.dest_dir = tempfile.mkdtemp()

        # Remove dest_dir as walk_and_copy creates it
        shutil.rmtree(self.dest_dir)

        # Create test files in source
        Path(self.src_dir, "file1.txt").write_text("content1")
        Path(self.src_dir, "file2.txt").write_text("content2")

        subdir = Path(self.src_dir, "subdir")
        subdir.mkdir()
        Path(subdir, "file3.txt").write_text("content3")

    def tearDown(self):
        """Clean up directories"""
        if os.path.exists(self.src_dir):
            shutil.rmtree(self.src_dir)
        if os.path.exists(self.dest_dir):
            shutil.rmtree(self.dest_dir)

    @patch('sys.stdout')
    def test_copies_files(self, mock_stdout):
        """Test that files are copied to destination"""
        extract_crtime.walk_and_copy(self.src_dir, self.dest_dir, None, False)

        # Verify files were copied
        self.assertTrue(os.path.exists(os.path.join(self.dest_dir, "file1.txt")))
        self.assertTrue(os.path.exists(os.path.join(self.dest_dir, "file2.txt")))
        self.assertTrue(os.path.exists(os.path.join(self.dest_dir, "subdir", "file3.txt")))

        # Verify content
        with open(os.path.join(self.dest_dir, "file1.txt"), 'r') as f:
            self.assertEqual(f.read(), "content1")

    @patch('sys.stdout')
    def test_creates_csv(self, mock_stdout):
        """Test that CSV file is created"""
        extract_crtime.walk_and_copy(self.src_dir, self.dest_dir, None, False)

        csv_path = os.path.join(self.dest_dir, "timestamps.csv")
        self.assertTrue(os.path.exists(csv_path))

        # Verify CSV has correct headers
        with open(csv_path, 'r') as f:
            first_line = f.readline().strip()
            self.assertEqual(first_line, "file,timestamp,timestamp_str,copy_successful,xattr_successful")

    @patch('sys.stdout')
    def test_csv_has_all_files(self, mock_stdout):
        """Test that CSV contains entries for all files"""
        extract_crtime.walk_and_copy(self.src_dir, self.dest_dir, None, False)

        csv_path = os.path.join(self.dest_dir, "timestamps.csv")
        with open(csv_path, 'r') as f:
            lines = f.readlines()
            # Header + 3 files
            self.assertEqual(len(lines), 4)

    @patch('sys.stdout')
    def test_empty_source_directory(self, mock_stdout):
        """Test with empty source directory"""
        empty_src = tempfile.mkdtemp()
        empty_dest = tempfile.mkdtemp()
        shutil.rmtree(empty_dest)

        try:
            extract_crtime.walk_and_copy(empty_src, empty_dest, None, False)
            # Should not crash
            self.assertTrue(True)
        finally:
            shutil.rmtree(empty_src)
            if os.path.exists(empty_dest):
                shutil.rmtree(empty_dest)


if __name__ == '__main__':
    unittest.main()
