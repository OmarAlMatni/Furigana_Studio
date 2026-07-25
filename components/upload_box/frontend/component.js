document.addEventListener("DOMContentLoaded", () => {
  const dropZone = document.getElementById("drop-zone");
  const fileInput = document.getElementById("file-input");
  const fileInfo = document.getElementById("file-info");

  if (!dropZone || !fileInput) return;

  // Click triggers hidden native file input
  dropZone.addEventListener("click", () => fileInput.click());

  // Prevent browser default drag/drop behaviors
  ["dragenter", "dragover", "dragleave", "drop"].forEach(eventName => {
    dropZone.addEventListener(eventName, preventDefaults, false);
    document.body.addEventListener(eventName, preventDefaults, false);
  });

  function preventDefaults(e) {
    e.preventDefault();
    e.stopPropagation();
  }

  // Hover animations
  ["dragenter", "dragover"].forEach(eventName => {
    dropZone.addEventListener(eventName, () => dropZone.classList.add("dragover"), false);
  });

  ["dragleave", "drop"].forEach(eventName => {
    dropZone.addEventListener(eventName, () => dropZone.classList.remove("dragover"), false);
  });

  // Handle dropped files
  dropZone.addEventListener("drop", (e) => {
    const dt = e.dataTransfer;
    const files = dt.files;
    handleFiles(files);
  });

  fileInput.addEventListener("change", (e) => {
    handleFiles(e.target.files);
  });

  function handleFiles(files) {
    if (!files.length) return;
    const file = files[0];

    if (!file.name.toLowerCase().endsWith(".srt")) {
      alert("Please upload a valid .srt file.");
      return;
    }

    if (fileInfo) {
      fileInfo.textContent = `Selected: ${file.name} (${(file.size / 1024).toFixed(1)} KB)`;
      fileInfo.classList.remove("hidden");
    }

    const reader = new FileReader();
    reader.onload = function(e) {
      const payload = {
        name: file.name,
        content: e.target.result,
        size: file.size
      };

      // Send file payload directly to parent window
      window.parent.postMessage({
        type: "FURIGANA_FILE_SELECTED",
        payload: payload
      }, "*");
    };
    reader.readAsText(file);
  }
});