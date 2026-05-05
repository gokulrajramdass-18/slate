/**
 * Clarification Step
 *
 * Asks follow-up questions to refine the analysis.
 */

'use client';

import { useState } from 'react';
import { useGuidedCreationStore } from '@/lib/stores/guided-creation-store';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { HelpCircle, Info, CheckCircle2, Edit3, Eye, EyeOff } from 'lucide-react';
import { cn } from '@/lib/utils';

export function ClarificationStep() {
  const { clarificationQuestions, clarificationAnswers, setClarificationAnswer } =
    useGuidedCreationStore();

  const [showAnswered, setShowAnswered] = useState(true);
  const [editingQuestion, setEditingQuestion] = useState<string | null>(null);

  if (clarificationQuestions.length === 0) {
    return <div>No clarification needed.</div>;
  }

  const answeredCount = Object.keys(clarificationAnswers).length;
  const totalCount = clarificationQuestions.length;
  const hasAnswers = answeredCount > 0;
  const allAnswered = answeredCount === totalCount;

  const getQuestionStatus = (question: any) => {
    const answer = clarificationAnswers[question.question];
    if (answer === undefined || answer === '') return 'unanswered';
    if (answer === '[SKIPPED]') return 'skipped';
    return 'answered';
  };

  const getAnswerDisplay = (question: any) => {
    const answer = clarificationAnswers[question.question];
    if (answer === '[SKIPPED]') return 'Skipped';
    if (question.type === 'date_range' && typeof answer === 'object') {
      return `${answer.start || 'N/A'} to ${answer.end || 'N/A'}`;
    }
    return answer || '';
  };

  const handleEdit = (questionText: string) => {
    setEditingQuestion(questionText);
  };

  const handleSkipQuestion = (questionText: string) => {
    setClarificationAnswer(questionText, '[SKIPPED]');
    setEditingQuestion(null);
  };

  const renderQuestionInput = (question: any, index: number) => {
    const currentAnswer = clarificationAnswers[question.question];
    const status = getQuestionStatus(question);

    switch (question.type) {
      case 'multiple_choice':
        return (
          <div className="space-y-3">
            <RadioGroup
              value={currentAnswer === '[SKIPPED]' ? '' : currentAnswer || ''}
              onValueChange={(value) => {
                setClarificationAnswer(question.question, value);
                setEditingQuestion(null);
              }}
            >
              <div className="space-y-2">
                {question.options?.map((option: string) => (
                  <div key={option} className="flex items-center space-x-2">
                    <RadioGroupItem value={option} id={`${index}-${option}`} />
                    <Label htmlFor={`${index}-${option}`} className="font-normal cursor-pointer">
                      {option}
                    </Label>
                  </div>
                ))}
              </div>
            </RadioGroup>
            {status === 'unanswered' && (
              <button
                onClick={() => handleSkipQuestion(question.question)}
                className="text-sm text-muted-foreground hover:text-foreground underline"
              >
                Skip this question
              </button>
            )}
          </div>
        );

      case 'text':
        return (
          <div className="space-y-3">
            <Textarea
              value={currentAnswer === '[SKIPPED]' ? '' : currentAnswer || ''}
              onChange={(e) => setClarificationAnswer(question.question, e.target.value)}
              placeholder="Enter your answer..."
              rows={4}
            />
            {status === 'unanswered' && (
              <button
                onClick={() => handleSkipQuestion(question.question)}
                className="text-sm text-muted-foreground hover:text-foreground underline"
              >
                Skip this question
              </button>
            )}
          </div>
        );

      case 'date_range':
        return (
          <div className="space-y-3">
            <div className="flex gap-4">
              <div className="flex-1">
                <Label className="text-sm">Start Date</Label>
                <Input
                  type="date"
                  value={currentAnswer === '[SKIPPED]' ? '' : currentAnswer?.start || ''}
                  onChange={(e) =>
                    setClarificationAnswer(question.question, {
                      ...currentAnswer,
                      start: e.target.value,
                    })
                  }
                />
              </div>
              <div className="flex-1">
                <Label className="text-sm">End Date</Label>
                <Input
                  type="date"
                  value={currentAnswer === '[SKIPPED]' ? '' : currentAnswer?.end || ''}
                  onChange={(e) =>
                    setClarificationAnswer(question.question, {
                      ...currentAnswer,
                      end: e.target.value,
                    })
                  }
                />
              </div>
            </div>
            {status === 'unanswered' && (
              <button
                onClick={() => handleSkipQuestion(question.question)}
                className="text-sm text-muted-foreground hover:text-foreground underline"
              >
                Skip this question
              </button>
            )}
          </div>
        );

      default:
        return (
          <div className="space-y-3">
            <Input
              value={currentAnswer === '[SKIPPED]' ? '' : currentAnswer || ''}
              onChange={(e) => setClarificationAnswer(question.question, e.target.value)}
              placeholder="Enter your answer..."
            />
            {status === 'unanswered' && (
              <button
                onClick={() => handleSkipQuestion(question.question)}
                className="text-sm text-muted-foreground hover:text-foreground underline"
              >
                Skip this question
              </button>
            )}
          </div>
        );
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start gap-4">
        <div className="p-3 bg-primary/10 rounded-lg">
          <HelpCircle className="h-6 w-6 text-primary" />
        </div>
        <div className="flex-1">
          <h2 className="text-2xl font-bold mb-2">A Few More Details (Optional)</h2>
          <p className="text-muted-foreground">
            Help us better understand your needs by answering these questions. This will allow us to
            recommend the most relevant resources and create a more accurate plan.
          </p>
        </div>
      </div>

      {/* Progress and Toggle */}
      <div className="flex items-center justify-between">
        <Alert className="flex-1 mr-4">
          <Info className="h-4 w-4" />
          <AlertDescription>
            <div className="space-y-1">
              <p>
                <strong>These questions are optional.</strong> You can answer them for better recommendations,
                or skip to continue with the current analysis.
              </p>
              <div className="flex items-center gap-2 mt-2">
                <span className="text-sm font-medium">
                  Progress: {answeredCount} of {totalCount} questions answered
                </span>
                {allAnswered && (
                  <Badge variant="default" className="bg-green-600">
                    <CheckCircle2 className="w-3 h-3 mr-1" />
                    Complete
                  </Badge>
                )}
              </div>
            </div>
          </AlertDescription>
        </Alert>

        {/* Toggle Button */}
        {hasAnswers && (
          <Button
            variant="outline"
            size="sm"
            onClick={() => setShowAnswered(!showAnswered)}
            className="shrink-0"
          >
            {showAnswered ? (
              <>
                <EyeOff className="w-4 h-4 mr-2" />
                Hide Answered
              </>
            ) : (
              <>
                <Eye className="w-4 h-4 mr-2" />
                Show All
              </>
            )}
          </Button>
        )}
      </div>

      {/* Questions */}
      <div className="space-y-4">
        {clarificationQuestions.map((question, index) => {
          const status = getQuestionStatus(question);
          const isEditing = editingQuestion === question.question;
          const shouldShow = status === 'unanswered' || showAnswered || isEditing;

          if (!shouldShow) return null;

          return (
            <Card
              key={index}
              className={cn(
                'transition-all',
                status === 'answered' && 'border-green-200 bg-green-50/50 dark:border-green-800 dark:bg-green-950/20',
                status === 'skipped' && 'border-gray-200 bg-gray-50 dark:border-gray-800 dark:bg-gray-900/50 opacity-60'
              )}
            >
              <CardHeader>
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <CardTitle className="text-base">
                        {index + 1}. {question.question}
                      </CardTitle>
                      {status === 'answered' && (
                        <Badge variant="default" className="bg-green-600 text-xs">
                          <CheckCircle2 className="w-3 h-3 mr-1" />
                          Answered
                        </Badge>
                      )}
                      {status === 'skipped' && (
                        <Badge variant="secondary" className="text-xs">
                          Skipped
                        </Badge>
                      )}
                    </div>
                    {question.help_text && (
                      <CardDescription>{question.help_text}</CardDescription>
                    )}
                  </div>

                  {/* Edit button for answered questions */}
                  {status !== 'unanswered' && !isEditing && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleEdit(question.question)}
                      className="shrink-0"
                    >
                      <Edit3 className="w-4 h-4" />
                    </Button>
                  )}
                </div>
              </CardHeader>

              <CardContent>
                {status !== 'unanswered' && !isEditing ? (
                  /* Show answer summary for answered/skipped questions */
                  <div className="p-3 bg-white dark:bg-gray-950 rounded-md border">
                    <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
                      {getAnswerDisplay(question)}
                    </p>
                  </div>
                ) : (
                  /* Show input for unanswered or editing questions */
                  renderQuestionInput(question, index)
                )}
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Show message when answered questions are hidden */}
      {hasAnswers && !showAnswered && answeredCount > 0 && (
        <Alert>
          <Info className="h-4 w-4" />
          <AlertDescription>
            {answeredCount} answered question{answeredCount > 1 ? 's are' : ' is'} hidden.{' '}
            <button
              onClick={() => setShowAnswered(true)}
              className="underline font-medium hover:text-primary"
            >
              Show all questions
            </button>
          </AlertDescription>
        </Alert>
      )}
    </div>
  );
}
