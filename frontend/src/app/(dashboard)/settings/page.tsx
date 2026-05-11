"use client";

import Link from "next/link";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Database,
  Cpu,
  Folder,
  Key,
  MessageSquare,
  Link as LinkIcon,
  Server,
  Plug,
  Mail,
  Wrench,
  Zap,
  Network,
  FileText,
  PlayCircle,
  UserCircle,
  Shield,
  Newspaper
} from "lucide-react";

const settingsCards = [
  {
    href: "/settings/daily-brief",
    title: "Daily Brief",
    description: "Configure daily brief feature and AI summaries",
    icon: Newspaper,
    color: "text-indigo-600",
    bgColor: "bg-indigo-50 dark:bg-indigo-950",
    badge: "Admin"
  },
  {
    href: "/settings/actions",
    title: "Actions",
    description: "Configure automated actions and webhooks",
    icon: PlayCircle,
    color: "text-rose-600",
    bgColor: "bg-rose-50 dark:bg-rose-950"
  },
  {
    href: "/settings/agents",
    title: "Agents & Prompts",
    description: "Manage agent configurations and saved queries",
    icon: FileText,
    color: "text-amber-600",
    bgColor: "bg-amber-50 dark:bg-amber-950"
  },
  {
    href: "/settings/skills",
    title: "Agent Skills",
    description: "Configure agent capabilities and skills",
    icon: Zap,
    color: "text-violet-600",
    bgColor: "bg-violet-50 dark:bg-violet-950"
  },
  {
    href: "/settings/models",
    title: "AI Models",
    description: "Configure language and embedding models",
    icon: Cpu,
    color: "text-purple-600",
    bgColor: "bg-purple-50 dark:bg-purple-950"
  },
  {
    href: "/settings/api-connections",
    title: "API Connections",
    description: "Configure external API integrations",
    icon: LinkIcon,
    color: "text-cyan-600",
    bgColor: "bg-cyan-50 dark:bg-cyan-950"
  },
  {
    href: "/settings/api-keys",
    title: "API Keys",
    description: "Manage credentials for AI providers",
    icon: Key,
    color: "text-red-600",
    bgColor: "bg-red-50 dark:bg-red-950"
  },
  {
    href: "/settings/chat",
    title: "Chat",
    description: "Configure chat preferences and generative UI",
    icon: MessageSquare,
    color: "text-green-600",
    bgColor: "bg-green-50 dark:bg-green-950"
  },
  {
    href: "/settings/database",
    title: "Database",
    description: "Manage database connections (SQLite / HANA Cloud)",
    icon: Database,
    color: "text-blue-600",
    bgColor: "bg-blue-50 dark:bg-blue-950"
  },
  {
    href: "/settings/folders",
    title: "Folders & Tags",
    description: "Organize notebooks with folders and tags",
    icon: Folder,
    color: "text-emerald-600",
    bgColor: "bg-emerald-50 dark:bg-emerald-950"
  },
  {
    href: "/settings/hana-connections",
    title: "HANA Connections",
    description: "Manage SAP HANA Cloud database connections",
    icon: Server,
    color: "text-orange-600",
    bgColor: "bg-orange-50 dark:bg-orange-950"
  },
  {
    href: "/settings/graph",
    title: "Knowledge Graph",
    description: "Configure graph visualization settings",
    icon: Network,
    color: "text-teal-600",
    bgColor: "bg-teal-50 dark:bg-teal-950"
  },
  {
    href: "/settings/mcp-servers",
    title: "MCP Servers",
    description: "Model Context Protocol server configurations",
    icon: Network,
    color: "text-indigo-600",
    bgColor: "bg-indigo-50 dark:bg-indigo-950"
  },
  {
    href: "/settings/oauth-apps",
    title: "OAuth Apps",
    description: "Manage OAuth applications and credentials",
    icon: Key,
    color: "text-blue-600",
    bgColor: "bg-blue-50 dark:bg-blue-950"
  },
  {
    href: "/settings/prompts",
    title: "Prompt Management",
    description: "Manage AI system prompts and templates",
    icon: MessageSquare,
    color: "text-indigo-600",
    bgColor: "bg-indigo-50 dark:bg-indigo-950"
  },
  {
    href: "/settings/roles",
    title: "Roles",
    description: "Configure user roles and access control",
    icon: Shield,
    color: "text-purple-600",
    bgColor: "bg-purple-50 dark:bg-purple-950"
  },
  {
    href: "/settings/smtp",
    title: "SMTP / Email",
    description: "Configure email server settings",
    icon: Mail,
    color: "text-pink-600",
    bgColor: "bg-pink-50 dark:bg-pink-950"
  },
  {
    href: "/settings/tools",
    title: "Tools",
    description: "Manage available tools and integrations",
    icon: Wrench,
    color: "text-yellow-600",
    bgColor: "bg-yellow-50 dark:bg-yellow-950"
  },
  {
    href: "/settings/users",
    title: "Users",
    description: "Manage user accounts and permissions",
    icon: UserCircle,
    color: "text-blue-600",
    bgColor: "bg-blue-50 dark:bg-blue-950"
  },
];

export default function SettingsPage() {
  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div className="animate-fade-in-up">
        <h1 className="text-3xl font-bold tracking-tight bg-gradient-to-r from-blue-600 via-purple-600 to-pink-600 bg-clip-text text-transparent">Settings</h1>
        <p className="text-gray-500 dark:text-gray-400">
          Configure Slate to match your needs
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {settingsCards.map((card, index) => {
          const Icon = card.icon;
          return (
            <Link key={card.href} href={card.href}>
              <Card
                className="hover:shadow-xl hover:scale-[1.02] transition-all duration-300 cursor-pointer h-full hover:border-purple-500/30 animate-fade-in-up"
                style={{
                  animationDelay: `${(index + 1) * 50}ms`,
                  opacity: 0
                }}
              >
                <CardHeader>
                  <div className="flex items-start gap-3">
                    <div className={`p-2 rounded-lg ${card.bgColor} transition-transform hover:scale-110`}>
                      <Icon className={`w-5 h-5 ${card.color}`} />
                    </div>
                    <div className="flex-1">
                      <CardTitle className="text-lg">{card.title}</CardTitle>
                      <CardDescription className="mt-1 text-sm">{card.description}</CardDescription>
                    </div>
                  </div>
                </CardHeader>
              </Card>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
