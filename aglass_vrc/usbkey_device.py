"""Experimental USB/IP USB Key: read-only media plus captured SCSI responses.

This serves a device on localhost. Windows still needs a USB/IP import driver;
starting this program alone does not create a Windows device or authorize Runtime.
No vendor DLL or process injection is used. See docs/USBKEY_DEVICE.md.
"""
import argparse
from collections import Counter
import hashlib
import json
import logging
from pathlib import Path
import struct
import time

LOG = logging.getLogger(__name__)
from .app_paths import application_root
# Portable response file takes precedence; bundled JSON remains a fallback.
_PORTABLE_KEY = application_root() / "aglass_key.bin"
TRACE = _PORTABLE_KEY if _PORTABLE_KEY.is_file() else Path(__file__).with_name("key_protocol.json")


class ReadOnlyImage:
    read_only = True

    def __init__(self, path, medium="disk"):
        if medium not in ("disk", "cdrom"):
            raise ValueError("medium must be disk or cdrom")
        self.path = Path(path) if path else None
        self.medium = medium
        self.block_size = 512 if medium == "disk" else 2048
        if self.path and not 0 < self.path.stat().st_size <= 64 * 1024 * 1024:
            raise ValueError("USB Key image must be nonempty and at most 64 MiB")
        self.data = self.path.read_bytes() if self.path else bytes(8 * 1024 * 1024)
        if len(self.data) % self.block_size:
            raise ValueError(f"image size must be a multiple of {self.block_size}")
        self.num_blocks = len(self.data) // self.block_size
        self.sha256 = hashlib.sha256(self.data).hexdigest()

    def read(self, lba, count):
        if lba < 0 or count < 0 or lba + count > self.num_blocks:
            raise ValueError("read outside image")
        return self.data[lba * self.block_size:(lba + count) * self.block_size]

    def write(self, lba, count, data):
        raise PermissionError("USB Key image is read-only")

    def report(self):
        sectors = [self.data[i:i + 512] for i in range(0, len(self.data), 512)]
        markers = (b"CD001", b"NSR02", b"NSR03", b"FAT12", b"FAT16", b"FAT32",
                   b"NTFS", b"EXFAT", b"EFI PART", b"conectix", b"vhdxfile")
        return {"image": str(self.path.resolve()) if self.path else "blank", "bytes": len(self.data),
                "sha256": self.sha256, "medium": self.medium,
                "block_size": self.block_size, "blocks": self.num_blocks,
                "unique_512_blocks": len(Counter(sectors)),
                "same_first_64_bytes_every_512_block": all(s[:64] == sectors[0][:64] for s in sectors),
                "mbr_signature": self.data[510:512].hex(),
                "signature_offsets": {m.decode(): self.data.find(m) for m in markers}}


class RecordedKey:
    """Only the observed EF/21 identity and EF/22 read/update exchanges.

    Responses come from the user's trace, not from the block image. This is a
    replay model, not a recovered firmware or general cryptographic implementation.
    """
    def __init__(self, path=TRACE):
        path = Path(path)
        if path.stat().st_size > 1024 * 1024:
            raise ValueError("Key response file must be at most 1 MiB; media BIN belongs in the image field")
        raw = path.read_bytes()
        self.replies = {}
        if raw.startswith(b"AGLASSKEY1"):
            if len(raw) < 11 or raw[10] != 6:
                raise ValueError("invalid AGLASSKEY1 response count")
            offset = 11
            for address, expected in zip(((2, 0x21), (3, 0x21), (2, 0x22), (3, 0x22), (2, 0x22), (3, 0x22)), (4, 19, 4, 142, 4, 6)):
                if offset + 2 > len(raw):
                    raise ValueError("truncated AGLASSKEY1 record")
                size = int.from_bytes(raw[offset:offset + 2], "little")
                offset += 2
                if size != expected or offset + size > len(raw):
                    raise ValueError("invalid AGLASSKEY1 record length")
                self.replies.setdefault(address, []).append(raw[offset:offset + size])
                offset += size
            if offset != len(raw):
                raise ValueError("trailing AGLASSKEY1 data")
        else:
            records = json.loads(raw.decode("utf-8-sig"))
            if not isinstance(records, list):
                raise ValueError("Key JSON must be an array of command records")
            for row in records:
                cdb = bytes.fromhex(row["cdb"])
                if row.get("dataIn") == 1 and row.get("in_hex") and cdb[:1] == b"\xef":
                    if len(cdb) != 10:
                        raise ValueError("invalid trace CDB length")
                    reply = bytes.fromhex(row["in_hex"])
                    if len(reply) != row["xfer"]:
                        raise ValueError("trace response length does not match xfer")
                    self.replies.setdefault((cdb[1], cdb[2]), []).append(reply)
        for rec, lengths in ((0x21, (4, 19)), (0x22, (4, 142))):
            for sub, length in zip((2, 3), lengths):
                replies = self.replies.get((sub, rec), [])
                if not replies or len(replies[0]) != length:
                    raise ValueError("trace is missing the expected USB Key response")
        if (len(self.replies[(2, 0x22)]) != 2 or len(self.replies[(3, 0x22)]) != 2
                or len(self.replies[(2, 0x22)][1]) != 4 or len(self.replies[(3, 0x22)][1]) != 6):
            raise ValueError("trace is missing the EF/22 update acknowledgement")
        self.commands = 0
        self.completed = 0
        self.reset()

    def reset(self):
        self.selected = None
        self.update = False

    def exchange(self, cdb, data_in, payload=b""):
        if len(cdb) != 10 or cdb[0] != 0xef or cdb[1] not in (1, 2, 3) or cdb[2] not in (0x21, 0x22):
            raise ValueError("unrecorded vendor command")
        sub, rec = cdb[1:3]
        if data_in:
            if sub not in (2, 3) or self.selected != rec or payload:
                raise ValueError("vendor read without matching request")
            result = self.replies[(sub, rec)][int(rec == 0x22 and self.update)]
        else:
            if sub != 1:
                raise ValueError("vendor command direction is invalid")
            if rec == 0x21:
                if payload:
                    raise ValueError("identity request must not contain a payload")
                self.update = False
            else:
                # E1/FF are Runtime 1.1 session commands observed after the
                # original E0 update. The supplied emulator uses the same ACK.
                if len(payload) != 143 or payload[:5] != b"\x80\x08\x00\x00\x8a" or payload[5] not in (0, 0xe0, 0xe1, 0xff):
                    raise ValueError(f"unrecorded EF/22 request layout (bytes={len(payload)}, header={payload[:6].hex()})")
                self.update = payload[5] != 0
            self.selected = rec
            result = b""
        self.commands += 1
        if data_in and rec == 0x22 and sub == 3 and self.update:
            self.completed += 1
        LOG.info("USB Key EF/%02X sub=%d %s bytes=%d", rec, sub,
                 "IN" if data_in else "OUT", len(result) if data_in else len(payload))
        return result


def make_device(image, key, medium="disk"):
    # Optional dependency; the existing OSC bridge does not import it.
    from usbip import USBDevice
    from usbip.classes.device.msc import MSC, SENSE_INVALID_FIELD, SENSE_OK

    class KeyStorage(MSC):
        def __init__(self):
            super().__init__(image, medium=medium, read_only=True, vendor="Generic",
                             product="Usb Key", revision="1.09", serial="AGLASS2OSC01",
                             on_command=LOG.debug)
            self.pending_key = None

        def on_reset(self):
            self.pending_key = self._write = None
            key.reset()
            for unit in self.luns:
                unit.sense = SENSE_OK

        def on_control(self, setup, data=b""):
            if setup.bRequest == 0xff:
                self.on_reset()
            return super().on_control(setup, data)

        def _handle_cbw(self, cbw):
            # Reject malformed CBWs and cap allocation before the library dispatch.
            if (len(cbw) != 31 or cbw[:4] != b"USBC" or not 6 <= cbw[14] <= 16
                    or int.from_bytes(cbw[8:12], "little") > 1024 * 1024):
                self.in_ep.stall()
                self.out_ep.stall()
                return
            return super()._handle_cbw(cbw)

        def _dispatch(self, lun, tag, dlen, cdb):
            if cdb[0] != 0xef:
                # Accesses beyond the CDB in MSC 0.7.0 must not reach IndexError.
                needed = 16 if cdb[0] == 0x9e else 12 if cdb[0] in (0xa8, 0xaa) else 10 if cdb[0] >= 0x20 else 6
                if len(cdb) < needed:
                    self._fail(lun, tag, dlen, SENSE_INVALID_FIELD, "short CDB")
                    return
                return super()._dispatch(lun, tag, dlen, cdb)
            if len(cdb) != 10 or dlen > 143:
                self._fail(lun, tag, dlen, SENSE_INVALID_FIELD, "USB Key request length")
            elif self._cbw_in:
                self.finish_key(lun, tag, dlen, cdb, True)
            elif dlen:
                self.pending_key = (lun, tag, dlen, cdb, bytearray())
            else:
                self.finish_key(lun, tag, dlen, cdb, False)

        def finish_key(self, lun, tag, dlen, cdb, data_in, payload=b""):
            try:
                reply = key.exchange(cdb, data_in, payload)
            except ValueError as exc:
                LOG.warning("USB Key unsupported exchange: %s", exc)
                # OUT data was already consumed, so do not stall a finished phase.
                self._fail(lun, tag, dlen if data_in else 0, SENSE_INVALID_FIELD, "USB Key")
                return
            if data_in:
                self._data_in(tag, dlen, reply)
            else:
                self._csw(tag, 0, 0)

        def on_out(self, ep, data):
            if self.pending_key is None:
                return super().on_out(ep, data)
            lun, tag, need, cdb, buf = self.pending_key
            if len(buf) + len(data) > need:
                self.pending_key = None
                self._fail(lun, tag, 0, SENSE_INVALID_FIELD, "USB Key excessive OUT data")
                return
            buf.extend(data)
            if len(buf) == need:
                self.pending_key = None
                self.finish_key(lun, tag, need, cdb, False, bytes(buf))

    dev = USBDevice(0x2012, 0x2011, manufacturer="Generic", product="Usb Key",
                    serial="AGLASS2OSC01", bcdDevice=0x0109)
    dev.set_busid("1-1")
    dev.add(KeyStorage())
    return dev


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", type=Path, required=True, help="local raw BIN; always read-only")
    parser.add_argument("--medium", choices=("disk", "cdrom"), default="disk")
    parser.add_argument("--trace", type=Path, default=TRACE)
    parser.add_argument("--port", type=int, default=3240, help="localhost USB/IP port")
    parser.add_argument("--inspect", action="store_true", help="report image only; no listener or driver")
    parser.add_argument("--duration", type=float, default=0, help="stop after seconds; 0 waits for Ctrl+C")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535 or args.duration < 0:
        parser.error("invalid port or duration")
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    try:
        image = ReadOnlyImage(args.image, args.medium)
        if args.inspect:
            print(json.dumps(image.report(), ensure_ascii=False, indent=2))
            return 0
        key = RecordedKey(args.trace)
        try:
            from usbip.transport import USBIP
        except ImportError as exc:
            raise RuntimeError("Install optional requirements-usbkey.txt first") from exc
        device = make_device(image, key, args.medium)
        with device.plug(via=USBIP("127.0.0.1", args.port)):
            LOG.info("Experimental USB Key: 127.0.0.1:%d busid=1-1 medium=%s read-only=%d bytes sha256=%s",
                     args.port, args.medium, len(image.data), image.sha256)
            LOG.info("USB/IP server ready; Windows device creation requires a USB/IP client driver. Runtime authorization is unverified.")
            deadline = time.monotonic() + args.duration if args.duration else None
            try:
                while deadline is None or time.monotonic() < deadline:
                    time.sleep(.1)
            except KeyboardInterrupt:
                pass
        LOG.info("USB Key server stopped; handled %d recorded vendor commands", key.commands)
        return 0
    except (OSError, ValueError, RuntimeError, KeyError) as exc:
        LOG.error("USB Key: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
