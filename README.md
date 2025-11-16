# ntfs2xattr
A couple of scripts to make the process of moving from Windows to Linux just a little bit easier. 😊 🤝 🐧

`ntfs2xattr.py` copies a directory from an NTFS-formatted volume to ext4 while preserving the crtime (NTFS-only) by adding it as an extended attribute to each file. It actually adds two xattrs:
* `user.ntfs_crtime`: the raw NTFS timestamp, defined as the number of 100-nanosecond intervals since 00:00 January 1, 1601 UTC (see https://learn.microsoft.com/en-gb/windows/win32/sysinfo/file-times);
* `user.ntfs_crtime_readable`: ISO 8601 string representation of that timestamp (e.g. "1998-01-22 00:00:00").

`nemo-ntfs2xattr.py` is an extension for the [Nemo](https://github.com/linuxmint/nemo) file manager that does two things:
* Adds a new property page called "Extended Attributes" to the file properties window that shows a list of all xattrs on the file;

* Adds a new column to the file browser window called "Date Created (NTFS)" which shows the creation time for each file, read from its xattr.

A debian-based Linux distribution (Ubuntu, Linux Mint, etc.) is assumed for all the instructions in this document; please adjust accordingly for other distros.

## Setup

### Clone the repo
```bash
git clone https://github.com/TriCrose/ntfs2xattr
cd ntfs2xattr
```

### Install the Nemo extension
[`nemo-python`](https://github.com/linuxmint/nemo-extensions/tree/master/nemo-python) is required to use the Nemo extension. You can install it with:
```bash
sudo apt install nemo-python
```
Then create the extensions directory:
```bash
mkdir -p ~/.local/share/nemo-python/extensions
```
Finally, copy over the extension and close any running Nemo instances:
```bash
cp nemo-ntfs2xattr.py ~/.local/share/nemo-python/extensions
chmod +x ~/.local/share/nemo-python/extensions/nemo-ntfs2xattr.py
nemo -q
```

## Usage
Looking at the output of `python ntfs2xattr.py -h`:
```
usage: ntfs2xattr.py [-h] --src SRC --dest DEST [--no-log] [--no-verify]

Copy a directory from an NTFS volume, preserving crtime via xattrs on each file.

options:
  -h, --help   show this help message and exit
  --src SRC    Source directory on NTFS mount
  --dest DEST  Destination directory
  --no-log     Disable logging
  --no-verify  Disable verification of file count
```
It's fairly self-explanatory. As an example, your command could look something like:
```
python3 ntfs2xattr.py --src /media/windows/7826D16A26D129C0/Users/John/Documents --dest ~/Documents
```
Upon running the script, it first counts the number of files in the source directory (used for the verification step at the end), before then beginning to copy all the files and set the xattr on each one. It prints the name and the extracted timestamp both to the terminal (with a progress bar along the bottom) and to a local `.log` file in the `logs/` directory. Each invocation of the script gets its own log file in this directory with a filename corresponding to the time of invocation.

Once copying is finished, the number of files in the target directory is counted and compared with the original source count. If they do not match, the script will print out the name of each file that didn't copy as well as the associated error message. This information is also available in the logs (try `grep`ing for "WARNING" or "ERROR"). The most common cases of failed copies, however, are Windows system files that don't play well with the Linux environment or that behave strangely due to quirks of the OS. Your personal documents, images, videos etc. are unlikely to have any issues.

Aside from using the Nemo extension, you can also inspect the extended attributes from the command-line using the `xattr` package (`sudo apt install xattr`):
```
~/Documents$ xattr -l Documents/novel.docx
user.ntfs_crtime:
0000   DE C1 13 61 78 51 DC 01                            ...axQ..

user.ntfs_crtime_readable: 2025-11-09 21:57:18
```

### Nemo extension
If you haven't installed the extension already, follow the [steps above](#install-the-nemo-extension).

Once installed, you can view any xattrs a file has via file the "Extended Attributes" page in the file properties window (right-click a file and click "Properties").

![Extended Attributes Screenshot](img/extended_attributes.png)

You can also add the "Date Created (NTFS)" column to the file browser column headers:

![Column Headers Screenshot](img/column_headers.png)

Though this will only set it for the current directory. To apply it across all directories, you can go to `Edit->Preferences->List Columns` and add it there.

## Tests
### Unit tests
### E2E
