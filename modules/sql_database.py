import os
import subprocess


class SqlDatabaseError(Exception):
    pass


_CREATE_DATABASE_SCRIPT = r"""
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$ErrorActionPreference = 'Stop'
try {
    $builder = New-Object System.Data.SqlClient.SqlConnectionStringBuilder
    $builder['Data Source'] = $env:ENGIHELP_SQL_SERVER
    $builder['Initial Catalog'] = 'master'
    $builder['Connect Timeout'] = 15
    $builder['Application Name'] = 'EngiHelp'
    if ($env:ENGIHELP_SQL_WINDOWS_AUTH -eq '1') {
        $builder['Integrated Security'] = $true
    } else {
        $builder['Integrated Security'] = $false
        $builder['User ID'] = $env:ENGIHELP_SQL_USER
        $builder['Password'] = $env:ENGIHELP_SQL_PASSWORD
    }

    $connection = New-Object System.Data.SqlClient.SqlConnection($builder.ConnectionString)
    try {
        $connection.Open()

        $checkCommand = $connection.CreateCommand()
        $checkCommand.CommandText = 'SELECT DB_ID(@DatabaseName)'
        $checkCommand.Parameters.AddWithValue('@DatabaseName', $env:ENGIHELP_SQL_DATABASE) | Out-Null
        $existingId = $checkCommand.ExecuteScalar()
        if ($null -ne $existingId -and $existingId -isnot [DBNull]) {
            throw ('База данных уже существует: ' + $env:ENGIHELP_SQL_DATABASE)
        }

        $createCommand = $connection.CreateCommand()
        $createCommand.CommandTimeout = 30
        $createCommand.CommandText = @'
DECLARE @QuotedName nvarchar(258) = QUOTENAME(@DatabaseName);
DECLARE @Sql nvarchar(max) = N'CREATE DATABASE ' + @QuotedName + N';';
EXEC sys.sp_executesql @Sql;
'@
        $createCommand.Parameters.AddWithValue('@DatabaseName', $env:ENGIHELP_SQL_DATABASE) | Out-Null
        $createCommand.ExecuteNonQuery() | Out-Null
    } finally {
        if ($connection.State -ne [System.Data.ConnectionState]::Closed) {
            $connection.Close()
        }
        $connection.Dispose()
    }
} catch {
    [Console]::Error.WriteLine($_.Exception.Message)
    exit 1
}
"""


_DATABASE_EXISTS_SCRIPT = r"""
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$ErrorActionPreference = 'Stop'
try {
    $builder = New-Object System.Data.SqlClient.SqlConnectionStringBuilder
    $builder['Data Source'] = $env:ENGIHELP_SQL_SERVER
    $builder['Initial Catalog'] = 'master'
    $builder['Connect Timeout'] = 15
    $builder['Application Name'] = 'EngiHelp'
    if ($env:ENGIHELP_SQL_WINDOWS_AUTH -eq '1') {
        $builder['Integrated Security'] = $true
    } else {
        $builder['Integrated Security'] = $false
        $builder['User ID'] = $env:ENGIHELP_SQL_USER
        $builder['Password'] = $env:ENGIHELP_SQL_PASSWORD
    }

    $connection = New-Object System.Data.SqlClient.SqlConnection($builder.ConnectionString)
    try {
        $connection.Open()
        $checkCommand = $connection.CreateCommand()
        $checkCommand.CommandText = 'SELECT DB_ID(@DatabaseName)'
        $checkCommand.Parameters.AddWithValue('@DatabaseName', $env:ENGIHELP_SQL_DATABASE) | Out-Null
        $existingId = $checkCommand.ExecuteScalar()
        if ($null -ne $existingId -and $existingId -isnot [DBNull]) {
            [Console]::WriteLine('1')
        } else {
            [Console]::WriteLine('0')
        }
    } finally {
        if ($connection.State -ne [System.Data.ConnectionState]::Closed) {
            $connection.Close()
        }
        $connection.Dispose()
    }
} catch {
    [Console]::Error.WriteLine($_.Exception.Message)
    exit 1
}
"""


def create_database(server, database, windows_auth=True, username="", password=""):
    server = server.strip()
    database = database.strip()
    username = username.strip()
    if not server:
        raise SqlDatabaseError("Укажите адрес SQL Server.")
    if not database:
        raise SqlDatabaseError("Укажите имя базы данных.")
    if len(database) > 128:
        raise SqlDatabaseError("Имя базы данных не должно превышать 128 символов.")
    if "\x00" in database:
        raise SqlDatabaseError("Имя базы данных содержит недопустимый символ.")
    if not windows_auth and not username:
        raise SqlDatabaseError("Укажите имя пользователя SQL Server.")

    env = os.environ.copy()
    env["ENGIHELP_SQL_SERVER"] = server
    env["ENGIHELP_SQL_DATABASE"] = database
    env["ENGIHELP_SQL_WINDOWS_AUTH"] = "1" if windows_auth else "0"
    env["ENGIHELP_SQL_USER"] = "" if windows_auth else username
    env["ENGIHELP_SQL_PASSWORD"] = "" if windows_auth else password

    try:
        result = subprocess.run(
            [
                "powershell.exe", "-NoProfile", "-NonInteractive",
                "-ExecutionPolicy", "Bypass", "-Command", _CREATE_DATABASE_SCRIPT,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            timeout=50,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except FileNotFoundError as e:
        raise SqlDatabaseError("Не найден PowerShell, необходимый для подключения к SQL Server.") from e
    except subprocess.TimeoutExpired as e:
        raise SqlDatabaseError("Превышено время ожидания ответа SQL Server.") from e

    if result.returncode != 0:
        details = (result.stderr or result.stdout).strip()
        raise SqlDatabaseError(details or "SQL Server не смог создать базу данных.")
    return database


def database_exists(server, database, windows_auth=True, username="", password=""):
    server = server.strip()
    database = database.strip()
    username = username.strip()
    if not server:
        raise SqlDatabaseError("Укажите адрес SQL Server.")
    if not database:
        raise SqlDatabaseError("Укажите имя базы данных.")
    if len(database) > 128:
        raise SqlDatabaseError("Имя базы данных не должно превышать 128 символов.")
    if "\x00" in database:
        raise SqlDatabaseError("Имя базы данных содержит недопустимый символ.")
    if not windows_auth and not username:
        raise SqlDatabaseError("Укажите имя пользователя SQL Server.")

    env = os.environ.copy()
    env["ENGIHELP_SQL_SERVER"] = server
    env["ENGIHELP_SQL_DATABASE"] = database
    env["ENGIHELP_SQL_WINDOWS_AUTH"] = "1" if windows_auth else "0"
    env["ENGIHELP_SQL_USER"] = "" if windows_auth else username
    env["ENGIHELP_SQL_PASSWORD"] = "" if windows_auth else password

    try:
        result = subprocess.run(
            [
                "powershell.exe", "-NoProfile", "-NonInteractive",
                "-ExecutionPolicy", "Bypass", "-Command", _DATABASE_EXISTS_SCRIPT,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            timeout=50,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except FileNotFoundError as e:
        raise SqlDatabaseError("Не найден PowerShell, необходимый для подключения к SQL Server.") from e
    except subprocess.TimeoutExpired as e:
        raise SqlDatabaseError("Превышено время ожидания ответа SQL Server.") from e

    if result.returncode != 0:
        details = (result.stderr or result.stdout).strip()
        raise SqlDatabaseError(details or "SQL Server не смог проверить базу данных.")
    answer = result.stdout.strip()
    if answer not in ("0", "1"):
        raise SqlDatabaseError("SQL Server вернул неожиданный ответ при проверке базы данных.")
    return answer == "1"
