import jsQR from "jsqr";

export const CAMERA_DENIED_HINT_VI = "Chưa mở được camera. Bạn hãy chọn ảnh chứa mã QR từ thư viện.";

/** Decode QR from raw RGBA pixels. Returns the payload or null. */
export function decodeQrFromImageData(data: Uint8ClampedArray, width: number, height: number): string | null {
  const result = jsQR(data, width, height, { inversionAttempts: "attemptBoth" });
  return result && result.data ? result.data : null;
}

function drawToImageData(
  source: CanvasImageSource,
  width: number,
  height: number,
): ImageData | null {
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  if (!ctx) return null;
  ctx.drawImage(source, 0, 0, width, height);
  return ctx.getImageData(0, 0, width, height);
}

/** Decode a QR code from an image file chosen by the user. */
export async function decodeQrFromImage(file: Blob): Promise<string | null> {
  const bitmap = await createImageBitmap(file);
  try {
    const img = drawToImageData(bitmap, bitmap.width, bitmap.height);
    return img ? decodeQrFromImageData(img.data, img.width, img.height) : null;
  } finally {
    bitmap.close?.();
  }
}

/** Decode one video frame. Returns null while the video has no frame yet. */
export function decodeQrFromVideoFrame(video: HTMLVideoElement): string | null {
  const w = video.videoWidth;
  const h = video.videoHeight;
  if (!w || !h) return null;
  const img = drawToImageData(video, w, h);
  return img ? decodeQrFromImageData(img.data, img.width, img.height) : null;
}

export type CameraResult =
  | { status: "ok"; stream: MediaStream }
  | { status: "denied"; hintVi: string }
  | { status: "unsupported"; hintVi: string };

/** Open the rear camera. When refused or missing, hint the user to pick an image. */
export async function openQrCamera(): Promise<CameraResult> {
  const devices = typeof navigator === "undefined" ? undefined : navigator.mediaDevices;
  if (!devices || typeof devices.getUserMedia !== "function") {
    return { status: "unsupported", hintVi: CAMERA_DENIED_HINT_VI };
  }
  try {
    const stream = await devices.getUserMedia({ video: { facingMode: "environment" }, audio: false });
    return { status: "ok", stream };
  } catch {
    return { status: "denied", hintVi: CAMERA_DENIED_HINT_VI };
  }
}

export function stopCamera(stream: MediaStream): void {
  stream.getTracks().forEach((t) => t.stop());
}

/**
 * Scan frames from a live camera stream until a QR is found, `signal` aborts,
 * or `timeoutMs` elapses. Frames are scheduled with requestAnimationFrame.
 */
export function scanVideoForQr(
  video: HTMLVideoElement,
  signal: AbortSignal,
  timeoutMs = 30_000,
): Promise<string | null> {
  return new Promise((resolve) => {
    const started = performance.now();
    const tick = (): void => {
      if (signal.aborted || performance.now() - started > timeoutMs) {
        resolve(null);
        return;
      }
      const found = decodeQrFromVideoFrame(video);
      if (found) {
        resolve(found);
        return;
      }
      requestAnimationFrame(tick);
    };
    tick();
  });
}
