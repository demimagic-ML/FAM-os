export interface EditorPosition {
  line: number;
  character: number;
}

export interface EditorRange {
  start: EditorPosition;
  end: EditorPosition;
}

export interface EditorTextEdit {
  range: EditorRange;
  new_text: string;
}

export interface PlannedTextEdit extends EditorTextEdit {
  start_offset: number;
  end_offset: number;
}

export interface EditPlan {
  document_uri: string;
  before_version: number;
  before_hash: string;
  before_revision: string;
  after_hash: string;
  edits: PlannedTextEdit[];
}
