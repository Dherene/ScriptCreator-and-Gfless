import json
import os
import uuid
import pickle
from datetime import datetime, timedelta
from urllib.request import Request, urlopen
from email.utils import parsedate_to_datetime

import sys
from PyQt5.QtWidgets import QMessageBox, QInputDialog

try:
    # this file can be generated during compilation to embed build details
    from build_info import BUILD_EXPIRATION, BUILD_LICENSE_KEY
except Exception:
    BUILD_EXPIRATION = "2099-01-01"
    BUILD_LICENSE_KEY = ""

BUILD_EXPIRATION_TS = datetime.fromisoformat(BUILD_EXPIRATION).timestamp()

# store licenses alongside the executable
LICENSE_FILE = os.path.join(os.path.dirname(sys.argv[0]), 'licenses.json')
# store sensitive license data in a separate binary file
DETAILS_FILE = os.path.join(os.path.dirname(sys.argv[0]), 'license_details.dat')


def internet_time():
    """Return current datetime from Google or ``None`` if unreachable."""
    try:
        req = Request('https://www.google.com', method='HEAD')
        with urlopen(req, timeout=5) as resp:
            date_hdr = resp.headers.get('Date')
        return parsedate_to_datetime(date_hdr)
    except Exception:
        return None


def load_licenses():
    """Return list of license keys stored in ``licenses.json``."""
    if os.path.exists(LICENSE_FILE):
        with open(LICENSE_FILE, 'r') as f:
            try:
                return json.load(f)
            except Exception:
                return []
    return []


def save_licenses(keys):
    with open(LICENSE_FILE, 'w') as f:
        json.dump(keys, f, indent=4)


def load_details():
    """Load binary license information."""
    if os.path.exists(DETAILS_FILE):
        try:
            with open(DETAILS_FILE, 'rb') as f:
                return pickle.load(f)
        except Exception:
            return {}
    return {}


def save_details(data):
    with open(DETAILS_FILE, 'wb') as f:
        pickle.dump(data, f)


def generate_license(days, key=None, *, reset=False):
    """Create a new license valid for ``days`` days and return its key.

    If ``key`` is provided, it will be used instead of generating a random one.
    When ``reset`` is ``True`` all previously stored licenses are removed and
    only the newly generated license is kept. This is useful when creating a
    distributable build that should ship with a single license.
    """
    key = key or uuid.uuid4().hex[:16]
    expires = (datetime.now() + timedelta(days=days)).timestamp()

    if reset:
        keys = [key]
        details = {key: {"expires": expires, "hwid": None, "blocked": False}}
    else:
        keys = load_licenses()
        details = load_details()
        if key not in keys:
            keys.append(key)
        details[key] = {"expires": expires, "hwid": None, "blocked": False}

    save_licenses(keys)
    save_details(details)
    return key


def find_license_for_hwid(hwid: str):
    """Return the license key bound to ``hwid`` or ``None``."""
    details = load_details()
    for k, info in details.items():
        if info.get("hwid") == hwid:
            return k
    return None


def extend_license(key, days):
    """Set a new expiration ``days`` from now for ``key``."""
    details = load_details()
    if key in details:
        details[key]["expires"] = (datetime.now() + timedelta(days=days)).timestamp()
        save_details(details)


def verify_license(key):
    """Verify ``key`` and return ``(ok, message)``."""
    now = internet_time()
    if now is None:
        return False, "Internet connection required"
    if now.timestamp() > BUILD_EXPIRATION_TS:
        return False, "Application expired"

    keys = load_licenses()
    details = load_details()
    if key not in keys or key not in details:
        return False, "Invalid license"
    lic = details[key]
    if lic.get("blocked"):
        return False, "License blocked due to HWID change"
    if lic["expires"] < now.timestamp():
        return False, "License expired"

    hwid = str(uuid.getnode())
    message = ""
    if lic["hwid"] is None:
        lic["hwid"] = hwid
        save_details(details)
        message = "This executable is now linked to this computer."
    elif lic["hwid"] != hwid:
        lic["blocked"] = True
        save_details(details)
        return False, "License blocked due to HWID change"

    time_left = timedelta(seconds=int(lic["expires"] - now.timestamp()))
    remaining = f"{time_left.days}d {time_left.seconds//3600}h {(time_left.seconds%3600)//60}m"
    if message:
        message += "\n"
    message += f"Time remaining: {remaining}"
    return True, message


def prompt_for_license():
    """Ask for a license key if needed and display remaining time."""
    hwid = str(uuid.getnode())
    key = find_license_for_hwid(hwid)

    if key is None:
        key, ok = QInputDialog.getText(None, 'License', 'Enter license key:')
        if not ok:
            return False

    ok, msg = verify_license(key)
    if not ok:
        QMessageBox.warning(None, 'AVISO', msg)
        return False

    QMessageBox.information(None, 'License', msg)
    return True