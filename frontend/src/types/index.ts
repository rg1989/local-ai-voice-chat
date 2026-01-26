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
  custom_rules?: string;
}

export interface Conversation {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  messages: Message[];
  custom_rules?: string;
}

// Conversation settings
export interface ConversationSettings {
  custom_rules: string;
}

// Tool types
export interface ToolInfo {
  name: string;
  description: string;
  enabled: boolean;
  requires_confirmation: boolean;
}

// Global settings
export interface GlobalSettings {
  tools: Record<string, boolean>; // tool_name -> enabled
  globalRules: string;
}

// Wake word settings
export interface WakeWordSettings {
  enabled: boolean;
  model: string;
  threshold: number;
  timeoutSeconds: number;
  availableModels?: Record<string, string>; // model_id -> display_name
  ready?: boolean; // True when backend model is loaded and ready
}

// Sound settings
export interface SoundSettings {
  enabled: boolean;
  wakeSound: string;      // sound id or 'none'
  messageSound: string;   // sound id or 'none'
  thinkingSound: string;  // sound id or 'none'
  volume: number;         // 0.0 to 1.0
}

// Memory usage tracking
export interface MemoryUsage {
  used_tokens: number;
  max_tokens: number;
  percentage: number;
  is_near_limit: boolean;
}

// Search types
export interface SearchMatch {
  message_id: string;
  message_index: number;
  role: 'user' | 'assistant';
  context: string;
  timestamp: string;
}

export interface SearchResult {
  conversation_id: string;
  title: string;
  matches: SearchMatch[];
  total_matches: number;
  title_match: boolean;
  updated_at: string;
}

// Memory types (persistent cross-chat memories)
export interface MemoryEntry {
  id: string;
  content: string;
  created_at: string;
  source_conversation_id: string | null;
  tags: string[];
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

export interface WSToolsListMessage {
  type: 'tools_list';
  tools: ToolInfo[];
}

export interface WSWakeWordSettingsMessage {
  type: 'wakeword_settings';
  enabled: boolean;
  model: string;
  threshold: number;
  timeoutSeconds: number;
  availableModels: Record<string, string>;
  ready?: boolean;
}

export interface WSWakeStatusMessage {
  type: 'wake_status';
  state: 'listening' | 'active' | 'disabled';
  model: string;
  displayName: string;
}

export interface WSMemoriesListMessage {
  type: 'memories_list';
  memories: MemoryEntry[];
  count: number;
}

export interface WSMemoryAddedMessage {
  type: 'memory_added';
  memory: MemoryEntry;
}

export interface WSMemoryDeletedMessage {
  type: 'memory_deleted';
  memory_id: string;
  success: boolean;
}

export interface WSMemoryUpdatedMessage {
  type: 'memory_updated';
  memory: MemoryEntry;
}

export type WSMessage =
  | WSStatusMessage
  | WSTranscriptionMessage
  | WSResponseTokenMessage
  | WSResponseEndMessage
  | WSAudioMessage
  | WSToolsListMessage
  | WSWakeWordSettingsMessage
  | WSWakeStatusMessage
  | WSMemoriesListMessage
  | WSMemoryAddedMessage
  | WSMemoryDeletedMessage
  | WSMemoryUpdatedMessage;
