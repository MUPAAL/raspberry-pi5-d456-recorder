"""Minimal Linux V4L2 MMAP capture with driver sequence/timestamp metadata.

This module intentionally bypasses OpenCV VideoCapture so callers can inspect
the ``v4l2_buffer.sequence`` and ``v4l2_buffer.timestamp`` values returned by
VIDIOC_DQBUF.  It supports the common UVC formats MJPEG, YUYV, BGR24, RGB24 and
GREY at 640x480.
"""

import ctypes
import errno
import mmap
import os
import select
import sys
import time

import cv2
import numpy as np


# ioctl encoding from Linux asm-generic/ioctl.h
_IOC_NRBITS = 8
_IOC_TYPEBITS = 8
_IOC_SIZEBITS = 14
_IOC_NRSHIFT = 0
_IOC_TYPESHIFT = _IOC_NRSHIFT + _IOC_NRBITS
_IOC_SIZESHIFT = _IOC_TYPESHIFT + _IOC_TYPEBITS
_IOC_DIRSHIFT = _IOC_SIZESHIFT + _IOC_SIZEBITS
_IOC_WRITE = 1
_IOC_READ = 2


def _ioc(direction, type_char, number, size):
    return (
        (direction << _IOC_DIRSHIFT)
        | (ord(type_char) << _IOC_TYPESHIFT)
        | (number << _IOC_NRSHIFT)
        | (size << _IOC_SIZESHIFT)
    )


def _ior(type_char, number, struct_type):
    return _ioc(_IOC_READ, type_char, number, ctypes.sizeof(struct_type))


def _iow(type_char, number, struct_type):
    return _ioc(_IOC_WRITE, type_char, number, ctypes.sizeof(struct_type))


def _iowr(type_char, number, struct_type):
    return _ioc(
        _IOC_READ | _IOC_WRITE,
        type_char,
        number,
        ctypes.sizeof(struct_type),
    )


def fourcc(text):
    if len(text) != 4:
        raise ValueError("fourcc must contain exactly four characters")
    return sum(ord(char) << (8 * index) for index, char in enumerate(text))


def fourcc_text(value):
    return "".join(chr((value >> (8 * index)) & 0xFF) for index in range(4))


class V4L2Capability(ctypes.Structure):
    _fields_ = [
        ("driver", ctypes.c_uint8 * 16),
        ("card", ctypes.c_uint8 * 32),
        ("bus_info", ctypes.c_uint8 * 32),
        ("version", ctypes.c_uint32),
        ("capabilities", ctypes.c_uint32),
        ("device_caps", ctypes.c_uint32),
        ("reserved", ctypes.c_uint32 * 3),
    ]


class V4L2PixFormat(ctypes.Structure):
    _fields_ = [
        ("width", ctypes.c_uint32),
        ("height", ctypes.c_uint32),
        ("pixelformat", ctypes.c_uint32),
        ("field", ctypes.c_uint32),
        ("bytesperline", ctypes.c_uint32),
        ("sizeimage", ctypes.c_uint32),
        ("colorspace", ctypes.c_uint32),
        ("priv", ctypes.c_uint32),
        ("flags", ctypes.c_uint32),
        ("ycbcr_enc", ctypes.c_uint32),
        ("quantization", ctypes.c_uint32),
        ("xfer_func", ctypes.c_uint32),
    ]


class V4L2FormatUnion(ctypes.Union):
    _fields_ = [
        ("pix", V4L2PixFormat),
        ("raw_data", ctypes.c_uint8 * 200),
        # Preserve the native union alignment used by pointer-bearing formats.
        ("alignment", ctypes.c_uint64),
    ]


class V4L2Format(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_uint32),
        ("fmt", V4L2FormatUnion),
    ]


class V4L2RequestBuffers(ctypes.Structure):
    _fields_ = [
        ("count", ctypes.c_uint32),
        ("type", ctypes.c_uint32),
        ("memory", ctypes.c_uint32),
        ("capabilities", ctypes.c_uint32),
        ("flags", ctypes.c_uint8),
        ("reserved", ctypes.c_uint8 * 3),
    ]


class TimeVal(ctypes.Structure):
    _fields_ = [
        ("tv_sec", ctypes.c_long),
        ("tv_usec", ctypes.c_long),
    ]


class V4L2TimeCode(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_uint32),
        ("flags", ctypes.c_uint32),
        ("frames", ctypes.c_uint8),
        ("seconds", ctypes.c_uint8),
        ("minutes", ctypes.c_uint8),
        ("hours", ctypes.c_uint8),
        ("userbits", ctypes.c_uint8 * 4),
    ]


class V4L2BufferMemory(ctypes.Union):
    _fields_ = [
        ("offset", ctypes.c_uint32),
        ("userptr", ctypes.c_ulong),
        ("planes", ctypes.c_void_p),
        ("fd", ctypes.c_int32),
    ]


class V4L2Buffer(ctypes.Structure):
    _fields_ = [
        ("index", ctypes.c_uint32),
        ("type", ctypes.c_uint32),
        ("bytesused", ctypes.c_uint32),
        ("flags", ctypes.c_uint32),
        ("field", ctypes.c_uint32),
        ("timestamp", TimeVal),
        ("timecode", V4L2TimeCode),
        ("sequence", ctypes.c_uint32),
        ("memory", ctypes.c_uint32),
        ("memory_union", V4L2BufferMemory),
        ("length", ctypes.c_uint32),
        ("reserved2", ctypes.c_uint32),
        ("request_fd", ctypes.c_int32),
    ]


class V4L2Fract(ctypes.Structure):
    _fields_ = [
        ("numerator", ctypes.c_uint32),
        ("denominator", ctypes.c_uint32),
    ]


class V4L2CaptureParm(ctypes.Structure):
    _fields_ = [
        ("capability", ctypes.c_uint32),
        ("capturemode", ctypes.c_uint32),
        ("timeperframe", V4L2Fract),
        ("extendedmode", ctypes.c_uint32),
        ("readbuffers", ctypes.c_uint32),
        ("reserved", ctypes.c_uint32 * 4),
    ]


class V4L2StreamParmUnion(ctypes.Union):
    _fields_ = [
        ("capture", V4L2CaptureParm),
        ("raw_data", ctypes.c_uint8 * 200),
    ]


class V4L2StreamParm(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_uint32),
        ("parm", V4L2StreamParmUnion),
    ]


V4L2_BUF_TYPE_VIDEO_CAPTURE = 1
V4L2_MEMORY_MMAP = 1
V4L2_FIELD_ANY = 0
V4L2_CAP_VIDEO_CAPTURE = 0x00000001
V4L2_CAP_STREAMING = 0x04000000
V4L2_CAP_DEVICE_CAPS = 0x80000000
V4L2_BUF_FLAG_ERROR = 0x00000040

VIDIOC_QUERYCAP = _ior("V", 0, V4L2Capability)
VIDIOC_S_FMT = _iowr("V", 5, V4L2Format)
VIDIOC_REQBUFS = _iowr("V", 8, V4L2RequestBuffers)
VIDIOC_QUERYBUF = _iowr("V", 9, V4L2Buffer)
VIDIOC_QBUF = _iowr("V", 15, V4L2Buffer)
VIDIOC_DQBUF = _iowr("V", 17, V4L2Buffer)
VIDIOC_STREAMON = _iow("V", 18, ctypes.c_int)
VIDIOC_STREAMOFF = _iow("V", 19, ctypes.c_int)
VIDIOC_S_PARM = _iowr("V", 22, V4L2StreamParm)


class V4L2SequenceCapture:
    """Capture decoded BGR frames plus V4L2 sequence and capture timestamp."""

    def __init__(
        self,
        device,
        width=640,
        height=480,
        fps=30,
        pixel_format="MJPG",
        buffer_count=4,
    ):
        if not sys.platform.startswith("linux"):
            raise RuntimeError("Direct V4L2 capture is supported only on Linux")

        self.device = device
        self.width = int(width)
        self.height = int(height)
        self.fps = int(fps)
        self.pixel_format = pixel_format
        self.buffer_count = int(buffer_count)
        self.fd = None
        self.mapped_buffers = []
        self.streaming = False

        self._libc = ctypes.CDLL(None, use_errno=True)
        self._libc.ioctl.argtypes = [
            ctypes.c_int,
            ctypes.c_ulong,
            ctypes.c_void_p,
        ]
        self._libc.ioctl.restype = ctypes.c_int

        self._open()

    def _ioctl(self, request, value):
        result = self._libc.ioctl(self.fd, request, ctypes.byref(value))
        if result < 0:
            error_number = ctypes.get_errno()
            raise OSError(error_number, os.strerror(error_number))

    def _open(self):
        try:
            self.fd = os.open(self.device, os.O_RDWR | os.O_NONBLOCK)

            capability = V4L2Capability()
            self._ioctl(VIDIOC_QUERYCAP, capability)
            caps = capability.device_caps
            if not (capability.capabilities & V4L2_CAP_DEVICE_CAPS):
                caps = capability.capabilities
            if not (caps & V4L2_CAP_VIDEO_CAPTURE):
                raise RuntimeError("Device is not a single-planar video capture device")
            if not (caps & V4L2_CAP_STREAMING):
                raise RuntimeError("Device does not support V4L2 streaming I/O")

            video_format = V4L2Format()
            video_format.type = V4L2_BUF_TYPE_VIDEO_CAPTURE
            video_format.fmt.pix.width = self.width
            video_format.fmt.pix.height = self.height
            video_format.fmt.pix.pixelformat = fourcc(self.pixel_format)
            video_format.fmt.pix.field = V4L2_FIELD_ANY
            self._ioctl(VIDIOC_S_FMT, video_format)

            self.width = int(video_format.fmt.pix.width)
            self.height = int(video_format.fmt.pix.height)
            self.pixel_format = fourcc_text(video_format.fmt.pix.pixelformat)
            if self.pixel_format not in {"MJPG", "JPEG", "YUYV", "BGR3", "RGB3", "GREY"}:
                raise RuntimeError(
                    "Unsupported camera pixel format returned by driver: "
                    + repr(self.pixel_format)
                )

            stream_parm = V4L2StreamParm()
            stream_parm.type = V4L2_BUF_TYPE_VIDEO_CAPTURE
            stream_parm.parm.capture.timeperframe.numerator = 1
            stream_parm.parm.capture.timeperframe.denominator = self.fps
            try:
                self._ioctl(VIDIOC_S_PARM, stream_parm)
            except OSError:
                # Some UVC drivers reject S_PARM while already enforcing the
                # selected profile's default frame rate.
                pass

            request = V4L2RequestBuffers()
            request.count = self.buffer_count
            request.type = V4L2_BUF_TYPE_VIDEO_CAPTURE
            request.memory = V4L2_MEMORY_MMAP
            self._ioctl(VIDIOC_REQBUFS, request)
            if request.count < 2:
                raise RuntimeError("V4L2 driver provided fewer than two buffers")

            for index in range(request.count):
                buffer_info = V4L2Buffer()
                buffer_info.type = V4L2_BUF_TYPE_VIDEO_CAPTURE
                buffer_info.memory = V4L2_MEMORY_MMAP
                buffer_info.index = index
                self._ioctl(VIDIOC_QUERYBUF, buffer_info)

                mapped = mmap.mmap(
                    self.fd,
                    buffer_info.length,
                    flags=mmap.MAP_SHARED,
                    prot=mmap.PROT_READ | mmap.PROT_WRITE,
                    offset=buffer_info.memory_union.offset,
                )
                self.mapped_buffers.append(mapped)

                queue_buffer = V4L2Buffer()
                queue_buffer.type = V4L2_BUF_TYPE_VIDEO_CAPTURE
                queue_buffer.memory = V4L2_MEMORY_MMAP
                queue_buffer.index = index
                self._ioctl(VIDIOC_QBUF, queue_buffer)

            stream_type = ctypes.c_int(V4L2_BUF_TYPE_VIDEO_CAPTURE)
            self._ioctl(VIDIOC_STREAMON, stream_type)
            self.streaming = True
        except Exception:
            self.close()
            raise

    def read(self, timeout=2.0):
        """Return ``(bgr_frame, sequence, timestamp_seconds)``."""
        deadline = time.monotonic() + timeout

        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("Timed out waiting for a V4L2 frame")

            readable, _, _ = select.select([self.fd], [], [], remaining)
            if not readable:
                raise TimeoutError("Timed out waiting for a V4L2 frame")

            buffer_info = V4L2Buffer()
            buffer_info.type = V4L2_BUF_TYPE_VIDEO_CAPTURE
            buffer_info.memory = V4L2_MEMORY_MMAP

            try:
                self._ioctl(VIDIOC_DQBUF, buffer_info)
            except OSError as exc:
                if exc.errno == errno.EAGAIN:
                    continue
                raise

            try:
                if buffer_info.index >= len(self.mapped_buffers):
                    raise RuntimeError("V4L2 returned an invalid buffer index")
                if buffer_info.flags & V4L2_BUF_FLAG_ERROR:
                    raise RuntimeError("V4L2 marked the captured buffer as corrupt")

                mapped = self.mapped_buffers[buffer_info.index]
                encoded = bytes(mapped[: buffer_info.bytesused])
                frame = self._decode(encoded)
                sequence = int(buffer_info.sequence)
                timestamp = (
                    float(buffer_info.timestamp.tv_sec)
                    + float(buffer_info.timestamp.tv_usec) / 1_000_000.0
                )
            finally:
                requeue = V4L2Buffer()
                requeue.type = V4L2_BUF_TYPE_VIDEO_CAPTURE
                requeue.memory = V4L2_MEMORY_MMAP
                requeue.index = buffer_info.index
                self._ioctl(VIDIOC_QBUF, requeue)

            return frame, sequence, timestamp

    def _decode(self, encoded):
        if self.pixel_format in {"MJPG", "JPEG"}:
            compressed = np.frombuffer(encoded, dtype=np.uint8)
            frame = cv2.imdecode(compressed, cv2.IMREAD_COLOR)
            if frame is None:
                raise RuntimeError("OpenCV failed to decode an MJPEG frame")
            return frame

        if self.pixel_format == "YUYV":
            required = self.width * self.height * 2
            if len(encoded) < required:
                raise RuntimeError("Short YUYV frame")
            yuyv = np.frombuffer(encoded[:required], dtype=np.uint8)
            yuyv = yuyv.reshape(self.height, self.width, 2)
            return cv2.cvtColor(yuyv, cv2.COLOR_YUV2BGR_YUY2)

        if self.pixel_format in {"BGR3", "RGB3"}:
            required = self.width * self.height * 3
            if len(encoded) < required:
                raise RuntimeError("Short 24-bit RGB frame")
            frame = np.frombuffer(encoded[:required], dtype=np.uint8)
            frame = frame.reshape(self.height, self.width, 3).copy()
            if self.pixel_format == "RGB3":
                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            return frame

        if self.pixel_format == "GREY":
            required = self.width * self.height
            if len(encoded) < required:
                raise RuntimeError("Short GREY frame")
            grey = np.frombuffer(encoded[:required], dtype=np.uint8)
            grey = grey.reshape(self.height, self.width)
            return cv2.cvtColor(grey, cv2.COLOR_GRAY2BGR)

        raise RuntimeError("Unsupported V4L2 pixel format: " + self.pixel_format)

    def close(self):
        if self.fd is not None and self.streaming:
            try:
                stream_type = ctypes.c_int(V4L2_BUF_TYPE_VIDEO_CAPTURE)
                self._ioctl(VIDIOC_STREAMOFF, stream_type)
            except Exception:
                pass
            self.streaming = False

        for mapped in self.mapped_buffers:
            try:
                mapped.close()
            except Exception:
                pass
        self.mapped_buffers.clear()

        if self.fd is not None:
            try:
                os.close(self.fd)
            except Exception:
                pass
            self.fd = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

