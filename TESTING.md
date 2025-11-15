# Unit Tests for ntfs2xattr

This directory contains comprehensive unit tests for the `extract_crtime.py` script.

## Running the Tests

### Run all tests:
```bash
python3 run_tests.py
```

Or from the tests directory:
```bash
python3 -m unittest discover
```

### Run a specific test class:
```bash
python3 -m unittest tests.test_extract_crtime.TestFiletimeToDatetime
```

### Run a specific test:
```bash
python3 -m unittest tests.test_extract_crtime.TestFiletimeToDatetime.test_epoch
```

## Test Coverage

The test suite covers all major functions in `extract_crtime.py`:

- **`filetime_to_datetime()`** - Tests FILETIME to datetime conversion
- **`day_with_suffix()`** - Tests ordinal suffix generation (1st, 2nd, 3rd, etc.)
- **`format_timestamp_local()`** - Tests timestamp formatting
- **`get_ntfs_crtime_with_raw()`** - Tests xattr reading and parsing
- **`build_file_list()`** - Tests recursive file discovery
- **`truncate_filename()`** - Tests filename truncation logic
- **`update_progress()`** - Tests progress bar output
- **`verify_target_count()`** - Tests file count verification
- **`setup_logger()`** - Tests logger configuration
- **`walk_and_copy()`** - Tests the main copy operation with CSV generation

## Test Structure

Each test class corresponds to a function in the main script:
- Tests use temporary directories and files where needed
- Mock objects are used for external dependencies (xattrs, stdout)
- Tests clean up after themselves to avoid side effects

## Requirements

The tests use Python's built-in `unittest` framework and require no additional dependencies beyond what's needed for the main script.
