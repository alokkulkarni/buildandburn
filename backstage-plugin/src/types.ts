export interface Service {
  name: string;
  endpoint: string;
}

export interface Database {
  endpoint: string;
  username?: string;
}

export interface MessageQueue {
  endpoint: string;
  username?: string;
}

export interface Environment {
  id: string;
  name: string;
  createdAt: string;
  status: 'active' | 'creating' | 'destroying' | 'failed';
  services?: Service[];
  database?: Database;
  messageQueue?: MessageQueue;
} 