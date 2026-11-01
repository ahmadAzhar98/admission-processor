"""Image-quality measurements with OpenCV.

All measures except resolution are taken on a copy scaled so its longer
side is 1000 px, so thresholds mean the same for a 12-megapixel phone
photo and a 150-dpi scan. The definitions were calibrated on the
synthetic dataset (see the quality section of docs/evaluation).
"""

import math

import cv2
import numpy as np
import numpy.typing as npt
from common.errors import InvalidRequestError

Gray = npt.NDArray[np.uint8]

NORMALISED_SIDE = 1000


def decode_gray(data: bytes) -> Gray:
    """Decode image bytes to an 8-bit grayscale array.

    Raises:
        InvalidRequestError: If the bytes are not a decodable image.
    """
    buffer = np.frombuffer(data, dtype=np.uint8)
    image = cv2.imdecode(buffer, cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise InvalidRequestError("file is not a readable image")
    return image.astype(np.uint8)


def normalise(gray: Gray) -> Gray:
    """Scale so the longer side is :data:`NORMALISED_SIDE` pixels."""
    scale = NORMALISED_SIDE / max(gray.shape)
    resized = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    return resized.astype(np.uint8)


def contrast(gray: Gray) -> float:
    """Spread between the 1st and 99th intensity percentiles (0-255).

    Percentiles rather than standard deviation, because a clean page is
    mostly white paper and its standard deviation is low even when the ink
    is perfectly crisp.
    """
    low, high = np.percentile(gray, [1, 99])
    return float(high - low)


def blur_score(gray: Gray) -> float:
    """Contrast-normalised variance of the Laplacian after light smoothing.

    The 5x5 Gaussian suppresses sensor noise, which otherwise looks like
    sharp detail; dividing by squared relative contrast stops faded but
    sharp scans from being reported as blurry. Higher is sharper.
    """
    smoothed = cv2.GaussianBlur(gray, (5, 5), 0)
    variance = float(cv2.Laplacian(smoothed, cv2.CV_64F).var())
    relative_contrast = max(contrast(gray), 13.0) / 255.0
    return variance / relative_contrast**2


def skew_degrees(gray: Gray) -> float:
    """Estimate page rotation from near-horizontal line segments.

    Text baselines, table rules and borders produce long near-horizontal
    segments; the length-weighted median of their angles is the skew.
    Returns 0 when no such segments are found.
    """
    edges = cv2.Canny(gray, 50, 150)
    lines = cv2.HoughLinesP(
        edges, 1, np.pi / 1800, threshold=100, minLineLength=gray.shape[1] // 8, maxLineGap=10
    )
    if lines is None:
        return 0.0
    angles: list[tuple[float, float]] = []
    for x1, y1, x2, y2 in lines.reshape(-1, 4):
        angle = math.degrees(math.atan2(float(y2 - y1), float(x2 - x1)))
        if abs(angle) <= 30:
            angles.append((angle, math.hypot(float(x2 - x1), float(y2 - y1))))
    if not angles:
        return 0.0
    angles.sort()
    weights = np.cumsum([w for _, w in angles])
    return angles[int(np.searchsorted(weights, weights[-1] / 2))][0]
