import { useParams } from "react-router-dom";
import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";

export default function PublicMicrositeViewPage() {
  const params = useParams<{ slug: string }>();
  const slug = params.slug as string;
  const [html, setHtml] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchMicrosite = async () => {
      try {
        setLoading(true);
        const response = await fetch(`/api/microsites/public/${slug}`);

        if (!response.ok) {
          if (response.status === 404) {
            setError("Microsite not found");
          } else {
            setError("Failed to load microsite");
          }
          return;
        }

        const htmlContent = await response.text();
        setHtml(htmlContent);
      } catch (err) {
        console.error("Error fetching microsite:", err);
        setError("Failed to load microsite");
      } finally {
        setLoading(false);
      }
    };

    if (slug) {
      fetchMicrosite();
    }
  }, [slug]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <Loader2 className="w-8 h-8 animate-spin mx-auto mb-4" />
          <p className="text-muted-foreground">Loading microsite...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <h1 className="text-2xl font-bold mb-2">Error</h1>
          <p className="text-muted-foreground">{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div
      className="microsite-container"
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}
