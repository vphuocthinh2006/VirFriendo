import ReactMarkdown from 'react-markdown'
import remarkBreaks from 'remark-breaks'
import type { Components } from 'react-markdown'

export type ChatMarkdownVariant = 'user' | 'narrative' | 'popup'

/** Block javascript:/data: URLs in untrusted markdown (XSS). */
function safeHref(href: string | undefined): string | undefined {
  if (!href) return undefined
  const t = href.trim().toLowerCase()
  if (t.startsWith('javascript:') || t.startsWith('data:') || t.startsWith('vbscript:')) {
    return undefined
  }
  return href
}

function mdComponents(variant: ChatMarkdownVariant): Components {
  const isNarrative = variant === 'narrative'
  return {
    p: ({ children }) => (
      <p className={isNarrative ? 'vf-chat-md__p vf-chat-md__p--narrative' : 'vf-chat-md__p'}>{children}</p>
    ),
    strong: ({ children }) => <strong className="vf-chat-md__strong">{children}</strong>,
    em: ({ children }) => <em className="vf-chat-md__em">{children}</em>,
    ul: ({ children }) => <ul className="vf-chat-md__ul">{children}</ul>,
    ol: ({ children }) => <ol className="vf-chat-md__ol">{children}</ol>,
    li: ({ children }) => <li className="vf-chat-md__li">{children}</li>,
    h1: ({ children }) => <h3 className="vf-chat-md__h">{children}</h3>,
    h2: ({ children }) => <h3 className="vf-chat-md__h">{children}</h3>,
    h3: ({ children }) => <h3 className="vf-chat-md__h">{children}</h3>,
    h4: ({ children }) => <h4 className="vf-chat-md__h vf-chat-md__h--sm">{children}</h4>,
    blockquote: ({ children }) => <blockquote className="vf-chat-md__quote">{children}</blockquote>,
    a: ({ href, children }) => {
      const h = safeHref(href)
      if (!h) return <span className="vf-chat-md__a vf-chat-md__a--blocked">{children}</span>
      return (
        <a
          href={h}
          className="vf-chat-md__a"
          target="_blank"
          rel="noopener noreferrer"
          onClick={(e) => e.stopPropagation()}
        >
          {children}
        </a>
      )
    },
    hr: () => <hr className="vf-chat-md__hr" />,
    code: ({ className, children, ...props }) => {
      const inline = !className
      if (inline) {
        return (
          <code className="vf-chat-md__code vf-chat-md__code--inline" {...props}>
            {children}
          </code>
        )
      }
      return (
        <code className={className} {...props}>
          {children}
        </code>
      )
    },
    pre: ({ children }) => <pre className="vf-chat-md__pre">{children}</pre>,
  }
}

export function ChatMarkdown({ text, variant = 'narrative' }: { text: string; variant?: ChatMarkdownVariant }) {
  const t = (text || '').trim()
  if (!t) return null
  return (
    <div className={`vf-chat-md vf-chat-md--${variant}`}>
      <ReactMarkdown remarkPlugins={[remarkBreaks]} components={mdComponents(variant)}>
        {t}
      </ReactMarkdown>
    </div>
  )
}
