import { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { Mail, Send, CheckCircle, XCircle, AlertCircle } from "lucide-react";
import { toast } from "sonner";
import { SettingsHeader } from "@/components/settings/settings-header";

interface SMTPConfig {
  smtp_host: string;
  smtp_port: number;
  smtp_username: string;
  smtp_from_email: string;
  smtp_from_name: string;
  smtp_use_tls: boolean;
  smtp_use_ssl: boolean;
  is_active: boolean;
}

export default function SettingsSmtpPage() {
  const [loading, setLoading] = useState(false);
  const [testing, setTesting] = useState(false);
  const [hasConfig, setHasConfig] = useState(false);

  const [smtpHost, setSmtpHost] = useState("");
  const [smtpPort, setSmtpPort] = useState(587);
  const [smtpUsername, setSmtpUsername] = useState("");
  const [smtpPassword, setSmtpPassword] = useState("");
  const [smtpFromEmail, setSmtpFromEmail] = useState("");
  const [smtpFromName, setSmtpFromName] = useState("Slate");
  const [smtpUseTls, setSmtpUseTls] = useState(true);
  const [smtpUseSsl, setSmtpUseSsl] = useState(false);
  const [isActive, setIsActive] = useState(true);

  const [testEmail, setTestEmail] = useState("");

  useEffect(() => {
    fetchConfig();
  }, []);

  const fetchConfig = async () => {
    try {
      const response = await fetch("http://localhost:5055/api/smtp/config");
      if (response.ok) {
        const data: SMTPConfig = await response.json();
        if (data) {
          setHasConfig(true);
          setSmtpHost(data.smtp_host);
          setSmtpPort(data.smtp_port);
          setSmtpUsername(data.smtp_username);
          setSmtpFromEmail(data.smtp_from_email);
          setSmtpFromName(data.smtp_from_name || "Open Notebook");
          setSmtpUseTls(data.smtp_use_tls);
          setSmtpUseSsl(data.smtp_use_ssl);
          setIsActive(data.is_active);
        }
      }
    } catch (error) {
      console.error("Failed to fetch SMTP config:", error);
    }
  };

  const handleSave = async () => {
    if (!smtpHost || !smtpPort || !smtpUsername || !smtpFromEmail) {
      toast.error("Please fill in all required fields");
      return;
    }

    if (!smtpPassword && !hasConfig) {
      toast.error("Password is required for new configuration");
      return;
    }

    try {
      setLoading(true);

      const payload: any = {
        smtp_host: smtpHost,
        smtp_port: smtpPort,
        smtp_username: smtpUsername,
        smtp_from_email: smtpFromEmail,
        smtp_from_name: smtpFromName,
        smtp_use_tls: smtpUseTls,
        smtp_use_ssl: smtpUseSsl,
      };

      // Only include password if it's been entered
      if (smtpPassword) {
        payload.smtp_password = smtpPassword;
      }

      const response = await fetch("http://localhost:5055/api/smtp/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (response.ok) {
        toast.success("SMTP configuration saved");
        setHasConfig(true);
        setSmtpPassword(""); // Clear password field after saving
        await fetchConfig();
      } else {
        const error = await response.json();
        toast.error(error.detail || "Failed to save SMTP configuration");
      }
    } catch (error) {
      toast.error("Failed to save SMTP configuration");
    } finally {
      setLoading(false);
    }
  };

  const handleTest = async () => {
    if (!testEmail) {
      toast.error("Please enter a test email address");
      return;
    }

    if (!hasConfig) {
      toast.error("Please save SMTP configuration first");
      return;
    }

    try {
      setTesting(true);

      const response = await fetch("http://localhost:5055/api/smtp/test", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ test_email: testEmail }),
      });

      if (response.ok) {
        toast.success(`Test email sent to ${testEmail}`);
      } else {
        const error = await response.json();
        toast.error(error.detail || "Failed to send test email");
      }
    } catch (error) {
      toast.error("Failed to send test email");
    } finally {
      setTesting(false);
    }
  };

  const handleDelete = async () => {
    if (!confirm("Are you sure you want to delete the SMTP configuration?")) {
      return;
    }

    try {
      const response = await fetch("http://localhost:5055/api/smtp/config", {
        method: "DELETE",
      });

      if (response.ok) {
        toast.success("SMTP configuration deleted");
        setHasConfig(false);
        setSmtpHost("");
        setSmtpPort(587);
        setSmtpUsername("");
        setSmtpPassword("");
        setSmtpFromEmail("");
        setSmtpFromName("Slate");
        setSmtpUseTls(true);
        setSmtpUseSsl(false);
      } else {
        toast.error("Failed to delete SMTP configuration");
      }
    } catch (error) {
      toast.error("Failed to delete SMTP configuration");
    }
  };

  return (
    <div className="space-y-6">
      <SettingsHeader
        title="SMTP Settings"
        description="Configure email settings for sending OTP codes and notifications"
      />

      {/* Status */}
      {hasConfig && (
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              {isActive ? (
                <>
                  <CheckCircle className="w-5 h-5 text-green-600" />
                  <div>
                    <p className="font-medium">SMTP Configured</p>
                    <p className="text-sm text-gray-500">Email sending is active</p>
                  </div>
                </>
              ) : (
                <>
                  <XCircle className="w-5 h-5 text-gray-400" />
                  <div>
                    <p className="font-medium">SMTP Inactive</p>
                    <p className="text-sm text-gray-500">Email sending is disabled</p>
                  </div>
                </>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Configuration Form */}
      <Card>
        <CardHeader>
          <CardTitle>SMTP Configuration</CardTitle>
          <CardDescription>
            Enter your SMTP server details. Common providers: Gmail (smtp.gmail.com:587),
            SendGrid (smtp.sendgrid.net:587), AWS SES, Mailgun
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <Label>SMTP Host *</Label>
              <Input
                value={smtpHost}
                onChange={(e) => setSmtpHost(e.target.value)}
                placeholder="smtp.gmail.com"
              />
            </div>

            <div>
              <Label>SMTP Port *</Label>
              <Input
                type="number"
                value={smtpPort}
                onChange={(e) => setSmtpPort(parseInt(e.target.value))}
                placeholder="587"
              />
            </div>

            <div>
              <Label>Username *</Label>
              <Input
                value={smtpUsername}
                onChange={(e) => setSmtpUsername(e.target.value)}
                placeholder="your-email@example.com"
              />
            </div>

            <div>
              <Label>Password *</Label>
              <Input
                type="password"
                value={smtpPassword}
                onChange={(e) => setSmtpPassword(e.target.value)}
                placeholder={hasConfig ? "••••••••" : "Enter password"}
              />
              {hasConfig && (
                <p className="text-xs text-gray-500 mt-1">
                  Leave blank to keep existing password
                </p>
              )}
            </div>

            <div>
              <Label>From Email *</Label>
              <Input
                type="email"
                value={smtpFromEmail}
                onChange={(e) => setSmtpFromEmail(e.target.value)}
                placeholder="noreply@example.com"
              />
            </div>

            <div>
              <Label>From Name</Label>
              <Input
                value={smtpFromName}
                onChange={(e) => setSmtpFromName(e.target.value)}
                placeholder="Slate"
              />
            </div>
          </div>

          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <Label>Use TLS</Label>
                <p className="text-xs text-gray-500">Recommended for port 587</p>
              </div>
              <Switch checked={smtpUseTls} onCheckedChange={setSmtpUseTls} />
            </div>

            <div className="flex items-center justify-between">
              <div>
                <Label>Use SSL</Label>
                <p className="text-xs text-gray-500">Recommended for port 465</p>
              </div>
              <Switch checked={smtpUseSsl} onCheckedChange={setSmtpUseSsl} />
            </div>
          </div>

          <div className="flex gap-2">
            <Button onClick={handleSave} disabled={loading}>
              {loading ? "Saving..." : "Save Configuration"}
            </Button>
            {hasConfig && (
              <Button variant="outline" onClick={handleDelete}>
                Delete Configuration
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Test Configuration */}
      {hasConfig && (
        <Card>
          <CardHeader>
            <CardTitle>Test Configuration</CardTitle>
            <CardDescription>
              Send a test email to verify your SMTP settings are working
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <Label>Test Email Address</Label>
              <Input
                type="email"
                value={testEmail}
                onChange={(e) => setTestEmail(e.target.value)}
                placeholder="test@example.com"
              />
            </div>
            <Button onClick={handleTest} disabled={testing}>
              <Send className="w-4 h-4 mr-2" />
              {testing ? "Sending..." : "Send Test Email"}
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Common Providers */}
      <Card>
        <CardHeader>
          <CardTitle>Common SMTP Providers</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3 text-sm">
            <div className="flex items-start gap-3">
              <Badge variant="outline">Gmail</Badge>
              <div>
                <p className="font-medium">smtp.gmail.com:587</p>
                <p className="text-gray-500">Use app password, not regular password</p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <Badge variant="outline">SendGrid</Badge>
              <div>
                <p className="font-medium">smtp.sendgrid.net:587</p>
                <p className="text-gray-500">Username: apikey, Password: Your API key</p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <Badge variant="outline">AWS SES</Badge>
              <div>
                <p className="font-medium">email-smtp.[region].amazonaws.com:587</p>
                <p className="text-gray-500">Use SMTP credentials from AWS console</p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <Badge variant="outline">Mailgun</Badge>
              <div>
                <p className="font-medium">smtp.mailgun.org:587</p>
                <p className="text-gray-500">Use Mailgun SMTP credentials</p>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
