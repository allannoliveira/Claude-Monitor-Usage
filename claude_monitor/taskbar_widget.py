"""Widget com barrinhas desenhado DENTRO da barra de tarefas do Windows.

Mesma técnica do projeto de referência: uma janela "layered" (alpha por pixel,
via ``UpdateLayeredWindow``) que vira filha de ``Shell_TrayWnd`` e fica logo à
esquerda da área de notificação (``TrayNotifyWnd``). Por ser filha da barra,
ela some junto com a barra (tela cheia, auto-ocultar) e não briga por z-order.

Tudo em ``ctypes`` (sem pywin32). A janela tem sua própria thread com loop de
mensagens; outras threads só chamam ``update()``/``set_style()``/``close()``,
que apenas postam mensagens para ela.

Interação: clique esquerdo alterna o estilo; clique direito abre um menu.
"""

from __future__ import annotations

import ctypes
import sys
import threading
from ctypes import wintypes as w
from typing import Callable

from PIL import Image

from .widget_render import STYLES, Row, next_style, render, system_uses_light_theme

if sys.platform != "win32":  # pragma: no cover - módulo exclusivo do Windows
    raise ImportError("taskbar_widget só funciona no Windows")

user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

LRESULT = ctypes.c_ssize_t
LONG_PTR = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, w.HWND, w.UINT, w.WPARAM, w.LPARAM)

# ---------------------------------------------------------------- constantes
WS_POPUP = 0x80000000
WS_CHILD = 0x40000000
WS_CLIPSIBLINGS = 0x04000000
WS_EX_TOPMOST = 0x00000008
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_LAYERED = 0x00080000
WS_EX_NOACTIVATE = 0x08000000
GWL_STYLE = -16
GWL_EXSTYLE = -20
SWP_NOSIZE, SWP_NOMOVE, SWP_NOZORDER, SWP_NOACTIVATE = 0x1, 0x2, 0x4, 0x10
SWP_FRAMECHANGED, SWP_SHOWWINDOW = 0x20, 0x40
HWND_TOP = 0
SW_SHOWNOACTIVATE = 4
ULW_ALPHA = 2
AC_SRC_OVER, AC_SRC_ALPHA = 0, 1
WM_DESTROY, WM_CLOSE, WM_TIMER, WM_NULL = 0x0002, 0x0010, 0x0113, 0x0000
WM_MOUSEACTIVATE, MA_NOACTIVATE = 0x0021, 3
WM_LBUTTONUP, WM_RBUTTONUP = 0x0202, 0x0205
WM_APP = 0x8000
WM_APP_REDRAW = WM_APP + 1
MF_STRING, MF_SEPARATOR, MF_CHECKED = 0x0, 0x800, 0x8
TPM_RIGHTBUTTON, TPM_BOTTOMALIGN, TPM_RETURNCMD = 0x2, 0x20, 0x100
IDC_ARROW = 32512
TIMER_ID = 1
TIMER_MS = 1000
CLASS_NAME = "ClaudeMonitorTaskbarWidget"

CMD_STYLE_BASE, CMD_REFRESH, CMD_HIDE, CMD_QUIT = 100, 10, 11, 12


# ---------------------------------------------------------------- estruturas
class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [("cbSize", w.UINT), ("style", w.UINT), ("lpfnWndProc", WNDPROC),
                ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int),
                ("hInstance", w.HINSTANCE), ("hIcon", w.HICON), ("hCursor", w.HANDLE),
                ("hbrBackground", w.HBRUSH), ("lpszMenuName", w.LPCWSTR),
                ("lpszClassName", w.LPCWSTR), ("hIconSm", w.HICON)]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", w.DWORD), ("biWidth", w.LONG), ("biHeight", w.LONG),
                ("biPlanes", w.WORD), ("biBitCount", w.WORD), ("biCompression", w.DWORD),
                ("biSizeImage", w.DWORD), ("biXPelsPerMeter", w.LONG),
                ("biYPelsPerMeter", w.LONG), ("biClrUsed", w.DWORD), ("biClrImportant", w.DWORD)]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", w.DWORD * 1)]


class BLENDFUNCTION(ctypes.Structure):
    _fields_ = [("BlendOp", ctypes.c_ubyte), ("BlendFlags", ctypes.c_ubyte),
                ("SourceConstantAlpha", ctypes.c_ubyte), ("AlphaFormat", ctypes.c_ubyte)]


# ---------------------------------------------------------------- assinaturas
def _sig(func, restype, *argtypes):
    func.restype = restype
    func.argtypes = argtypes
    return func


_sig(user32.DefWindowProcW, LRESULT, w.HWND, w.UINT, w.WPARAM, w.LPARAM)
_sig(user32.RegisterClassExW, w.ATOM, ctypes.POINTER(WNDCLASSEXW))
_sig(user32.CreateWindowExW, w.HWND, w.DWORD, w.LPCWSTR, w.LPCWSTR, w.DWORD, ctypes.c_int,
     ctypes.c_int, ctypes.c_int, ctypes.c_int, w.HWND, w.HMENU, w.HINSTANCE, w.LPVOID)
_sig(user32.DestroyWindow, w.BOOL, w.HWND)
_sig(user32.ShowWindow, w.BOOL, w.HWND, ctypes.c_int)
_sig(user32.FindWindowW, w.HWND, w.LPCWSTR, w.LPCWSTR)
_sig(user32.FindWindowExW, w.HWND, w.HWND, w.HWND, w.LPCWSTR, w.LPCWSTR)
_sig(user32.GetWindowRect, w.BOOL, w.HWND, ctypes.POINTER(w.RECT))
_sig(user32.IsWindow, w.BOOL, w.HWND)
_sig(user32.GetParent, w.HWND, w.HWND)
_sig(user32.SetParent, w.HWND, w.HWND, w.HWND)
_sig(user32.GetWindowLongPtrW, LONG_PTR, w.HWND, ctypes.c_int)
_sig(user32.SetWindowLongPtrW, LONG_PTR, w.HWND, ctypes.c_int, LONG_PTR)
_sig(user32.SetWindowPos, w.BOOL, w.HWND, w.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int,
     ctypes.c_int, w.UINT)
_sig(user32.MapWindowPoints, ctypes.c_int, w.HWND, w.HWND, ctypes.POINTER(w.POINT), w.UINT)
_sig(user32.UpdateLayeredWindow, w.BOOL, w.HWND, w.HDC, ctypes.POINTER(w.POINT),
     ctypes.POINTER(w.SIZE), w.HDC, ctypes.POINTER(w.POINT), w.COLORREF,
     ctypes.POINTER(BLENDFUNCTION), w.DWORD)
_sig(user32.GetDC, w.HDC, w.HWND)
_sig(user32.ReleaseDC, ctypes.c_int, w.HWND, w.HDC)
_sig(user32.PostMessageW, w.BOOL, w.HWND, w.UINT, w.WPARAM, w.LPARAM)
_sig(user32.GetMessageW, w.BOOL, ctypes.POINTER(w.MSG), w.HWND, w.UINT, w.UINT)
_sig(user32.TranslateMessage, w.BOOL, ctypes.POINTER(w.MSG))
_sig(user32.DispatchMessageW, LRESULT, ctypes.POINTER(w.MSG))
_sig(user32.PostQuitMessage, None, ctypes.c_int)
_sig(user32.SetTimer, ctypes.c_size_t, w.HWND, ctypes.c_size_t, w.UINT, w.LPVOID)
_sig(user32.KillTimer, w.BOOL, w.HWND, ctypes.c_size_t)
_sig(user32.CreatePopupMenu, w.HMENU)
_sig(user32.AppendMenuW, w.BOOL, w.HMENU, w.UINT, ctypes.c_size_t, w.LPCWSTR)
_sig(user32.TrackPopupMenu, w.BOOL, w.HMENU, w.UINT, ctypes.c_int, ctypes.c_int, ctypes.c_int,
     w.HWND, w.LPVOID)
_sig(user32.DestroyMenu, w.BOOL, w.HMENU)
_sig(user32.GetCursorPos, w.BOOL, ctypes.POINTER(w.POINT))
_sig(user32.SetForegroundWindow, w.BOOL, w.HWND)
_sig(user32.LoadCursorW, w.HANDLE, w.HINSTANCE, w.LPVOID)
_sig(gdi32.CreateCompatibleDC, w.HDC, w.HDC)
_sig(gdi32.DeleteDC, w.BOOL, w.HDC)
_sig(gdi32.CreateDIBSection, w.HBITMAP, w.HDC, ctypes.POINTER(BITMAPINFO), w.UINT,
     ctypes.POINTER(ctypes.c_void_p), w.HANDLE, w.DWORD)
_sig(gdi32.SelectObject, w.HGDIOBJ, w.HDC, w.HGDIOBJ)
_sig(gdi32.DeleteObject, w.BOOL, w.HGDIOBJ)
_sig(kernel32.GetModuleHandleW, w.HMODULE, w.LPCWSTR)

try:
    _sig(user32.GetDpiForWindow, w.UINT, w.HWND)
    _HAS_DPI = True
except AttributeError:  # Windows < 10 1607
    _HAS_DPI = False


def enable_dpi_awareness() -> None:
    """Coordenadas em pixels físicos (necessário para alinhar com a barra)."""
    try:
        user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))  # PER_MONITOR_AWARE_V2
    except (AttributeError, OSError):
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except (AttributeError, OSError):
            pass


def _rect(hwnd) -> w.RECT | None:
    r = w.RECT()
    return r if hwnd and user32.GetWindowRect(hwnd, ctypes.byref(r)) else None


# ---------------------------------------------------------------- widget
class TaskbarWidget:
    def __init__(self, style: str, on_style: Callable[[str], None], on_refresh: Callable[[], None],
                 on_hide: Callable[[], None], on_quit: Callable[[], None]):
        self.style = style if style in STYLES else "segmentos"
        self._on_style, self._on_refresh = on_style, on_refresh
        self._on_hide, self._on_quit = on_hide, on_quit
        self._rows = [Row("5h", None, None), Row("7d", None, None)]
        self.hwnd = None
        self._menu_owner = None
        self._taskbar = None
        self._embedded = False
        self._size = (0, 0)
        self._ticks = 0
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self._wndproc = WNDPROC(self._proc)  # manter referência viva!

    # ------------------------------------------------ API (qualquer thread)
    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="taskbar-widget", daemon=True)
        self._thread.start()
        self._ready.wait(5)

    def update(self, rows: list[Row]) -> None:
        self._rows = rows
        self._post(WM_APP_REDRAW)

    def set_style(self, style: str) -> None:
        if style in STYLES:
            self.style = style
            self._post(WM_APP_REDRAW)

    def close(self) -> None:
        self._post(WM_CLOSE)
        if self._thread and self._thread is not threading.current_thread():
            self._thread.join(2)

    def _post(self, msg: int) -> None:
        if self.hwnd:
            user32.PostMessageW(self.hwnd, msg, 0, 0)

    # ------------------------------------------------ thread da janela
    def _run(self) -> None:
        hinst = kernel32.GetModuleHandleW(None)
        wc = WNDCLASSEXW()
        wc.cbSize = ctypes.sizeof(WNDCLASSEXW)
        wc.lpfnWndProc = self._wndproc
        wc.hInstance = hinst
        wc.hCursor = user32.LoadCursorW(None, ctypes.c_void_p(IDC_ARROW))
        wc.lpszClassName = CLASS_NAME
        user32.RegisterClassExW(ctypes.byref(wc))  # falha se já existe: tudo bem

        ex = WS_EX_LAYERED | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE | WS_EX_TOPMOST
        self.hwnd = user32.CreateWindowExW(ex, CLASS_NAME, "Claude Monitor Widget", WS_POPUP,
                                           0, 0, 1, 1, None, None, hinst, None)
        # Dono invisível do menu de contexto (precisa ser uma janela top-level).
        self._menu_owner = user32.CreateWindowExW(WS_EX_TOOLWINDOW, CLASS_NAME, "", WS_POPUP,
                                                  0, 0, 0, 0, None, None, hinst, None)
        if not self.hwnd:
            self._ready.set()
            return

        self._attach()
        self._present()
        user32.ShowWindow(self.hwnd, SW_SHOWNOACTIVATE)
        user32.SetTimer(self.hwnd, TIMER_ID, TIMER_MS, None)
        self._ready.set()

        msg = w.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

    def _attach(self) -> None:
        """Torna a janela filha da barra de tarefas (ou mantém como popup)."""
        taskbar = user32.FindWindowW("Shell_TrayWnd", None)
        self._taskbar = taskbar
        self._embedded = False
        if not taskbar:
            return
        hwnd = self.hwnd
        ex = user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
        user32.SetWindowLongPtrW(hwnd, GWL_EXSTYLE,
                                 (ex | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE) & ~WS_EX_TOPMOST)
        style = user32.GetWindowLongPtrW(hwnd, GWL_STYLE)
        user32.SetWindowLongPtrW(hwnd, GWL_STYLE, (style & ~WS_POPUP) | WS_CHILD | WS_CLIPSIBLINGS)
        user32.SetParent(hwnd, taskbar)
        if user32.GetParent(hwnd) == taskbar:
            self._embedded = True
            # Windows 11 pode deixar a superfície reparentada atrás do visual
            # DirectComposition da barra; religar WS_EX_LAYERED resolve.
            ex = user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
            user32.SetWindowLongPtrW(hwnd, GWL_EXSTYLE, ex & ~WS_EX_LAYERED)
            user32.SetWindowLongPtrW(hwnd, GWL_EXSTYLE, ex)
        else:  # não conseguiu embutir: volta a ser popup sempre-no-topo
            user32.SetWindowLongPtrW(hwnd, GWL_STYLE, style)
            user32.SetWindowLongPtrW(hwnd, GWL_EXSTYLE, ex | WS_EX_TOPMOST)
        user32.SetWindowPos(hwnd, HWND_TOP, 0, 0, 0, 0,
                            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_FRAMECHANGED)

    def _geometry(self) -> tuple[w.RECT, w.RECT | None, float] | None:
        tb = _rect(self._taskbar)
        if tb is None:
            return None
        tray = _rect(user32.FindWindowExW(self._taskbar, None, "TrayNotifyWnd", None))
        dpi = user32.GetDpiForWindow(self._taskbar) if _HAS_DPI else 96
        return tb, tray, (dpi or 96) / 96

    def _position(self, width: int, height: int) -> None:
        geo = self._geometry()
        if geo is None:
            return
        tb, tray, scale = geo
        margin = round(4 * scale)
        horizontal = (tb.right - tb.left) >= (tb.bottom - tb.top)
        if horizontal:
            right_edge = tray.left if tray else tb.right
            x = right_edge - width - margin
            y = tb.top + ((tb.bottom - tb.top) - height) // 2
        else:  # barra vertical: acima da área de notificação
            x = tb.left
            y = (tray.top if tray else tb.bottom) - height - margin
        if self._embedded:
            pt = w.POINT(x, y)
            user32.MapWindowPoints(None, self._taskbar, ctypes.byref(pt), 1)
            x, y = pt.x, pt.y
        user32.SetWindowPos(self.hwnd, None, x, y, width, height, SWP_NOZORDER | SWP_NOACTIVATE)

    def _present(self) -> None:
        geo = self._geometry()
        if geo is None:
            return
        tb, _tray, scale = geo
        horizontal = (tb.right - tb.left) >= (tb.bottom - tb.top)
        height = (tb.bottom - tb.top) if horizontal else round(48 * scale)
        img = render(self._rows, self.style, height, scale, system_uses_light_theme())
        width, height = img.size
        self._size = (width, height)
        self._position(width, height)

        # Alpha 0 deixa o clique "atravessar"; 1 mantém a área clicável.
        r, g, b, a = img.split()
        a = a.point(lambda v: max(v, 1))
        premult = img.copy()
        premult.putalpha(a)
        r, g, b, a = premult.convert("RGBa").split()
        data = Image.merge("RGBA", (b, g, r, a)).tobytes()  # ordem BGRA do DIB

        screen = user32.GetDC(None)
        mem = gdi32.CreateCompatibleDC(screen)
        info = BITMAPINFO()
        info.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        info.bmiHeader.biWidth = width
        info.bmiHeader.biHeight = -height  # top-down
        info.bmiHeader.biPlanes = 1
        info.bmiHeader.biBitCount = 32
        bits = ctypes.c_void_p()
        bmp = gdi32.CreateDIBSection(mem, ctypes.byref(info), 0, ctypes.byref(bits), None, 0)
        if bmp and bits:
            ctypes.memmove(bits, data, len(data))
            old = gdi32.SelectObject(mem, bmp)
            blend = BLENDFUNCTION(AC_SRC_OVER, 0, 255, AC_SRC_ALPHA)
            user32.UpdateLayeredWindow(self.hwnd, screen, None, ctypes.byref(w.SIZE(width, height)),
                                       mem, ctypes.byref(w.POINT(0, 0)), 0, ctypes.byref(blend),
                                       ULW_ALPHA)
            gdi32.SelectObject(mem, old)
            gdi32.DeleteObject(bmp)
        gdi32.DeleteDC(mem)
        user32.ReleaseDC(None, screen)

    def _show_menu(self) -> None:
        menu = user32.CreatePopupMenu()
        for i, (key, label) in enumerate(STYLES.items()):
            flags = MF_STRING | (MF_CHECKED if key == self.style else 0)
            user32.AppendMenuW(menu, flags, CMD_STYLE_BASE + i, f"Estilo: {label}")
        user32.AppendMenuW(menu, MF_SEPARATOR, 0, None)
        user32.AppendMenuW(menu, MF_STRING, CMD_REFRESH, "Atualizar")
        user32.AppendMenuW(menu, MF_STRING, CMD_HIDE, "Esconder widget")
        user32.AppendMenuW(menu, MF_STRING, CMD_QUIT, "Sair")
        pt = w.POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        user32.SetForegroundWindow(self._menu_owner)
        cmd = user32.TrackPopupMenu(menu, TPM_RETURNCMD | TPM_RIGHTBUTTON | TPM_BOTTOMALIGN,
                                    pt.x, pt.y, 0, self._menu_owner, None)
        user32.PostMessageW(self._menu_owner, WM_NULL, 0, 0)
        user32.DestroyMenu(menu)

        keys = list(STYLES)
        if CMD_STYLE_BASE <= cmd < CMD_STYLE_BASE + len(keys):
            self._change_style(keys[cmd - CMD_STYLE_BASE])
        elif cmd == CMD_REFRESH:
            threading.Thread(target=self._on_refresh, daemon=True).start()
        elif cmd == CMD_HIDE:
            self._on_hide()
        elif cmd == CMD_QUIT:
            self._on_quit()

    def _change_style(self, style: str) -> None:
        self.style = style
        self._present()
        self._on_style(style)

    def _proc(self, hwnd, msg, wparam, lparam):
        try:
            if hwnd == self.hwnd:
                if msg == WM_TIMER:
                    if not user32.IsWindow(self._taskbar) or (
                        self._embedded and user32.GetParent(hwnd) != self._taskbar
                    ):  # Explorer reiniciou: embutir de novo
                        self._attach()
                        self._present()
                    else:
                        self._ticks += 1
                        if self._ticks % 30 == 0:  # atualiza contagem regressiva
                            self._present()
                        else:
                            self._position(*self._size)
                    return 0
                if msg == WM_APP_REDRAW:
                    self._present()
                    return 0
                if msg == WM_MOUSEACTIVATE:
                    return MA_NOACTIVATE
                if msg == WM_LBUTTONUP:
                    self._change_style(next_style(self.style))
                    return 0
                if msg == WM_RBUTTONUP:
                    self._show_menu()
                    return 0
                if msg == WM_CLOSE:
                    user32.KillTimer(hwnd, TIMER_ID)
                    user32.DestroyWindow(hwnd)
                    if self._menu_owner:
                        user32.DestroyWindow(self._menu_owner)
                    return 0
                if msg == WM_DESTROY:
                    self.hwnd = None
                    user32.PostQuitMessage(0)
                    return 0
        except Exception as exc:  # nunca deixar exceção escapar do WndProc
            print(f"[widget] erro: {exc!r}")
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)
