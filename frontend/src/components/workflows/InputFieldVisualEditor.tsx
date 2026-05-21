import React from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Checkbox } from '@/components/ui/checkbox';
import { Plus, Trash2 } from 'lucide-react';
import type { DropdownOption, InputFieldDefinition } from '@/lib/stores/graph-store';

interface InputFieldVisualEditorProps {
  fields: InputFieldDefinition[];
  onChange: (fields: InputFieldDefinition[]) => void;
}

type DropdownOptionMode = 'simple' | 'keyvalue';

function detectDropdownMode(options: Array<string | DropdownOption> | undefined): DropdownOptionMode {
  if (!options || options.length === 0) return 'simple';
  return options.some((o) => typeof o === 'object' && o !== null) ? 'keyvalue' : 'simple';
}

function DropdownOptionsEditor({
  options,
  onChange,
}: {
  options: Array<string | DropdownOption>;
  onChange: (next: Array<string | DropdownOption>) => void;
}) {
  const mode = detectDropdownMode(options);

  const setMode = (next: DropdownOptionMode) => {
    if (next === mode) return;
    if (next === 'simple') {
      onChange(options.map((o) => (typeof o === 'string' ? o : String(o.value ?? ''))));
    } else {
      onChange(
        options.map((o) =>
          typeof o === 'string'
            ? { label: o, value: o }
            : { label: o.label ?? '', value: o.value ?? '' },
        ),
      );
    }
  };

  const addOption = () => {
    if (mode === 'simple') {
      onChange([...options, '']);
    } else {
      onChange([...options, { label: '', value: '' }]);
    }
  };

  const removeOption = (idx: number) => {
    onChange(options.filter((_, i) => i !== idx));
  };

  const updateOption = (idx: number, value: string | DropdownOption) => {
    const next = [...options];
    next[idx] = value;
    onChange(next);
  };

  return (
    <div className="space-y-3 rounded-md border bg-muted/30 p-3">
      <div className="flex items-center justify-between">
        <Label className="text-xs">Options</Label>
        <Select value={mode} onValueChange={(v) => setMode(v as DropdownOptionMode)}>
          <SelectTrigger className="h-7 w-[140px] text-xs">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="simple">Simple list</SelectItem>
            <SelectItem value="keyvalue">Key / value</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {options.length === 0 ? (
        <p className="text-xs text-muted-foreground">No options yet.</p>
      ) : (
        <div className="space-y-2">
          {options.map((opt, idx) =>
            mode === 'simple' ? (
              <div key={idx} className="flex items-center gap-2">
                <Input
                  value={typeof opt === 'string' ? opt : String(opt.value ?? '')}
                  onChange={(e) => updateOption(idx, e.target.value)}
                  placeholder="Value"
                  className="h-8 text-xs"
                />
                <Button size="icon" variant="ghost" onClick={() => removeOption(idx)} className="h-7 w-7">
                  <Trash2 className="h-3.5 w-3.5 text-destructive" />
                </Button>
              </div>
            ) : (
              <div key={idx} className="flex items-center gap-2">
                <Input
                  value={typeof opt === 'object' ? opt.label : ''}
                  onChange={(e) =>
                    updateOption(idx, {
                      label: e.target.value,
                      value: typeof opt === 'object' ? opt.value : '',
                    })
                  }
                  placeholder="Label (shown to user)"
                  className="h-8 text-xs"
                />
                <Input
                  value={typeof opt === 'object' ? String(opt.value ?? '') : ''}
                  onChange={(e) =>
                    updateOption(idx, {
                      label: typeof opt === 'object' ? opt.label : '',
                      value: e.target.value,
                    })
                  }
                  placeholder="Value (sent downstream)"
                  className="h-8 text-xs"
                />
                <Button size="icon" variant="ghost" onClick={() => removeOption(idx)} className="h-7 w-7">
                  <Trash2 className="h-3.5 w-3.5 text-destructive" />
                </Button>
              </div>
            ),
          )}
        </div>
      )}

      <Button size="sm" variant="outline" onClick={addOption} className="h-7 text-xs">
        <Plus className="h-3 w-3 mr-1" />
        Add Option
      </Button>
    </div>
  );
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
                    onValueChange={(value) => {
                      const updates: Partial<InputFieldDefinition> = { type: value as any };
                      if (value === 'dropdown' && (!field.options || field.options.length === 0)) {
                        updates.options = [];
                      }
                      updateField(index, updates);
                    }}
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
                      <SelectItem value="dropdown">Dropdown</SelectItem>
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

              {field.type === 'dropdown' && (
                <DropdownOptionsEditor
                  options={field.options || []}
                  onChange={(options) => updateField(index, { options })}
                />
              )}

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
