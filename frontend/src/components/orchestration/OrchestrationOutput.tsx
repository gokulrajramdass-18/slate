/**
 * Orchestration Output Display
 *
 * Renders orchestration results with markdown formatting and export options
 */

'use client';

import React, { useState, useRef } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { CheckCircle2, XCircle, Download, FileText, FileJson, Copy, Check } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/cjs/styles/prism';
import { useToast } from '@/hooks/use-toast';
import jsPDF from 'jspdf';
import html2canvas from 'html2canvas';

interface OrchestrationOutputProps {
  result: any;
  status: 'completed' | 'failed';
  spawnedAgents?: number;
  completedTasks?: number;
  totalTasks?: number;
  duration?: string;
}

export function OrchestrationOutput({
  result,
  status,
  spawnedAgents = 0,
  completedTasks = 0,
  totalTasks = 0,
  duration = '0s',
}: OrchestrationOutputProps) {
  const { toast } = useToast();
  const [copied, setCopied] = useState(false);
  const [activeTab, setActiveTab] = useState<'rendered' | 'raw'>('rendered');
  const [isGeneratingPDF, setIsGeneratingPDF] = useState(false);
  const contentRef = useRef<HTMLDivElement>(null);

  // Extract output from result
  const output = result?.combined_output || result?.output || '';
  const isError = status === 'failed';

  // Format output for download
  const formatForDownload = (format: 'markdown' | 'json') => {
    if (format === 'markdown') {
      return `# Orchestration Result\n\n${output}`;
    } else {
      return JSON.stringify(result, null, 2);
    }
  };

  // Download as file
  const handleDownload = async (format: 'markdown' | 'json' | 'pdf') => {
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, -5);
    const filename = `orchestration-${timestamp}`;

    if (format === 'pdf') {
      setIsGeneratingPDF(true);
      toast({
        title: 'Generating PDF',
        description: 'Please wait while we create your PDF...',
      });

      try {
        // Create a temporary container for PDF rendering
        const pdfContainer = document.createElement('div');
        pdfContainer.style.position = 'absolute';
        pdfContainer.style.left = '-9999px';
        pdfContainer.style.width = '210mm'; // A4 width
        pdfContainer.style.backgroundColor = 'white';
        pdfContainer.style.padding = '20mm';
        pdfContainer.style.fontFamily = 'Arial, sans-serif';
        pdfContainer.style.fontSize = '11pt';
        pdfContainer.style.lineHeight = '1.6';
        pdfContainer.style.color = '#000';

        // Create formatted HTML content
        const htmlContent = `
          <div style="max-width: 170mm; margin: 0 auto;">
            <div style="border-bottom: 3px solid #10b981; padding-bottom: 15px; margin-bottom: 20px;">
              <h1 style="font-size: 24pt; font-weight: bold; color: #059669; margin: 0 0 10px 0;">
                Orchestration Result
              </h1>
              <p style="font-size: 10pt; color: #6b7280; margin: 0;">
                Generated on ${new Date().toLocaleString()}
              </p>
            </div>

            ${spawnedAgents > 0 || completedTasks > 0 || duration !== '0s' ? `
              <div style="background: #f0fdf4; border: 1px solid #86efac; border-radius: 8px; padding: 15px; margin-bottom: 20px;">
                <table style="width: 100%; border-collapse: collapse;">
                  <tr>
                    <td style="padding: 8px; text-align: center; border-right: 1px solid #86efac;">
                      <div style="font-size: 9pt; color: #059669; font-weight: 600; margin-bottom: 5px;">AGENTS SPAWNED</div>
                      <div style="font-size: 20pt; font-weight: bold; color: #047857;">${spawnedAgents}</div>
                    </td>
                    <td style="padding: 8px; text-align: center; border-right: 1px solid #86efac;">
                      <div style="font-size: 9pt; color: #059669; font-weight: 600; margin-bottom: 5px;">TASKS COMPLETED</div>
                      <div style="font-size: 20pt; font-weight: bold; color: #047857;">${completedTasks}/${totalTasks || completedTasks}</div>
                    </td>
                    <td style="padding: 8px; text-align: center;">
                      <div style="font-size: 9pt; color: #059669; font-weight: 600; margin-bottom: 5px;">DURATION</div>
                      <div style="font-size: 20pt; font-weight: bold; color: #047857;">${duration}</div>
                    </td>
                  </tr>
                </table>
              </div>
            ` : ''}

            <div style="margin-top: 20px;">
              ${formatMarkdownForPDF(output)}
            </div>
          </div>
        `;

        pdfContainer.innerHTML = htmlContent;
        document.body.appendChild(pdfContainer);

        // Wait for images and content to load
        await new Promise(resolve => setTimeout(resolve, 500));

        // Capture the content as canvas
        const canvas = await html2canvas(pdfContainer, {
          scale: 2,
          useCORS: true,
          logging: false,
          backgroundColor: '#ffffff',
        });

        // Remove temporary container
        document.body.removeChild(pdfContainer);

        // Create PDF
        const pdf = new jsPDF({
          orientation: 'portrait',
          unit: 'mm',
          format: 'a4',
        });

        const imgWidth = 210; // A4 width in mm
        const imgHeight = (canvas.height * imgWidth) / canvas.width;
        const pageHeight = 297; // A4 height in mm
        let heightLeft = imgHeight;
        let position = 0;

        // Add first page
        pdf.addImage(canvas.toDataURL('image/png'), 'PNG', 0, position, imgWidth, imgHeight);
        heightLeft -= pageHeight;

        // Add additional pages if needed
        while (heightLeft > 0) {
          position = heightLeft - imgHeight;
          pdf.addPage();
          pdf.addImage(canvas.toDataURL('image/png'), 'PNG', 0, position, imgWidth, imgHeight);
          heightLeft -= pageHeight;
        }

        // Save PDF
        pdf.save(`${filename}.pdf`);

        toast({
          title: 'PDF Downloaded',
          description: `Result saved as ${filename}.pdf`,
        });
      } catch (error) {
        console.error('PDF generation error:', error);
        toast({
          title: 'Error',
          description: 'Failed to generate PDF. Please try again.',
          variant: 'destructive',
        });
      } finally {
        setIsGeneratingPDF(false);
      }
      return;
    }

    // For markdown and JSON
    const content = formatForDownload(format);
    const mimeType = format === 'markdown' ? 'text/markdown' : 'application/json';
    const extension = format === 'markdown' ? 'md' : 'json';

    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${filename}.${extension}`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);

    toast({
      title: 'Downloaded',
      description: `Result saved as ${filename}.${extension}`,
    });
  };

  // Format markdown for PDF
  const formatMarkdownForPDF = (markdown: string): string => {
    // Simple markdown to HTML conversion for PDF
    let html = markdown
      // Headers
      .replace(/### (.*?)$/gm, '<h3 style="font-size: 14pt; font-weight: 600; margin: 15px 0 10px 0; color: #1f2937;">$1</h3>')
      .replace(/## (.*?)$/gm, '<h2 style="font-size: 16pt; font-weight: 600; margin: 20px 0 12px 0; color: #111827; border-bottom: 1px solid #e5e7eb; padding-bottom: 5px;">$1</h2>')
      .replace(/# (.*?)$/gm, '<h1 style="font-size: 18pt; font-weight: bold; margin: 25px 0 15px 0; color: #000; border-bottom: 2px solid #d1d5db; padding-bottom: 8px;">$1</h1>')
      // Bold and italic
      .replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>')
      .replace(/\*\*(.+?)\*\*/g, '<strong style="font-weight: 600; color: #000;">$1</strong>')
      .replace(/\*(.+?)\*/g, '<em>$1</em>')
      // Inline code
      .replace(/`(.+?)`/g, '<code style="background: #f3f4f6; padding: 2px 6px; border-radius: 3px; font-family: monospace; font-size: 9pt; color: #dc2626;">$1</code>')
      // Lists
      .replace(/^- (.+)$/gm, '<li style="margin: 5px 0; line-height: 1.6;">$1</li>')
      .replace(/^(\d+)\. (.+)$/gm, '<li style="margin: 5px 0; line-height: 1.6;">$2</li>')
      // Tables (basic support)
      .replace(/\|(.+?)\|/g, (match) => {
        const cells = match.split('|').filter(c => c.trim());
        return '<tr>' + cells.map(c => `<td style="border: 1px solid #e5e7eb; padding: 8px;">${c.trim()}</td>`).join('') + '</tr>';
      })
      // Paragraphs
      .replace(/\n\n/g, '</p><p style="margin: 10px 0; line-height: 1.6;">')
      // Line breaks
      .replace(/\n/g, '<br/>');

    // Wrap in paragraph
    html = '<p style="margin: 10px 0; line-height: 1.6;">' + html + '</p>';

    // Wrap lists
    html = html.replace(/(<li.*?<\/li>)+/g, '<ul style="margin: 10px 0; padding-left: 25px;">$&</ul>');

    return html;
  };

  // Copy to clipboard
  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(output);
      setCopied(true);
      toast({
        title: 'Copied',
        description: 'Output copied to clipboard',
      });
      setTimeout(() => setCopied(false), 2000);
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to copy to clipboard',
        variant: 'destructive',
      });
    }
  };

  return (
    <Card className={`${isError ? 'border-red-500 bg-red-50/50 dark:bg-red-950/20' : 'border-green-500 bg-green-50/50 dark:bg-green-950/20'} shadow-lg`}>
      <CardHeader className="border-b bg-white/50 dark:bg-gray-900/50">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-3 text-xl">
            {isError ? (
              <>
                <XCircle className="h-6 w-6 text-red-500" />
                <span className="bg-gradient-to-r from-red-600 to-red-800 bg-clip-text text-transparent">
                  Execution Failed
                </span>
              </>
            ) : (
              <>
                <CheckCircle2 className="h-6 w-6 text-green-600" />
                <span className="bg-gradient-to-r from-green-600 to-emerald-600 bg-clip-text text-transparent">
                  Execution Result
                </span>
              </>
            )}
          </CardTitle>

          {/* Export Buttons */}
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={handleCopy}
              className="gap-2 hover:bg-blue-50 dark:hover:bg-blue-950/30 transition-colors"
            >
              {copied ? (
                <>
                  <Check className="h-4 w-4 text-green-600" />
                  <span className="text-green-600">Copied</span>
                </>
              ) : (
                <>
                  <Copy className="h-4 w-4" />
                  Copy
                </>
              )}
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => handleDownload('markdown')}
              className="gap-2 hover:bg-purple-50 dark:hover:bg-purple-950/30 transition-colors"
            >
              <FileText className="h-4 w-4" />
              Markdown
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => handleDownload('json')}
              className="gap-2 hover:bg-amber-50 dark:hover:bg-amber-950/30 transition-colors"
            >
              <FileJson className="h-4 w-4" />
              JSON
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => handleDownload('pdf')}
              disabled={isGeneratingPDF}
              className="gap-2 hover:bg-emerald-50 dark:hover:bg-emerald-950/30 transition-colors"
            >
              {isGeneratingPDF ? (
                <>
                  <div className="h-4 w-4 animate-spin rounded-full border-2 border-gray-300 border-t-emerald-600" />
                  Generating...
                </>
              ) : (
                <>
                  <Download className="h-4 w-4" />
                  PDF
                </>
              )}
            </Button>
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-6 pt-6">
        {/* Tabs for Rendered vs Raw */}
        <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as 'rendered' | 'raw')} className="w-full">
          <TabsList className="grid w-full grid-cols-2 h-12 bg-gray-100 dark:bg-gray-800 p-1 rounded-lg">
            <TabsTrigger
              value="rendered"
              className="data-[state=active]:bg-white dark:data-[state=active]:bg-gray-900 data-[state=active]:shadow-sm rounded-md font-medium transition-all"
            >
              <span className="flex items-center gap-2">
                <FileText className="h-4 w-4" />
                Rendered
              </span>
            </TabsTrigger>
            <TabsTrigger
              value="raw"
              className="data-[state=active]:bg-white dark:data-[state=active]:bg-gray-900 data-[state=active]:shadow-sm rounded-md font-medium transition-all"
            >
              <span className="flex items-center gap-2">
                <FileJson className="h-4 w-4" />
                Raw
              </span>
            </TabsTrigger>
          </TabsList>

          {/* Rendered View */}
          <TabsContent value="rendered" className="space-y-4">
            <div className="prose prose-lg dark:prose-invert max-w-none bg-white dark:bg-gray-900 rounded-lg p-8 shadow-sm border border-gray-200 dark:border-gray-800">
              <style jsx global>{`
                .prose h1 {
                  font-size: 2.25rem;
                  font-weight: 700;
                  margin-top: 0;
                  margin-bottom: 1.5rem;
                  color: #1f2937;
                  border-bottom: 2px solid #e5e7eb;
                  padding-bottom: 0.5rem;
                }
                .dark .prose h1 {
                  color: #f9fafb;
                  border-bottom-color: #374151;
                }
                .prose h2 {
                  font-size: 1.875rem;
                  font-weight: 600;
                  margin-top: 2rem;
                  margin-bottom: 1rem;
                  color: #374151;
                  border-bottom: 1px solid #e5e7eb;
                  padding-bottom: 0.375rem;
                }
                .dark .prose h2 {
                  color: #e5e7eb;
                  border-bottom-color: #4b5563;
                }
                .prose h3 {
                  font-size: 1.5rem;
                  font-weight: 600;
                  margin-top: 1.5rem;
                  margin-bottom: 0.75rem;
                  color: #4b5563;
                }
                .dark .prose h3 {
                  color: #d1d5db;
                }
                .prose p {
                  font-size: 1rem;
                  line-height: 1.75;
                  margin-top: 0.75rem;
                  margin-bottom: 0.75rem;
                  color: #374151;
                }
                .dark .prose p {
                  color: #d1d5db;
                }
                .prose strong {
                  font-weight: 600;
                  color: #1f2937;
                }
                .dark .prose strong {
                  color: #f3f4f6;
                }
                .prose ul, .prose ol {
                  margin-top: 1rem;
                  margin-bottom: 1rem;
                  padding-left: 1.75rem;
                }
                .prose li {
                  margin-top: 0.5rem;
                  margin-bottom: 0.5rem;
                  line-height: 1.75;
                }
                .prose table {
                  width: 100%;
                  margin-top: 1.5rem;
                  margin-bottom: 1.5rem;
                  border-collapse: collapse;
                  font-size: 0.95rem;
                  box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1);
                  border-radius: 0.5rem;
                  overflow: hidden;
                }
                .prose thead {
                  background: linear-gradient(to bottom, #f9fafb, #f3f4f6);
                }
                .dark .prose thead {
                  background: linear-gradient(to bottom, #374151, #1f2937);
                }
                .prose th {
                  padding: 0.75rem 1rem;
                  text-align: left;
                  font-weight: 600;
                  color: #1f2937;
                  border-bottom: 2px solid #e5e7eb;
                }
                .dark .prose th {
                  color: #f9fafb;
                  border-bottom-color: #4b5563;
                }
                .prose td {
                  padding: 0.75rem 1rem;
                  border-bottom: 1px solid #f3f4f6;
                  color: #374151;
                }
                .dark .prose td {
                  border-bottom-color: #374151;
                  color: #d1d5db;
                }
                .prose tr:hover {
                  background-color: #f9fafb;
                }
                .dark .prose tr:hover {
                  background-color: #1f2937;
                }
                .prose code {
                  background-color: #f3f4f6;
                  padding: 0.2rem 0.4rem;
                  border-radius: 0.25rem;
                  font-size: 0.875rem;
                  font-weight: 500;
                  color: #dc2626;
                }
                .dark .prose code {
                  background-color: #374151;
                  color: #fca5a5;
                }
                .prose pre {
                  margin-top: 1.5rem;
                  margin-bottom: 1.5rem;
                  border-radius: 0.5rem;
                  overflow-x: auto;
                }
                .prose blockquote {
                  border-left: 4px solid #3b82f6;
                  padding-left: 1rem;
                  font-style: italic;
                  color: #6b7280;
                  margin: 1.5rem 0;
                }
                .dark .prose blockquote {
                  border-left-color: #60a5fa;
                  color: #9ca3af;
                }
                .prose a {
                  color: #3b82f6;
                  text-decoration: none;
                  font-weight: 500;
                  border-bottom: 1px solid transparent;
                  transition: border-color 0.2s;
                }
                .prose a:hover {
                  border-bottom-color: #3b82f6;
                }
                .dark .prose a {
                  color: #60a5fa;
                }
                .dark .prose a:hover {
                  border-bottom-color: #60a5fa;
                }
                .prose hr {
                  border: 0;
                  border-top: 1px solid #e5e7eb;
                  margin: 2rem 0;
                }
                .dark .prose hr {
                  border-top-color: #374151;
                }
              `}</style>
              <ReactMarkdown
                components={{
                  code({ node, inline, className, children, ...props }: any) {
                    const match = /language-(\w+)/.exec(className || '');
                    return !inline && match ? (
                      <SyntaxHighlighter
                        style={oneDark}
                        language={match[1]}
                        PreTag="div"
                        customStyle={{
                          borderRadius: '0.5rem',
                          padding: '1.25rem',
                          fontSize: '0.9rem',
                          lineHeight: '1.6',
                          marginTop: '1.5rem',
                          marginBottom: '1.5rem',
                        }}
                        {...props}
                      >
                        {String(children).replace(/\n$/, '')}
                      </SyntaxHighlighter>
                    ) : (
                      <code className={className} {...props}>
                        {children}
                      </code>
                    );
                  },
                }}
              >
                {output || 'No output generated'}
              </ReactMarkdown>
            </div>
          </TabsContent>

          {/* Raw View */}
          <TabsContent value="raw" className="space-y-4 mt-4">
            <div className="relative">
              <pre className="bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-lg p-6 text-sm overflow-x-auto max-h-[600px] overflow-y-auto shadow-inner">
                <code className="font-mono text-gray-800 dark:text-gray-200 leading-relaxed">
                  {output || 'No output generated'}
                </code>
              </pre>
            </div>
          </TabsContent>
        </Tabs>

        {/* Execution Statistics */}
        {!isError && (spawnedAgents > 0 || completedTasks > 0 || duration !== '0s') && (
          <div className="grid grid-cols-3 gap-6 p-6 bg-gradient-to-br from-blue-50 to-indigo-50 dark:from-blue-950/30 dark:to-indigo-950/30 rounded-lg border border-blue-200 dark:border-blue-800">
            <div className="text-center">
              <div className="text-xs font-semibold text-blue-600 dark:text-blue-400 uppercase tracking-wide mb-2">
                Agents Spawned
              </div>
              <div className="text-4xl font-bold bg-gradient-to-br from-blue-600 to-indigo-600 bg-clip-text text-transparent">
                {spawnedAgents}
              </div>
            </div>
            <div className="text-center border-x border-blue-200 dark:border-blue-800">
              <div className="text-xs font-semibold text-emerald-600 dark:text-emerald-400 uppercase tracking-wide mb-2">
                Tasks Completed
              </div>
              <div className="text-4xl font-bold bg-gradient-to-br from-emerald-600 to-teal-600 bg-clip-text text-transparent">
                {completedTasks}/{totalTasks || completedTasks}
              </div>
            </div>
            <div className="text-center">
              <div className="text-xs font-semibold text-purple-600 dark:text-purple-400 uppercase tracking-wide mb-2">
                Duration
              </div>
              <div className="text-4xl font-bold bg-gradient-to-br from-purple-600 to-pink-600 bg-clip-text text-transparent">
                {duration}
              </div>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
