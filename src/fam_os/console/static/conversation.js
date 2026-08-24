(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.FamConversation = api;
}(typeof globalThis === "undefined" ? this : globalThis, function () {
  function typingDuration(characterCount) {
    if (!Number.isFinite(characterCount) || characterCount <= 0) return 0;
    return Math.min(1400, Math.max(320, characterCount * 4));
  }

  function revealText(element, text, options = {}) {
    const value = typeof text === "string" ? text : String(text ?? "");
    const requestFrame = options.requestFrame || requestAnimationFrame;
    const now = options.now || (() => performance.now());
    const onComplete = options.onComplete || (() => {});
    let completed = false;
    let cancelled = false;
    let startedAt = null;

    function complete() {
      if (completed) return;
      completed = true;
      element.textContent = value;
      onComplete();
    }

    if (options.reducedMotion || value.length === 0) {
      complete();
      return Object.freeze({cancel: complete, finish: complete});
    }

    const duration = typingDuration(value.length);
    element.textContent = "";
    function frame(timestamp) {
      if (cancelled || completed) return;
      if (startedAt === null) startedAt = Number.isFinite(timestamp) ? timestamp : now();
      const elapsed = Math.max(0, (Number.isFinite(timestamp) ? timestamp : now()) - startedAt);
      const progress = Math.min(1, elapsed / duration);
      const visible = Math.min(value.length, Math.max(1, Math.ceil(value.length * progress)));
      element.textContent = value.slice(0, visible);
      if (progress >= 1) complete();
      else requestFrame(frame);
    }
    requestFrame(frame);

    return Object.freeze({
      cancel() { cancelled = true; },
      finish() { cancelled = true; complete(); },
    });
  }

  function scrollMessageStart(container, message, options = {}) {
    if (!container || !message || typeof container.scrollTo !== "function") return;
    const containerBox = container.getBoundingClientRect();
    const messageBox = message.getBoundingClientRect();
    const padding = Number.isFinite(options.padding) ? options.padding : 24;
    const top = Math.max(0, container.scrollTop + messageBox.top - containerBox.top - padding);
    container.scrollTo({top, behavior: options.reducedMotion ? "auto" : "smooth"});
  }

  return Object.freeze({revealText, scrollMessageStart, typingDuration});
}));
