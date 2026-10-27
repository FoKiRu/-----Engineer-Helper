# ======================= udb_api.py =======================
# Подготовка базы справочников rk7.udb для стенда через API utils.ucs.ru (/v2/api):
# сброс дилера, AddDealerFromRal, код предприятия, отключение проверки лицензии обновления,
# для 7.25+ — деактивация ресторанов. Описание API — «ТЗ: API подготовки базы справочников rk7.udb».
#
# Логин и пароль сайта хранятся зашифрованными (DPAPI, только для текущего пользователя Windows)
# в том же файле, что у скриптов стендов (stend-common.ps1):
# %USERPROFILE%\.stand-RK7-creds\WEB-<host>.pscred — base64(DPAPI("логин|пароль")).

import base64
import ctypes
import ctypes.wintypes
import hashlib
import os
import re
import uuid
from urllib.parse import urlsplit

import requests

DEFAULT_URL = "https://utils.ucs.ru/v2/api"
CRED_DIR = os.path.join(os.path.expanduser("~"), ".stand-RK7-creds")

# Операции в порядке выполнения на сервере (RefsCatalog::all()) и их параметры
OPERATIONS = [
    ("resetdealer", "Сброс кода дилера"),
    ("enableadddealerfromral", "Включить AddDealerFromRal"),
    ("setenterprisecode", "Сменить код предприятия"),
    ("disablelicensecheck", "Отключить проверку лицензии обновления"),
    ("disablerestaurants", "Деактивировать все рестораны"),
]
OPERATION_TITLES = dict(OPERATIONS)

# Значения параметров по умолчанию — для стендов (как в stend-common.ps1)
DEFAULT_PARAMS = {
    "newdealercode": "508",       # код дилера сотрудника при сбросе дилера
    "newenterprisecode": "19999",
    "restcode": "79",             # код ресторана (для 7.25 и новее)
    "newrefsdataversion": "",     # пусто — определяет сервер
}

VERSION_RE = re.compile(r'^7\.\d+\.\d+\.\d+$')

class ApiError(Exception):
    """Ошибка запроса к API: status — HTTP-код, code — машинный код ошибки из ответа."""
    def __init__(self, message, status=None, code=None):
        super().__init__(message)
        self.status = status
        self.code = code

# ======================= Версия R-Keeper =======================

def rk_version_from_ini_path(ini_path):
    """Версия R-Keeper по пути bin/win: .../INST7.26.04.2002/bin/win -> 7.26.04.2002 (или '')."""
    if not ini_path:
        return ""
    name = os.path.basename(os.path.dirname(os.path.dirname(os.path.normpath(ini_path))))
    m = re.match(r'^INST(7\.\d+\.\d+\.\d+)', name, re.IGNORECASE)
    return m.group(1) if m else ""

def default_operations(version):
    """Операции подготовки для версии: лицензия обновления — только у 7.7.0 и 7.25+,
    деактивация ресторанов — у 7.25+ (как Get-StandUdbOperations)."""
    ops = ["resetdealer", "enableadddealerfromral", "setenterprisecode"]
    if not VERSION_RE.match(version or ""):
        return ops
    parts = [int(p) for p in version.split(".")]
    is770 = parts[1] == 7 and parts[2] == 0
    is725 = parts[1] >= 25
    if is770 or is725:
        ops.append("disablelicensecheck")
    if is725:
        ops.append("disablerestaurants")
    return ops

# ======================= Логин и пароль (DPAPI) =======================

class _DataBlob(ctypes.Structure):
    _fields_ = [("cbData", ctypes.wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

def _blob(data):
    buf = ctypes.create_string_buffer(data, len(data))
    return _DataBlob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char))), buf

def _dpapi(data, protect):
    blob_in, _buf = _blob(data)
    blob_out = _DataBlob()
    crypt32 = ctypes.windll.crypt32
    func = crypt32.CryptProtectData if protect else crypt32.CryptUnprotectData
    # Без доп. энтропии и с областью CurrentUser — как ProtectedData в PowerShell
    if not func(ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)):
        raise OSError(ctypes.FormatError())
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)

def _cred_file(host):
    return os.path.join(CRED_DIR, "WEB-" + re.sub(r'[^A-Za-z0-9.\-]', '_', host) + ".pscred")

def api_host(url):
    return urlsplit(url).hostname or ""

def load_credential(host):
    """(логин, пароль) из общего хранилища или None."""
    path = _cred_file(host)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="ascii") as f:
            clear = _dpapi(base64.b64decode(f.read().strip()), protect=False).decode("utf-8")
        login, _, password = clear.partition("|")
        return (login, password) if login else None
    except Exception as e:
        print(f"[UDB] Не удалось прочитать сохранённый пароль {host}: {e}")
        return None

def save_credential(host, login, password):
    os.makedirs(CRED_DIR, exist_ok=True)
    data = _dpapi(f"{login}|{password}".encode("utf-8"), protect=True)
    with open(_cred_file(host), "w", encoding="ascii") as f:
        f.write(base64.b64encode(data).decode("ascii"))

def remove_credential(host):
    path = _cred_file(host)
    if os.path.isfile(path):
        os.remove(path)

# ======================= Запросы к API =======================

class _MultipartStream:
    """Тело multipart/form-data, которое читается по частям: файл не загружается в память
    целиком, а progress(отправлено, всего) показывает ход загрузки."""
    CHUNK = 1024 * 1024

    def __init__(self, fields, file_field, file_path, progress=None):
        self.boundary = uuid.uuid4().hex
        self.file_path = file_path
        self.progress = progress
        head = b""
        for name, values in fields.items():
            for value in (values if isinstance(values, (list, tuple)) else [values]):
                head += (f'--{self.boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n'
                         f'{value}\r\n').encode("utf-8")
        file_name = os.path.basename(file_path)
        head += (f'--{self.boundary}\r\nContent-Disposition: form-data; name="{file_field}"; '
                 f'filename="{file_name}"\r\nContent-Type: application/octet-stream\r\n\r\n').encode("utf-8")
        self.head = head
        self.tail = f'\r\n--{self.boundary}--\r\n'.encode("ascii")
        self.length = len(head) + os.path.getsize(file_path) + len(self.tail)

    def __len__(self):
        # По длине requests ставит Content-Length вместо Transfer-Encoding: chunked
        return self.length

    @property
    def content_type(self):
        return f"multipart/form-data; boundary={self.boundary}"

    def __iter__(self):
        sent = len(self.head)
        yield self.head
        with open(self.file_path, "rb") as f:
            while True:
                chunk = f.read(self.CHUNK)
                if not chunk:
                    break
                sent += len(chunk)
                if self.progress:
                    self.progress(sent, self.length)
                yield chunk
        yield self.tail

def _get(obj, *names):
    """Значение по одному из имён без учёта регистра (PowerShell-клиент читает JSON так же)."""
    if isinstance(obj, dict):
        lower = {str(k).lower(): v for k, v in obj.items()}
        for name in names:
            if lower.get(name.lower()) not in (None, ""):
                return lower[name.lower()]
    return None

def _find_strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for value in obj.values():
            yield from _find_strings(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from _find_strings(value)

def result_file(result):
    """(id папки загрузки, путь для скачивания) из ответа /refs/process.
    По ТЗ это поля id и download; если их нет — берутся из ссылки /api/files/{id}/{имя}
    или пути /uploaded/.../{id}/{имя} в любом поле ответа. Не найдено — (None, None)."""
    file_id = _get(result, "id")
    download = _get(result, "download")
    if not download:
        download = next((s for s in _find_strings(result) if re.search(r'/api/files/[^/]+/[^/]+$', s)), None)
    if not download:
        uploaded = _get(result, "file") or next(
            (s for s in _find_strings(result) if s.startswith("/uploaded/")), None)
        if isinstance(uploaded, str) and uploaded.count("/") >= 3:
            folder, name = uploaded.rstrip("/").split("/")[-2:]
            download = f"/v2/api/files/{folder}/{name}"
    if download and not file_id:
        m = re.search(r'/files/([^/]+)/[^/]+$', download)
        file_id = m.group(1) if m else None
    return file_id, download

class UtilsApi:
    """Клиент API utils.ucs.ru: Basic Auth и обязательный заголовок X-UCS-Api: 1."""

    def __init__(self, base_url, login, password, timeout=900):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.auth = (login, password)
        self.session.headers.update({"X-UCS-Api": "1", "Accept-Language": "ru"})
        self.timeout = timeout

    def _url(self, path):
        # Путь от корня сайта (/v2/api/files/...) или относительно адреса API (/refs/process)
        if path.startswith("/v2/"):
            parts = urlsplit(self.base_url)
            return f"{parts.scheme}://{parts.netloc}{path}"
        return self.base_url + path

    def _check(self, response):
        if response.status_code == 401:
            raise ApiError("Неверный логин или пароль", 401)
        if response.ok:
            return
        message = f"HTTP {response.status_code}"
        code = None
        try:
            error = response.json().get("error") or {}
            code = error.get("code")
            message = f"{code}: {error.get('message')}"
            if error.get("fields"):
                message += " [" + ", ".join(error["fields"]) + "]"
        except ValueError:
            pass
        raise ApiError(message, response.status_code, code)

    def operations(self):
        """Операции и параметры, доступные пользователю (GET /refs/operations)."""
        response = self.session.get(self._url("/refs/operations"), timeout=60)
        self._check(response)
        return response.json()

    def process(self, udb_path, ops, params, progress=None):
        """Загрузка rk7.udb и выполнение операций (POST /refs/process). Возвращает ответ сервера."""
        fields = {"ops[]": list(ops)}
        fields.update(params)
        body = _MultipartStream(fields, "dbfile", udb_path, progress)
        response = self.session.post(self._url("/refs/process"), data=body, timeout=self.timeout,
                                     headers={"Content-Type": body.content_type})
        self._check(response)
        return response.json()

    def download(self, path, out_file, progress=None):
        """Скачивает файл (GET /files/{id}/{name}) и проверяет SHA-256 из X-Content-SHA256."""
        with self.session.get(self._url(path), stream=True, timeout=self.timeout) as response:
            self._check(response)
            total = int(response.headers.get("Content-Length") or 0)
            expected = (response.headers.get("X-Content-SHA256") or "").lower()
            sha = hashlib.sha256()
            done = 0
            with open(out_file, "wb") as f:
                for chunk in response.iter_content(1024 * 1024):
                    f.write(chunk)
                    sha.update(chunk)
                    done += len(chunk)
                    if progress:
                        progress(done, total)
        if expected and sha.hexdigest() != expected:
            os.remove(out_file)
            raise ApiError("Скачанный rk7.udb повреждён (SHA-256 не совпадает)")

    def delete(self, file_id):
        """Удаляет папку загрузки на сервере (DELETE /files/{id})."""
        response = self.session.delete(self._url(f"/files/{file_id}"), timeout=60)
        if response.status_code != 404:
            self._check(response)
