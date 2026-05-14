import { LucideIcon } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Link } from 'react-router-dom';

interface HeroStatCardProps {
  title: string;
  value: number;
  icon: LucideIcon;
  color?: string;
  bgColor?: string;
  href?: string;
  trend?: { value: number; direction: "up" | "down" } | null;
  highlight?: boolean;
}

export function HeroStatCard({
  title,
  value,
  icon: Icon,
  color,
  bgColor,
  href,
  trend,
  highlight = false,
}: HeroStatCardProps) {
  const cardContent = (
    <Card
      className={`hover:shadow-xl hover:scale-105 transition-all duration-300 border-2 ${
        highlight && value > 0 ? "border-orange-500 animate-pulse-slow" : "hover:border-opacity-50"
      }`}
    >
      <CardContent className="pt-6">
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <p className="text-sm font-medium text-gray-600 dark:text-gray-400 mb-2">
              {title}
            </p>
            <div className="flex items-baseline gap-2">
              <p className="text-4xl font-bold">{value.toLocaleString()}</p>
              {trend && (
                <span
                  className={`text-sm font-medium ${
                    trend.direction === "up" ? "text-green-600" : "text-red-600"
                  }`}
                >
                  {trend.direction === "up" ? "↑" : "↓"} {trend.value}%
                </span>
              )}
            </div>
          </div>
          <div
            className={`p-3 rounded-lg ${bgColor} transition-transform hover:scale-110`}
          >
            <Icon className={`w-7 h-7 ${color}`} />
          </div>
        </div>
      </CardContent>
    </Card>
  );

  if (href) {
    return <Link to={href}>{cardContent}</Link>;
  }

  return cardContent;
}
