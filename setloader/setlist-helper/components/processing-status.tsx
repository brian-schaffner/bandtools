"use client";

import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Progress } from './ui/progress';
import { Badge } from './ui/badge';
import { CheckCircle, Clock, AlertCircle, Loader2 } from 'lucide-react';

interface ProcessingStage {
  id: string;
  name: string;
  status: 'pending' | 'running' | 'completed' | 'error';
  message?: string;
  details?: string;
  duration?: number;
}

interface ProcessingStatusProps {
  isProcessing: boolean;
  stages: ProcessingStage[];
  currentStage?: string;
  error?: string;
  onComplete?: () => void;
}

export function ProcessingStatus({ 
  isProcessing, 
  stages, 
  currentStage, 
  error, 
  onComplete 
}: ProcessingStatusProps) {
  const [expandedStage, setExpandedStage] = useState<string | null>(null);

  useEffect(() => {
    if (!isProcessing && stages.length > 0 && onComplete) {
      const allCompleted = stages.every(stage => stage.status === 'completed' || stage.status === 'error');
      if (allCompleted) {
        setTimeout(onComplete, 1000);
      }
    }
  }, [isProcessing, stages, onComplete]);

  if (!isProcessing && stages.length === 0) {
    return null;
  }

  const completedStages = stages.filter(stage => stage.status === 'completed').length;
  const progress = stages.length > 0 ? (completedStages / stages.length) * 100 : 0;

  const getStageIcon = (stage: ProcessingStage) => {
    switch (stage.status) {
      case 'completed':
        return <CheckCircle className="h-4 w-4 text-green-500" />;
      case 'running':
        return <Loader2 className="h-4 w-4 animate-spin text-blue-500" />;
      case 'error':
        return <AlertCircle className="h-4 w-4 text-red-500" />;
      default:
        return <Clock className="h-4 w-4 text-gray-400" />;
    }
  };

  const getStageBadge = (stage: ProcessingStage) => {
    switch (stage.status) {
      case 'completed':
        return <Badge variant="default" className="bg-green-500">Completed</Badge>;
      case 'running':
        return <Badge variant="default" className="bg-blue-500">Running</Badge>;
      case 'error':
        return <Badge variant="destructive">Error</Badge>;
      default:
        return <Badge variant="secondary">Pending</Badge>;
    }
  };

  return (
    <Card className="w-full">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          {isProcessing ? (
            <Loader2 className="h-5 w-5 animate-spin text-blue-500" />
          ) : error ? (
            <AlertCircle className="h-5 w-5 text-red-500" />
          ) : (
            <CheckCircle className="h-5 w-5 text-green-500" />
          )}
          {isProcessing ? 'Processing Setlist...' : error ? 'Processing Failed' : 'Processing Complete'}
        </CardTitle>
        <div className="space-y-2">
          <div className="flex justify-between text-sm text-muted-foreground">
            <span>Progress</span>
            <span>{Math.round(progress)}%</span>
          </div>
          <Progress value={progress} className="w-full" />
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {stages.map((stage, index) => (
          <div key={stage.id} className="space-y-2">
            <div 
              className="flex items-center justify-between p-3 rounded-lg border cursor-pointer hover:bg-muted/50"
              onClick={() => setExpandedStage(expandedStage === stage.id ? null : stage.id)}
            >
              <div className="flex items-center gap-3">
                {getStageIcon(stage)}
                <div>
                  <div className="font-medium">{stage.name}</div>
                  {stage.message && (
                    <div className="text-sm text-muted-foreground">{stage.message}</div>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-2">
                {stage.duration && (
                  <span className="text-xs text-muted-foreground">
                    {stage.duration}ms
                  </span>
                )}
                {getStageBadge(stage)}
              </div>
            </div>
            
            {expandedStage === stage.id && stage.details && (
              <div className="ml-7 p-3 bg-muted/50 rounded-lg">
                <div className="text-sm font-medium mb-2">Details:</div>
                <pre className="text-xs text-muted-foreground whitespace-pre-wrap">
                  {stage.details}
                </pre>
              </div>
            )}
          </div>
        ))}
        
        {error && (
          <div className="p-3 bg-red-50 border border-red-200 rounded-lg">
            <div className="flex items-center gap-2 text-red-700">
              <AlertCircle className="h-4 w-4" />
              <span className="font-medium">Error:</span>
            </div>
            <div className="text-sm text-red-600 mt-1">{error}</div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}