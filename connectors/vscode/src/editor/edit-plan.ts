import {
  EditPlan,
  EditorPosition,
  EditorTextEdit,
  PlannedTextEdit,
} from "./types";
import { documentRevision, sha256 } from "./revision";

const MAX_DOCUMENT_CHARACTERS = 1_048_576;
const MAX_EDIT_CHARACTERS = 262_144;
const MAX_EDITS = 64;

export function buildEditPlan(
  documentUri: string,
  version: number,
  content: string,
  expectedRevision: string,
  edits: EditorTextEdit[],
): EditPlan {
  if (content.length > MAX_DOCUMENT_CHARACTERS) throw new Error("document exceeds edit limit");
  if (edits.length === 0 || edits.length > MAX_EDITS) throw new Error("edit count is invalid");
  if (edits.reduce((total, item) => total + item.new_text.length, 0) > MAX_EDIT_CHARACTERS) {
    throw new Error("replacement text exceeds limit");
  }
  const beforeRevision = documentRevision(version, content);
  if (expectedRevision !== beforeRevision) throw new Error("document revision changed");
  const planned = planOffsets(content, edits);
  const updated = applyPlannedEdits(content, planned);
  return {
    document_uri: documentUri,
    before_version: version,
    before_hash: sha256(content),
    before_revision: beforeRevision,
    after_hash: sha256(updated),
    edits: planned,
  };
}

export function applyPlannedEdits(content: string, edits: PlannedTextEdit[]): string {
  let updated = content;
  for (const edit of [...edits].sort((left, right) => right.start_offset - left.start_offset)) {
    updated = updated.slice(0, edit.start_offset) + edit.new_text + updated.slice(edit.end_offset);
  }
  return updated;
}

function planOffsets(content: string, edits: EditorTextEdit[]): PlannedTextEdit[] {
  const lines = lineBounds(content);
  const planned = edits.map((edit) => {
    const start = offset(lines, edit.range.start);
    const end = offset(lines, edit.range.end);
    if (start > end) throw new Error("edit range is reversed");
    return { ...edit, start_offset: start, end_offset: end };
  }).sort((left, right) => left.start_offset - right.start_offset);
  for (let index = 1; index < planned.length; index += 1) {
    if (planned[index].start_offset < planned[index - 1].end_offset
      || planned[index].start_offset === planned[index - 1].start_offset) {
      throw new Error("edit ranges overlap");
    }
  }
  return planned;
}

interface LineBound {
  start: number;
  length: number;
}

function lineBounds(content: string): LineBound[] {
  const bounds: LineBound[] = [];
  let start = 0;
  for (let index = 0; index <= content.length; index += 1) {
    if (index !== content.length && content[index] !== "\n") continue;
    let length = index - start;
    if (length > 0 && content[start + length - 1] === "\r") length -= 1;
    bounds.push({ start, length });
    start = index + 1;
  }
  return bounds;
}

function offset(lines: LineBound[], position: EditorPosition): number {
  if (!Number.isSafeInteger(position.line) || !Number.isSafeInteger(position.character)) {
    throw new Error("edit position must be an integer");
  }
  const line = lines[position.line];
  if (line === undefined || position.character < 0 || position.character > line.length) {
    throw new Error("edit position is outside document");
  }
  return line.start + position.character;
}
