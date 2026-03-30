import React from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './api/AuthProvider.jsx'
import NavBar          from './components/NavBar.jsx'
import Login           from './pages/Login.jsx'
import Dashboard       from './pages/Dashboard.jsx'
import Upload          from './pages/Upload.jsx'
import Review          from './pages/Review.jsx'
import BonusReport     from './pages/BonusReport.jsx'
import ReferenceTables from './pages/ReferenceTablesPage.jsx'

export default function App() {
  return (
    <AuthProvider>
      <AppShell />
    </AuthProvider>
  )
}

function AppShell() {
  const { user, loading } = useAuth()

  if (loading) return (
    <div style={{ display:'flex', justifyContent:'center', alignItems:'center', height:'100vh', background:'var(--navy)' }}>
      <div style={{ color:'var(--gold)', fontSize:13, letterSpacing:3 }}>STUDYLINK</div>
    </div>
  )

  if (!user) return <Login />

  return (
    <div style={{ minHeight:'100vh', background:'var(--bg)', fontFamily:'var(--font)' }}>
      <NavBar user={user} />
      <main style={{ marginLeft:220, minHeight:'100vh', padding:'32px 36px' }}>
        <Routes>
          <Route path="/"               element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard"      element={<Dashboard />} />
          <Route path="/upload"         element={<Upload />} />
          <Route path="/review/:id"     element={<Review />} />
          <Route path="/report/:id"     element={<BonusReport />} />
          <Route path="/reference"      element={user?.is_admin ? <ReferenceTables /> : <Navigate to="/dashboard" replace />} />
          {/* Legacy routes kept for backward compat */}
          <Route path="/history"        element={<Navigate to="/dashboard" replace />} />
          <Route path="/results/:id"    element={<Navigate to="/report/:id" replace />} />
          <Route path="*"               element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </main>
    </div>
  )
}
