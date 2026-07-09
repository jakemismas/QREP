/*
 * Open-project modal (S2, issue #42). The hidden file input covers the whole
 * drop zone so both click-to-browse and native drag-drop-onto-input work
 * through one control. A parse failure surfaces the "malformed JSON" envelope
 * message via the toast (never a traceback) and leaves the modal open.
 */
import { Modal, useToast } from "../ui";
import { useProject } from "../state/project";

export function OpenModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { openFromText, openDemo } = useProject();
  const toast = useToast();

  async function handleFile(input: HTMLInputElement) {
    const file = input.files?.[0];
    input.value = "";
    if (!file) return;
    let text: string;
    try {
      text = await file.text();
    } catch {
      toast.push("Couldn’t read that file.", "error");
      return;
    }
    if (openFromText(text, file.name)) onClose();
  }

  async function loadSample() {
    if (await openDemo()) onClose();
  }

  return (
    <Modal open={open} onClose={onClose} title="Open a project">
      <div data-testid="open-modal" className="open-modal-body">
        <p className="open-modal-lead">
          QREP projects are plain .json files — easy to email, back up, or share with a
          friend.
        </p>

        <label className="dropzone">
          <svg width="34" height="30" viewBox="0 0 34 30" fill="none" aria-hidden="true">
            <path
              d="M17 20V8m0 0-5 5m5-5 5 5M4 20v4a2 2 0 0 0 2 2h22a2 2 0 0 0 2-2v-4"
              stroke="currentColor"
              strokeWidth="2.2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          <span className="dropzone-title">Drop a .json project here</span>
          <span className="dropzone-sub">or tap to browse</span>
          <input
            type="file"
            data-testid="open-file-input"
            className="dropzone-input"
            accept=".json,application/json"
            onChange={(event) => {
              void handleFile(event.currentTarget);
            }}
          />
        </label>

        <div className="open-modal-footer">
          <button
            type="button"
            data-testid="load-sample"
            className="btn btn--secondary"
            onClick={() => {
              void loadSample();
            }}
          >
            Load the sample project
          </button>
        </div>
      </div>
    </Modal>
  );
}
