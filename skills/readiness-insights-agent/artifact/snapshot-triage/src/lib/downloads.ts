declare global {
  interface Window {
    claude?: {
      use?: (name: string) => Promise<unknown>;
    };
  }
}

interface DownloadsCapability {
  save: (opts: { filename: string; data: string }) => Promise<void>;
}

/** Saves via the artifact's downloads capability when granted, else copies to the clipboard. */
export async function offerDownload(filename: string, data: string): Promise<string> {
  try {
    const downloads = (await window.claude?.use?.("downloads")) as DownloadsCapability | null;
    if (downloads) {
      await downloads.save({ filename, data });
      return `Saved ${filename}.`;
    }
  } catch (err) {
    const code = (err as { code?: string } | undefined)?.code;
    return code === "user_rejected" ? "Save cancelled." : "That save did not go through — try again.";
  }
  try {
    await navigator.clipboard.writeText(data);
    return `Downloads are not available here — ${filename} copied to your clipboard instead.`;
  } catch {
    return "Downloads are not available in this view, and the clipboard was blocked too. Select the page content manually.";
  }
}

export {};
