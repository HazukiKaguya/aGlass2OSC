#!/usr/bin/env python3
"""aGlass 软件狗 (soft dongle)
================================================================
把 aGlass 加密狗的两层行为都在进程内伪造掉, 不需要任何硬件、不修改厂商文件:

  第 1 层 设备发现 (SetupAPI)  —— 伪造出一个 VID_2012&PID_2011 / Generic Usb Key 的设备
             SetupDiGetClassDevsA/W, SetupDiEnumDeviceInterfaces,
             SetupDiGetDeviceInterfaceDetailA/W, SetupDiDestroyDeviceInfoList
  第 2 层 设备通信 (内核句柄)  —— 拦截对假设备的打开与 IOCTL
             CreateFileA/W, DeviceIoControl, CloseHandle
             其中 IOCTL_SCSI_PASS_THROUGH_DIRECT(0x4D014) 上的厂商命令 0xEF 用录制数据回答

hide_real=True 时会把真狗的路径从枚举结果里"藏掉", 方便在真狗还插着的情况下做验证。

用法:
    python soft_dongle.py --selftest        # 在本进程自证: 隐藏真狗, 只靠假设备跑完协议
装入其它进程请配合 inject_soft_dongle.py (见 README)
"""
import ctypes, ctypes.wintypes as w, json, os, struct, sys, tempfile, uuid

# ------------------------------------------------------------------ 协议常量
_HERE = os.path.dirname(os.path.abspath(__file__))
REC = json.load(open(os.path.join(_HERE, 'key_protocol.json'), encoding='utf-8'))

def _payload(prefix, data_in):
    for r in REC:
        if r['cdb'].startswith(prefix) and r['dataIn'] == data_in and r['in_hex']:
            return bytes.fromhex(r['in_hex'])
    raise SystemExit('抓包文件里缺少 ' + prefix)

HDR_ID, REC_ID = _payload('ef 02 21', 1), _payload('ef 03 21', 1)
HDR_LIC, REC_LIC = _payload('ef 02 22', 1), _payload('ef 03 22', 1)
_acks = [bytes.fromhex(r['in_hex']) for r in REC if r['cdb'].startswith('ef 03 22') and r['in_hex']]
_hdrs = [bytes.fromhex(r['in_hex']) for r in REC if r['cdb'].startswith('ef 02 22') and r['in_hex']]
ACK22, HDR_ACK = _acks[-1], _hdrs[-1]

DEVICE_PATHS = {
    'A5DCBF10-6530-11D2-901F-00C04FB951ED': r'\\?\usb#vid_2012&pid_2011#0&0&0#{a5dcbf10-6530-11d2-901f-00c04fb951ed}',
    '53F56308-B6BF-11D0-94F2-00A0C91EFB8B': r'\\?\usbstor#cdrom&ven_generic&prod_usb_key&rev_1.09#0&0&0#{53f56308-b6bf-11d0-94f2-00a0c91efb8b}',
    '53F56307-B6BF-11D0-94F2-00A0C91EFB8B': r'\\?\usbstor#disk&ven_generic&prod_usb_key&rev_1.09#0&0&0#{53f56307-b6bf-11d0-94f2-00a0c91efb8b}',
}
KEY_PATH_MARKERS = ('vid_2012', 'usb_key')

# ------------------------------------------------------------------ 真函数
k32 = ctypes.WinDLL('kernel32', use_last_error=True)
sapi = ctypes.WinDLL('setupapi', use_last_error=True)
k32.VirtualProtect.argtypes = [ctypes.c_void_p, ctypes.c_size_t, w.DWORD, ctypes.POINTER(w.DWORD)]
k32.CreateFileW.restype = w.HANDLE
k32.CreateFileW.argtypes = [w.LPCWSTR, w.DWORD, w.DWORD, ctypes.c_void_p, w.DWORD, w.DWORD, w.HANDLE]
k32.CreateFileA.restype = w.HANDLE
k32.CreateFileA.argtypes = [ctypes.c_char_p, w.DWORD, w.DWORD, ctypes.c_void_p, w.DWORD, w.DWORD, w.HANDLE]
k32.CloseHandle.argtypes = [w.HANDLE]
k32.DeviceIoControl.argtypes = [w.HANDLE, w.DWORD, ctypes.c_void_p, w.DWORD, ctypes.c_void_p, w.DWORD,
                               ctypes.POINTER(w.DWORD), ctypes.c_void_p]
sapi.SetupDiGetClassDevsW.restype = ctypes.c_void_p
sapi.SetupDiGetClassDevsA.restype = ctypes.c_void_p
sapi.SetupDiEnumDeviceInterfaces.restype = w.BOOL
sapi.SetupDiGetDeviceInterfaceDetailW.restype = w.BOOL
sapi.SetupDiGetDeviceInterfaceDetailA.restype = w.BOOL
sapi.SetupDiDestroyDeviceInfoList.restype = w.BOOL

LOGF = print
def log(*a):
    LOGF('[soft-dongle]', *a)

# ------------------------------------------------------------------ 状态
class State:
    hide_real = True
    emulate = True
    log_files = bool(os.environ.get('SOFT_DONGLE_LOG_FILES'))   # 记录目标进程打开的所有文件/设备
    log_spti = bool(os.environ.get('SOFT_DONGLE_LOG_SPTI'))     # 记录所有 SCSI pass-through 会话(含真设备)
    log_enum = bool(os.environ.get('SOFT_DONGLE_LOG_ENUM'))     # 记录目标进程枚举了哪些设备类(GUID)
    fake_usb = os.environ.get('SOFT_DONGLE_NO_USB') != '1'      # 是否在 "USB 设备" 类里插假条目
    hdev_guid = {}        # hdev -> guid 字符串
    pending_fake = {}     # hdev -> True  刚返回了假条目, 下一次 Detail 归我们
    last_fake_hdev = None
    fake_handles = {}     # handle -> True
    dummy = None          # 假句柄(真实存在的临时文件句柄)
    stats = {'enum_fake': 0, 'open_fake': 0, 'ef_cmds': 0, 'hidden_real': 0}
    tables = None         # (setupapi 钩子表, kernel32 钩子表) —— 给动态模块监控复用
    patched_bases = set() # 已经挂钩过的模块基址(避免重复挂钩 / 支持卸载后重挂)
    watch_allow = ()      # 动态监控白名单
    # 协议状态机(与固件 aglass_key.c 完全一致)
    last_write = b''
    count22 = 0
    lic_is_read = False

S = State()

# setupapi / kernel32 的 argtypes 必须声明, 否则 64 位指针会被当成 32 位整数报 OverflowError
sapi.SetupDiGetClassDevsW.argtypes = [ctypes.c_void_p, w.LPCWSTR, ctypes.c_void_p, w.DWORD]
sapi.SetupDiGetClassDevsA.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_void_p, w.DWORD]
sapi.SetupDiEnumDeviceInterfaces.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, w.DWORD, ctypes.c_void_p]
sapi.SetupDiGetDeviceInterfaceDetailW.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, w.DWORD,
                                                  ctypes.POINTER(w.DWORD), ctypes.c_void_p]
sapi.SetupDiGetDeviceInterfaceDetailA.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, w.DWORD,
                                                  ctypes.POINTER(w.DWORD), ctypes.c_void_p]
sapi.SetupDiDestroyDeviceInfoList.argtypes = [ctypes.c_void_p]

def is_key_path(p):
    if not p:
        return False
    l = p.lower()
    return any(m in l for m in KEY_PATH_MARKERS)

def akey_handle(cdb, buf, buflen, data_in):
    """0xEF 协议状态机 -> (handled, out_bytes)"""
    if cdb[0] != 0xEF:
        return False, b''
    sub, rec = cdb[1], cdb[2]
    S.stats['ef_cmds'] += 1
    if not data_in:
        if sub == 0x01 and rec == 0x22:
            S.last_write = bytes(buf[:buflen])
            S.count22 += 1
            if len(S.last_write) > 5:
                S.lic_is_read = (S.last_write[5] == 0x00)
            else:
                S.lic_is_read = (S.count22 % 2) == 1
        return True, b''
    if rec == 0x21:
        return True, (HDR_ID if sub == 0x02 else REC_ID)
    if rec == 0x22:
        if sub == 0x02:
            return True, (HDR_LIC if S.lic_is_read else HDR_ACK)
        return True, (REC_LIC if S.lic_is_read else ACK22)
    return True, b''

# ------------------------------------------------------------------ 假设备 IOCTL
def fake_ioctl(code, inbuf, inlen, outbuf, outlen, lpRet):
    if code == 0x4D014 and inbuf and inlen >= 56:          # IOCTL_SCSI_PASS_THROUGH_DIRECT
        b = ctypes.string_at(inbuf, 56)
        _, _, _, _, _, cdblen, senselen, datain = struct.unpack_from('<HBBBBBBB', b, 0)
        dtl = struct.unpack_from('<I', b, 12)[0]
        databuf = struct.unpack_from('<Q', b, 24)[0]
        senseoff = struct.unpack_from('<I', b, 32)[0]
        cdb = ctypes.string_at(inbuf + 36, min(cdblen, 16))
        status = 0
        data = b''
        if cdb and cdb[0] == 0xEF:
            handled, data = akey_handle(cdb, ctypes.string_at(databuf, dtl) if (not datain and databuf and dtl) else b'', dtl, bool(datain))
        elif cdb and cdb[0] == 0x12:                        # INQUIRY
            data = bytearray(36)
            data[0] = 0x05; data[1] = 0x80; data[3] = 0x01; data[4] = 0x1F
            data[8:16] = b'Generic '; data[16:32] = b'Usb Key         '; data[32:36] = b'1.09'
            data = bytes(data)
        elif cdb and cdb[0] == 0x25:                        # READ CAPACITY(10)
            data = struct.pack('>II', 256, 2048)
        elif cdb and cdb[0] == 0x00:                        # TEST UNIT READY
            data = b''
        else:
            status = 0x02                                   # CHECK CONDITION
        if data and databuf:
            ctypes.memmove(databuf, data, min(len(data), dtl if dtl else len(data)))
            if not dtl and inbuf:
                ctypes.memmove(inbuf + 12, struct.pack('<I', len(data)), 4)
        ctypes.memmove((outbuf or inbuf) + 2, bytes([status]), 1)
        if senseoff and senselen and status and (outbuf or inbuf):
            ctypes.memmove((outbuf or inbuf) + senseoff, b'\x70\x00\x05\x00' + b'\x00' * 14 + b'\x20\x00\x00', 18)
        if lpRet:
            lpRet[0] = inlen
        return True

    if code == 0x2D1400:                                    # IOCTL_STORAGE_QUERY_PROPERTY
        vend, prod, rev = b'Generic', b'Usb Key', b'1.09'
        off = 36
        body = bytearray(off + len(vend) + 1 + len(prod) + 1 + len(rev) + 1 + 4)
        struct.pack_into('<II', body, 0, 40, len(body))
        body[8] = 0x05                                      # CD-ROM
        body[10] = 1                                        # RemovableMedia
        body[11] = 0                                        # CommandQueueing
        voff = off; body[voff:voff + len(vend)] = vend
        poff = voff + len(vend) + 1; body[poff:poff + len(prod)] = prod
        roff = poff + len(prod) + 1; body[roff:roff + len(rev)] = rev
        struct.pack_into('<III', body, 12, voff, poff, roff)
        struct.pack_into('<I', body, 24, 0)                 # SerialNumberOffset
        struct.pack_into('<I', body, 28, 7)                 # BusType = USB
        struct.pack_into('<I', body, 32, 0)                 # RawPropertiesLength
        if outbuf:
            ctypes.memmove(outbuf, bytes(body), min(len(body), outlen))
        if lpRet:
            lpRet[0] = len(body)
        return True

    if code == 0x41018:                                     # IOCTL_SCSI_GET_ADDRESS
        if outbuf:
            ctypes.memmove(outbuf, struct.pack('<IIII', 8, 0, 0, 0), 16)
        if lpRet:
            lpRet[0] = 8
        return True

    if code == 0x2D0800:                                    # IOCTL_STORAGE_CHECK_VERIFY2
        if lpRet:
            lpRet[0] = 0
        return True

    k32.SetLastError(1)                                     # ERROR_INVALID_FUNCTION
    return False

# ------------------------------------------------------------------ 钩子函数
P_CFG_W = ctypes.WINFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, w.LPCWSTR, ctypes.c_void_p, w.DWORD)
P_CFG_A = ctypes.WINFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_char_p, ctypes.c_void_p, w.DWORD)
P_ENUM = ctypes.WINFUNCTYPE(w.BOOL, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, w.DWORD, ctypes.c_void_p)
P_DETAIL_W = ctypes.WINFUNCTYPE(w.BOOL, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, w.DWORD, ctypes.POINTER(w.DWORD), ctypes.c_void_p)
P_DETAIL_A = ctypes.WINFUNCTYPE(w.BOOL, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, w.DWORD, ctypes.POINTER(w.DWORD), ctypes.c_void_p)
P_DESTROY = ctypes.WINFUNCTYPE(w.BOOL, ctypes.c_void_p)
P_CFW = ctypes.WINFUNCTYPE(w.HANDLE, w.LPCWSTR, w.DWORD, w.DWORD, ctypes.c_void_p, w.DWORD, w.DWORD, w.HANDLE)
P_CFA = ctypes.WINFUNCTYPE(w.HANDLE, ctypes.c_char_p, w.DWORD, w.DWORD, ctypes.c_void_p, w.DWORD, w.DWORD, w.HANDLE)
P_CLOSE = ctypes.WINFUNCTYPE(w.BOOL, w.HANDLE)
P_DIOC = ctypes.WINFUNCTYPE(w.BOOL, w.HANDLE, w.DWORD, ctypes.c_void_p, w.DWORD, ctypes.c_void_p, w.DWORD,
                            ctypes.POINTER(w.DWORD), ctypes.c_void_p)

def _guid_str(p):
    try:
        return str(uuid.UUID(bytes_le=ctypes.string_at(p, 16))).upper()
    except Exception:
        return ''

def h_cfg_w(guid, enum, hwnd, flags):
    h = sapi.SetupDiGetClassDevsW(guid, enum, hwnd, flags)
    if h and h != ctypes.c_void_p(-1).value and guid:
        S.hdev_guid[h] = _guid_str(guid)
        if S.log_enum:
            log('枚举设备类(W): %s' % S.hdev_guid[h])
    return h

def h_cfg_a(guid, enum, hwnd, flags):
    h = sapi.SetupDiGetClassDevsA(guid, enum, hwnd, flags)
    if h and h != ctypes.c_void_p(-1).value and guid:
        S.hdev_guid[h] = _guid_str(guid)
        if S.log_enum:
            log('枚举设备类(A): %s' % S.hdev_guid[h])
    return h

_enum_cache = {}      # (hdev, class_guid_bytes) -> [(DID 原始 32 字节, 路径), ...]

def _real_entries(hdev, guid):
    """一次性取出该 hdev/class 下所有真实接口条目, 便于"过滤掉真狗"后再按索引提供"""
    if not guid:
        return []
    key = (hdev, ctypes.string_at(guid, 16))
    if key in _enum_cache:
        return _enum_cache[key]
    out = []
    i = 0
    while True:
        did = ctypes.create_string_buffer(32)
        ctypes.memmove(did, struct.pack('<I', 32), 4)
        if not sapi.SetupDiEnumDeviceInterfaces(hdev, None, guid, i, did):
            break
        need = w.DWORD(0)
        sapi.SetupDiGetDeviceInterfaceDetailW(hdev, did, None, 0, ctypes.byref(need), None)
        path = ''
        if need.value >= 8:
            buf = ctypes.create_string_buffer(need.value)
            if sapi.SetupDiGetDeviceInterfaceDetailW(hdev, did, buf, need.value, ctypes.byref(need), None):
                try:
                    path = ctypes.wstring_at(ctypes.addressof(buf) + 4)
                except Exception:
                    path = ''
        out.append((did.raw[:32], path))
        i += 1
        if i > 512:
            break
    _enum_cache[key] = out
    return out

def h_enum(hdev, devinfo, guid, index, did):
    """枚举: 把真狗(如果 hide_real)从列表里彻底过滤掉, 再在末尾补我们的假条目。
    之前只在"取路径"时隐藏, 真狗仍留在列表里 -> 运行时会看到两只钥匙,
    触发厂商的 DEVICE_MULTIPLE_OR_NO_FOUND(-106), 于是禁用"眼睛选择"菜单。

    只对钥匙类(DISK / CDROM / USB 设备)做过滤和插入; 其它设备类原样透传 ——
    否则会连带改变相机等设备的枚举行为(旧写法对每个类都做一次快照)。"""
    if not guid:
        return sapi.SetupDiEnumDeviceInterfaces(hdev, devinfo, guid, index, did)
    if S.hdev_guid.get(hdev, '') not in DEVICE_PATHS:
        return sapi.SetupDiEnumDeviceInterfaces(hdev, devinfo, guid, index, did)

    entries = _real_entries(hdev, guid)
    visible = [e for e in entries if not (S.hide_real and is_key_path(e[1]))]

    if index < len(visible):
        if did:
            ctypes.memmove(did, visible[index][0], 32)
        return True

    if not S.emulate:
        return False
    if S.hdev_guid.get(hdev, '') not in DEVICE_PATHS:
        return False
    if index != len(visible) or S.pending_fake.get(hdev):
        return False
    S.pending_fake[hdev] = True
    S.last_fake_hdev = hdev
    S.stats['enum_fake'] += 1
    if did:
        ctypes.memmove(did, struct.pack('<I', 32), 4)
        ctypes.memmove(did + 4, guid, 16)
        ctypes.memmove(did + 20, struct.pack('<I', 1), 4)   # SPINT_ACTIVE
        ctypes.memmove(did + 24, struct.pack('<Q', 0), 8)
    log('伪造设备接口: class=%s (真实可见条目 %d, 隐藏 %d)' % (
        S.hdev_guid.get(hdev), len(visible), len(entries) - len(visible)))
    return True

def _detail(hdev, did, detail, size, required, path, wide):
    enc = 'utf-16-le' if wide else 'latin1'
    raw = path.encode(enc) + (b'\x00\x00' if wide else b'\x00')
    need = 4 + len(raw)
    need = (need + 7) & ~7                      # x64 下结构体按 8 字节对齐
    if not detail or (size and size < need):
        if required:
            required[0] = need
        if detail:
            k32.SetLastError(122)               # ERROR_INSUFFICIENT_BUFFER
            return False
        k32.SetLastError(122)
        return False
    ctypes.memmove(detail, struct.pack('<I', 8), 4)
    ctypes.memmove(detail + 4, raw, len(raw))
    if required:
        required[0] = need
    return True

def h_detail_w(hdev, did, detail, size, required, devinfo):
    if S.pending_fake.get(hdev) and S.hdev_guid.get(hdev) in DEVICE_PATHS:
        S.pending_fake[hdev] = False
        p = DEVICE_PATHS[S.hdev_guid[hdev]]
        log('提供假设备路径: %s' % p)
        return _detail(hdev, did, detail, size, required, p, True)
    ok = sapi.SetupDiGetDeviceInterfaceDetailW(did, detail, size, required, devinfo)
    if ok and detail and size >= 8:
        p = ctypes.wstring_at(detail + 4)
        if S.hide_real and is_key_path(p):
            S.stats['hidden_real'] += 1
            log('隐藏真实设备路径: %s' % p)
            k32.SetLastError(2)
            return False
    return ok

def h_detail_a(hdev, did, detail, size, required, devinfo):
    if S.pending_fake.get(hdev) and S.hdev_guid.get(hdev) in DEVICE_PATHS:
        S.pending_fake[hdev] = False
        p = DEVICE_PATHS[S.hdev_guid[hdev]]
        log('提供假设备路径(A): %s' % p)
        return _detail(hdev, did, detail, size, required, p, False)
    ok = sapi.SetupDiGetDeviceInterfaceDetailA(hdev, did, detail, size, required, devinfo)
    if ok and detail and size >= 5:
        p = ctypes.string_at(detail + 4).decode('latin1')
        if S.hide_real and is_key_path(p):
            S.stats['hidden_real'] += 1
            log('隐藏真实设备路径(A): %s' % p)
            k32.SetLastError(2)
            return False
    return ok

def h_destroy(hdev):
    S.hdev_guid.pop(hdev, None)
    S.pending_fake.pop(hdev, None)
    for k in [k for k in list(_enum_cache) if k[0] == hdev]:
        _enum_cache.pop(k, None)
    return sapi.SetupDiDestroyDeviceInfoList(hdev)

def _dummy_handle():
    if S.dummy is None:
        p = os.path.join(tempfile.gettempdir(), 'aglass_softkey.bin')
        S.dummy = k32.CreateFileW(p, 0xC0000000, 3, None, 4, 0x80, None)   # OPEN_ALWAYS
        log('创建假句柄: %s -> %s' % (p, S.dummy))
    return S.dummy

def h_cfw(fn, acc, sh, sa, cr, fl, tm):
    p = fn or ''
    if S.emulate and is_key_path(p):
        h = _dummy_handle()
        S.fake_handles[int(h)] = True
        S.stats['open_fake'] += 1
        log('拦截打开假设备: %s -> 句柄 %s' % (p, h))
        return h
    if S.log_files:
        log('[文件] %s' % p)
    return k32.CreateFileW(fn, acc, sh, sa, cr, fl, tm)

def h_cfa(fn, acc, sh, sa, cr, fl, tm):
    p = (fn or b'').decode('latin1')
    if S.emulate and is_key_path(p):
        h = _dummy_handle()
        S.fake_handles[int(h)] = True
        S.stats['open_fake'] += 1
        log('拦截打开假设备(A): %s -> 句柄 %s' % (p, h))
        return h
    if S.log_files:
        log('[文件A] %s' % p)
    return k32.CreateFileA(fn, acc, sh, sa, cr, fl, tm)

def h_close(h):
    S.fake_handles.pop(int(h), None)
    return k32.CloseHandle(h)

def h_dioc(hf, code, inbuf, inlen, outbuf, outlen, lpRet, ov):
    if S.emulate and int(hf) in S.fake_handles:
        ok = fake_ioctl(code, inbuf, inlen, outbuf, outlen, lpRet)
        if code == 0x4D014:
            log('假设备收到 SPTI: %s' % ctypes.string_at(inbuf + 36, 10).hex(' ') if inbuf else '?')
        else:
            log('假设备收到 IOCTL 0x%08X -> %s' % (code, 'OK' if ok else '不支持'))
        return ok
    # 穿透路径: 需要时把真设备的会话也记下来(用于比对真/假狗的行为)
    if S.log_spti and code == 0x4D014 and inbuf and inlen >= 56:
        b = ctypes.string_at(inbuf, 56)
        _, _, _, _, _, cdblen, _, datain = struct.unpack_from('<HBBBBBBB', b, 0)
        dtl = struct.unpack_from('<I', b, 12)[0]
        databuf = struct.unpack_from('<Q', b, 24)[0]
        cdb = ctypes.string_at(inbuf + 36, min(cdblen, 16))
        wr = ''
        if not datain and databuf and dtl:
            wr = ' 写:%s' % ctypes.string_at(databuf, min(dtl, 12)).hex(' ')
        ok = k32.DeviceIoControl(hf, code, inbuf, inlen, outbuf, outlen, lpRet, ov)
        rd = ''
        if datain and databuf and dtl:
            rd = ' 读:%s' % ctypes.string_at(databuf, min(dtl, 16)).hex(' ')
        log('[真设备SPTI] %s dataIn=%d xfer=%d ok=%s%s%s' % (cdb.hex(' '), datain, dtl, bool(ok), wr, rd))
        return ok
    return k32.DeviceIoControl(hf, code, inbuf, inlen, outbuf, outlen, lpRet, ov)

# ------------------------------------------------------------------ 调用方归属
_module_cache = {'t': 0.0, 'ranges': []}
SKIP_FRAME_MODULES = ('python312.dll', 'python3.dll', '_ctypes.pyd', 'kernel32.dll', 'kernelbase.dll',
                      'ntdll.dll', 'ucrtbase.dll', 'vcruntime140.dll')

def module_ranges():
    import time as _t
    now = _t.time()
    if now - _module_cache['t'] > 2 or not _module_cache['ranges']:
        rngs = [(base, base + max(size, 0x1000), name)
                for name, path, base, size in self_modules() if base]
        rngs.sort()
        _module_cache['ranges'] = rngs
        _module_cache['t'] = now
    return _module_cache['ranges']

def addr_module(addr):
    for lo, hi, name in module_ranges():
        if lo <= addr < hi:
            return name
    return ''

def caller_mod():
    """回溯栈, 返回"发起这次调用"的模块名(跳过 Python/系统 DLL)"""
    try:
        k32.RtlCaptureStackBackTrace.argtypes = [w.DWORD, w.DWORD, ctypes.c_void_p, ctypes.c_void_p]
        k32.RtlCaptureStackBackTrace.restype = w.WORD
        n = 32
        arr = (ctypes.c_void_p * n)()
        got = k32.RtlCaptureStackBackTrace(0, n, arr, None)
        for i in range(min(got, n)):
            a = arr[i]
            if not a:
                break
            m = addr_module(a)
            if m and m.lower() not in SKIP_FRAME_MODULES:
                return m
    except Exception:
        pass
    return '?'


# ------------------------------------------------------------------ IAT 挂钩
def self_modules():
    """列出当前进程的已加载模块 (名字, 路径, 基址, 大小)"""
    k32.CreateToolhelp32Snapshot.restype = ctypes.c_void_p
    k32.CreateToolhelp32Snapshot.argtypes = [w.DWORD, w.DWORD]
    k32.GetCurrentProcessId.restype = w.DWORD
    k32.Module32First.argtypes = [w.HANDLE, ctypes.c_void_p]
    k32.Module32Next.argtypes = [w.HANDLE, ctypes.c_void_p]

    class ME32(ctypes.Structure):
        _fields_ = [("dwSize", w.DWORD), ("th32ModuleID", w.DWORD), ("th32ProcessID", w.DWORD),
                    ("GlblcntUsage", w.DWORD), ("ProccntUsage", w.DWORD),
                    ("modBaseAddr", ctypes.c_void_p), ("modBaseSize", w.DWORD), ("hModule", w.HMODULE),
                    ("szModule", ctypes.c_char * 256), ("szExePath", ctypes.c_char * 260)]

    snap = k32.CreateToolhelp32Snapshot(0x8 | 0x10, k32.GetCurrentProcessId())
    out = []
    if not snap or snap == ctypes.c_void_p(-1).value:
        return out
    me = ME32(); me.dwSize = ctypes.sizeof(me)
    ok = k32.Module32First(snap, ctypes.byref(me))
    while ok:
        out.append((me.szModule.decode('latin1'), me.szExePath.decode('latin1'),
                    ctypes.cast(me.modBaseAddr, ctypes.c_void_p).value, me.modBaseSize))
        ok = k32.Module32Next(snap, ctypes.byref(me))
    k32.CloseHandle(snap)
    return out


SKIP_MODULES = {'kernel32.dll', 'kernelbase.dll', 'setupapi.dll', 'ntdll.dll', 'user32.dll',
                'advapi32.dll', 'gdi32.dll', 'ole32.dll', 'shell32.dll', 'combase.dll',
                'msvcrt.dll', 'ucrtbase.dll', 'rpcrt4.dll', 'sechost.dll', 'shcore.dll'}


def patch_iat(base, dll_substr, table, log_patched=True):
    """把 base 模块 IAT 里指定 DLL 的若干函数换成我们的钩子。
    做了严格 PE 校验 + 越界检查 + 异常保护(进程里存在不是标准 PE 的映像)。"""
    n = 0
    try:
        if ctypes.string_at(base, 2) != b'MZ':
            return 0
        e_lfanew = struct.unpack('<I', ctypes.string_at(base + 0x3C, 4))[0]
        if not (0 < e_lfanew < 0x1000) or ctypes.string_at(base + e_lfanew, 4) != b'PE\0\0':
            return 0
        opt = base + e_lfanew + 24
        magic = struct.unpack('<H', ctypes.string_at(opt, 2))[0]
        if magic not in (0x10b, 0x20b):
            return 0
        size_of_image = struct.unpack('<I', ctypes.string_at(opt + 56, 4))[0]
        ddoff = opt + (112 if magic == 0x20b else 96)
        rva, _ = struct.unpack('<II', ctypes.string_at(ddoff + 8, 8))

        def in_mod(x):
            return 0 < x < size_of_image

        if not in_mod(rva):
            return 0
        desc = base + rva
        i = 0
        while True:
            oft, tds, fc, name_rva, ft = struct.unpack('<IIIII', ctypes.string_at(desc + i * 20, 20))
            if name_rva == 0:
                break
            if not in_mod(name_rva) or not in_mod(ft):
                break
            name = ctypes.string_at(base + name_rva).decode('latin1', 'replace').lower()
            if dll_substr in name:
                thr = base + (oft or ft)
                j = 0
                while True:
                    ent = struct.unpack('<Q', ctypes.string_at(thr + j * 8, 8))[0]
                    if ent == 0:
                        break
                    if not in_mod(ent & 0x7FFFFFFF):
                        break
                    fname = ctypes.string_at(base + (ent & 0x7FFFFFFF) + 2).split(b'\0')[0]
                    if fname in table:
                        slot = base + ft + j * 8
                        old = ctypes.c_ulong(0)
                        k32.VirtualProtect(slot, 8, 0x40, ctypes.byref(old))
                        # 原子 8 字节写: 正在跑的其他线程只会看到旧值或新值, 不会读到半截地址
                        ctypes.c_uint64.from_address(slot).value = table[fname]
                        k32.VirtualProtect(slot, 8, old, ctypes.byref(old))
                        if log_patched:
                            log('已挂钩 %s!%s' % (name, fname.decode()))
                        n += 1
                    j += 1
            i += 1
    except Exception as e:
        if log_patched:
            log('跳过模块 0x%X: %r' % (base, e))
        return n
    return n

_callbacks = {}

def _module_base(module_path=None, dll_handle=None):
    """拿到 aGlass_vr_api.dll 在当前进程里的基址"""
    if dll_handle:
        return dll_handle._handle
    try:
        k32.GetModuleHandleW.restype = ctypes.c_void_p
        k32.GetModuleHandleW.argtypes = [ctypes.c_wchar_p]
    except Exception:
        pass
    h = k32.GetModuleHandleW('aGlass_vr_api.dll')
    if not h:
        if not module_path:
            module_path = r'C:\Program Files\aGlass\aGlass_vr_api.dll'
        h = ctypes.WinDLL(module_path)._handle
    if not h:
        raise RuntimeError('找不到 aGlass_vr_api.dll (基址=0)')
    return h

def install(module_path=None, hide_real=True, emulate=True, logger=print, dll_handle=None,
            all_modules=False, watch_modules=("aGlass_vr_api.dll",), watch_interval=5.0):
    """在当前进程里安装软件狗。
    module_path    : aGlass_vr_api.dll 的路径(未加载时用于加载)
    all_modules    : 给进程内**其它**模块也挂钩子。默认关闭 ——
                     运行时自带"模组保活"扫描, 钩了它自己托盘 Eye Mode 会变灰。
                     需要时用 SOFT_DONGLE_ALLMOD=1 或本参数显式打开。
    watch_modules  : 动态模块监控白名单。安装**之后**才加载的 DLL 若命中白名单会被自动挂钩
                     (LdrRegisterDllNotification + 周期兜底扫描)。默认只盯 aGlass_vr_api.dll。
                     传 () / None 关闭。
    watch_interval : 兜底扫描周期(秒)。
    """
    global LOGF
    LOGF = logger
    S.hide_real, S.emulate = hide_real, emulate
    S.patched_bases = set()
    S.watch_allow = tuple(watch_modules or ())

    base = _module_base(module_path, dll_handle)
    log('目标模块基址 = 0x%X' % base)

    cb = _callbacks
    cb['sapi'] = {
        b'SetupDiGetClassDevsW': P_CFG_W(h_cfg_w),
        b'SetupDiGetClassDevsA': P_CFG_A(h_cfg_a),
        b'SetupDiEnumDeviceInterfaces': P_ENUM(h_enum),
        b'SetupDiGetDeviceInterfaceDetailW': P_DETAIL_W(h_detail_w),
        b'SetupDiGetDeviceInterfaceDetailA': P_DETAIL_A(h_detail_a),
        b'SetupDiDestroyDeviceInfoList': P_DESTROY(h_destroy),
    }
    cb['k32'] = {
        b'CreateFileW': P_CFW(h_cfw),
        b'CreateFileA': P_CFA(h_cfa),
        b'CloseHandle': P_CLOSE(h_close),
        b'DeviceIoControl': P_DIOC(h_dioc),
    }
    t_sapi = {k: ctypes.cast(v, ctypes.c_void_p).value for k, v in cb['sapi'].items()}
    t_k32 = {k: ctypes.cast(v, ctypes.c_void_p).value for k, v in cb['k32'].items()}
    # 留给动态监控复用(module_watch 靠这两个值挂钩下一条新加载的 DLL)
    S.tables = (t_sapi, t_k32)
    S.patched_bases.add(base)

    n1 = patch_iat(base, 'setupapi', t_sapi)
    n2 = patch_iat(base, 'kernel32', t_k32)
    log('挂钩完成(主模块): setupapi %d 项, kernel32 %d 项' % (n1, n2))

    if all_modules:
        patched = []
        for name, path, mbase, msize in self_modules():
            if name.lower() in SKIP_MODULES or mbase == base or not mbase:
                continue
            a = patch_iat(mbase, 'setupapi', t_sapi, log_patched=False)
            b = patch_iat(mbase, 'kernel32', t_k32, log_patched=False)
            S.patched_bases.add(mbase)
            if a or b:
                patched.append('%s(setupapi %d, kernel32 %d)' % (name, a, b))
        log('附加挂钩 %d 个模块: %s' % (len(patched), ', '.join(patched)))

    if S.watch_allow:
        try:
            try:                      # 作为包的一部分运行时(aglass_vrc/)
                from . import module_watch
            except ImportError:       # 作为顶层模块运行时
                import module_watch
            module_watch.start(allow=S.watch_allow, interval=watch_interval)
        except Exception as e:
            log('动态模块监控启动失败(不影响已挂钩子): %r' % (e,))
    return base

# ------------------------------------------------------------------ 自证
def selftest():
    log('=== 软件狗自证: 隐藏真狗, 只用假设备跑 aGlass 的钥匙协议 ===')
    dll = ctypes.WinDLL(r'C:\Program Files\aGlass\aGlass_vr_api.dll')
    install(dll_handle=dll, hide_real=True, emulate=True)

    EVT = ctypes.CFUNCTYPE(None, ctypes.c_int, ctypes.c_void_p)
    evt = EVT(lambda c, u: log('设备事件回调 code=%d' % c))
    dll.aGlass_set_debug.argtypes = [ctypes.c_int]
    dll.aGlass_init_usb_listener.argtypes = [EVT, ctypes.c_void_p]
    dll.aGlass_init_usb_listener.restype = ctypes.c_int
    dll.aGlass_init.restype = ctypes.c_int
    dll.aGlass_init.argtypes = [ctypes.c_void_p]
    dll.aGlass_release.restype = ctypes.c_int

    dll.aGlass_set_debug(1)
    log('listener -> %d' % dll.aGlass_init_usb_listener(evt, None))
    buf = ctypes.create_string_buffer(64)
    struct.pack_into('<ii', buf, 0, 29000, 29001)
    log('init -> %d' % dll.aGlass_init(ctypes.byref(buf)))
    dll.aGlass_release()

    log('')
    log('统计: 伪造枚举 %d 次, 拦截打开 %d 次, 处理厂商命令 %d 条, 隐藏真狗路径 %d 次'
        % (S.stats['enum_fake'], S.stats['open_fake'], S.stats['ef_cmds'], S.stats['hidden_real']))
    verdict = (S.stats['open_fake'] > 0 and S.stats['ef_cmds'] >= 9)
    log('结论: %s' % ('软件狗完整接管了设备发现与通信 ✅' if verdict else '❌ 未完整接管, 检查上面的日志'))
    return 0 if verdict else 1

if __name__ == '__main__':
    if '--selftest' in sys.argv:
        sys.exit(selftest())
    print(__doc__)
