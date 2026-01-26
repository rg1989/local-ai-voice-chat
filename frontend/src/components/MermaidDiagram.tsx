import { useEffect, useRef, useState } from 'react';
import mermaid from 'mermaid';

// Initialize mermaid with dark theme
mermaid.initialize({
  startOnLoad: false,
  theme: 'dark',
  themeVariables: {
    primaryColor: '#10b981',
    primaryTextColor: '#f1f5f9',
    primaryBorderColor: '#334155',
    lineColor: '#64748b',
    secondaryColor: '#1e293b',
    tertiaryColor: '#0f172a',
    background: '#1e2227',
    mainBkg: '#2a2d32',
    nodeBorder: '#334155',
    clusterBkg: '#1e293b',
    titleColor: '#f1f5f9',
    edgeLabelBackground: '#1e293b',
  },
  fontFamily: 'ui-sans-serif, system-ui, sans-serif',
  securityLevel: 'loose',
});

interface MermaidDiagramProps {
  chart: string;
  isStreaming?: boolean;
  onRender?: () => void;  // Callback when diagram renders (for scroll updates)
}

// Chart icon for placeholder
function ChartIcon() {
  return (
    <svg className="w-6 h-6 text-emerald-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 21a4 4 0 01-4-4V5a2 2 0 012-2h4a2 2 0 012 2v12a4 4 0 01-4 4zm0 0h12a2 2 0 002-2v-4a2 2 0 00-2-2h-2.343M11 7.343l1.657-1.657a2 2 0 012.828 0l2.829 2.829a2 2 0 010 2.828l-8.486 8.485M7 17h.01" />
    </svg>
  );
}

// Copy icon
function CopyIcon() {
  return (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
    </svg>
  );
}

// Check icon for copy confirmation
function CheckIcon() {
  return (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
    </svg>
  );
}

export function MermaidDiagram({ chart, isStreaming = false, onRender }: MermaidDiagramProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [svg, setSvg] = useState<string>('');
  const [isRendering, setIsRendering] = useState(false);
  const [hasError, setHasError] = useState(false);
  const [copied, setCopied] = useState(false);
  const renderTimeoutRef = useRef<number | null>(null);
  const lastSuccessfulChartRef = useRef<string>('');

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(chart);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  useEffect(() => {
    // Clear any pending render
    if (renderTimeoutRef.current) {
      clearTimeout(renderTimeoutRef.current);
    }

    // Don't try to render empty charts
    if (!chart.trim()) return;

    // If streaming, wait longer before attempting render (debounce)
    const delay = isStreaming ? 500 : 100;

    renderTimeoutRef.current = window.setTimeout(async () => {
      // Generate a unique ID for each render attempt
      const renderId = `mermaid-${Math.random().toString(36).substr(2, 9)}`;
      
      try {
        setIsRendering(true);
        setHasError(false);
        
        const { svg: renderedSvg } = await mermaid.render(renderId, chart);
        setSvg(renderedSvg);
        lastSuccessfulChartRef.current = chart;
        
        // Notify parent that diagram rendered (for scroll updates)
        if (onRender) {
          setTimeout(onRender, 50);
        }
      } catch {
        // Silently fail during streaming - just show placeholder
        // Only mark as error if not streaming and we don't have a previous successful render
        if (!isStreaming && !lastSuccessfulChartRef.current) {
          setHasError(true);
        }
        // Keep showing the last successful render if we have one
      } finally {
        setIsRendering(false);
      }
    }, delay);

    return () => {
      if (renderTimeoutRef.current) {
        clearTimeout(renderTimeoutRef.current);
      }
    };
  }, [chart, isStreaming]);

  // Show placeholder while streaming or rendering, or if there's an error during streaming
  if ((isStreaming && !svg) || (isRendering && !svg)) {
    return (
      <div className="my-3 p-6 bg-slate-800/50 rounded-lg flex flex-col items-center justify-center gap-3 border border-slate-700/50">
        <div className="flex items-center gap-2">
          <div className="animate-pulse">
            <ChartIcon />
          </div>
          <span className="text-sm text-slate-400">
            {isStreaming ? 'Generating diagram...' : 'Rendering diagram...'}
          </span>
        </div>
        <div className="w-24 h-1 bg-slate-700 rounded-full overflow-hidden">
          <div className="h-full bg-emerald-500 rounded-full animate-[loading_1.5s_ease-in-out_infinite]" 
               style={{ 
                 width: '40%',
                 animation: 'loading 1.5s ease-in-out infinite'
               }} />
        </div>
        <style>{`
          @keyframes loading {
            0% { transform: translateX(-100%); }
            50% { transform: translateX(150%); }
            100% { transform: translateX(-100%); }
          }
        `}</style>
      </div>
    );
  }

  // Show error state only for completed (non-streaming) content with no successful render
  if (hasError && !svg && !isStreaming) {
    return (
      <div className="my-3 p-4 bg-amber-900/20 border border-amber-500/30 rounded-lg">
        <p className="text-amber-400 text-sm font-medium mb-2">Could not render diagram</p>
        <details className="mt-1">
          <summary className="text-xs text-slate-400 cursor-pointer hover:text-slate-300">
            Show source code
          </summary>
          <pre className="mt-2 text-xs text-slate-500 whitespace-pre-wrap bg-slate-800/50 p-2 rounded">{chart}</pre>
        </details>
      </div>
    );
  }

  // Show the rendered diagram
  if (svg) {
    return (
      <div className="my-3 rounded-lg overflow-hidden border border-slate-700/50">
        {/* Header bar with copy button */}
        <div className="flex items-center justify-between px-3 py-1.5 bg-slate-800 border-b border-slate-700/50">
          <span className="text-xs text-slate-400">mermaid</span>
          <button
            onClick={handleCopy}
            className="text-slate-500 hover:text-slate-300 transition-colors flex items-center gap-1"
            title="Copy diagram source"
          >
            {copied ? (
              <>
                <CheckIcon />
                <span className="text-xs text-emerald-400">Copied!</span>
              </>
            ) : (
              <CopyIcon />
            )}
          </button>
        </div>
        {/* Diagram content */}
        <div 
          ref={containerRef}
          className="p-4 bg-slate-800/30 overflow-x-auto"
          dangerouslySetInnerHTML={{ __html: svg }}
        />
      </div>
    );
  }

  // Fallback placeholder
  return (
    <div className="my-3 p-6 bg-slate-800/50 rounded-lg flex items-center justify-center gap-2 border border-slate-700/50">
      <ChartIcon />
      <span className="text-sm text-slate-400">Diagram</span>
    </div>
  );
}
