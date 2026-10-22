import { Link, Outlet } from 'react-router-dom';

export default function Layout() {
  return (
    <div className="page">
      <header className="topbar">
        <Link to="/" className="brand">Альфа-Бизнес</Link>
        <nav className="nav">
          <Link to="/">Главная</Link>
          <Link to="/news" className="nav-accent">Новостная аналитика</Link>
        </nav>
      </header>
      <main className="content">
        <Outlet />
      </main>
    </div>
  );
}