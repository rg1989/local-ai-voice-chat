export enum AppState {
  IDLE = 'idle',
  LISTENING = 'listening',
  TRANSCRIBING = 'transcribing',
  THINKING = 'thinking',
  SPEAKING = 'speaking',
}

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

export interface Voice {
  id: string;
  name: string;
  language: string;
}

// WebSocket message types
export interface WSStatusMessage {
  type: 'status';
  status: string;
  data?: Record<string, unknown>;
}

export interface WSTranscriptionMessage {
  type: 'transcription';
  text: string;
}

export interface WSResponseTokenMessage {
  type: 'response_token';
  token: string;
}

export interface WSResponseEndMessage {
  type: 'response_end';
}

export interface WSAudioMessage {
  type: 'audio';
  audio: string; // base64 encoded
  sample_rate: number;
}

export type WSMessage =
  | WSStatusMessage
  | WSTranscriptionMessage
  | WSResponseTokenMessage
  | WSResponseEndMessage
  | WSAudioMessage;
