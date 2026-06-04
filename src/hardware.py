import threading
import struct
import io
import logging
import pywinusb.hid as hid_lib
from PIL import Image

Logger = logging.getLogger("yp")

DEVICES = [
    {"name": "StreamDock MiraBox", "vid": 0x6603, "pid": 0x1014, "keys": 15, "img_size": 72, "img_flip_h": True,  "img_flip_v": True,  "page_hdr": 8},
    {"name": "StreamDock",         "vid": 0x0fd9, "pid": 0x0063, "keys": 15, "img_size": 72, "img_flip_h": True,  "img_flip_v": True,  "page_hdr": 8},
    {"name": "StreamDeck v2",      "vid": 0x0fd9, "pid": 0x006d, "keys": 15, "img_size": 72, "img_flip_h": True,  "img_flip_v": True,  "page_hdr": 8},
    {"name": "StreamDeck v1",      "vid": 0x0fd9, "pid": 0x0060, "keys": 15, "img_size": 72, "img_flip_h": True,  "img_flip_v": True,  "page_hdr": 16},
]

PAGE_SIZE = 512


def _encode_image(pil_image, size, flip_h, flip_v):
    img = pil_image.resize((size, size), Image.LANCZOS).convert("RGB")
    if flip_h:
        img = img.transpose(Image.FLIP_LEFT_RIGHT)
    if flip_v:
        img = img.transpose(Image.FLIP_TOP_BOTTOM)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95)
    return buf.getvalue()


def _build_image_payload(key_index, img_data, page_hdr):
    pages = []
    remaining = img_data
    page_num = 0
    payload_size = PAGE_SIZE - page_hdr
    while remaining:
        chunk = remaining[:payload_size]
        remaining = remaining[payload_size:]
        is_last = 1 if len(remaining) == 0 else 0
        if page_hdr == 8:
            header = struct.pack("<BBBBHH",
                                 0x02, 0x07, key_index,
                                 is_last, len(chunk), page_num)
        else:
            header = struct.pack("<BBHBB",
                                 0x02, 0x01, len(chunk), is_last, key_index + 1)
            header += b'\x00' * (16 - len(header))
        padded = bytearray(header) + bytearray(chunk)
        if len(padded) < PAGE_SIZE:
            padded += bytearray(PAGE_SIZE - len(padded))
        pages.append(bytes(padded[:PAGE_SIZE]))
        page_num += 1
    return pages


class StreamDockDevice:

    def __init__(self, profile):
        self._profile = profile
        self._device  = None
        self._lock    = threading.Lock()
        self._running = False
        self._cb      = None
        self._prev    = [False] * profile["keys"]

    @property
    def key_count(self):
        return self._profile["keys"]

    @property
    def name(self):
        return self._profile["name"]

    def open(self):
        f = hid_lib.HidDeviceFilter(
            vendor_id=self._profile["vid"],
            product_id=self._profile["pid"]
        )
        devices = f.get_devices()
        if not devices:
            raise RuntimeError(f"Device not found: {self._profile['name']}")
        self._device = devices[0]
        self._device.open()
        self._device.set_raw_data_handler(self._on_data)
        Logger.info(f"Connected to {self.name}")
        out_reports = self._device.find_output_reports()
        Logger.info(f"Output reports found: {len(out_reports)}")
        for i, r in enumerate(out_reports):
            raw = r.get_raw_data()
            Logger.info(f"  Report {i}: ID={raw[0] if raw else 'N/A'} Size={len(raw) if raw else 0}")
        self._running = True
        self.reset()

    def close(self):
        self._running = False
        if self._device:
            try:
                self._device.close()
            except Exception:
                pass

    def set_key_callback(self, cb):
        self._cb = cb

    def _on_data(self, data):
        for i in range(self._profile["keys"]):
            idx = 4 + i
            if idx >= len(data):
                break
            pressed = bool(data[idx])
            if pressed != self._prev[i]:
                self._prev[i] = pressed
                if self._cb:
                    try:
                        self._cb(i, pressed)
                    except Exception as e:
                        Logger.error(f"Callback error: {e}")

    def set_brightness(self, pct):
        pct = max(0, min(100, pct))
        payload = bytearray(PAGE_SIZE)
        if self._profile["page_hdr"] == 8:
            payload[0:6] = [0x03, 0x08, pct, 0x00, 0x00, 0x00]
        else:
            payload[0:5] = [0x05, 0x55, 0xaa, 0xd1, 0x01]
            payload[5]   = pct
        self._write(bytes(payload))

    def reset(self):
        payload = bytearray(PAGE_SIZE)
        if self._profile["page_hdr"] == 8:
            payload[0:2] = [0x03, 0x02]
        else:
            payload[0:5] = [0x0b, 0x63, 0x00, 0x00, 0x00]
        self._write(bytes(payload))

    def set_key_image(self, key_index, pil_image):
        p        = self._profile
        img_data = _encode_image(pil_image, p["img_size"],
                                  p["img_flip_h"], p["img_flip_v"])
        pages    = _build_image_payload(key_index, img_data, p["page_hdr"])
        with self._lock:
            for page in pages:
                self._write(page)

    def clear_key(self, key_index):
        self.set_key_image(key_index,
                           Image.new("RGB", (72, 72), (0, 0, 0)))

    def clear_all(self):
        for i in range(self.key_count):
            self.clear_key(i)

    def _write(self, data):
        if not self._device:
            return
        try:
            out_reports = self._device.find_output_reports()
            if not out_reports:
                self._device.send_output_report([0x00] + list(data))
                return
            report      = out_reports[0]
            rdata       = report.get_raw_data()
            report_id   = rdata[0]
            report_size = len(rdata)
            payload     = [report_id] + list(data[:(report_size - 1)])
            while len(payload) < report_size:
                payload.append(0)
            report.set_raw_data(payload)
            report.send()
        except Exception as e:
            Logger.error(f"Write error: {e}")


def find_device(custom_vid=None, custom_pid=None):
    candidates = list(DEVICES)
    if custom_vid and custom_pid:
        candidates.insert(0, {
            "name":       "Custom Device",
            "vid":        custom_vid,
            "pid":        custom_pid,
            "keys":       15,
            "img_size":   72,
            "img_flip_h": True,
            "img_flip_v": True,
            "page_hdr":   8
        })
    for profile in candidates:
        f = hid_lib.HidDeviceFilter(
            vendor_id=profile["vid"],
            product_id=profile["pid"]
        )
        if f.get_devices():
            Logger.info(f"Found: {profile['name']}")
            return StreamDockDevice(profile)
    Logger.error("No compatible device found.")
    return None
