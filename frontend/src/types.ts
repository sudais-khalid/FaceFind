export interface User {
  name: string;
  email: string;
  scope?: 'attendee' | 'organizer';
  consentGiven?: boolean;
}

export interface EventSummary {
  event_id: string;
  title: string;
  event_code: string;
  organizer_name?: string;
  files_total?: number;
  status?: string;
}

export interface MatchedFile {
  file_id: string;
  score: number;
  thumbnail_url: string;
  mime_type?: string;
  filename?: string;
  confidence?: 'high' | 'medium';
}
