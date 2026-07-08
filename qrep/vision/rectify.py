"""Rectification: find the quilt-background quad and warp it upright.

The renderer guarantees a uniform #404040 margin, so the quilt is the largest
non-background region. When the detected quad deviates from an axis-aligned
rectangle by less than 1 percent of image size we skip warping entirely
(identity path, confidence 1.0); the L0 test exercises that path.
"""

import cv2
import numpy as np
from pydantic import BaseModel

BACKGROUND_BGR = np.array([0x40, 0x40, 0x40], dtype=np.float32)
IDENTITY_THRESHOLD = 0.01  # fraction of max image dimension


class RectifyResult(BaseModel):
    model_config = {"arbitrary_types_allowed": True}

    image: np.ndarray  # rectified BGR quilt-only image
    mask: np.ndarray  # uint8, 255 inside the quilt quad (output coordinates)
    corners: list[tuple[float, float]]  # detected quad in source px, TL TR BR BL
    identity: bool
    confidence: float


def _order_corners(points: np.ndarray) -> np.ndarray:
    """Order 4 points TL, TR, BR, BL by their sums and differences."""
    sums = points.sum(axis=1)
    diffs = points[:, 0] - points[:, 1]
    return np.array(
        [
            points[np.argmin(sums)],
            points[np.argmax(diffs)],
            points[np.argmax(sums)],
            points[np.argmin(diffs)],
        ],
        dtype=np.float64,
    )


def _detect_quad(image: np.ndarray) -> tuple[np.ndarray, float]:
    """Largest non-background contour approximated to 4 corners.

    Returns (corners TL TR BR BL, fit residual normalized by perimeter)."""
    distance = np.linalg.norm(image.astype(np.float32) - BACKGROUND_BGR, axis=2)
    mask = (distance > 40).astype(np.uint8) * 255
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        raise ValueError("no quilt found: image is entirely background-colored")
    contour = max(contours, key=cv2.contourArea)
    hull = cv2.convexHull(contour)
    peri = cv2.arcLength(hull, True)
    for epsilon_frac in (0.01, 0.02, 0.03, 0.05):
        approx = cv2.approxPolyDP(hull, epsilon_frac * peri, True)
        if len(approx) == 4:
            break
    else:
        # fall back to the minimum-area rectangle when simplification refuses
        approx = cv2.boxPoints(cv2.minAreaRect(contour)).reshape(-1, 1, 2)
    corners = _order_corners(approx.reshape(-1, 2).astype(np.float64))
    # residual: how far the hull strays from the 4-corner polygon
    poly = corners.astype(np.float32)
    residuals = [
        abs(cv2.pointPolygonTest(poly.reshape(-1, 1, 2), (float(p[0][0]), float(p[0][1])), True))
        for p in hull
    ]
    residual_norm = float(np.mean(residuals)) / max(peri, 1.0)
    return corners, residual_norm


def rectify(image: np.ndarray, corners: list[tuple[float, float]] | None = None) -> RectifyResult:
    """Detect (or accept) the quilt quad and return the upright quilt image.

    User-supplied corners are the real-photo escape hatch; round-trip tests
    always call with the image alone.
    """
    max_dim = max(image.shape[0], image.shape[1])
    if corners is not None:
        quad = _order_corners(np.array(corners, dtype=np.float64))
        residual_norm = 0.0
    else:
        quad, residual_norm = _detect_quad(image)

    # deviation of the quad from its own axis-aligned bounding rectangle
    x0, y0 = quad[:, 0].min(), quad[:, 1].min()
    x1, y1 = quad[:, 0].max(), quad[:, 1].max()
    rect = np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1]], dtype=np.float64)
    deviation = float(np.abs(quad - rect).max()) / max_dim

    if deviation < IDENTITY_THRESHOLD:
        cx0, cy0 = int(round(x0)), int(round(y0))
        cropped = image[cy0 : int(round(y1)), cx0 : int(round(x1))]
        # the crop is the quad's bounding box; pixels between the quad and
        # the box are background wedges, and the design doc pins palette
        # extraction to pixels inside the QUAD only, so mask them out
        mask = np.zeros(cropped.shape[:2], dtype=np.uint8)
        local_quad = (quad - np.array([cx0, cy0])).astype(np.int32)
        cv2.fillConvexPoly(mask, local_quad, 255)
        return RectifyResult(
            image=cropped,
            mask=mask,
            corners=[tuple(p) for p in rect],
            identity=True,
            confidence=1.0,
        )

    # output size from mean opposite edge lengths, so pitch survives the warp
    width = int(round((np.linalg.norm(quad[1] - quad[0]) + np.linalg.norm(quad[2] - quad[3])) / 2))
    height = int(round((np.linalg.norm(quad[3] - quad[0]) + np.linalg.norm(quad[2] - quad[1])) / 2))
    target = np.array([[0, 0], [width, 0], [width, height], [0, height]], dtype=np.float32)
    matrix = cv2.getPerspectiveTransform(quad.astype(np.float32), target)
    warped = cv2.warpPerspective(image, matrix, (width, height), flags=cv2.INTER_LINEAR)

    # confidence: 1 - residual, scaled down by warp magnitude, so identity is
    # 1.0 and any real warp lands strictly below it (design doc formula)
    warp_magnitude = float(np.mean(np.linalg.norm(quad - rect, axis=1))) / max_dim
    confidence = max(0.0, (1.0 - min(residual_norm * 10, 1.0)) * (1.0 - warp_magnitude))
    return RectifyResult(
        image=warped,
        # the whole warp target IS the quad interior
        mask=np.full((height, width), 255, dtype=np.uint8),
        corners=[tuple(p) for p in quad],
        identity=False,
        confidence=min(confidence, 0.999),
    )
