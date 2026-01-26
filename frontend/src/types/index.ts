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

// Conversation types
export interface ConversationSummary {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
  last_message: {
    role: 'user' | 'assistant';
    preview: string;
    timestamp: string;
  } | null;
}

export interface Conversation {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  messages: Message[];
}

// Memory usage tracking
export interface MemoryUsage {
  used_tokens: number;
  max_tokens: number;
  percentage: number;
  is_near_limit: boolean;
}

// WebSocket message types
export interface WSStatusMessage {
  type: 'status';
  status: string;
  data?: Record<string, unknown>;
  memory?: MemoryUsage;
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
