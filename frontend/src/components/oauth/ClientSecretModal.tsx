'use client';

import { useState } from 'react';
import { Copy, Check } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import { Alert, AlertDescription } from '@/components/ui/alert';

interface ClientSecretModalProps {
  secret: string | null;
  open: boolean;
  onClose: () => void;
}

export function ClientSecretModal({ secret, open, onClose }: ClientSecretModalProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    if (secret) {
      navigator.clipboard.writeText(secret);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Client Secret Created</DialogTitle>
          <DialogDescription>
            Your client secret has been generated. Copy it now - it won't be shown again.
          </DialogDescription>
        </DialogHeader>

        <Alert variant="destructive">
          <AlertDescription>
            Make sure to copy your client secret now. You won't be able to see it again!
          </AlertDescription>
        </Alert>

        <div className="space-y-4">
          <div className="bg-muted p-4 rounded-lg font-mono text-sm break-all relative group">
            {secret}
            <Button
              variant="ghost"
              size="sm"
              className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity"
              onClick={handleCopy}
            >
              {copied ? (
                <Check className="h-4 w-4 text-green-500" />
              ) : (
                <Copy className="h-4 w-4" />
              )}
            </Button>
          </div>

          <div className="text-sm text-muted-foreground space-y-2">
            <p className="font-medium">Next steps:</p>
            <ol className="list-decimal list-inside space-y-1 ml-2">
              <li>Copy and securely store this client secret</li>
              <li>Use it with your client ID to obtain access tokens</li>
              <li>Make authenticated requests to the Agent APIs</li>
            </ol>
          </div>
        </div>

        <DialogFooter>
          <Button onClick={handleCopy}>
            {copied ? (
              <>
                <Check className="mr-2 h-4 w-4" />
                Copied!
              </>
            ) : (
              <>
                <Copy className="mr-2 h-4 w-4" />
                Copy Secret
              </>
            )}
          </Button>
          <Button variant="outline" onClick={onClose}>
            Close
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
