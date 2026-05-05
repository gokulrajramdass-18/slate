import { Badge } from "@/components/ui/badge";
import { ArrowRight } from "lucide-react";
import Link from "next/link";
import { formatDistanceToNow } from "date-fns";

interface RecentItem {
  id: string;
  title?: string;
  status?: string;
  created_at?: string;
  started_at?: string;
  href: string;
}

interface RecentItemListProps {
  items: RecentItem[];
  emptyMessage?: string;
}

const statusColors: Record<string, string> = {
  completed: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300",
  failed: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300",
  running: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300",
  pending: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300",
  cancelled: "bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-300",
};

export function RecentItemList({ items, emptyMessage = "No recent items" }: RecentItemListProps) {
  if (items.length === 0) {
    return (
      <div className="text-sm text-muted-foreground text-center py-8">
        {emptyMessage}
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {items.map((item) => (
        <Link
          key={item.id}
          href={item.href}
          className="flex items-center justify-between p-3 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800 transition-all duration-300 hover:scale-[1.02] hover:shadow-md group"
        >
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <p className="text-sm font-medium truncate">{item.title || item.id}</p>
              {item.status && (
                <Badge className={`text-xs ${statusColors[item.status] || statusColors.pending}`}>
                  {item.status}
                </Badge>
              )}
            </div>
            <p className="text-xs text-muted-foreground">
              {item.started_at
                ? formatDistanceToNow(new Date(item.started_at), { addSuffix: true })
                : item.created_at
                ? formatDistanceToNow(new Date(item.created_at), { addSuffix: true })
                : "Recently"}
            </p>
          </div>
          <ArrowRight className="w-4 h-4 text-gray-400 transition-transform group-hover:translate-x-1" />
        </Link>
      ))}
    </div>
  );
}
