import { Link } from 'react-router-dom'

export default function Landing() {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-4 bg-cream-100">
      <div className="text-center max-w-md">
        <h1 className="text-3xl font-semibold text-stone-800 mb-2">AI Anime Companion</h1>
        <p className="text-stone-500 mb-8">Trò chuyện, lắng nghe và đồng hành cùng bạn.</p>
        <div className="flex flex-col sm:flex-row gap-3 justify-center">
          <Link
            to="/login"
            className="px-5 py-2.5 rounded-xl bg-accent text-cream-50 text-sm font-medium hover:bg-accent-hover transition shadow-sm"
          >
            Đăng nhập
          </Link>
          <Link
            to="/register"
            className="px-5 py-2.5 rounded-xl border border-chat-border bg-cream-50 text-stone-700 text-sm font-medium hover:bg-accent-light/50 transition"
          >
            Đăng ký
          </Link>
        </div>
      </div>
    </div>
  )
}
