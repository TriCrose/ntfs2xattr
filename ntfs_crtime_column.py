#!/usr/bin/env python3
import os
import urllib.parse
import datetime

from gi.repository import GObject, Nemo, Gtk

# xattr names
ATTR_RAW = "user.ntfs_crtime"
ATTR_READABLE = "user.ntfs_crtime_readable"

# FILETIME epoch
FILETIME_EPOCH = datetime.datetime(1601, 1, 1, tzinfo=datetime.timezone.utc)
FILETIME_TICKS_PER_SECOND = 10_000_000  # 100ns units per second


def filetime_to_datetime(filetime: int) -> datetime.datetime:
    seconds, remainder = divmod(filetime, FILETIME_TICKS_PER_SECOND)
    microseconds = remainder // 10
    return FILETIME_EPOCH + datetime.timedelta(seconds=seconds,
                                               microseconds=microseconds)


def format_timestamp_local(dt_utc: datetime.datetime) -> str:
    """
    Format as: Sun 09 Nov HH:MM:SS (24-hour)
    """
    dt_local = dt_utc.astimezone()
    return dt_local.strftime("%a %d %b %H:%M:%S")


def get_ntfs_crtime_string(path: str) -> str:
    """
    Return human-readable NTFS crtime string for a given file, or '' if not present.
    Priority:
      1. user.ntfs_crtime_readable (UTF-8 string)
      2. user.ntfs_crtime (8-byte FILETIME or hex)
    """
    # 1) Try the readable xattr first
    try:
        raw_readable = os.getxattr(path, ATTR_READABLE)
        try:
            txt = raw_readable.decode("utf-8").strip()
            if txt:
                # We *could* re-parse and reformat, but assume it's ok or return as-is.
                # To force the new format, we could try to parse, but that’s brittle.
                return txt
        except Exception:
            pass
    except OSError:
        pass

    # 2) Fall back to raw FILETIME bytes / hex
    try:
        raw = os.getxattr(path, ATTR_RAW)
    except OSError:
        return ""

    # 8 bytes: FILETIME
    if len(raw) == 8:
        filetime_int = int.from_bytes(raw, "little", signed=False)
        dt = filetime_to_datetime(filetime_int)
        return format_timestamp_local(dt)

    # Try ASCII hex
    try:
        text = raw.decode("ascii").strip()
        if text.startswith(("0x", "0X")):
            hex_part = text[2:]
        else:
            hex_part = text
        filetime_int = int(hex_part, 16)
        dt = filetime_to_datetime(filetime_int)
        return format_timestamp_local(dt)
    except Exception:
        return ""


class NTFSCRTimeExtension(GObject.GObject,
                          Nemo.ColumnProvider,
                          Nemo.InfoProvider,
                          Nemo.PropertyPageProvider):
    """
    Nemo extension that:
      - Adds a 'Date Created (NTFS)' column
      - Adds a 'Date Created (NTFS)' Property tab
    using xattrs:
      - user.ntfs_crtime_readable
      - user.ntfs_crtime
    """

    def __init__(self):
        super().__init__()

    # === ColumnProvider ===
    def get_columns(self):
        """
        Define the custom column.
        """
        return (
            Nemo.Column(
                name="NemoPython::ntfs_crtime_column",
                attribute="ntfs_crtime",
                label="Date Created (NTFS)",
                description="NTFS creation time from extended attributes",
            ),
        )

    # === InfoProvider ===
    def update_file_info(self, file):
        """
        Called by Nemo for files; we attach the 'ntfs_crtime' string attribute.
        """
        if file.get_uri_scheme() != "file":
            return

        uri = file.get_uri()  # e.g. file:///home/user/foo
        path = urllib.parse.unquote(uri[7:])  # strip 'file://'

        value = get_ntfs_crtime_string(path)
        file.add_string_attribute("ntfs_crtime", value)

    # === PropertyPageProvider ===
    def get_property_pages(self, files):
        """
        Create a "Date Created (NTFS)" tab in the Properties dialog
        when a single local file is selected.
        """
        if not files or len(files) != 1:
            return

        file = files[0]
        if file.get_uri_scheme() != "file":
            return

        uri = file.get_uri()
        path = urllib.parse.unquote(uri[7:])
        value = get_ntfs_crtime_string(path)

        if not value:
            return

        # Simple vertical box with a label inside
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.set_border_width(6)

        label = Gtk.Label(label=value)
        label.set_xalign(0.0)  # left-align
        box.pack_start(label, False, False, 0)

        page = Nemo.PropertyPage(
            name="NemoPython::ntfs_crtime_properties",
            label="Date Created (NTFS)",
            page=box,
        )
        return [page]

