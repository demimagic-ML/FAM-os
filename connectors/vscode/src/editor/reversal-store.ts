import { randomUUID } from "node:crypto";

export interface ReversalRecord {
  token: string;
  documentUri: string;
  expectedRevision: string;
  restoreText: string;
  restoreHash: string;
}

export class ReversalStore {
  private readonly records = new Map<string, ReversalRecord>();

  constructor(private readonly maximumRecords = 64) {
    if (maximumRecords <= 0 || maximumRecords > 1024) throw new Error("invalid reversal limit");
  }

  create(values: Omit<ReversalRecord, "token">): ReversalRecord {
    const record = { token: randomUUID(), ...values };
    this.records.set(record.token, record);
    while (this.records.size > this.maximumRecords) {
      const oldest = this.records.keys().next().value as string | undefined;
      if (oldest !== undefined) this.records.delete(oldest);
    }
    return record;
  }

  get(token: string): ReversalRecord {
    const record = this.records.get(token);
    if (record === undefined) throw new Error("reversal token is unavailable");
    return record;
  }

  consume(token: string): void {
    if (!this.records.delete(token)) throw new Error("reversal token is unavailable");
  }

  clear(): void {
    this.records.clear();
  }
}
