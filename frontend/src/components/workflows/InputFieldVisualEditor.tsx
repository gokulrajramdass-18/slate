import React from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Checkbox } from '@/components/ui/checkbox';
import { Plus, Trash2 } from 'lucide-react';
import type { InputFieldDefinition } from '@/lib/stores/graph-store';

interface InputFieldVisualEditorProps {
  fields: InputFieldDefinition[];
  onChange: (fields: InputFieldDefinition[]) => void;
}

export function InputFieldVisualEditor({ fields, onChange }: InputFieldVisualEditorProps) {
  const addField = () => {
    onChange([...fields, {
      name: '',
      type: 'string',
      required: false,
      description: '',
    }]);
  };

  const updateField = (index: number, updates: Partial<InputFieldDefinition>) => {
    const newFields = [...fields];
    newFields[index] = { ...newFields[index], ...updates };
    onChange(newFields);
  };

  const removeField = (index: number) => {
    onChange(fields.filter((_, i) => i !== index));
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium">Input Fields</h3>
        <Button size="sm" variant="outline" onClick={addField}>
          <Plus className="h-4 w-4 mr-2" />
          Add Field
        </Button>
      </div>

      {fields.length === 0 ? (
        <p className="text-sm text-muted-foreground text-center py-6">
          No fields defined. Click "Add Field" to create input parameters.
        </p>
      ) : (
        <div className="space-y-4">
          {fields.map((field, index) => (
            <div key={index} className="p-4 border rounded-lg space-y-3">
              <div className="flex items-start justify-between">
                <div className="space-y-2 flex-1 pr-2">
                  <Label htmlFor={`field-name-${index}`}>Field Name</Label>
                  <Input
                    id={`field-name-${index}`}
                    value={field.name}
                    onChange={(e) => updateField(index, { name: e.target.value })}
                    placeholder="e.g., query, user_id, filters"
                  />
                </div>
                <Button
                  size="icon"
                  variant="ghost"
                  onClick={() => removeField(index)}
                  className="mt-6"
                >
                  <Trash2 className="h-4 w-4 text-destructive" />
                </Button>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-2">
                  <Label htmlFor={`field-type-${index}`}>Type</Label>
                  <Select
                    value={field.type}
                    onValueChange={(value) => updateField(index, { type: value as any })}
                  >
                    <SelectTrigger id={`field-type-${index}`}>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="string">String</SelectItem>
                      <SelectItem value="number">Number</SelectItem>
                      <SelectItem value="boolean">Boolean</SelectItem>
                      <SelectItem value="array">Array</SelectItem>
                      <SelectItem value="object">Object</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label htmlFor={`field-default-${index}`}>Default Value</Label>
                  <Input
                    id={`field-default-${index}`}
                    value={field.default_value || ''}
                    onChange={(e) => updateField(index, { default_value: e.target.value })}
                    placeholder="Optional"
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor={`field-desc-${index}`}>Description</Label>
                <Input
                  id={`field-desc-${index}`}
                  value={field.description || ''}
                  onChange={(e) => updateField(index, { description: e.target.value })}
                  placeholder="Help text for users"
                />
              </div>

              <div className="flex items-center space-x-2">
                <Checkbox
                  id={`field-required-${index}`}
                  checked={field.required}
                  onCheckedChange={(checked) => updateField(index, { required: checked as boolean })}
                />
                <Label htmlFor={`field-required-${index}`} className="font-normal cursor-pointer">
                  Required field
                </Label>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
