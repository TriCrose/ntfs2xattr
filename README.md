# ntfs2xattr
A couple of scripts to help make the process of moving from Windows to Linux just a little bit easier. 🐧

`ntfs2xattr.py` copies a directory from an NTFS-formatted drive/partition to ext4 while preserving the crtime (NTFS-only) by adding it as an extended attribute to each file ext4. It actually adds two xattrs:
* `user.ntfs_crtime`
* `user.ntfs_crtime_readable`

`nemo-ntfs2xattr.py` is an extension for the Nemo file manager that does two things:
* Adds a new property page called "Extended Attributes" to the file properties window that shows a list of all xattrs on the file;
* Adds a new column to the file browser window called "Date Created (NTFS)" which shows the creation time for each file, read from its xattr.

## Setup

## Usage

## Tests
### Unit tests
### E2E
