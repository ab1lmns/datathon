/** Jury API contract. Optional fields below are frontend extensions, not requirements of the supplied JSON schema. */
export interface ObjectObservation { timestamp_sec: number; state: string }
export interface EvidenceObject { id: string; kind: string; name: string; state: string; bbox: [number,number,number,number]; color?: string; history?: ObjectObservation[] }
export interface EvidenceFrame { timestamp_sec: number; image_base64: string; objects?: EvidenceObject[] }
export interface RuleSource { document: string; section?: string; url?: string; assessment?: string; reason?: string; checked_at?: string; source_verification?: string; relation?: string; sources?: {document:string; section:string; url?:string; quote?:string}[]; unknown_conditions?: {id:string; text:string; value:string}[] }
export interface Violation { type: string; timecode_sec: number; description: string; evidence_frames: EvidenceFrame[]; rule?: RuleSource }
export type JobResponse =
 | { job_id: string; status: 'processing'; progress?: number }
 | { job_id: string; status: 'failed'; error?: string }
 | { job_id: string; status: 'done'; verdict: 'violation' | 'no_violation'; violations: Violation[] };
export interface Settings { mode: 'demo' | 'api'; baseUrl: string; apiKey: string }
export interface ReviewEvent { title: string; time: number; description: string; frames: EvidenceFrame[]; rule?: RuleSource }
export interface ReviewJob { id: string; remoteId?: string; name: string; status: 'attention'|'clean'|'processing'|'failed'; time: string; url: string; progress?: number; events: ReviewEvent[]; demo: boolean; error?: string; file?: File }
