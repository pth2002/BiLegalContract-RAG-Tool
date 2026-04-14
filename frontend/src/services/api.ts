// API client service for the contract review tool

import axios, { type AxiosInstance } from 'axios'; 
import type {
  Document,
  DocumentMetadata,
  PerspectiveInfo,
  PerspectiveType,
  AnalysisRequest,
  RefineRequest,
} from '../types';

const API_BASE_URL = '/api';

class ApiService {
  private client: AxiosInstance;

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      timeout: 600000, // 10 minutes for streaming
    });
  }

  async uploadDocument(
    file: File,
    sessionId: string
  ): Promise<{ document: Document; message: string }> {
    const formData = new FormData();
    formData.append('file', file);

    const response = await this.client.post(`/documents/upload?session_id=${sessionId}`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });

    return response.data;
  }

  async getDocument(documentId: string): Promise<{ document: Document }> {
    const response = await this.client.get(`/documents/${documentId}`);
    return response.data;
  }

  async listDocuments(sessionId?: string): Promise<{ documents: DocumentMetadata[] }> {
    const response = await this.client.get('/documents', {
      params: sessionId ? { session_id: sessionId } : undefined,
    });
    return response.data;
  }

  async deleteDocument(documentId: string): Promise<void> {
    await this.client.delete(`/documents/${documentId}`);
  }

  async getPerspectives(): Promise<{ perspectives: PerspectiveInfo[] }> {
    const response = await this.client.get('/perspectives');
    return response.data;
  }

  async analyzeStream(
    request: AnalysisRequest,
    onEvent: (eventType: string, data: unknown) => void
  ): Promise<void> {
    const response = await fetch(`${API_BASE_URL}/analyze/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    });

    if (!response.ok || !response.body) {
      throw new Error(`Stream failed: ${response.statusText}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split('\n\n');
      buffer = parts.pop() || '';

      for (const part of parts) {
        if (part.startsWith('event: ')) {
          const eventType = part.split('\n')[0].slice(7).trim();
          const dataLine = part.split('\n').find(l => l.startsWith('data: '));
          if (dataLine) {
            try {
              const data = JSON.parse(dataLine.slice(6));
              onEvent(eventType, data);
            } catch (e) {
              console.error('[API] Parse error:', e);
            }
          }
        }
      }
    }
  }

  async refineSuggestion(
    riskId: string,
    request: RefineRequest
  ): Promise<{
    original: { id: string; suggestedRevision: string };
    refined: { id: string; suggestedRevision: string };
    changes: { added: string[]; removed: string[] };
  }> {
    const response = await this.client.post(`/risks/${riskId}/refine`, request);
    return response.data;
  }

  async exportReport(
    documentId: string,
    format: 'docx' | 'markdown',
    perspective: PerspectiveType,
    includeRisks: boolean,
    includeSummary: boolean
  ): Promise<Blob> {
    const params = new URLSearchParams({
      document_id: documentId,
      perspective,
      format,
      include_risks: String(includeRisks),
      include_summary: String(includeSummary),
    });

    const response = await this.client.post(`/export?${params.toString()}`, null, {
      responseType: 'blob',
    });

    return response.data;
  }

  async getExportTemplate(): Promise<string> {
    const response = await this.client.get('/export/template');
    return response.data;
  }

  async checkHealth(): Promise<{ status: string; version: string }> {
    const response = await this.client.get('/health');
    return response.data;
  }
}

export const api = new ApiService();
