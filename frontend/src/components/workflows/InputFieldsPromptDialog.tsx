/**
 * InputFieldsPromptDialog
 *
 * Collects values for an Input node's input_fields before executing a workflow
 * or saving a schedule. Reused on both manual Execute and Schedule create/edit.
 */

'use client';

import React from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Switch } from '@/components/ui/switch';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import type { InputFieldDefinition } from '@/lib/stores/graph-store';

// ============================================================================
// Helpers
// ============================================================================

type FieldValues = Record<string, any>;
type FieldErrors = Record<string, string | undefined>;

interface NormalizedOption {
  label: string;
  value: any;
  /** Stable string key used by the Select primitive (Radix requires string values). */
  key: string;
}

function normalizeDropdownOptions(field: InputFieldDefinition): NormalizedOption[] {
  if (!field.options) return [];
  return field.options.map((opt) => {
    if (opt && typeof opt === 'object' && 'value' in opt) {
      const value = (opt as { value: any }).value;
      const label = String((opt as { label?: any }).label ?? value ?? '');
      return { label, value, key: String(value ?? label) };
    }
    const v = opt as any;
    return { label: String(v ?? ''), value: v, key: String(v ?? '') };
  });
}

function coerceInitial(field: InputFieldDefinition, provided: any): any {
  if (provided !== undefined && provided !== null) {
    if (field.type === 'array' || field.type === 'object') {
      return typeof provided === 'string' ? provided : JSON.stringify(provided, null, 2);
    }
    if (field.type === 'boolean') return Boolean(provided);
    return provided;
  }
  if (field.default_value !== undefined && field.default_value !== null && field.default_value !== '') {
    if (field.type === 'array' || field.type === 'object') {
      return typeof field.default_value === 'string'
        ? field.default_value
        : JSON.stringify(field.default_value, null, 2);
    }
    if (field.type === 'boolean') return Boolean(field.default_value);
    return field.default_value;
  }
  if (field.type === 'boolean') return false;
  return '';
}

function isEmpty(value: any): boolean {
  if (value === undefined || value === null) return true;
  if (typeof value === 'string' && value.trim() === '') return true;
  return false;
}

function buildInitialValues(
  fields: InputFieldDefinition[],
  initialValues?: FieldValues,
): FieldValues {
  const values: FieldValues = {};
  for (const field of fields) {
    values[field.name] = coerceInitial(field, initialValues?.[field.name]);
  }
  return values;
}

/**
 * Validate raw form values against field definitions.
 * Returns coerced submission values on success, or errors on failure.
 */
export function validateFieldValues(
  fields: InputFieldDefinition[],
  values: FieldValues,
): { ok: true; values: FieldValues } | { ok: false; errors: FieldErrors } {
  const errors: FieldErrors = {};
  const submission: FieldValues = {};

  for (const field of fields) {
    const raw = values[field.name];

    if (field.type === 'boolean') {
      submission[field.name] = Boolean(raw);
      continue;
    }

    if (isEmpty(raw)) {
      if (field.required) {
        errors[field.name] = 'This field is required';
      } else if (field.default_value !== undefined && field.default_value !== null && field.default_value !== '') {
        submission[field.name] = field.default_value;
      }
      continue;
    }

    if (field.type === 'number') {
      const num = typeof raw === 'number' ? raw : Number(raw);
      if (Number.isNaN(num)) {
        errors[field.name] = 'Must be a valid number';
      } else {
        submission[field.name] = num;
      }
      continue;
    }

    if (field.type === 'array' || field.type === 'object') {
      try {
        const parsed = JSON.parse(raw);
        if (field.type === 'array' && !Array.isArray(parsed)) {
          errors[field.name] = 'Must be a JSON array';
        } else if (field.type === 'object' && (parsed === null || Array.isArray(parsed) || typeof parsed !== 'object')) {
          errors[field.name] = 'Must be a JSON object';
        } else {
          submission[field.name] = parsed;
        }
      } catch {
        errors[field.name] = 'Must be valid JSON';
      }
      continue;
    }

    if (field.type === 'dropdown') {
      const opts = normalizeDropdownOptions(field);
      const match = opts.find((o) => String(o.value) === String(raw) || o.key === String(raw));
      if (!match) {
        errors[field.name] = 'Select a valid option';
      } else {
        submission[field.name] = match.value;
      }
      continue;
    }

    submission[field.name] = raw;
  }

  if (Object.keys(errors).length > 0) {
    return { ok: false, errors };
  }
  return { ok: true, values: submission };
}

/** True if the workflow's input node declares any required fields. */
export function getRequiredInputFields(
  workflow: any,
): InputFieldDefinition[] {
  if (!workflow) return [];
  if (workflow.required_input_fields && workflow.required_input_fields.length > 0) {
    return workflow.required_input_fields;
  }
  const nodes = workflow.graph?.nodes || [];
  const inputNode = nodes.find((n: any) => n?.type === 'input');
  return inputNode?.config?.input_fields || [];
}

export function hasRequiredInputFields(workflow: any): boolean {
  return getRequiredInputFields(workflow).some((f) => f.required);
}

// ============================================================================
// Inline form (also embeddable inside other dialogs, e.g. ScheduleDialog)
// ============================================================================

export interface InputFieldsFormProps {
  fields: InputFieldDefinition[];
  values: FieldValues;
  errors?: FieldErrors;
  onChange: (values: FieldValues) => void;
}

export function InputFieldsForm({ fields, values, errors, onChange }: InputFieldsFormProps) {
  const update = (name: string, value: any) => {
    onChange({ ...values, [name]: value });
  };

  return (
    <div className="space-y-4">
      {fields.map((field) => {
        const fieldId = `input-field-${field.name}`;
        const error = errors?.[field.name];

        return (
          <div key={field.name} className="space-y-2">
            <Label htmlFor={fieldId} className="flex items-center gap-1">
              <span>{field.name}</span>
              {field.required && <span className="text-destructive">*</span>}
              <span className="text-xs text-muted-foreground font-normal">({field.type})</span>
            </Label>

            {field.type === 'dropdown' ? (
              (() => {
                const opts = normalizeDropdownOptions(field);
                const current = values[field.name];
                const selectedKey =
                  current === undefined || current === null || current === ''
                    ? ''
                    : (opts.find((o) => String(o.value) === String(current))?.key ?? '');
                return (
                  <Select
                    value={selectedKey}
                    onValueChange={(key) => {
                      const match = opts.find((o) => o.key === key);
                      update(field.name, match ? match.value : key);
                    }}
                  >
                    <SelectTrigger id={fieldId}>
                      <SelectValue placeholder="Select an option" />
                    </SelectTrigger>
                    <SelectContent>
                      {opts.length === 0 ? (
                        <div className="px-2 py-1.5 text-xs text-muted-foreground">
                          No options defined
                        </div>
                      ) : (
                        opts.map((o) => (
                          <SelectItem key={o.key} value={o.key}>
                            {o.label}
                          </SelectItem>
                        ))
                      )}
                    </SelectContent>
                  </Select>
                );
              })()
            ) : field.type === 'boolean' ? (
              <div className="flex items-center gap-2">
                <Switch
                  id={fieldId}
                  checked={Boolean(values[field.name])}
                  onCheckedChange={(checked) => update(field.name, checked)}
                />
                <span className="text-sm text-muted-foreground">
                  {values[field.name] ? 'true' : 'false'}
                </span>
              </div>
            ) : field.type === 'array' || field.type === 'object' ? (
              <Textarea
                id={fieldId}
                value={values[field.name] ?? ''}
                onChange={(e) => update(field.name, e.target.value)}
                placeholder={field.type === 'array' ? '[]' : '{}'}
                rows={4}
                className="font-mono text-xs"
              />
            ) : field.type === 'number' ? (
              <Input
                id={fieldId}
                type="number"
                value={values[field.name] ?? ''}
                onChange={(e) => update(field.name, e.target.value)}
                placeholder={field.default_value !== undefined ? String(field.default_value) : ''}
              />
            ) : (
              <Input
                id={fieldId}
                type="text"
                value={values[field.name] ?? ''}
                onChange={(e) => update(field.name, e.target.value)}
                placeholder={field.default_value !== undefined ? String(field.default_value) : ''}
              />
            )}

            {field.description && !error && (
              <p className="text-xs text-muted-foreground">{field.description}</p>
            )}
            {error && <p className="text-xs text-destructive">{error}</p>}
          </div>
        );
      })}
    </div>
  );
}

/** Build the initial form-state for a set of fields, optionally seeded with prior values. */
export function useInputFieldsFormState(
  fields: InputFieldDefinition[],
  initialValues?: FieldValues,
) {
  const [values, setValues] = React.useState<FieldValues>(() =>
    buildInitialValues(fields, initialValues),
  );
  const [errors, setErrors] = React.useState<FieldErrors>({});

  // Reset when fields or initialValues change identity
  React.useEffect(() => {
    setValues(buildInitialValues(fields, initialValues));
    setErrors({});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fields, JSON.stringify(initialValues)]);

  return { values, setValues, errors, setErrors };
}

// ============================================================================
// Standalone prompt dialog
// ============================================================================

export interface InputFieldsPromptDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  fields: InputFieldDefinition[];
  initialValues?: FieldValues;
  title?: string;
  description?: string;
  submitLabel?: string;
  onSubmit: (values: FieldValues) => void;
  submitting?: boolean;
}

export function InputFieldsPromptDialog({
  open,
  onOpenChange,
  fields,
  initialValues,
  title = 'Provide Workflow Inputs',
  description = 'This workflow requires input values before it can run.',
  submitLabel = 'Continue',
  onSubmit,
  submitting = false,
}: InputFieldsPromptDialogProps) {
  const { values, setValues, errors, setErrors } = useInputFieldsFormState(fields, initialValues);

  // Reset when dialog opens
  React.useEffect(() => {
    if (open) {
      setValues(buildInitialValues(fields, initialValues));
      setErrors({});
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const allRequiredFilled = fields.every((f) =>
    !f.required || f.type === 'boolean' || !isEmpty(values[f.name]),
  );

  const handleSubmit = () => {
    const result = validateFieldValues(fields, values);
    if (!result.ok) {
      setErrors(result.errors);
      return;
    }
    setErrors({});
    onSubmit(result.values);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[550px] max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>

        <div className="py-4">
          <InputFieldsForm
            fields={fields}
            values={values}
            errors={errors}
            onChange={setValues}
          />
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={submitting}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={!allRequiredFilled || submitting}>
            {submitting ? 'Working…' : submitLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
