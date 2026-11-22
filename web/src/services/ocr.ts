import { createWorker, type Worker } from "tesseract.js";

export const OCR_LANG = "vie";

let workerPromise: Promise<Worker> | null = null;

async function tessdataAvailable(): Promise<boolean> {
  try {
    const res = await fetch("/tessdata/vie.traineddata.gz", { method: "HEAD" });
    return res.ok;
  } catch {
    return false;
  }
}

/** Lazily create one `vie` worker and reuse it. */
export function getOcrWorker(): Promise<Worker> {
  if (!workerPromise) {
    workerPromise = (async () => {
      const local = await tessdataAvailable();
      return createWorker(OCR_LANG, undefined, local ? { langPath: "/tessdata" } : {});
    })();
    workerPromise.catch(() => {
      workerPromise = null;
    });
  }
  return workerPromise;
}

export async function recognizeText(image: Blob | string | HTMLCanvasElement | HTMLImageElement): Promise<string> {
  const worker = await getOcrWorker();
  const { data } = await worker.recognize(image);
  return data.text;
}

export async function terminateOcrWorker(): Promise<void> {
  const pending = workerPromise;
  workerPromise = null;
  if (pending) {
    try {
      await (await pending).terminate();
    } catch {
      /* already gone */
    }
  }
}
