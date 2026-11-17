import os
import re

UDB_FILENAME = "rk7.udb"
SQLITE_FILENAME = "rk7.SQLite"
SQLITE_MIN_VERSION = (7, 26, 11, 2001)
REFERENCE_DB_FILENAMES = (SQLITE_FILENAME, UDB_FILENAME)


def supports_sqlite(version):
    match = re.fullmatch(r"7\.(\d+)\.(\d+)\.(\d+)", version or "")
    if not match:
        return False
    return (7, *(int(part) for part in match.groups())) >= SQLITE_MIN_VERSION


def is_reference_db_name(name):
    return name.lower() in (filename.lower() for filename in REFERENCE_DB_FILENAMES)


def reference_db_name(base_path, rk_version="", default=UDB_FILENAME):
    filenames = REFERENCE_DB_FILENAMES
    if rk_version and not supports_sqlite(rk_version):
        filenames = tuple(reversed(filenames))
    for filename in filenames:
        if os.path.isfile(os.path.join(base_path, filename)):
            return filename
    if supports_sqlite(rk_version):
        return SQLITE_FILENAME
    return default if is_reference_db_name(default) else UDB_FILENAME


def reference_db_path(base_path, rk_version="", default=UDB_FILENAME):
    filename = reference_db_name(base_path, rk_version, default)
    return os.path.normpath(os.path.join(base_path, filename))
