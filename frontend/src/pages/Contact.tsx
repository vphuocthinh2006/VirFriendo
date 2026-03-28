import LandingTopbar from '../components/LandingTopbar'

const CONTACT_ROWS: { href: string; name: string }[] = [
  { href: 'https://www.facebook.com/vothinhcplus/', name: 'Vo Phuoc Thinh' },
  { href: 'https://www.facebook.com/thanh.toan.9209', name: 'Le Ngo Thanh Toan' },
  { href: 'https://www.facebook.com/ma.hoang.9693001', name: 'Lien Phuc Thinh' },
  { href: 'https://www.facebook.com/phuc.thinh.2510', name: 'Nguyen Tan Phuc Thinh' },
]

function FacebookGlyph() {
  return (
    <svg className="aid-contact-fb-svg" viewBox="0 0 24 24" aria-hidden focusable="false">
      <path
        fill="currentColor"
        d="M13.5 22v-8.2h2.7l.4-3.2h-3.1V9.1c0-.9.25-1.5 1.6-1.5h1.7V4.9c-.3 0-1.3-.1-2.5-.1-2.5 0-4.2 1.5-4.2 4.3v2.4H7.5v3.2h2.7V22h3.3z"
      />
    </svg>
  )
}

export default function Contact() {
  return (
    <div className="aid-root aid-contact-root" id="top">
      <LandingTopbar />

      <main className="aid-contact-main">
        <h1 className="aid-contact-headline">
          <span className="aid-contact-headline-pale">CONT</span>
          <span className="aid-contact-headline-yellow">ACT</span>
        </h1>
        <p className="aid-contact-tagline">SAY HELLO</p>

        <ul className="aid-contact-list">
          {CONTACT_ROWS.map((row) => (
            <li key={row.href} className="aid-contact-row">
              <a
                className="aid-contact-row-anchor"
                href={row.href}
                target="_blank"
                rel="noopener noreferrer"
              >
                <span className="aid-contact-icon-tile" aria-hidden>
                  <FacebookGlyph />
                </span>
                <span className="aid-contact-row-body">
                  <span className="aid-contact-row-label">Facebook — reach out at </span>
                  <span className="aid-contact-row-name">{row.name}</span>
                </span>
              </a>
            </li>
          ))}
        </ul>
      </main>
    </div>
  )
}
