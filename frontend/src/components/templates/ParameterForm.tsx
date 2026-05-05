"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { HelpCircle } from "lucide-react";
import type { TemplateParameter } from "@/lib/api/templates";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";

interface ParameterFormProps {
  parameters: TemplateParameter[];
  values: Record<string, any>;
  onChange: (values: Record<string, any>) => void;
  errors?: Record<string, string>;
}

export function ParameterForm({ parameters, values, onChange, errors = {} }: ParameterFormProps) {
  const [localValues, setLocalValues] = useState<Record<string, any>>(values);

  useEffect(() => {
    setLocalValues(values);
  }, [values]);

  const handleChange = (paramName: string, value: any) => {
    const newValues = { ...localValues, [paramName]: value };
    setLocalValues(newValues);
    onChange(newValues);
  };

  const renderField = (param: TemplateParameter) => {
    const value = localValues[param.name] ?? param.default_value ?? "";
    const error = errors[param.name];

    switch (param.type) {
      case "string":
        return (
          <Input
            id={param.name}
            type="text"
            value={value}
            onChange={(e) => handleChange(param.name, e.target.value)}
            placeholder={param.default_value || `Enter ${param.name}`}
            className={error ? "border-destructive" : ""}
          />
        );

      case "number":
        return (
          <Input
            id={param.name}
            type="number"
            value={value}
            onChange={(e) => handleChange(param.name, parseFloat(e.target.value) || 0)}
            placeholder={param.default_value?.toString() || `Enter ${param.name}`}
            className={error ? "border-destructive" : ""}
          />
        );

      case "boolean":
        return (
          <div className="flex items-center space-x-2">
            <Checkbox
              id={param.name}
              checked={value === true || value === "true"}
              onCheckedChange={(checked) => handleChange(param.name, checked)}
            />
            <Label
              htmlFor={param.name}
              className="text-sm font-normal cursor-pointer"
            >
              Enable
            </Label>
          </div>
        );

      case "date":
        return (
          <Input
            id={param.name}
            type="date"
            value={value || ""}
            onChange={(e) => handleChange(param.name, e.target.value)}
            className={error ? "border-destructive" : ""}
          />
        );

      case "select":
        return (
          <Select
            value={value}
            onValueChange={(val) => handleChange(param.name, val)}
          >
            <SelectTrigger
              id={param.name}
              className={error ? "border-destructive" : ""}
            >
              <SelectValue placeholder={`Select ${param.name}`} />
            </SelectTrigger>
            <SelectContent>
              {param.options?.map((option) => (
                <SelectItem key={option} value={option}>
                  {option}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        );

      default:
        return (
          <Input
            id={param.name}
            type="text"
            value={value}
            onChange={(e) => handleChange(param.name, e.target.value)}
            className={error ? "border-destructive" : ""}
          />
        );
    }
  };

  if (parameters.length === 0) {
    return (
      <div className="text-center py-8 text-muted-foreground">
        <p>No parameters required for this template.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {parameters.map((param) => {
        const error = errors[param.name];

        return (
          <div key={param.name} className="space-y-2">
            <div className="flex items-center gap-2">
              <Label htmlFor={param.name} className="flex items-center gap-1.5">
                {param.name}
                {param.required && <span className="text-destructive">*</span>}
              </Label>
              {param.description && (
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <HelpCircle className="h-4 w-4 text-muted-foreground cursor-help" />
                    </TooltipTrigger>
                    <TooltipContent side="right" className="max-w-xs">
                      <p className="text-sm">{param.description}</p>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              )}
            </div>

            {renderField(param)}

            {error && (
              <p className="text-sm text-destructive">{error}</p>
            )}

            {param.description && !error && (
              <p className="text-sm text-muted-foreground">{param.description}</p>
            )}
          </div>
        );
      })}

      <div className="text-xs text-muted-foreground">
        <p>* Required fields</p>
      </div>
    </div>
  );
}
