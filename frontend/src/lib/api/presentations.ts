/**
 * Presentations API Client
 *
 * TypeScript client for PowerPoint presentation generation endpoints.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5055';

export interface PresentationTemplate {
  id: string;
  name: string;
  description: string;
  category: string;
  theme_json: string | object;
  slide_layouts: string | string[];
  is_active: number;
  created_at: string;
  updated_at: string;
}

export interface SlideContent {
  id: string;
  presentation_id: string;
  slide_number: number;
  slide_type: 'title' | 'bullets' | 'two_column' | 'content' | 'image_text' | 'chart';
  content_html?: string;
  content_json: {
    title: string;
    subtitle?: string;
    elements: Array<{
      type: string;
      content: string;
      column?: string;
      level?: number;
    }>;
  };
  speaker_notes?: string;
  created_at: string;
  updated_at: string;
}

export interface Presentation {
  id: string;
  notebook_id?: string;
  template_id?: string;
  title: string;
  description?: string;
  created_at: string;
  updated_at: string;
  created_by?: string;
  slide_count?: number;
}

export interface GenerateRequest {
  template_id: string;
  source_ids: string[];
  notebook_id?: string;
  user_prompt: string;
  target_slide_count: number;
}

export interface GenerateResponse {
  success: boolean;
  presentation_id: string;
  slide_count: number;
  preview_url: string;
  download_url: string;
}

export interface UpdateSlideRequest {
  slide_type?: string;
  content_json?: object;
  speaker_notes?: string;
}

export interface RefineRequest {
  message: string;
}

export const presentationApi = {
  /**
   * Generate presentation from sources
   */
  async generate(
    presentationId: string,
    request: GenerateRequest
  ): Promise<GenerateResponse> {
    const response = await fetch(
      `${API_BASE}/api/presentations/${presentationId}/generate`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request),
      }
    );

    if (!response.ok) {
      throw new Error(`Failed to generate presentation: ${response.statusText}`);
    }

    return response.json();
  },

  /**
   * Get HTML preview of presentation
   */
  async getPreview(presentationId: string): Promise<string> {
    const response = await fetch(
      `${API_BASE}/api/presentations/${presentationId}/preview`
    );

    if (!response.ok) {
      throw new Error(`Failed to get preview: ${response.statusText}`);
    }

    return response.text();
  },

  /**
   * Get all slides in a presentation
   */
  async getSlides(presentationId: string): Promise<SlideContent[]> {
    const response = await fetch(
      `${API_BASE}/api/presentations/${presentationId}/slides`
    );

    if (!response.ok) {
      throw new Error(`Failed to get slides: ${response.statusText}`);
    }

    const data = await response.json();
    return data.slides;
  },

  /**
   * Get a specific slide
   */
  async getSlide(
    presentationId: string,
    slideNumber: number
  ): Promise<SlideContent> {
    const response = await fetch(
      `${API_BASE}/api/presentations/${presentationId}/slides/${slideNumber}`
    );

    if (!response.ok) {
      throw new Error(`Failed to get slide: ${response.statusText}`);
    }

    return response.json();
  },

  /**
   * Update slide content
   */
  async updateSlide(
    presentationId: string,
    slideNumber: number,
    data: UpdateSlideRequest
  ): Promise<{ success: boolean; message: string }> {
    const response = await fetch(
      `${API_BASE}/api/presentations/${presentationId}/slides/${slideNumber}`,
      {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      }
    );

    if (!response.ok) {
      throw new Error(`Failed to update slide: ${response.statusText}`);
    }

    return response.json();
  },

  /**
   * Delete a slide
   */
  async deleteSlide(
    presentationId: string,
    slideNumber: number
  ): Promise<{ success: boolean; message: string }> {
    const response = await fetch(
      `${API_BASE}/api/presentations/${presentationId}/slides/${slideNumber}`,
      {
        method: 'DELETE',
      }
    );

    if (!response.ok) {
      throw new Error(`Failed to delete slide: ${response.statusText}`);
    }

    return response.json();
  },

  /**
   * Download presentation as PPTX file
   */
  async download(presentationId: string, title: string = 'presentation'): Promise<void> {
    const response = await fetch(
      `${API_BASE}/api/presentations/${presentationId}/download`
    );

    if (!response.ok) {
      throw new Error(`Failed to download presentation: ${response.statusText}`);
    }

    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${title}.pptx`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
  },

  /**
   * Refine presentation using natural language
   */
  async refine(
    presentationId: string,
    message: string
  ): Promise<{ success: boolean; message: string }> {
    const response = await fetch(
      `${API_BASE}/api/presentations/${presentationId}/refine`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message }),
      }
    );

    if (!response.ok) {
      throw new Error(`Failed to refine presentation: ${response.statusText}`);
    }

    return response.json();
  },

  /**
   * List all available templates
   */
  async listTemplates(category?: string): Promise<PresentationTemplate[]> {
    const url = new URL(`${API_BASE}/api/presentations/templates`);
    if (category) {
      url.searchParams.set('category', category);
    }

    const response = await fetch(url.toString());

    if (!response.ok) {
      throw new Error(`Failed to list templates: ${response.statusText}`);
    }

    const data = await response.json();
    return data.templates;
  },

  /**
   * Get a specific template
   */
  async getTemplate(templateId: string): Promise<PresentationTemplate> {
    const response = await fetch(
      `${API_BASE}/api/presentations/templates/${templateId}`
    );

    if (!response.ok) {
      throw new Error(`Failed to get template: ${response.statusText}`);
    }

    return response.json();
  },

  /**
   * Create a new presentation record
   */
  async create(data: {
    notebook_id?: string;
    template_id?: string;
    title: string;
    description?: string;
  }): Promise<{ success: boolean; presentation_id: string; presentation: Presentation }> {
    const response = await fetch(`${API_BASE}/api/presentations/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });

    if (!response.ok) {
      throw new Error(`Failed to create presentation: ${response.statusText}`);
    }

    return response.json();
  },

  /**
   * Get presentation metadata
   */
  async get(presentationId: string): Promise<Presentation> {
    const response = await fetch(
      `${API_BASE}/api/presentations/${presentationId}`
    );

    if (!response.ok) {
      throw new Error(`Failed to get presentation: ${response.statusText}`);
    }

    return response.json();
  },

  /**
   * Delete a presentation
   */
  async delete(presentationId: string): Promise<{ success: boolean; message: string }> {
    const response = await fetch(
      `${API_BASE}/api/presentations/${presentationId}`,
      {
        method: 'DELETE',
      }
    );

    if (!response.ok) {
      throw new Error(`Failed to delete presentation: ${response.statusText}`);
    }

    return response.json();
  },
};
