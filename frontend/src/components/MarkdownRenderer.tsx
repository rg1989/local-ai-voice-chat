import { memo, useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { MermaidDiagram } from './MermaidDiagram';
import type { Components } from 'react-markdown';

interface MarkdownRendererProps {
  content: string;
  className?: string;
  isStreaming?: boolean;
  onContentChange?: () => void;  // Callback when content changes (e.g., diagram renders)
}

// Custom dark theme based on oneDark but matching our app
const customTheme = {
  ...oneDark,
  'pre[class*="language-"]': {
    ...oneDark['pre[class*="language-"]'],
    background: '#1e1e1e',
    margin: 0,
    padding: '1rem',
    borderRadius: '0.5rem',
  },
  'code[class*="language-"]': {
    ...oneDark['code[class*="language-"]'],
    background: 'transparent',
  },
};

// Memoized MarkdownRenderer to prevent unnecessary re-renders
export const MarkdownRenderer = memo(function MarkdownRenderer({ 
  content, 
  className = '', 
  isStreaming = false, 
  onContentChange 
}: MarkdownRendererProps) {
  // Memoize the components object to prevent ReactMarkdown from remounting children
  const components: Components = useMemo(() => ({
    // Code blocks with syntax highlighting
    code({ className, children, ...props }) {
      const match = /language-(\w+)/.exec(className || '');
      const language = match ? match[1] : '';
      const codeString = String(children).replace(/\n$/, '');
      
      // Check if this is inline code (no language specified and short content)
      const isInline = !match && !codeString.includes('\n');
      
      if (isInline) {
        return (
          <code 
            className="px-1.5 py-0.5 bg-slate-700/50 text-emerald-400 rounded text-sm font-mono" 
            {...props}
          >
            {children}
          </code>
        );
      }

      // Handle mermaid diagrams
      if (language === 'mermaid') {
        return <MermaidDiagram chart={codeString} isStreaming={isStreaming} onRender={onContentChange} />;
      }

      // Regular code blocks with syntax highlighting
      return (
        <div className="my-3 rounded-lg overflow-hidden border border-slate-700/50">
          {language && (
            <div className="px-3 py-1.5 bg-slate-800 text-xs text-slate-400 border-b border-slate-700/50 flex items-center justify-between">
              <span>{language}</span>
              <button
                onClick={() => navigator.clipboard.writeText(codeString)}
                className="text-slate-500 hover:text-slate-300 transition-colors"
                title="Copy code"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                </svg>
              </button>
            </div>
          )}
          <SyntaxHighlighter
            style={customTheme}
            language={language || 'text'}
            PreTag="div"
            customStyle={{
              margin: 0,
              background: '#1a1d21',
              fontSize: '0.875rem',
            }}
          >
            {codeString}
          </SyntaxHighlighter>
        </div>
      );
    },

    // Paragraphs
    p({ children }) {
      return <p className="mb-3 last:mb-0 leading-relaxed">{children}</p>;
    },

    // Headings
    h1({ children }) {
      return <h1 className="text-xl font-bold mb-3 mt-4 first:mt-0 text-white">{children}</h1>;
    },
    h2({ children }) {
      return <h2 className="text-lg font-bold mb-2 mt-4 first:mt-0 text-white">{children}</h2>;
    },
    h3({ children }) {
      return <h3 className="text-base font-bold mb-2 mt-3 first:mt-0 text-white">{children}</h3>;
    },
    h4({ children }) {
      return <h4 className="text-sm font-bold mb-2 mt-3 first:mt-0 text-white">{children}</h4>;
    },

    // Lists
    ul({ children }) {
      return <ul className="list-disc list-inside mb-3 space-y-1 pl-2">{children}</ul>;
    },
    ol({ children }) {
      return <ol className="list-decimal list-inside mb-3 space-y-1 pl-2">{children}</ol>;
    },
    li({ children }) {
      return <li className="text-slate-200">{children}</li>;
    },

    // Blockquotes
    blockquote({ children }) {
      return (
        <blockquote className="border-l-4 border-emerald-500/50 pl-4 my-3 text-slate-300 italic">
          {children}
        </blockquote>
      );
    },

    // Tables
    table({ children }) {
      return (
        <div className="my-3 overflow-x-auto rounded-lg border border-slate-700/50">
          <table className="min-w-full divide-y divide-slate-700/50">{children}</table>
        </div>
      );
    },
    thead({ children }) {
      return <thead className="bg-slate-800/50">{children}</thead>;
    },
    tbody({ children }) {
      return <tbody className="divide-y divide-slate-700/50">{children}</tbody>;
    },
    tr({ children }) {
      return <tr className="hover:bg-slate-800/30 transition-colors">{children}</tr>;
    },
    th({ children }) {
      return (
        <th className="px-3 py-2 text-left text-xs font-medium text-slate-300 uppercase tracking-wider">
          {children}
        </th>
      );
    },
    td({ children }) {
      return <td className="px-3 py-2 text-sm text-slate-300">{children}</td>;
    },

    // Links
    a({ href, children }) {
      return (
        <a
          href={href}
          target="_blank"
          rel="noopener noreferrer"
          className="text-emerald-400 hover:text-emerald-300 underline underline-offset-2 transition-colors"
        >
          {children}
        </a>
      );
    },

    // Strong/Bold
    strong({ children }) {
      return <strong className="font-bold text-white">{children}</strong>;
    },

    // Emphasis/Italic
    em({ children }) {
      return <em className="italic text-slate-200">{children}</em>;
    },

    // Horizontal rule
    hr() {
      return <hr className="my-4 border-slate-700/50" />;
    },

    // Images
    img({ src, alt }) {
      return (
        <img
          src={src}
          alt={alt || ''}
          className="my-3 rounded-lg max-w-full h-auto"
        />
      );
    },
  }), [isStreaming, onContentChange]);

  return (
    <div className={`markdown-content text-sm text-slate-100 ${className}`}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {content}
      </ReactMarkdown>
    </div>
  );
});
