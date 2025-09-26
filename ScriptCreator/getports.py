import re

import pywinctl as pwc

_PORT_TITLE_MARKER = "] - Phoenix Bot:"


def _extract_window_details(title):
    """Return the character name, ports and login state for a window title."""

    if _PORT_TITLE_MARKER not in title:
        return None

    prefix, _, port_section = title.partition(_PORT_TITLE_MARKER)
    if not port_section:
        return None

    is_login_screen = False
    prefix_lower = prefix.lower()
    if "lv.0" in prefix_lower or "lv 0" in prefix_lower:
        is_login_screen = True

    # ``prefix`` looks like ``"[Lv 99(+90) Character Name"``.
    # ``maxsplit=2`` keeps the remainder (the actual name) intact even if it
    # contains spaces.
    name_parts = prefix.split(" ", 2)
    if len(name_parts) == 3:
        name = name_parts[2]
    else:
        name = name_parts[-1]

    name = name.lstrip("[").strip()
    if not name:
        name = None

    ports = re.findall(r"\d+", port_section)
    if not ports:
        return None

    old_api_port = ports[0]
    new_api_port = ports[1] if len(ports) > 1 else None
    return name, old_api_port, new_api_port, is_login_screen

def getNames():
    titles = pwc.getAllTitles()
    return titles

### Returns all of the current ports with names of the characters associated with it.
# Each item contains [character_name, old_api_port, pid] by default.  When
# ``include_new_api`` is True, the new API port and a boolean indicating
# whether the client is at the login screen are appended, producing entries of
# the form ``[name, old_port, pid, new_port, is_login_screen]``.
def returnAllPorts(include_new_api=False):
    """Return Phoenix Bot characters with their legacy API ports.

    The default payload matches the pre-dual-port structure::

        [[character_name, old_api_port, pid], ...]

    Pass ``include_new_api=True`` to append the optional new API port to each
    entry. When requested, the list shape becomes ``[name, old_port, pid,␊
    new_port, is_login_screen]`` so legacy callers remain unaffected while newer
    tools can opt in to the extra data.
    """

    ports = []
    for title in getNames():
        details = _extract_window_details(title)
        if not details:
            continue

        name, old_api_port, new_api_port, is_login_screen = details
        if not old_api_port:
            continue

        pid = pwc.getWindowsWithTitle(title)[0].getPID()
        entry = [name, old_api_port, pid]
        if include_new_api:
            entry.append(new_api_port)
            entry.append(is_login_screen)
        ports.append(entry)

    return ports

### returns only 1 port
def returnCorrectPort(playerName, api_version="old"):
    version = (api_version or "old").lower()
    include_new_api = version == "new"
    allPorts = returnAllPorts(include_new_api=include_new_api)
    for entry in allPorts:
        name, old_api_port, _pid, *maybe_new_port = entry
        if playerName != name:
            continue

        if version == "new":
            new_api_port = maybe_new_port[0] if maybe_new_port else None
            if new_api_port:
                return int(new_api_port)

        if old_api_port:
            return int(old_api_port)

def returnCorrectPID(playerName):
    allPorts = returnAllPorts()
    for entry in allPorts:
        if playerName == entry[0]:
            return int(entry[2])