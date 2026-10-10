"""Ajustes específicos da bandeja do Windows 11.

O Windows 11 guarda, por ícone, se ele fica visível na barra ou escondido no
menu "^" em ``HKCU\\Control Panel\\NotifyIconSettings\\<id>`` (valor
``IsPromoted``). A entrada é criada pelo Explorer quando o ícone aparece pela
primeira vez; aqui marcamos ``IsPromoted = 1`` nas entradas deste app.
"""

from __future__ import annotations

import os
import sys

TOOLTIP_PREFIX = "Claude Code"
_KEY = r"Control Panel\NotifyIconSettings"


def _our_executables() -> set[str]:
    exes = {sys.executable, getattr(sys, "_base_executable", sys.executable)}
    result = set()
    for exe in exes:
        if exe:
            result.add(os.path.normcase(os.path.abspath(exe)))
            # pythonw/python do mesmo interpretador
            folder, name = os.path.split(exe)
            for alt in ("python.exe", "pythonw.exe"):
                result.add(os.path.normcase(os.path.join(folder, alt)))
    return result


def promote_tray_icon() -> int:
    """Torna o ícone sempre visível na barra. Retorna quantas entradas mudou."""
    if sys.platform != "win32":
        return 0
    try:
        import winreg
    except ImportError:
        return 0

    exes = _our_executables()
    changed = 0
    try:
        root = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _KEY)
    except OSError:
        return 0  # Windows 10 ou versão sem esse recurso
    with root:
        index = 0
        while True:
            try:
                sub_name = winreg.EnumKey(root, index)
            except OSError:
                break
            index += 1
            try:
                with winreg.OpenKey(root, sub_name, 0, winreg.KEY_READ | winreg.KEY_SET_VALUE) as sub:
                    def value(name):
                        try:
                            return winreg.QueryValueEx(sub, name)[0]
                        except OSError:
                            return None

                    exe = value("ExecutablePath")
                    tip = value("InitialTooltip") or ""
                    if not exe or os.path.normcase(os.path.abspath(exe)) not in exes:
                        continue
                    if not str(tip).startswith(TOOLTIP_PREFIX):
                        continue
                    if value("IsPromoted") != 1:
                        winreg.SetValueEx(sub, "IsPromoted", 0, winreg.REG_DWORD, 1)
                        changed += 1
            except OSError:
                continue
    return changed
