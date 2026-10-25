import { Route, Routes } from 'react-router-dom';
import Layout from './components/Layout';
import Home from './pages/Home';
import Feed from './pages/Feed';
import InsightPage from './pages/InsightPage';

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Home />} />
        <Route path="/news" element={<Feed />} />
        <Route path="/news/:id" element={<InsightPage />} />
      </Route>
    </Routes>
  );
}