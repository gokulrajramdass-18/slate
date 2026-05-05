"use client";

import { Youtube, User, Clock, Eye, Calendar } from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import type { Source, AssetData } from "@/lib/types";
import { parseAssetData, formatDuration, formatViewCount } from "@/lib/utils/source-helpers";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

interface AssetMetadataCardProps {
  source: Source;
}

export function AssetMetadataCard({ source }: AssetMetadataCardProps) {
  const assetData = parseAssetData(source);

  if (!assetData) return null;

  // Route to type-specific renderer
  switch (source.source_type) {
    case 'youtube':
      return <YouTubeMetadata data={assetData} />;
    case 'hana_table':
      return <HANATableMetadata data={assetData} />;
    case 'api':
      return <APIMetadata data={assetData} />;
    default:
      return <GenericMetadata data={assetData} />;
  }
}

// ============================================================================
// YouTube Metadata
// ============================================================================

function YouTubeMetadata({ data }: { data: AssetData }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Youtube className="w-5 h-5" />
          YouTube Video Details
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Channel */}
        {data.channel_name && (
          <div className="flex items-center gap-2">
            <User className="w-4 h-4 text-gray-500 dark:text-gray-400" />
            <span className="font-medium">{data.channel_name}</span>
            {data.channel_handle && (
              <span className="text-sm text-gray-500 dark:text-gray-400">
                {data.channel_handle}
              </span>
            )}
          </div>
        )}

        {/* Stats Row */}
        <div className="flex flex-wrap items-center gap-4 text-sm text-gray-600 dark:text-gray-400">
          {data.duration_seconds && (
            <div className="flex items-center gap-1">
              <Clock className="w-4 h-4" />
              {formatDuration(data.duration_seconds)}
            </div>
          )}
          {data.view_count !== undefined && (
            <div className="flex items-center gap-1">
              <Eye className="w-4 h-4" />
              {formatViewCount(data.view_count)} views
            </div>
          )}
          {data.upload_date && (
            <div className="flex items-center gap-1">
              <Calendar className="w-4 h-4" />
              {formatDistanceToNow(new Date(data.upload_date), { addSuffix: true })}
            </div>
          )}
        </div>

        {/* Transcript Info */}
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant={data.transcript_available ? "default" : "secondary"}>
            {data.transcript_language?.toUpperCase() || 'N/A'}
          </Badge>
          {data.transcript_auto_generated && (
            <Badge variant="outline">Auto-generated</Badge>
          )}
          {data.transcript_auto_generated === false && (
            <Badge variant="outline">Manual</Badge>
          )}
          {!data.transcript_available && (
            <Badge variant="destructive">Transcript Unavailable</Badge>
          )}
        </div>

        {/* Keywords */}
        {data.keywords && data.keywords.length > 0 && (
          <div className="space-y-2">
            <div className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Keywords
            </div>
            <div className="flex flex-wrap gap-2">
              {data.keywords.slice(0, 10).map((keyword, idx) => (
                <Badge key={idx} variant="secondary" className="text-xs">
                  {keyword}
                </Badge>
              ))}
              {data.keywords.length > 10 && (
                <Badge variant="outline" className="text-xs">
                  +{data.keywords.length - 10} more
                </Badge>
              )}
            </div>
          </div>
        )}

        {/* Description */}
        {data.description && (
          <div className="space-y-2">
            <div className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Description
            </div>
            <p className="text-sm text-gray-600 dark:text-gray-400 line-clamp-3">
              {data.description}
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// ============================================================================
// HANA Table Metadata
// ============================================================================

function HANATableMetadata({ data }: { data: AssetData }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          HANA Table Details
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {/* Schema + Table */}
        {data.schema_name && data.table_name && (
          <div>
            <div className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Table
            </div>
            <code className="text-sm bg-gray-100 dark:bg-gray-800 px-2 py-1 rounded">
              {data.schema_name}.{data.table_name}
            </code>
          </div>
        )}

        {/* Record Count */}
        {data.record_count !== undefined && (
          <div>
            <div className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Records
            </div>
            <div className="text-sm text-gray-600 dark:text-gray-400">
              {data.record_count.toLocaleString()} rows
            </div>
          </div>
        )}

        {/* Columns */}
        {data.columns && data.columns.length > 0 && (
          <div>
            <div className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Columns ({data.columns.length})
            </div>
            <div className="flex flex-wrap gap-2">
              {data.columns.slice(0, 10).map((col, idx) => (
                <Badge key={idx} variant="secondary" className="text-xs font-mono">
                  {col}
                </Badge>
              ))}
              {data.columns.length > 10 && (
                <Badge variant="outline" className="text-xs">
                  +{data.columns.length - 10} more
                </Badge>
              )}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// ============================================================================
// API Metadata
// ============================================================================

function APIMetadata({ data }: { data: AssetData }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          API Source Details
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {/* Endpoint */}
        {data.endpoint && (
          <div>
            <div className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Endpoint
            </div>
            <code className="text-xs bg-gray-100 dark:bg-gray-800 px-2 py-1 rounded break-all">
              {data.endpoint}
            </code>
          </div>
        )}

        {/* Auth Type */}
        {data.auth_type && (
          <div className="flex items-center gap-2">
            <div className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Authentication:
            </div>
            <Badge variant="secondary">{data.auth_type}</Badge>
          </div>
        )}

        {/* Response Format */}
        {data.response_format && (
          <div className="flex items-center gap-2">
            <div className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Format:
            </div>
            <Badge variant="outline">{data.response_format}</Badge>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// ============================================================================
// Generic Metadata (Fallback)
// ============================================================================

function GenericMetadata({ data }: { data: AssetData }) {
  // Filter out empty/null values
  const entries = Object.entries(data).filter(
    ([, value]) => value !== null && value !== undefined && value !== ''
  );

  if (entries.length === 0) return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Asset Metadata</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {entries.map(([key, value]) => (
          <div key={key} className="flex justify-between items-start gap-4">
            <div className="text-sm font-medium text-gray-700 dark:text-gray-300 capitalize">
              {key.replace(/_/g, ' ')}:
            </div>
            <div className="text-sm text-gray-600 dark:text-gray-400 text-right">
              {typeof value === 'object' ? JSON.stringify(value) : String(value)}
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
