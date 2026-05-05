import React, { useState } from 'react';
import { Textarea } from '@/components/ui/textarea';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { AlertCircle, Check } from 'lucide-react';

interface InputFieldJsonEditorProps {
  schemaJson: string;
  onChange: (json: string) => void;
}

export function InputFieldJsonEditor({ schemaJson, onChange }: InputFieldJsonEditorProps) {
  const [localValue, setLocalValue] = useState(schemaJson);
  const [error, setError] = useState<string | null>(null);

  const validateAndApply = () => {
    try {
      JSON.parse(localValue || '{}');
      onChange(localValue);
      setError(null);
    } catch (e) {
      setError('Invalid JSON: ' + (e as Error).message);
    }
  };

  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-sm font-medium mb-2">JSON Schema</h3>
        <p className="text-xs text-muted-foreground mb-3">
          Define input schema using JSON Schema format. This provides more advanced validation options.
        </p>
      </div>

      <Textarea
        value={localValue}
        onChange={(e) => setLocalValue(e.target.value)}
        placeholder={JSON.stringify({
          type: "object",
          properties: {
            query: { type: "string", description: "Search query" },
            limit: { type: "number", minimum: 1, maximum: 100 }
          },
          required: ["query"]
        }, null, 2)}
        className="font-mono text-xs min-h-[300px]"
      />

      {error && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <Button onClick={validateAndApply} className="w-full">
        <Check className="h-4 w-4 mr-2" />
        Apply JSON Schema
      </Button>
    </div>
  );
}
