import { useCallback, useEffect, useMemo, useState, type FormEvent, type ReactNode } from 'react'
import {
  Activity, ArrowRight, ArrowUpRight, Bell, BookOpenCheck, BriefcaseBusiness,
  CalendarClock, Check, ChevronDown, CircleHelp, ClipboardList, Clock3, FileCheck2, FileText, AlertTriangle,
  Filter, LayoutDashboard, LockKeyhole, LogOut, Menu, Plus, Search, ShieldCheck, SlidersHorizontal,
  Sparkles, Users, X,
} from 'lucide-react'
import { api, clearToken, getToken, saveToken, type Application, type ApplicationEvent, type ApplicationEvidence, type ComplianceOverview, type EventVerification, type PolicyVersion, type NotificationRecord, type ComplianceEscalation, type User } from './api'

type View = 'overview' | 'applications' | 'detail' | 'policies' | 'compliance'

const statusLabels: Record<string, string> = {
  draft: 'Draft', submitted: 'Submitted', under_scrutiny: 'Under scrutiny', scrutiny: 'Under scrutiny',
  clarification_requested: 'Clarification requested', returned: 'Returned for changes',
  recommended_for_approval: 'Recommended for approval', pending_authority_decision: 'Decision pending',
  approved: 'Approved', rejected: 'Rejected', re_scrutiny: 'Re-scrutiny',
  awaiting_institution_response: 'Awaiting response', evc_pending: 'EVC pending',
  evc_scheduled: 'EVC scheduled', evc_completed: 'EVC completed', committee_review: 'Committee review',
  decision_pending: 'Decision pending', completed: 'Completed', withdrawn: 'Withdrawn',
}

function initials(name: string) {
  return name.split(/\s+/).filter(Boolean).slice(0, 2).map(part => part[0]).join('').toUpperCase()
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }).format(new Date(value))
}

function App() {
  const [user, setUser] = useState<User | null>(null)
  const [booting, setBooting] = useState(true)
  const [view, setView] = useState<View>('overview')
  const [applications, setApplications] = useState<Application[]>([])
  const [selectedApplication, setSelectedApplication] = useState<Application | null>(null)
  const [caseEvents, setCaseEvents] = useState<ApplicationEvent[]>([])
  const [evidenceItems, setEvidenceItems] = useState<ApplicationEvidence[]>([])
  const [loadingEvidence, setLoadingEvidence] = useState(false)
  const [evidenceTitle, setEvidenceTitle] = useState('')
  const [evidenceCategory, setEvidenceCategory] = useState('approval_letter')
  const [evidenceReference, setEvidenceReference] = useState('')
  const [evidenceIssued, setEvidenceIssued] = useState('')
  const [evidenceExpires, setEvidenceExpires] = useState('')
  const [evidencePolicy, setEvidencePolicy] = useState('')
  const [evidenceNotes, setEvidenceNotes] = useState('')
  const [savingEvidence, setSavingEvidence] = useState(false)
  const [eventVerification, setEventVerification] = useState<EventVerification | null>(null)
  const [loadingTimeline, setLoadingTimeline] = useState(false)
  const [transitionReason, setTransitionReason] = useState('')
  const [transitionBusy, setTransitionBusy] = useState(false)
  const [compliance, setCompliance] = useState<ComplianceOverview | null>(null)
  const [loadingCompliance, setLoadingCompliance] = useState(false)
  const [escalations, setEscalations] = useState<ComplianceEscalation[]>([])
  const [loadingEscalations, setLoadingEscalations] = useState(false)
  const [notifications, setNotifications] = useState<NotificationRecord[]>([])
  const [notificationsOpen, setNotificationsOpen] = useState(false)
  const [loadingNotifications, setLoadingNotifications] = useState(false)
  const [queueingNotifications, setQueueingNotifications] = useState(false)
  const [policies, setPolicies] = useState<PolicyVersion[]>([])
  const [loadingPolicies, setLoadingPolicies] = useState(false)
  const [total, setTotal] = useState(0)
  const [loadingCases, setLoadingCases] = useState(false)
  const [query, setQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [notice, setNotice] = useState('')
  const [mobileNav, setMobileNav] = useState(false)
  const [createOpen, setCreateOpen] = useState(false)
  const [newTitle, setNewTitle] = useState('')
  const [newSummary, setNewSummary] = useState('')
  const [creating, setCreating] = useState(false)
  const [loginEmail, setLoginEmail] = useState('demo.institution@example.test')
  const [loginPassword, setLoginPassword] = useState('')
  const [loggingIn, setLoggingIn] = useState(false)
  const [loginError, setLoginError] = useState('')

  const signOut = useCallback(() => {
    clearToken()
    setUser(null)
    setApplications([])
    setTotal(0)
    setView('overview')
  }, [])

  useEffect(() => {
    const onUnauthorized = () => signOut()
    window.addEventListener('pravaah:unauthorized', onUnauthorized)
    const token = getToken()
    if (!token) {
      setBooting(false)
    } else {
      api.me().then(setUser).catch(signOut).finally(() => setBooting(false))
    }
    return () => window.removeEventListener('pravaah:unauthorized', onUnauthorized)
  }, [signOut])

  const loadApplications = useCallback(async () => {
    if (!user) return
    setLoadingCases(true)
    setNotice('')
    try {
      const result = await api.applications({ page: 1, pageSize: 100, q: query.trim(), status: statusFilter })
      setApplications(result.items)
      setTotal(result.total)
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'Could not load applications.')
    } finally {
      setLoadingCases(false)
    }
  }, [user, query, statusFilter])

  useEffect(() => {
    if (user) void loadApplications()
  }, [user, loadApplications])

  useEffect(() => {
    if (!user || view !== 'detail' || !selectedApplication) return
    let cancelled = false
    setLoadingTimeline(true)
    setLoadingEvidence(true)
    Promise.all([api.applicationEvents(selectedApplication.id), api.verifyEvents(selectedApplication.id), api.evidence(selectedApplication.id)])
      .then(([events, verification, evidence]) => {
        if (!cancelled) { setCaseEvents(events); setEventVerification(verification); setEvidenceItems(evidence) }
      })
      .catch(error => { if (!cancelled) setNotice(error instanceof Error ? error.message : 'Could not load the application timeline and evidence.') })
      .finally(() => { if (!cancelled) { setLoadingTimeline(false); setLoadingEvidence(false) } })
    return () => { cancelled = true }
  }, [user, view, selectedApplication])

  const loadNotifications = useCallback(async () => {
    if (!user) return
    setLoadingNotifications(true)
    try { setNotifications(await api.notifications()) }
    catch (error) { setNotice(error instanceof Error ? error.message : 'Could not load notifications.') }
    finally { setLoadingNotifications(false) }
  }, [user])

  useEffect(() => { if (user) void loadNotifications() }, [user, loadNotifications])

  async function handleMarkNotificationRead(notification: NotificationRecord) {
    try {
      if (!notification.read_at) await api.markNotificationRead(notification.id)
      setNotifications(items => items.map(item => item.id === notification.id && !item.read_at ? { ...item, read_at: new Date().toISOString() } : item))
      setNotificationsOpen(false)
      await openAlertApplication(notification.application_id)
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'Could not open this notification.')
    }
  }

  async function handleQueueNotifications() {
    setQueueingNotifications(true)
    setNotice('')
    try {
      const result = await api.queueExpiryNotifications()
      await loadNotifications()
      await loadCompliance()
      setNotice(`Queued ${result.created} notification(s); ${result.skipped_existing} duplicate(s) skipped.`)
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'Could not queue expiry notifications.')
    } finally {
      setQueueingNotifications(false)
    }
  }

  const loadEscalations = useCallback(async () => {
    if (!user) return
    setLoadingEscalations(true)
    try { setEscalations(await api.escalations()) }
    catch (error) { setNotice(error instanceof Error ? error.message : 'Could not load compliance escalations.') }
    finally { setLoadingEscalations(false) }
  }, [user])

  useEffect(() => { if (user && view === 'compliance') void loadEscalations() }, [user, view, loadEscalations])

  async function handleResolveEscalation(escalation: ComplianceEscalation) {
    try {
      await api.resolveEscalation(escalation.id)
      setEscalations(items => items.filter(item => item.id !== escalation.id))
      setNotice('Compliance escalation resolved and recorded in the audit timeline.')
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'Could not resolve this escalation.')
    }
  }

  const loadCompliance = useCallback(async () => {
    if (!user) return
    setLoadingCompliance(true)
    setNotice('')
    try { setCompliance(await api.complianceOverview()) }
    catch (error) { setNotice(error instanceof Error ? error.message : 'Could not load compliance overview.') }
    finally { setLoadingCompliance(false) }
  }, [user])

  useEffect(() => { if (user && view === 'compliance') void loadCompliance() }, [user, view, loadCompliance])

  async function openAlertApplication(applicationId: string) {
    try { setSelectedApplication(await api.application(applicationId)); setView('detail') }
    catch (error) { setNotice(error instanceof Error ? error.message : 'Could not open the application.') }
  }

  const loadPolicies = useCallback(async () => {
    if (!user) return
    setLoadingPolicies(true)
    setNotice('')
    try {
      setPolicies(await api.policies())
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'Could not load policy registry.')
    } finally {
      setLoadingPolicies(false)
    }
  }, [user])

  useEffect(() => {
    if (user && view === 'policies') void loadPolicies()
  }, [user, view, loadPolicies])

  const metrics = useMemo(() => {
    const active = applications.filter(item => !['completed', 'withdrawn'].includes(item.status)).length
    const awaiting = applications.filter(item => ['submitted', 'scrutiny', 're_scrutiny', 'awaiting_institution_response'].includes(item.status)).length
    const completed = applications.filter(item => item.status === 'completed').length
    return { active, awaiting, completed }
  }, [applications])

  async function handleLogin(event: FormEvent) {
    event.preventDefault()
    setLoggingIn(true)
    setLoginError('')
    try {
      const result = await api.login(loginEmail.trim(), loginPassword)
      saveToken(result.access_token)
      const profile = await api.me()
      setUser(profile)
      setLoginPassword('')
    } catch (error) {
      clearToken()
      setLoginError(error instanceof Error ? error.message : 'Unable to sign in. Check the API connection.')
    } finally {
      setLoggingIn(false)
    }
  }

  async function handleCreate(event: FormEvent) {
    event.preventDefault()
    if (newTitle.trim().length < 3) return
    setCreating(true)
    setNotice('')
    try {
      await api.createApplication(newTitle.trim(), newSummary.trim())
      setNewTitle('')
      setNewSummary('')
      setCreateOpen(false)
      setView('applications')
      await loadApplications()
      setNotice('Draft application created successfully.')
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'Could not create the application.')
    } finally {
      setCreating(false)
    }
  }

  async function handleRegisterEvidence(event: FormEvent) {
    event.preventDefault()
    if (!selectedApplication || evidenceTitle.trim().length < 2) return
    setSavingEvidence(true)
    setNotice('')
    try {
      const payload = {
        title: evidenceTitle.trim(), category: evidenceCategory,
        ...(evidenceReference.trim() ? { reference_number: evidenceReference.trim() } : {}),
        ...(evidenceIssued ? { issued_on: evidenceIssued } : {}),
        ...(evidenceExpires ? { expires_on: evidenceExpires } : {}),
        ...(evidencePolicy.trim() ? { policy_key: evidencePolicy.trim() } : {}),
        ...(evidenceNotes.trim() ? { notes: evidenceNotes.trim() } : {}),
      }
      await api.registerEvidence(selectedApplication.id, payload)
      const [evidence, events, verification] = await Promise.all([api.evidence(selectedApplication.id), api.applicationEvents(selectedApplication.id), api.verifyEvents(selectedApplication.id)])
      setEvidenceItems(evidence)
      setCaseEvents(events)
      setEventVerification(verification)
      setEvidenceTitle(''); setEvidenceReference(''); setEvidenceIssued(''); setEvidenceExpires(''); setEvidencePolicy(''); setEvidenceNotes('')
      setNotice('Evidence metadata registered and added to the audit timeline.')
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'Could not register evidence metadata.')
    } finally {
      setSavingEvidence(false)
    }
  }

  async function handleTransition(targetStatus: string) {
    if (!selectedApplication) return
    setTransitionBusy(true)
    setNotice('')
    try {
      const updated = await api.transitionApplication(selectedApplication.id, targetStatus, selectedApplication.status, transitionReason.trim() || undefined)
      setSelectedApplication(updated)
      setTransitionReason('')
      await loadApplications()
      setNotice('Status updated. The action is recorded in the application timeline.')
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'Could not update application status.')
    } finally {
      setTransitionBusy(false)
    }
  }

  if (booting) return <div className="boot-screen"><div className="brand-mark"><Activity size={24} /></div><span>Preparing your workspace…</span></div>

  if (!user) return (
    <main className="login-layout">
      <section className="login-story">
        <div className="login-brand"><div className="brand-mark"><Activity size={24} /></div><span>PRAVAAH</span><span className="brand-divider" /><span className="brand-sub">Approval intelligence</span></div>
        <div className="story-copy">
          <div className="eyebrow light"><Sparkles size={14} /> POLICY-DRIVEN WORKFLOW</div>
          <h1>Every approval.<br /><span>One clear path.</span></h1>
          <p>A calmer, more accountable way to coordinate applications, compliance evidence and critical deadlines.</p>
          <div className="story-points"><div><ShieldCheck size={18} /><span>Traceable decisions and evidence</span></div><div><CalendarClock size={18} /><span>Deadline-aware case management</span></div><div><FileCheck2 size={18} /><span>One view of every application</span></div></div>
        </div>
        <div className="story-footer"><span>BUILT FOR TRANSPARENCY</span><span>Independent prototype · Synthetic data</span></div>
      </section>
      <section className="login-panel">
        <form className="login-card" onSubmit={handleLogin}>
          <div className="mobile-brand"><div className="brand-mark"><Activity size={22} /></div><strong>PRAVAAH</strong></div>
          <div className="eyebrow">WELCOME BACK</div>
          <h2>Sign in to your workspace</h2>
          <p className="muted login-description">Use your assigned demo account to continue.</p>
          <label className="field-label" htmlFor="email">Email address</label>
          <div className="input-wrap"><Users size={17} /><input id="email" type="email" autoComplete="username" value={loginEmail} onChange={e => setLoginEmail(e.target.value)} required /></div>
          <label className="field-label" htmlFor="password">Password</label>
          <div className="input-wrap"><LockKeyhole size={17} /><input id="password" type="password" autoComplete="current-password" value={loginPassword} onChange={e => setLoginPassword(e.target.value)} placeholder="Enter your password" required /></div>
          {loginError && <div className="inline-error" role="alert">{loginError}</div>}
          <button className="primary-button login-submit" disabled={loggingIn}>{loggingIn ? 'Signing in…' : 'Sign in'} <ArrowRight size={17} /></button>
          <div className="login-security"><LockKeyhole size={14} /><span>Secure session · Role-based access</span></div>
          <div className="demo-hint">Local demo credentials are documented in the repository README. The demo password is only for local development.</div>
        </form>
        <div className="login-bottom">© 2026 PRAVAAH <span>·</span> Transparent by design</div>
      </section>
    </main>
  )

  const navItems = [
    { id: 'overview' as const, label: 'Overview', icon: LayoutDashboard },
    { id: 'applications' as const, label: 'Applications', icon: ClipboardList, count: total },

  ]
  const roleLabel = user.role.replaceAll('_', ' ').replace(/\b\w/g, char => char.toUpperCase())

  return (
    <div className="app-shell">
      {mobileNav && <button className="mobile-backdrop" aria-label="Close navigation" onClick={() => setMobileNav(false)} />}
      <aside className={`sidebar ${mobileNav ? 'sidebar-open' : ''}`}>
        <div className="sidebar-brand"><div className="brand-mark"><Activity size={22} /></div><div><strong>PRAVAAH</strong><span>APPROVAL INTELLIGENCE</span></div><button className="mobile-close icon-button" onClick={() => setMobileNav(false)} aria-label="Close menu"><X size={18} /></button></div>
        <div className="workspace-select"><div className="workspace-avatar">{initials(user.full_name)}</div><div className="workspace-meta"><strong>{user.role === 'institution_user' ? 'Institution workspace' : 'Review workspace'}</strong><span>{roleLabel}</span></div><ChevronDown size={15} /></div>
        <div className="nav-label">WORKSPACE</div>
        <nav className="side-nav" aria-label="Main navigation">
          {navItems.map(item => <button key={item.id} className={`nav-item ${view === item.id ? 'active' : ''}`} onClick={() => { setView(item.id); setMobileNav(false) }}><item.icon size={18} /><span>{item.label}</span>{item.id === 'applications' && <span className="nav-count">{total}</span>}</button>)}
        </nav>
        <div className="nav-label nav-label-spaced">OPERATIONS</div>
        <div className="nav-item nav-disabled"><CalendarClock size={18} /><span>Deadlines & compliance</span><span className="soon-dot" /></div>
        <button className="nav-item" onClick={() => { setView("policies"); setMobileNav(false) }}><BookOpenCheck size={18} /><span>Policy registry</span></button>
        <div className="nav-item nav-disabled"><FileCheck2 size={18} /><span>Evidence & documents</span><span className="soon-dot" /></div>
        <div className="sidebar-bottom"><div className="help-card"><div className="help-icon"><CircleHelp size={18} /></div><strong>Need a hand?</strong><p>Explore the workflow guide as modules become available.</p><span>Prototype workspace</span></div><div className="sidebar-foot"><span className="online-dot" /> API-connected workspace <span className="version">v0.1</span></div></div>
      </aside>

      <main className="main-panel">
        <header className="topbar"><div className="topbar-left"><button className="icon-button mobile-menu" aria-label="Open navigation" onClick={() => setMobileNav(true)}><Menu size={20} /></button><div className="breadcrumb">Workspace <span>/</span> <strong>{view === 'overview' ? 'Overview' : view === 'applications' ? 'Applications' : view === 'detail' ? 'Application details' : view === 'compliance' ? 'Deadlines & compliance' : 'Policy registry'}</strong></div></div><div className="topbar-right"><div className="environment-pill"><span /> Demo environment</div><div className="notification-wrap"><button className="icon-button notification-button" aria-label="Notifications" title="Open notifications" onClick={() => { const next = !notificationsOpen; setNotificationsOpen(next); if (next) void loadNotifications() }}><Bell size={18} />{notifications.some(item => !item.read_at) && <i />}</button>{notificationsOpen && <div className="notification-popover"><div className="notification-popover-head"><div><strong>Notifications</strong><span>{notifications.filter(item => !item.read_at).length} unread</span></div><button className="text-button" onClick={() => void loadNotifications()} disabled={loadingNotifications}>Refresh</button></div>{loadingNotifications && notifications.length === 0 ? <div className="notification-empty">Loading notifications…</div> : notifications.length === 0 ? <div className="notification-empty">No notifications yet. Expiry alerts can be queued from Deadlines & compliance.</div> : <div className="notification-list">{notifications.slice(0, 12).map(item => <button className={'notification-row ' + (!item.read_at ? 'unread' : '')} key={item.id} onClick={() => void handleMarkNotificationRead(item)}><span className={'notification-severity ' + item.severity}><Bell size={14}/></span><span className="notification-row-copy"><strong>{item.title}</strong><span>{item.message}</span><small>{formatDate(item.created_at)} · {item.delivery_status}</small></span>{!item.read_at && <i />}</button>)}</div>}</div>}</div><div className="topbar-divider" /><button className="profile-button" onClick={signOut} title="Sign out"><div className="profile-avatar">{initials(user.full_name)}</div><div className="profile-copy"><strong>{user.full_name}</strong><span>{roleLabel}</span></div><LogOut size={16} className="logout-icon" /></button></div></header>

        <div className="content-area">
          <div className="page-heading"><div><div className="eyebrow">YOUR WORKSPACE <span className="heading-dot">·</span> {new Intl.DateTimeFormat('en-IN', { weekday: 'long', day: 'numeric', month: 'long' }).format(new Date())}</div><h1>{view === 'overview' ? 'Good to see you, ' + user.full_name.split(' ')[0] + '.' : view === 'applications' ? 'Applications' : view === 'detail' ? 'Application details' : view === 'compliance' ? 'Deadlines & compliance' : 'Policy registry'}</h1><p>{view === 'overview' ? 'Here’s the latest view of your approval workflow.' : view === 'applications' ? 'Search, review and manage your application records.' : view === 'detail' ? 'Review the current record and its latest status.' : view === 'compliance' ? 'Monitor recorded evidence expiry dates across your visible applications.' : 'Review versioned policy records and their configured rules.'}</p></div><div className="heading-actions"><button className="secondary-button" onClick={() => void (view === 'policies' ? loadPolicies() : loadApplications())} disabled={view === 'policies' ? loadingPolicies : loadingCases}><Activity size={16} className={(view === 'policies' ? loadingPolicies : loadingCases) ? 'spin' : ''} /> Refresh</button>{view !== 'policies' && user.role === 'institution_user' && <button className="primary-button" onClick={() => setCreateOpen(true)}><Plus size={17} /> New application</button>}</div></div>

          {notice && <div className={`notice ${notice.toLowerCase().includes('success') ? 'notice-success' : ''}`} role="status"><span>{notice}</span><button onClick={() => setNotice('')} aria-label="Dismiss message"><X size={16} /></button></div>}

          {view === 'overview' && <>
            <section className="welcome-banner"><div className="banner-orb orb-one" /><div className="banner-orb orb-two" /><div className="banner-copy"><div className="banner-kicker"><Sparkles size={14} /> WORKFLOW SNAPSHOT</div><h2>Clarity at every stage.</h2><p>Keep applications moving with a clearer view of status, ownership and next steps.</p><button className="banner-link" onClick={() => setView('applications')}>View application register <ArrowRight size={15} /></button></div><div className="banner-art" aria-hidden="true"><div className="art-ring ring-a"/><div className="art-ring ring-b"/><div className="art-center"><Activity size={36}/></div><div className="art-chip chip-a"><Check size={13}/></div><div className="art-chip chip-b"><Clock3 size={13}/></div><div className="art-chip chip-c"><FileCheck2 size={13}/></div></div></section>

            <div className="section-heading"><div><h2>Application overview</h2><p>Live figures from the records available to your account.</p></div><button className="text-button" onClick={() => setView('applications')}>View all <ArrowRight size={15}/></button></div>
            <section className="metrics-grid">
              <MetricCard icon={<BriefcaseBusiness size={19}/>} label="Visible applications" value={String(total)} note="Records in your current scope" tone="blue" trendIcon={<Activity size={14}/>} />
              <MetricCard icon={<Clock3 size={19}/>} label="Active cases" value={String(metrics.active)} note="Not completed or withdrawn" tone="amber" trendIcon={<ArrowUpRight size={14}/>} />
              <MetricCard icon={<ClipboardList size={19}/>} label="In review stages" value={String(metrics.awaiting)} note="Submitted or under scrutiny" tone="violet" trendIcon={<Activity size={14}/>} />
              <MetricCard icon={<FileCheck2 size={19}/>} label="Completed" value={String(metrics.completed)} note="Marked complete in the registry" tone="green" trendIcon={<Check size={14}/>} />
            </section>

            <section className="content-grid"><div className="panel recent-panel"><div className="panel-heading"><div><h2>Recent applications</h2><p>Latest activity in your visible register</p></div><button className="subtle-icon-button" onClick={() => setView('applications')} aria-label="View all applications"><ArrowRight size={17}/></button></div><ApplicationTable applications={applications.slice(0, 5)} loading={loadingCases} onOpen={application => { setSelectedApplication(application); setView('detail') }} compact /></div><div className="panel status-panel"><div className="panel-heading"><div><h2>Workflow health</h2><p>Based on visible application statuses</p></div><Activity size={18} className="panel-heading-icon"/></div><div className="status-total"><strong>{total}</strong><span>total visible records</span></div><div className="status-bars">{[
              {label:'Draft', count:applications.filter(a=>a.status==='draft').length, color:'bar-slate'},
              {label:'Submitted', count:applications.filter(a=>a.status==='submitted').length, color:'bar-blue'},
              {label:'In scrutiny', count:applications.filter(a=>['scrutiny','re_scrutiny'].includes(a.status)).length, color:'bar-violet'},
              {label:'Completed', count:metrics.completed, color:'bar-green'},
            ].map(item=><div className="status-row" key={item.label}><div className="status-row-top"><span>{item.label}</span><strong>{item.count}</strong></div><div className="bar-track"><div className={`bar-fill ${item.color}`} style={{width: `${total ? Math.max(item.count / total * 100, item.count ? 4 : 0) : 0}%`}}/></div></div>)}</div><div className="status-foot"><span className="status-foot-dot"/> Counts update when the register refreshes.</div></div></section>
          </>}

          {view === 'applications' && <section className="panel applications-panel"><div className="panel-heading list-panel-heading"><div><h2>Application register</h2><p>{total} record{total===1?'':'s'} visible within your access scope</p></div><div className="register-actions"><button className="secondary-button small-button" onClick={() => void loadApplications()} disabled={loadingCases}><Activity size={15} className={loadingCases?'spin':''}/> Refresh</button>{user.role==='institution_user'&&<button className="primary-button small-button" onClick={() => setCreateOpen(true)}><Plus size={16}/> New application</button>}</div></div><div className="filter-row"><div className="search-field"><Search size={17}/><input value={query} onChange={e=>setQuery(e.target.value)} onKeyDown={e=>{if(e.key==='Enter')void loadApplications()}} placeholder="Search by title or application ID" aria-label="Search applications"/><kbd>Enter</kbd></div><div className="filter-select-wrap"><Filter size={16}/><select value={statusFilter} onChange={e=>setStatusFilter(e.target.value)} aria-label="Filter by status"><option value="">All statuses</option>{Object.entries(statusLabels).map(([key,label])=><option key={key} value={key}>{label}</option>)}</select><ChevronDown size={14}/></div><button className="secondary-button filter-apply" onClick={()=>void loadApplications()}><SlidersHorizontal size={15}/> Apply filters</button></div><ApplicationTable applications={applications} loading={loadingCases} onOpen={application => { setSelectedApplication(application); setView('detail') }} /><div className="table-footer"><span>Showing <strong>{applications.length}</strong> of <strong>{total}</strong> matching records</span><span className="footer-scope"><ShieldCheck size={14}/> Access-scoped results</span></div></section>}


          {view === 'detail' && selectedApplication && <section className="panel case-detail-panel">
            <div className="panel-heading"><div><div className="eyebrow">APPLICATION {selectedApplication.application_number}</div><h2>{selectedApplication.title}</h2><p>{selectedApplication.summary || 'No summary provided.'}</p></div><button className="secondary-button small-button" onClick={() => setView('applications')}><ArrowRight size={15}/> Back to register</button></div>
            <div className="case-detail-facts"><div><span>Current status</span><strong>{statusLabels[selectedApplication.status] || selectedApplication.status.replaceAll('_', ' ')}</strong></div><div><span>Created</span><strong>{formatDate(selectedApplication.created_at)}</strong></div><div><span>Last updated</span><strong>{formatDate(selectedApplication.updated_at)}</strong></div><div><span>Submitted</span><strong>{selectedApplication.submitted_at ? formatDate(selectedApplication.submitted_at) : 'Not submitted'}</strong></div><div><span>Institution reference</span><strong>{selectedApplication.institution_id.slice(0, 8).toUpperCase()}</strong></div></div>
            {(() => {
              const actionMap: Record<string, { roles: string[]; targets: string[] }> = {
                draft: { roles: ['institution_user'], targets: ['submitted'] },
                submitted: { roles: ['scrutiny_officer'], targets: ['under_scrutiny', 'clarification_requested'] },
                clarification_requested: { roles: ['institution_user'], targets: ['submitted'] },
                under_scrutiny: { roles: ['scrutiny_officer'], targets: ['clarification_requested', 'recommended_for_approval', 'returned'] },
                returned: { roles: ['institution_user'], targets: ['submitted'] },
                recommended_for_approval: { roles: ['bureau_officer'], targets: ['pending_authority_decision'] },
                pending_authority_decision: { roles: ['competent_authority'], targets: ['approved', 'rejected'] },
              }
              const config = actionMap[selectedApplication.status]
              const targets = config && config.roles.includes(user.role) ? config.targets : []
              return <div className="detail-actions"><div><h3>Workflow actions</h3><p>Actions are limited by role and current status, and rechecked by the server.</p></div>{targets.length ? <><textarea value={transitionReason} onChange={event => setTransitionReason(event.target.value)} rows={2} maxLength={2000} placeholder="Optional note for the audit trail"/><div className="detail-action-buttons">{targets.map(target => <button key={target} className={target === 'rejected' || target === 'returned' ? 'secondary-button' : 'primary-button'} disabled={transitionBusy} onClick={() => void handleTransition(target)}>{transitionBusy ? 'Saving…' : target.replaceAll('_', ' ').replace(/^\w/, letter => letter.toUpperCase())}</button>)}</div></> : <p className="no-detail-actions">No action is available for your role in this status.</p>}</div>
            })()}
            <div className="evidence-section">
              <div className="panel-heading"><div><h2>Evidence & expiry tracking</h2><p>Register evidence metadata and connect it to a policy record. This does not upload or store document files.</p></div><span className="evidence-count">{evidenceItems.length} items</span></div>
              <form className="evidence-form" onSubmit={handleRegisterEvidence}>
                <div className="evidence-form-grid">
                  <label>Evidence title<input value={evidenceTitle} onChange={event => setEvidenceTitle(event.target.value)} placeholder="e.g. Fire safety certificate" minLength={2} maxLength={240} required /></label>
                  <label>Category<select value={evidenceCategory} onChange={event => setEvidenceCategory(event.target.value)}><option value="approval_letter">Approval letter</option><option value="accreditation">Accreditation</option><option value="fire_safety">Fire safety</option><option value="building_safety">Building safety</option><option value="faculty_records">Faculty records</option><option value="financial">Financial</option><option value="other">Other</option></select></label>
                  <label>Reference number<input value={evidenceReference} onChange={event => setEvidenceReference(event.target.value)} placeholder="Optional document reference" maxLength={160}/></label>
                  <label>Linked policy key<input value={evidencePolicy} onChange={event => setEvidencePolicy(event.target.value)} placeholder="e.g. EVIDENCE_EXPIRY" maxLength={100}/></label>
                  <label>Issue date<input type="date" value={evidenceIssued} onChange={event => setEvidenceIssued(event.target.value)} max={evidenceExpires || undefined}/></label>
                  <label>Expiry date<input type="date" value={evidenceExpires} onChange={event => setEvidenceExpires(event.target.value)} min={evidenceIssued || undefined}/></label>
                </div>
                <label className="evidence-notes-label">Notes<textarea value={evidenceNotes} onChange={event => setEvidenceNotes(event.target.value)} rows={2} maxLength={3000} placeholder="Optional context for reviewers"/></label>
                <button className="primary-button" disabled={savingEvidence || evidenceTitle.trim().length < 2}>{savingEvidence ? 'Registering…' : 'Register evidence'}</button>
              </form>
              <div className="evidence-list">
                {loadingEvidence ? <div className="table-state"><div className="loading-line"/><span>Loading evidence register…</span></div> : evidenceItems.length === 0 ? <div className="empty-state"><div className="empty-icon"><FileCheck2 size={20}/></div><strong>No evidence registered yet</strong><p>Add evidence metadata above to start the compliance register.</p></div> : evidenceItems.map(item => {
                  const today = new Date().toISOString().slice(0, 10)
                  const days = item.expires_on ? Math.ceil((new Date(item.expires_on + 'T00:00:00Z').getTime() - new Date(today + 'T00:00:00Z').getTime()) / 86400000) : null
                  const expiryState = days === null ? 'No expiry date' : days < 0 ? 'Expired' : days <= 30 ? 'Expires soon' : 'Valid'
                  return <article className="evidence-item" key={item.id}>
                    <div className="evidence-file-icon"><FileCheck2 size={18}/></div><div className="evidence-item-main"><div className="evidence-item-heading"><strong>{item.title}</strong><span className={'evidence-expiry ' + (days !== null && days < 0 ? 'expired' : days !== null && days <= 30 ? 'expiring' : 'valid')}>{expiryState}</span></div><p>{item.category.replaceAll('_', ' ')}{item.reference_number ? ' · Ref ' + item.reference_number : ''}{item.policy_key ? ' · Policy ' + item.policy_key : ''}</p>{item.notes && <p className="evidence-notes">{item.notes}</p>}<span className="evidence-date">{item.expires_on ? 'Expires ' + formatDate(item.expires_on) : 'Expiry not recorded'}{item.issued_on ? ' · Issued ' + formatDate(item.issued_on) : ''}</span></div>
                  </article>
                })}
              </div>
            </div>
            <div className="audit-summary"><ShieldCheck size={19}/><div><strong>{loadingTimeline ? 'Verifying audit history…' : eventVerification?.valid ? 'Audit chain verified' : eventVerification ? 'Audit chain check failed' : 'Audit verification unavailable'}</strong><p>{eventVerification ? eventVerification.event_count + ' events checked. ' + (eventVerification.valid ? 'No tampering detected in the stored chain.' : 'First invalid sequence: ' + eventVerification.first_invalid_sequence + '.') : 'The event chain is tamper-evident and is not an external trust anchor.'}</p></div></div>
            <div className="detail-timeline"><div className="panel-heading"><div><h2>Application timeline</h2><p>Chronological record of application events</p></div><span>{caseEvents.length} events</span></div>
              {loadingTimeline ? <div className="table-state"><div className="loading-line"/><span>Loading events…</span></div> : caseEvents.length === 0 ? <div className="empty-state"><strong>No timeline events</strong><p>Events appear here as the application progresses.</p></div> : <div className="event-list">{caseEvents.map(event => <div className="event-row" key={event.id}><div className="event-dot"/><div><strong>{event.event_type.replaceAll('_', ' ')}</strong><p>{event.from_status ? (statusLabels[event.from_status] || event.from_status.replaceAll('_', ' ')) + ' → ' + (statusLabels[event.to_status || ''] || (event.to_status || '').replaceAll('_', ' ')) : 'Initial record created'}{event.reason ? ' · ' + event.reason : ''}</p><span>{new Intl.DateTimeFormat('en-IN', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(event.occurred_at))}</span><details><summary>Event hash</summary><code>{event.event_hash}</code></details></div></div>)}</div>}
            </div>
          </section>}


          {view === 'compliance' && <section className="compliance-page">
            <div className="compliance-intro"><div className="compliance-intro-icon"><CalendarClock size={22}/></div><div><div className="eyebrow">DEADLINE INTELLIGENCE</div><h2>Evidence expiry overview</h2><p>Computed from recorded evidence dates for applications visible to your account.</p></div><button className="secondary-button small-button" onClick={() => void loadCompliance()} disabled={loadingCompliance}><Activity size={15} className={loadingCompliance ? 'spin' : ''}/> Refresh</button></div>
            {['scrutiny_officer', 'regional_officer', 'bureau_officer', 'policy_admin', 'system_admin', 'evc_coordinator'].includes(user.role) && <div className="compliance-queue-action"><div><strong>Notification queue</strong><span>Generate in-app reminders for evidence due within 30 days. Duplicate alerts are skipped.</span></div><button className="primary-button small-button" onClick={() => void handleQueueNotifications()} disabled={queueingNotifications}>{queueingNotifications ? <Activity size={15} className="spin"/> : <Bell size={15}/>} Queue expiry alerts</button></div>}
            <div className="compliance-disclaimer"><AlertTriangle size={18}/><span><strong>Illustrative warning windows.</strong> {compliance?.warning_source || 'Synthetic demo defaults; not official AICTE deadlines.'} Alerts are computed from recorded dates; the Compose worker scans periodically. Warning and escalation thresholds are synthetic demo defaults.</span></div>
            {loadingCompliance && !compliance ? <div className="table-state"><div className="loading-line"/><div className="loading-line"/><span>Calculating expiry overview…</span></div> : compliance ? <>
              <div className="compliance-metrics">
                <MetricCard icon={<FileCheck2 size={19}/>} label="Evidence records" value={String(compliance.total_evidence)} note="Metadata records in scope" tone="blue" trendIcon={<Activity size={14}/>} />
                <MetricCard icon={<AlertTriangle size={19}/>} label="Expired" value={String(compliance.expired)} note="Expiry date has passed" tone="amber" trendIcon={<ArrowUpRight size={14}/>} />
                <MetricCard icon={<Clock3 size={19}/>} label="Due within 7 days" value={String(compliance.due_within_1_day + compliance.due_within_7_days)} note="Urgent and near-term" tone="violet" trendIcon={<CalendarClock size={14}/>} />
                <MetricCard icon={<CircleHelp size={19}/>} label="No expiry date" value={String(compliance.without_expiry)} note="Validity needs review" tone="green" trendIcon={<FileCheck2 size={14}/>} />
              </div>
              <div className="compliance-summary-strip"><span>As of <strong>{formatDate(compliance.as_of)}</strong></span><span>Warning windows <strong>{compliance.warning_windows_days.join(' / ')} days</strong></span><span>Due within 30 days <strong>{compliance.due_within_30_days + compliance.due_within_7_days + compliance.due_within_1_day}</strong></span></div>
              <div className="panel compliance-alerts"><div className="panel-heading"><div><h2>Expiry alerts</h2><p>Expired items and evidence due within the next 30 days</p></div><span className="evidence-count">{compliance.alerts.length} alerts</span></div>
                {compliance.alerts.length === 0 ? <div className="empty-state"><div className="empty-icon"><ShieldCheck size={22}/></div><strong>No upcoming expiry alerts</strong><p>No expired or near-expiry evidence was found in the records currently visible to you.</p></div> : <div className="compliance-alert-list">{compliance.alerts.map(alert => <article className="compliance-alert-row" key={alert.evidence_id}><div className={'compliance-alert-icon ' + alert.severity}><AlertTriangle size={18}/></div><div className="compliance-alert-main"><div className="compliance-alert-title"><strong>{alert.title}</strong><span className={'evidence-expiry ' + (alert.severity === 'expired' ? 'expired' : alert.severity === 'urgent' || alert.severity === 'warning' ? 'expiring' : 'valid')}>{alert.severity === 'expired' ? 'Expired' : alert.days_remaining === 0 ? 'Expires today' : alert.days_remaining === 1 ? '1 day left' : alert.days_remaining + ' days left'}</span></div><p>{alert.application_number} · {alert.application_title}</p><span className="evidence-date">{alert.category.replaceAll('_', ' ')}{alert.policy_key ? ' · ' + alert.policy_key : ''} · Expires {formatDate(alert.expires_on)}</span></div><button className="secondary-button small-button" onClick={() => void openAlertApplication(alert.application_id)}>Open case <ArrowRight size={14}/></button></article>)}</div>}
              </div>
              <div className="panel compliance-alerts"><div className="panel-heading"><div><h2>Open escalations</h2><p>Evidence expired beyond the configured demo threshold</p></div><span className="evidence-count">{escalations.length} open</span></div>
                {loadingEscalations && escalations.length === 0 ? <div className="table-state"><span>Loading escalations…</span></div> : escalations.length === 0 ? <div className="empty-state"><div className="empty-icon"><ShieldCheck size={22}/></div><strong>No open escalations</strong><p>Long-overdue evidence will appear here after the scheduled worker scan.</p></div> : <div className="compliance-alert-list">{escalations.map(item => <article className="compliance-alert-row" key={item.id}><div className="compliance-alert-icon expired"><AlertTriangle size={18}/></div><div className="compliance-alert-main"><div className="compliance-alert-title"><strong>{item.summary}</strong><span className="evidence-expiry expired">Open · High</span></div><span className="evidence-date">Raised {formatDate(item.triggered_at)}</span></div><button className="secondary-button small-button" onClick={() => void openAlertApplication(item.application_id)}>Open case <ArrowRight size={14}/></button>{['scrutiny_officer', 'regional_officer', 'bureau_officer', 'policy_admin', 'system_admin', 'evc_coordinator'].includes(user.role) && <button className="secondary-button small-button" onClick={() => void handleResolveEscalation(item)}>Resolve <Check size={14}/></button>}</article>)}</div>}
              </div>
            </> : <div className="empty-state"><strong>Compliance overview unavailable</strong><p>Refresh the page after checking the API connection.</p><button className="secondary-button" onClick={() => void loadCompliance()}>Try again</button></div>}
          </section>}

          {view === 'policies' && <section className="policy-page">
            <div className="policy-intro"><div className="policy-intro-icon"><BookOpenCheck size={22}/></div><div><div className="eyebrow">GOVERNANCE & TRACEABILITY</div><h1>Policy registry</h1><p>Versioned policy records used by this prototype. Each entry shows its stated source and configured rules.</p></div><button className="secondary-button small-button" onClick={() => void loadPolicies()} disabled={loadingPolicies}><Activity size={15} className={loadingPolicies ? 'spin' : ''}/> Refresh</button></div>
            <div className="policy-disclaimer"><ShieldCheck size={18}/><span><strong>Demo policy data.</strong> These entries are synthetic examples, not official AICTE regulations or legal guidance.</span></div>
            {loadingPolicies && policies.length === 0 ? <div className="table-state"><div className="loading-line"/><div className="loading-line"/><span>Loading policy registry…</span></div> : policies.length === 0 ? <div className="empty-state"><div className="empty-icon"><BookOpenCheck size={22}/></div><strong>No policy versions published</strong><p>Policy versions will appear here when the demo seed data is loaded.</p></div> : <div className="policy-grid">{policies.map(policy => <article className="policy-card" key={policy.id}>
              <div className="policy-card-top"><span className="policy-key">{policy.policy_key.replaceAll('_', ' ')}</span><span className={policy.is_active ? 'policy-active' : 'policy-inactive'}>{policy.is_active ? 'Active' : 'Archived'}</span></div>
              <h2>{policy.title}</h2><p className="policy-description">{policy.description}</p>
              <div className="policy-meta"><span>Version <strong>v{policy.version}</strong></span><span>Effective <strong>{formatDate(policy.effective_from)}</strong></span></div>
              <div className="policy-rules"><div><strong>Configured rules</strong><span>{Object.keys(policy.rules || {}).length} rule field{Object.keys(policy.rules || {}).length === 1 ? '' : 's'}</span></div><pre>{JSON.stringify(policy.rules, null, 2)}</pre></div>
              <div className="policy-source"><FileCheck2 size={15}/><span>{policy.source_label}</span></div>
            </article>)}</div>}
          </section>}

          <footer className="page-footer"><span>PRAVAAH <span className="footer-sep">/</span> Independent prototype for workflow transparency</span><span>Demo data only <span className="footer-sep">·</span> No official AICTE integration</span></footer>
        </div>
      </main>

      {createOpen && <div className="modal-backdrop" role="presentation" onMouseDown={e=>{if(e.target===e.currentTarget)setCreateOpen(false)}}><form className="modal-card" onSubmit={handleCreate}><div className="modal-heading"><div><div className="eyebrow">APPLICATION INTAKE</div><h2>Create a draft application</h2><p>Start a new record for your institution.</p></div><button type="button" className="icon-button" onClick={()=>setCreateOpen(false)} aria-label="Close"><X size={18}/></button></div><label className="field-label" htmlFor="application-title">Application title</label><input className="text-input" id="application-title" value={newTitle} onChange={e=>setNewTitle(e.target.value)} minLength={3} maxLength={240} placeholder="e.g. New programme approval" required/><label className="field-label" htmlFor="application-summary">Short description <span className="optional">OPTIONAL</span></label><textarea className="text-input summary-input" id="application-summary" value={newSummary} onChange={e=>setNewSummary(e.target.value)} maxLength={5000} placeholder="Add context for your institution's internal tracking…"/><div className="modal-note"><LockKeyhole size={15}/> This creates a draft only. No statutory decision is made.</div>{notice&&!notice.toLowerCase().includes('success')&&<div className="inline-error">{notice}</div>}<div className="modal-actions"><button type="button" className="secondary-button" onClick={()=>setCreateOpen(false)}>Cancel</button><button className="primary-button" disabled={creating||newTitle.trim().length<3}>{creating?'Creating…':'Create draft'} <ArrowRight size={16}/></button></div></form></div>}
    </div>
  )
}

function MetricCard({icon,label,value,note,tone,trendIcon}:{icon:ReactNode;label:string;value:string;note:string;tone:string;trendIcon:ReactNode}) {
  return <article className="metric-card"><div className="metric-top"><div className={`metric-icon ${tone}`}>{icon}</div><span className={`metric-trend ${tone}`}>{trendIcon}</span></div><div className="metric-value">{value}</div><div className="metric-label">{label}</div><div className="metric-note">{note}</div></article>
}

function ApplicationTable({applications,loading,onOpen,compact=false}:{applications:Application[];loading:boolean;onOpen:(application: Application)=>void;compact?:boolean}) {
  if (loading) return <div className="table-state"><div className="loading-line"/><div className="loading-line"/><div className="loading-line"/><span>Loading applications…</span></div>
  if (!applications.length) return <div className="empty-state"><div className="empty-icon"><FileText size={22}/></div><strong>No applications found</strong><p>When records are available in your access scope, they’ll appear here.</p>{!compact&&<span>Try changing the search or status filter.</span>}</div>
  return <div className="table-scroll"><table className="application-table"><thead><tr><th>APPLICATION</th><th>STATUS</th><th>LAST UPDATED</th>{!compact&&<th>INSTITUTION REF.</th>}<th><span className="sr-only">Open</span></th></tr></thead><tbody>{applications.map(application=><tr key={application.id} onClick={() => onOpen(application)} className="clickable-row"><td><div className="case-cell"><div className="case-icon"><FileText size={16}/></div><div><strong>{application.title}</strong><span>{application.application_number}</span></div></div></td><td><span className={`status-badge status-${application.status.replaceAll('_','-')}`}><span/>{statusLabels[application.status]||application.status.replaceAll('_',' ')}</span></td><td className="date-cell">{formatDate(application.updated_at)}</td>{!compact&&<td className="ref-cell">{application.institution_id.slice(0,8).toUpperCase()}</td>}<td><button className="row-arrow" aria-label={`Open ${application.application_number}`} onClick={e=>{e.stopPropagation();onOpen(application)}}><ArrowRight size={15}/></button></td></tr>)}</tbody></table></div>
}

export default App
