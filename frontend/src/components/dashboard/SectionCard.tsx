import { LucideIcon, ArrowRight } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Link } from 'react-router-dom';

interface SectionCardProps {
  title: string;
  icon: LucideIcon;
  href?: string;
  children: React.ReactNode;
  action?: {
    label: string;
    onClick: () => void;
  };
}

export function SectionCard({
  title,
  icon: Icon,
  href,
  children,
  action,
}: SectionCardProps) {
  return (
    <Card className="h-full">
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <div className="flex items-center gap-2">
          <Icon className="w-5 h-5" />
          <CardTitle className="text-lg">{title}</CardTitle>
        </div>
        <div className="flex items-center gap-2">
          {action && (
            <Button
              variant="outline"
              size="sm"
              onClick={action.onClick}
              className="text-xs"
            >
              {action.label}
            </Button>
          )}
          {href && (
            <Link to={href}>
              <Button variant="link" size="sm" className="text-xs hover:translate-x-1 transition-transform">
                View all
                <ArrowRight className="w-3 h-3 ml-1" />
              </Button>
            </Link>
          )}
        </div>
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}
