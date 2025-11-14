#!/usr/bin/env python3
import os
import argparse
import datetime
import sys
import shutil
import logging
from typing import List, Optional, Tuple

NTFS_CRTIME_ATTR_SRC = "system.ntfs_crtime"   # from NTFS
NTFS_CRTIME_ATTR_DST = "user.ntfs_crtime"     # raw FILETIME bytes
NTFS_CRTIME_ATTR_READABLE = "user.ntfs_crtime_readable"  # readable string

FILETIME_EPOCH = datetime.datetime(1601, 1, 1, tzinfo=datetime.timezone.utc)
FILETIME_TICKS_PER_SECOND = 10_000_000  # 100ns units per second

# ANSI colors
YELLOW = "\033[33m"
GREEN  = "\033[32m"
WHITE  = "\033[37m"
RED    = "\033[31m"
RESET  = "\033[0m"


def filetime_to_datetime(filetime: int) -> datetime.datetime:
    seconds, remainder = divmod(filetime, FILETIME_TICKS_PER_SECOND)
    microseconds = remainder // 10
    return FILETIME_EPOCH + datetime.timedelta(seconds=seconds,
                                               microseconds=microseconds)


def day_with_suffix(day: int) -> str:
    if 11 <= day % 100 <= 13:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
    return f"{day}{suffix}"


def format_timestamp_local(dt_utc: datetime.datetime) -> str:
    dt_local = dt_utc.astimezone()
    day_str = day_with_suffix(dt_local.day)
    month_str = dt_local.strftime("%B")
    return f"{day_str} {month_str} {dt_local.year} at {dt_local:%H:%M}"


def get_ntfs_crtime_with_raw(path: str) -> Tuple[Optional[datetime.datetime],
                                                 Optional[str],
                                                 Optional[bytes]]:
    """
    Return (datetime_in_UTC, raw_hex_string_like_getfattr, raw_bytes) or (None, None, None)
    """
    try:
        raw = os.getxattr(path, NTFS_CRTIME_ATTR_SRC)
    except OSError:
        return None, None, None

    dt: Optional[datetime.datetime] = None
    raw_hex_str: Optional[str] = None
    raw_bytes: Optional[bytes] = raw

    if len(raw) == 8:
        raw_hex_str = "0x" + raw.hex()
        filetime_int = int.from_bytes(raw, "little", signed=False)
        dt = filetime_to_datetime(filetime_int)
    else:
        try:
            text = raw.decode("ascii").strip()
            if text.startswith(("0x", "0X")):
                hex_part = text[2:]
                raw_hex_str = "0x" + hex_part.lower()
            else:
                hex_part = text
                raw_hex_str = "0x" + hex_part.lower()
            filetime_int = int(hex_part, 16)
            dt = filetime_to_datetime(filetime_int)
            raw_bytes = int(filetime_int).to_bytes(8, "little", signed=False)
        except Exception:
            try:
                raw_hex_str = text
            except NameError:
                raw_hex_str = None
            raw_bytes = None

    return dt, raw_hex_str, raw_bytes


def build_file_list(input_dir: str) -> List[str]:
    files: List[str] = []
    count = 0
    for root, _, fnames in os.walk(input_dir):
        for name in fnames:
            files.append(os.path.join(root, name))
            count += 1
            sys.stdout.write(
                f"\r\033[2K{YELLOW}Building file list... {WHITE}{count}{RESET}"
            )
            sys.stdout.flush()
    sys.stdout.write("\n")
    return files


def truncate_filename(rel_path: str, term_width: int, ts_str: str) -> str:
    ts_len = len(ts_str)
    max_line_width = max(20, term_width - 20)
    max_name_chars = max_line_width - (ts_len + 4)
    if max_name_chars <= 0:
        return "..."
    if len(rel_path) <= max_name_chars:
        return rel_path
    if max_name_chars <= 3:
        return "." * max_name_chars
    tail_len = max_name_chars - 3
    return "..." + rel_path[-tail_len:]


def update_progress(i: int, total: int, rel_path: str, ts_str: Optional[str]) -> None:
    try:
        width = shutil.get_terminal_size().columns
    except Exception:
        width = 80

    if i > 0:
        sys.stdout.write("\r\033[2K")
    if ts_str is not None and rel_path:
        display_name = truncate_filename(rel_path, width, ts_str)
        print(f"'{display_name}'  {YELLOW}{ts_str}{RESET}")

    bar_width = max(10, width - 10)
    progress = min(1.0, (i + 1) / total)
    filled = int(bar_width * progress)
    bar = "#" * filled + " " * (bar_width - filled)
    percent = int(progress * 100)
    sys.stdout.write(f"[{GREEN}{bar}{RESET}] {percent:3d}%")
    sys.stdout.flush()


def verify_target_count(dest_dir: str, expected_count: int,
                        logger: Optional[logging.Logger], do_verify: bool) -> None:
    if not do_verify:
        return
    count = 0
    msg_prefix = "Verifying target directory file count... "
    for root, _, fnames in os.walk(dest_dir):
        for _ in fnames:
            count += 1
            sys.stdout.write(f"\r\033[2K{msg_prefix}{count}")
            sys.stdout.flush()

    if count == expected_count:
        sys.stdout.write(f"\r{msg_prefix}{count} ✅\n")
        if logger:
            logger.info(
                f"Counted {count} files in the target directory (matches source directory)"
            )
    else:
        sys.stdout.write(
            f"\r{msg_prefix}{count} ❌ (doesn't match source count of {expected_count})\n"
        )
        if logger:
            logger.warning(
                f"Counted {count} files in the target directory "
                f"(does not match source directory count of {expected_count})"
            )


def setup_logger(script_name: str, enabled: bool) -> Optional[logging.Logger]:
    if not enabled:
        return None

    logger = logging.getLogger("ntfs_copy_logger")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    info_handler = logging.FileHandler(script_name + ".INFO.log", "a", "utf-8")
    info_handler.setLevel(logging.INFO)
    info_handler.setFormatter(logging.Formatter("[%(asctime)s - %(levelname)s] %(message)s"))
    logger.addHandler(info_handler)

    cmdline = " ".join(sys.argv)
    now = datetime.datetime.now()
    logger.info(f"Command: {cmdline}")
    logger.info(f"Run at {now:%H:%M:%S} on {now:%Y/%m/%d}")
    return logger


def walk_and_copy(src_dir: str, dest_dir: str,
                  logger: Optional[logging.Logger], verify: bool) -> None:
    src_dir, dest_dir = map(os.path.abspath, (src_dir, dest_dir))
    os.makedirs(dest_dir, exist_ok=True)
    files = build_file_list(src_dir)
    total = len(files)
    if logger:
        logger.info(f"{total} files found in source '{src_dir}'")
    if not total:
        print("No files found.")
        verify_target_count(dest_dir, 0, logger, verify)
        return

    print(f"{YELLOW}Extracting NTFS creation times{RESET}")

    for i, src_path in enumerate(files):
        rel = os.path.relpath(src_path, src_dir)
        dst_path = os.path.join(dest_dir, rel)
        dt, raw_hex, raw_bytes = get_ntfs_crtime_with_raw(src_path)
        readable_ts = format_timestamp_local(dt) if dt else "N/A"
        raw_ts_for_log = raw_hex or "N/A"
        try:
            os.makedirs(os.path.dirname(dst_path), exist_ok=True)
            shutil.copy2(src_path, dst_path)
            # Add xattrs
            if raw_bytes:
                try:
                    os.setxattr(dst_path, NTFS_CRTIME_ATTR_DST, raw_bytes)
                    os.setxattr(dst_path, NTFS_CRTIME_ATTR_READABLE,
                                readable_ts.encode("utf-8"))
                except OSError as e:
                    if logger:
                        logger.warning(
                            f"'{dst_path}': failed to set xattr: {e}")
            if logger:
                logger.info(
                    f"'{src_path}' --> '{dst_path}'  "
                    f"with timestamp {raw_ts_for_log} ({readable_ts})")
            update_progress(i, total, rel, readable_ts)
        except Exception as e:
            print(f"{WHITE}'{rel}'{RESET}{RED} failed to copy: {RESET}{WHITE}{e}{RESET}")
            if logger:
                logger.error(f"'{src_path}' failed to copy: {e}")
            update_progress(i, total, "", None)

    sys.stdout.write("\n")
    verify_target_count(dest_dir, total, logger, verify)


def main():
    parser = argparse.ArgumentParser(
        description="Copy NTFS files, preserving creation time in xattrs "
                    "and logging activity with progress indicators.")
    parser.add_argument("--src", required=True, help="Source directory on NTFS mount")
    parser.add_argument("--dest", required=True, help="Destination directory")
    parser.add_argument("--no-log", action="store_true", help="Disable logging")
    parser.add_argument("--no-verify", action="store_true",
                        help="Disable verification of file count")
    args = parser.parse_args()

    if not os.path.isdir(args.src):
        sys.exit(f"Error: '{args.src}' is not a directory")

    if os.path.exists(args.dest):
        sys.exit(f"'{args.dest}' directory already exists. Please specify an empty directory.")

    script_name = os.path.basename(sys.argv[0]) or "script"
    logger = setup_logger(script_name, not args.no_log)
    walk_and_copy(args.src, args.dest, logger, not args.no_verify)


if __name__ == "__main__":
    main()

