/** Jury API contract. Optional fields below are frontend extensions, not requirements of the supplied JSON schema. */
export interface EvidenceFrame { timestamp_sec: number; image_base64: string }
export interface RuleSource { document: string; section?: string; url?: string }
export interface Violation { type: string; timecode_sec: number; description: string; evidence_frames: EvidenceFrame[]; rule?: RuleSource }
export type JobResponse =
 | { job_id: string; status: 'processing'; progress?: number }
 | { job_id: string; status: 'failed'; error?: string }
 | { job_id: string; status: 'done'; verdict: 'violation' | 'no_violation'; violations: Violation[] };
export interface Settings { mode: 'demo' | 'api'; baseUrl: string; apiKey: string }
export interface ReviewEvent { title: string; time: number; description: string; frames: EvidenceFrame[]; rule?: RuleSource }
export interface ReviewJob { id: string; remoteId?: string; name: string; status: 'attention'|'clean'|'processing'|'failed'; time: string; url: string; progress?: number; events: ReviewEvent[]; demo: boolean; error?: string; file?: File }
