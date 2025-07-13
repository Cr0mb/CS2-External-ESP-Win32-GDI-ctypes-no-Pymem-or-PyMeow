import ctypes
import struct
import time
import math
import win32gui
import win32con
import win32api
import win32ui
from ctypes import wintypes, windll, byref
 
class Offsets:
    dwEntityList = 27280608
    dwLocalPlayerController = 27602208
    dwViewMatrix = 27710080
    m_hPlayerPawn = 2084
    m_iHealth = 836
    m_iHealthBarRenderMaskIndex = 5136
    m_iTeamNum = 995
    m_pBoneArray = 496
    m_pGameSceneNode = 808
    m_vOldOrigin = 4900
    
PROCESS_ALL_ACCESS = 0x1F0FFF
 
def wnd_proc(hwnd, msg, wparam, lparam):
    if msg == win32con.WM_DESTROY:
        win32gui.PostQuitMessage(0)
    return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)
 
class Vec3(ctypes.Structure):
    _fields_ = [("x", ctypes.c_float), ("y", ctypes.c_float), ("z", ctypes.c_float)]
 
class Overlay:
    def __init__(self):
        self.width = win32api.GetSystemMetrics(0)
        self.height = win32api.GetSystemMetrics(1)
        self.fps = 144
 
    def init(self, title="GHax", fps=144):
        self.fps = fps
        wc = win32gui.WNDCLASS()
        wc.lpfnWndProc = wnd_proc
        wc.lpszClassName = title
        wc.hInstance = win32api.GetModuleHandle(None)
        class_atom = win32gui.RegisterClass(wc)
 
        ex_style = win32con.WS_EX_LAYERED | win32con.WS_EX_TRANSPARENT | win32con.WS_EX_TOPMOST | win32con.WS_EX_TOOLWINDOW
 
        self.hwnd = win32gui.CreateWindowEx(
            ex_style,
            class_atom, title, win32con.WS_POPUP,
            0, 0, self.width, self.height, None, None, wc.hInstance, None
        )
 
        win32gui.SetLayeredWindowAttributes(self.hwnd, 0x000000, 0, win32con.LWA_COLORKEY)
        win32gui.ShowWindow(self.hwnd, win32con.SW_SHOW)
 
        self.hdc = win32gui.GetDC(self.hwnd)
        self.hdc_obj = win32ui.CreateDCFromHandle(self.hdc)
        self.memdc = self.hdc_obj.CreateCompatibleDC()
        self.buffer = win32ui.CreateBitmap()
        self.buffer.CreateCompatibleBitmap(self.hdc_obj, self.width, self.height)
        self.memdc.SelectObject(self.buffer)
 
    def begin_scene(self):
        time.sleep(1.0 / self.fps)
        brush = win32gui.CreateSolidBrush(0x000000)
        win32gui.FillRect(self.memdc.GetSafeHdc(), (0, 0, self.width, self.height), brush)
        return True
 
    def end_scene(self):
        self.hdc_obj.BitBlt((0, 0), (self.width, self.height), self.memdc, (0, 0), win32con.SRCCOPY)
 
    def draw_box(self, x, y, w, h, color):
        pen = win32gui.CreatePen(win32con.PS_SOLID, 1, win32api.RGB(*color))
        win32gui.SelectObject(self.memdc.GetSafeHdc(), pen)
        win32gui.SelectObject(self.memdc.GetSafeHdc(), win32gui.GetStockObject(win32con.NULL_BRUSH))
        win32gui.Rectangle(self.memdc.GetSafeHdc(), int(x), int(y), int(x + w), int(y + h))
 
    def draw_filled_rect(self, x, y, w, h, color):
        brush = win32gui.CreateSolidBrush(win32api.RGB(*color))
        win32gui.FillRect(self.memdc.GetSafeHdc(), (int(x), int(y), int(x + w), int(y + h)), brush)
 
    def get_module_base(self, pid, module_name):
        snapshot = windll.kernel32.CreateToolhelp32Snapshot(0x00000008, pid)
 
        class MODULEENTRY32(ctypes.Structure):
            _fields_ = [
                ("dwSize", wintypes.DWORD), ("th32ModuleID", wintypes.DWORD),
                ("th32ProcessID", wintypes.DWORD), ("GlblcntUsage", wintypes.DWORD),
                ("ProccntUsage", wintypes.DWORD), ("modBaseAddr", ctypes.POINTER(ctypes.c_byte)),
                ("modBaseSize", wintypes.DWORD), ("hModule", wintypes.HMODULE),
                ("szModule", ctypes.c_char * 256), ("szExePath", ctypes.c_char * 260),
            ]
 
        me32 = MODULEENTRY32()
        me32.dwSize = ctypes.sizeof(MODULEENTRY32)
 
        if windll.kernel32.Module32First(snapshot, byref(me32)):
            while True:
                if me32.szModule.decode("utf-8") == module_name:
                    windll.kernel32.CloseHandle(snapshot)
                    return ctypes.cast(me32.modBaseAddr, ctypes.c_void_p).value
                if not windll.kernel32.Module32Next(snapshot, byref(me32)):
                    break
        windll.kernel32.CloseHandle(snapshot)
        return None
 
def read_bytes(handle, addr, size):
    if addr == 0 or addr > 0x7FFFFFFFFFFF:
        return b'\x00' * size
    buf = ctypes.create_string_buffer(size)
    bytes_read = ctypes.c_size_t()
    windll.kernel32.ReadProcessMemory(
        ctypes.c_void_p(handle),
        ctypes.c_void_p(addr),
        buf,
        size,
        byref(bytes_read)
    )
    return buf.raw
 
def read_int(handle, addr): return struct.unpack("i", read_bytes(handle, addr, 4))[0]
def read_uint64(handle, addr): return struct.unpack("Q", read_bytes(handle, addr, 8))[0]
def safe_read_uint64(handle, addr):
    try:
        if not addr or addr > 0x7FFFFFFFFFFF:
            return 0
        return read_uint64(handle, addr)
    except:
        return 0
def read_float(handle, addr): return struct.unpack("f", read_bytes(handle, addr, 4))[0]
def read_vec3(handle, addr): return Vec3.from_buffer_copy(read_bytes(handle, addr, 12))
def read_matrix(handle, addr): return struct.unpack("f" * 16, read_bytes(handle, addr, 64))
 
def world_to_screen(matrix, pos, width, height):
    x = matrix[0] * pos.x + matrix[1] * pos.y + matrix[2] * pos.z + matrix[3]
    y = matrix[4] * pos.x + matrix[5] * pos.y + matrix[6] * pos.z + matrix[7]
    w = matrix[12] * pos.x + matrix[13] * pos.y + matrix[14] * pos.z + matrix[15]
    if w < 0.1: raise Exception("Behind camera")
    inv_w = 1.0 / w
    screen_x = width / 2 + (x * inv_w) * width / 2
    screen_y = height / 2 - (y * inv_w) * height / 2
    return {"x": screen_x, "y": screen_y}
 
class Entity:
    def __init__(self, controller, pawn, handle):
        self.handle = handle
        self.controller = controller
        self.pawn = pawn
 
    def read_data(self):
        self.hp = read_int(self.handle, self.pawn + Offsets.m_iHealth)
        self.team = read_int(self.handle, self.pawn + Offsets.m_iTeamNum)
        self.pos = read_vec3(self.handle, self.pawn + Offsets.m_vOldOrigin)
 
        scene = safe_read_uint64(self.handle, self.pawn + Offsets.m_pGameSceneNode)
        bones = safe_read_uint64(self.handle, scene + Offsets.m_pBoneArray)
        self.head = read_vec3(self.handle, bones + 6 * 32)
 
    def wts(self, matrix, width, height):
        try:
            self.feet2d = world_to_screen(matrix, self.pos, width, height)
            self.head2d = world_to_screen(matrix, self.head, width, height)
            return True
        except:
            return False
 
def get_entities(handle, base):
    local = safe_read_uint64(handle, base + Offsets.dwLocalPlayerController)
    list_ptr = safe_read_uint64(handle, base + Offsets.dwEntityList)
    result = []
 
    for i in range(1, 65):
        try:
            entry = safe_read_uint64(handle, list_ptr + (8 * (i & 0x7FFF) >> 9) + 16)
            ctrl = safe_read_uint64(handle, entry + 120 * (i & 0x1FF))
            if not ctrl or ctrl == local:
                continue
            pawn_handle = safe_read_uint64(handle, ctrl + Offsets.m_hPlayerPawn)
            pawn_entry = safe_read_uint64(handle, list_ptr + 0x8 * ((pawn_handle & 0x7FFF) >> 9) + 16)
            pawn = safe_read_uint64(handle, pawn_entry + 120 * (pawn_handle & 0x1FF))
            if not pawn: continue
 
            ent = Entity(ctrl, pawn, handle)
            ent.read_data()
            result.append(ent)
        except: continue
    return result
 
def main():
    print("[*] Starting ctypes Box ESP")
 
    hwnd = windll.user32.FindWindowW(None, "Counter-Strike 2")
    if not hwnd:
        print("[!] CS2 not running.")
        return
 
    pid = wintypes.DWORD()
    windll.user32.GetWindowThreadProcessId(hwnd, byref(pid))
    handle = windll.kernel32.OpenProcess(PROCESS_ALL_ACCESS, False, pid.value)
 
    overlay = Overlay()
    base = overlay.get_module_base(pid.value, "client.dll")
    overlay.init("CS2 Box ESP")
 
    while overlay.begin_scene():
        try:
            
            msg = wintypes.MSG()
            while windll.user32.PeekMessageW(byref(msg), 0, 0, 0, win32con.PM_REMOVE):
                windll.user32.TranslateMessage(byref(msg))
                windll.user32.DispatchMessageW(byref(msg))
 
            w, h = overlay.width, overlay.height
            matrix = read_matrix(handle, base + Offsets.dwViewMatrix)
            for ent in get_entities(handle, base):
                if ent.hp <= 0 or not ent.wts(matrix, w, h): continue
 
                box_h = (ent.feet2d["y"] - ent.head2d["y"]) * 1.08
                box_w = box_h / 2
                x, y = ent.head2d["x"] - box_w / 2, ent.head2d["y"] - box_h * 0.08
 
                color = (255, 0, 0) if ent.team == 2 else (0, 128, 255)
                overlay.draw_box(x, y, box_w, box_h, color)
 
                hp_ratio = ent.hp / 100
                bar_height = box_h * hp_ratio
                hp_color = (0, 255, 0) if hp_ratio > 0.66 else (255, 255, 0) if hp_ratio > 0.33 else (255, 0, 0)
                overlay.draw_filled_rect(x - 5, y + (box_h - bar_height), 3, bar_height, hp_color)
        except Exception as e:
            print("[!] ESP Error:", e)
        overlay.end_scene()
 
if __name__ == "__main__":
    main()
