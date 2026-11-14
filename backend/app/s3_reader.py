"""Read small sub-arrays (boxes) directly from SPHEREx Level-2 FITS files on AWS S3 via HTTP Range requests.

SPHEREx Level-2 images on AWS S3 are multi-extension FITS (2040x2040 pixels):
  - HDU 0: PRIMARY (metadata header only)
  - HDU 1: IMAGE (uncompressed float32)
  - HDU 2: FLAGS (RICE_1 compressed int32, 1 tile per row)
  - HDU 3: VARIANCE (uncompressed float32)
  - HDU 4: ZODI (uncompressed float32 model background)
  - HDU 5: EPSF (binary table)
  - HDU 6: WCS-WAVE (binary table, spectral WCS key "W")

Reading only the bounding box rows avoids downloading the full ~60 MB file.
CRPIX1/CRPIX2 (sky WCS) and CRPIX1W/CRPIX2W (spectral WCS) are shifted by the
cutout origin (x0, y0) so astrometry and wavelength calculations match the full image.
"""
import io
import re
import threading
import time
from pathlib import Path

import numpy as np
import requests
from astropy.io import fits
from astropy.io.fits.hdu.compressed._codecs import Rice1
from astropy.wcs import WCS

from backend.app.config import PIXEL_SCALE_ARCSEC, RETRIES, S3_BUCKET_URL

NPIX = 2040
_local = threading.local()


class S3ReaderError(RuntimeError):
    """Failed to read or parse FITS data from AWS S3."""


class S3NotInImage(S3ReaderError):
    """The requested coordinates fall outside this image detector."""


def _get_session() -> requests.Session:
    if not hasattr(_local, "session"):
        s = requests.Session()
        adapter = requests.adapters.HTTPAdapter(pool_connections=8, pool_maxsize=8)
        s.mount("https://", adapter)
        s.mount("http://", adapter)
        _local.session = s
    return _local.session


def get_range(key: str, start: int, length: int, tries: int = RETRIES) -> bytes:
    """Download a byte range [start, start + length - 1] from public S3."""
    url = f"{S3_BUCKET_URL}/{key}"
    end = start + length - 1
    last_err = None
    sess = _get_session()

    for attempt in range(tries):
        try:
            resp = sess.get(url, headers={"Range": f"bytes={start}-{end}"}, timeout=60)
            if resp.status_code == 206:
                content = resp.content
                # If reading near the end of the file, S3 returns fewer bytes up to EOF
                if len(content) == length or (len(content) > 0 and len(content) < length):
                    return content
                last_err = f"HTTP 206 returned {len(content)} bytes, expected {length}"
            else:
                last_err = f"HTTP {resp.status_code}: {resp.text[:80]}"
        except requests.RequestException as exc:
            last_err = str(exc)
        time.sleep(0.5 * (2 ** attempt))

    raise S3ReaderError(f"Failed to read bytes {start}-{end} from {key}: {last_err}")


def parse_header(buf: bytes, pos: int = 0) -> tuple[fits.Header, int] | None:
    """Scan 2880-byte FITS blocks for the END card.

    Returns (Header, next_byte_offset) if found, or None.
    """
    i = pos
    while i + 2880 <= len(buf):
        block = buf[i:i + 2880]
        for k in range(0, 2880, 80):
            if block[k:k + 8] == b"END     ":
                header_text = buf[pos:i + 2880].decode("ascii", errors="replace")
                return fits.Header.fromstring(header_text), i + 2880
        i += 2880
    return None


def read_header(key: str, start: int, first: int = 57600) -> tuple[fits.Header, int, bytes]:
    """Read and parse one FITS header starting at byte offset `start`.

    Returns (header, data_offset, remaining_buffer).
    """
    buf = get_range(key, start, first)
    found = parse_header(buf, 0)
    if found is None:
        # Extend read window if header exceeds first block guess
        buf = get_range(key, start, first * 4)
        found = parse_header(buf, 0)

    if found is None:
        raise S3ReaderError(f"No END card found in header starting at byte {start} in {key}")

    header, header_bytes = found
    return header, start + header_bytes, buf[header_bytes:]


def hdu_end(header: fits.Header, data_start: int) -> int:
    """Calculate the byte offset of the next HDU, padded to 2880-byte blocks."""
    bitpix = abs(header.get("BITPIX", 8))
    naxis = header.get("NAXIS", 0)
    data_bytes = 0
    if naxis > 0:
        data_bytes = bitpix // 8
        for i in range(1, naxis + 1):
            data_bytes *= header.get(f"NAXIS{i}", 1)

    data_bytes += header.get("PCOUNT", 0)
    padding = -(-data_bytes // 2880) * 2880
    return data_start + padding


def read_rows(
    key: str, header: fits.Header, data_start: int, after_buf: bytes, y0: int, nrow: int
) -> np.ndarray:
    """Read rows y0 .. y0 + nrow - 1 for an uncompressed or RICE_1 compressed 2040x2040 HDU."""
    if not header.get("ZIMAGE"):
        # Uncompressed 2D image
        bitpix = header["BITPIX"]
        dt = {-32: ">f4", 32: ">i4", 16: ">i2", 8: ">u1"}[bitpix]
        row_bytes = NPIX * (abs(bitpix) // 8)
        start_byte = data_start + y0 * row_bytes
        total_bytes = nrow * row_bytes
        raw = get_range(key, start_byte, total_bytes)
        return np.frombuffer(raw, dtype=dt).reshape(nrow, NPIX)

    # Compressed HDU (SPHEREx uses RICE_1 with 1 tile per row)
    if header.get("ZCMPTYPE") != "RICE_1" or header.get("ZTILE1") != NPIX or header.get("ZTILE2") != 1:
        raise S3ReaderError(
            f"Unsupported compression {header.get('ZCMPTYPE')} "
            f"tile {header.get('ZTILE1')}x{header.get('ZTILE2')}"
        )

    # Row tile descriptors table (2 x int32 per row: byte count, heap offset)
    table_bytes = header["NAXIS1"] * header["NAXIS2"]
    if len(after_buf) >= table_bytes:
        desc_buf = after_buf[:table_bytes]
    else:
        desc_buf = get_range(key, data_start, table_bytes)

    desc = np.frombuffer(desc_buf, dtype=">i4").reshape(header["NAXIS2"], 2)
    count = desc[y0:y0 + nrow, 0]
    offset = desc[y0:y0 + nrow, 1]

    heap_start = data_start + header.get("THEAP", table_bytes)
    lo = int(offset.min())
    hi = int((offset + count).max())
    heap_bytes = get_range(key, heap_start + lo, hi - lo)
    heap_array = np.frombuffer(heap_bytes, dtype=np.uint8)

    # Initialize Rice1 decompressor
    params = {header[f"ZNAME{i}"]: header[f"ZVAL{i}"] for i in range(1, 5) if f"ZNAME{i}" in header}
    blocksize = int(params.get("BLOCKSIZE", 32))
    bytepix = int(params.get("BYTEPIX", header["ZBITPIX"] // 8))
    codec = Rice1(blocksize=blocksize, bytepix=bytepix, tilesize=NPIX)

    rows = [codec.decode(heap_array[o - lo:o - lo + c]) for o, c in zip(offset, count)]
    return np.stack(rows).astype(np.int32)


def read_box(
    key: str,
    ra: float,
    dec: float,
    size_deg: float = 0.05,
    target_path: Path | None = None,
) -> fits.HDUList:
    """Read a small sub-array box around (ra, dec) from an S3 SPHEREx Level-2 FITS file.

    Builds an HDUList containing PRIMARY, IMAGE, FLAGS, VARIANCE, ZODI, and WCS-WAVE.
    If target_path is specified, writes the FITS file atomically to disk.
    """
    # 1. Parse PRIMARY header
    prim_hdr, p_end, _ = read_header(key, 0, 2880)

    # 2. Parse IMAGE header and check sky coordinates
    img_hdr, img_data0, img_after = read_header(key, p_end, 28800)
    w_sky = WCS(img_hdr)
    x, y = w_sky.all_world2pix(ra, dec, 0)
    x = float(x)
    y = float(y)

    if not (0 <= x < NPIX and 0 <= y < NPIX):
        raise S3NotInImage(f"Target ({ra:.5f}, {dec:.5f}) outside detector: pixel ({x:.1f}, {y:.1f})")

    # 3. Calculate bounding box
    box_size = max(5, int(np.round(size_deg * 3600.0 / PIXEL_SCALE_ARCSEC)))
    half = box_size // 2

    xc = int(np.round(x))
    yc = int(np.round(y))

    x0 = max(0, xc - half)
    x1 = min(NPIX - 1, xc + half)
    y0 = max(0, yc - half)
    y1 = min(NPIX - 1, yc + half)

    nrow = y1 - y0 + 1
    ncol = x1 - x0 + 1
    cols = slice(x0, x1 + 1)

    # 4. Read IMAGE slice
    img_data = read_rows(key, img_hdr, img_data0, img_after, y0, nrow)[:, cols].astype(np.float32)

    # 5. Read FLAGS slice
    flg_hdr, flg_data0, flg_after = read_header(key, hdu_end(img_hdr, img_data0), 57600)
    flg_data = read_rows(key, flg_hdr, flg_data0, flg_after, y0, nrow)[:, cols].astype(np.int32)

    # 6. Read VARIANCE slice
    var_hdr, var_data0, var_after = read_header(key, hdu_end(flg_hdr, flg_data0), 28800)
    var_data = read_rows(key, var_hdr, var_data0, var_after, y0, nrow)[:, cols].astype(np.float32)

    # 7. Read ZODI slice
    zodi_hdr, zodi_data0, zodi_after = read_header(key, hdu_end(var_hdr, var_data0), 28800)
    zodi_data = read_rows(key, zodi_hdr, zodi_data0, zodi_after, y0, nrow)[:, cols].astype(np.float32)

    # 8. Step past EPSF and locate WCS-WAVE binary table
    epsf_hdr, epsf_data0, _ = read_header(key, hdu_end(zodi_hdr, zodi_data0), 2880)
    wcs_wave_start = hdu_end(epsf_hdr, epsf_data0)

    # WCS-WAVE table is typically 5760 bytes (2880 header + 2880 data)
    wcs_wave_bytes = get_range(key, wcs_wave_start, 5760)
    wcs_wave_hdu = fits.BinTableHDU.fromstring(wcs_wave_bytes)

    # 9. Shift reference pixel coordinates
    crop_img_hdr = img_hdr.copy()
    crop_img_hdr["CRPIX1"] = img_hdr["CRPIX1"] - x0
    crop_img_hdr["CRPIX2"] = img_hdr["CRPIX2"] - y0
    if "CRPIX1W" in crop_img_hdr:
        crop_img_hdr["CRPIX1W"] = img_hdr.get("CRPIX1W", 1) - x0
    if "CRPIX2W" in crop_img_hdr:
        crop_img_hdr["CRPIX2W"] = img_hdr.get("CRPIX2W", 1) - y0

    # 10. Clean FLAGS header (remove compression metadata)
    crop_flg_hdr = flg_hdr.copy()
    for k in list(crop_flg_hdr.keys()):
        if k.startswith("Z") or k in ("TFIELDS", "TFORM1", "THEAP", "PCOUNT", "GCOUNT"):
            del crop_flg_hdr[k]

    # 11. Assemble HDUList
    hdul = fits.HDUList([
        fits.PrimaryHDU(header=prim_hdr),
        fits.ImageHDU(data=img_data, header=crop_img_hdr, name="IMAGE"),
        fits.ImageHDU(data=flg_data, header=crop_flg_hdr, name="FLAGS"),
        fits.ImageHDU(data=var_data, header=var_hdr.copy(), name="VARIANCE"),
        fits.ImageHDU(data=zodi_data, header=zodi_hdr.copy(), name="ZODI"),
        wcs_wave_hdu,
    ])

    if target_path is not None:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = target_path.with_suffix(".part")
        hdul.writeto(tmp_path, overwrite=True, output_verify="silentfix")
        tmp_path.rename(target_path)

    return hdul

