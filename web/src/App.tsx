import { useCallback, useEffect, useMemo, useState, type FormEvent, type ReactNode } from 'react'
import {
  Activity, ArrowRight, ArrowUpRight, Bell, BookOpenCheck, BriefcaseBusiness,
  CalendarClock, Check, ChevronDown, CircleHelp, ClipboardList, Clock3, FileCheck2, FileText, AlertTriangle,
  Filter, LayoutDashboard, LockKeyhole, LogOut, Menu, Plus, Search, ShieldCheck, SlidersHorizontal,
  Sparkles, Users, X, Inbox, MailWarning,
} from 'lucide-react'
import { api, clearToken, getToken, saveToken, type Application, type ApplicationEvent, type ApplicationEvidence, type ComplianceOverview, type EventVerification, type PolicyVersion, type NotificationRecord, type ComplianceEscalation, type EVCVisit, type EVCEligibility, type EvidenceAttachment, type ComplianceSubmission, type OperationsMetrics, type PendencyAnalytics, type TaskInbox, type TaskInboxItem, type NotificationOperationsSummary, type NotificationOperationsItem, type PolicyToProofDossier, type User } from './api'

type View = 'overview' | 'applications' | 'detail' | 'policies' | 'compliance' | 'evc' | 'inbox' | 'notifications' | 'reports'
type EVCChecklistItem = { key: 'governance' | 'infrastructure' | 'faculty' | 'curriculum' | 'safety' | 'records'; label: string; result: 'pass' | 'needs_attention' | 'not_applicable'; notes: string }
const EVC_CHECKLIST = [
  { key: 'governance', label: 'Governance and approvals' },
  { key: 'infrastructure', label: 'Infrastructure readiness' },
  { key: 'faculty', label: 'Faculty availability' },
  { key: 'curriculum', label: 'Curriculum and programme' },
  { key: 'safety', label: 'Safety and accessibility' },
  { key: 'records', label: 'Records and evidence' },
] as const

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
  const date = new Date(value)
  if (!value || Number.isNaN(date.getTime())) return 'Date unavailable'
  return new Intl.DateTimeFormat('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }).format(date)
}

function formatStatus(status: string) {
  return statusLabels[status] || status.replaceAll('_', ' ').replace(/\\b\\w/g, character => character.toUpperCase())
}

function App() {
  const [user, setUser] = useState<User | null>(null)
  const [booting, setBooting] = useState(true)
  const [view, setView] = useState<View>('overview')
  const [applications, setApplications] = useState<Application[]>([])
  const [selectedApplication, setSelectedApplication] = useState<Application | null>(null)
  const [caseEvents, setCaseEvents] = useState<ApplicationEvent[]>([])
  const [evidenceItems, setEvidenceItems] = useState<ApplicationEvidence[]>([])
  const [submissions, setSubmissions] = useState<ComplianceSubmission[]>([])
  const [loadingSubmissions, setLoadingSubmissions] = useState(false)
  const [submissionBusy, setSubmissionBusy] = useState(false)
  const [undertakingType, setUndertakingType] = useState('annual_undertaking')
  const [undertakingTitle, setUndertakingTitle] = useState('Annual compliance undertaking')
  const [undertakingDeclaration, setUndertakingDeclaration] = useState('')
  const [undertakingEvidenceIds, setUndertakingEvidenceIds] = useState<string[]>([])
  const [reviewNotes, setReviewNotes] = useState('')
  const [correctionForId, setCorrectionForId] = useState<string | null>(null)
  const [evidenceVisitReferences, setEvidenceVisitReferences] = useState<EVCVisit[]>([])
  const [attachmentsByEvidence, setAttachmentsByEvidence] = useState<Record<string, EvidenceAttachment[]>>({})
  const [uploadingEvidenceId, setUploadingEvidenceId] = useState<string | null>(null)
  const [downloadingAttachmentId, setDownloadingAttachmentId] = useState<string | null>(null)
  const [previewImage, setPreviewImage] = useState<{ url: string; name: string } | null>(null)
  const [loadingEvidence, setLoadingEvidence] = useState(false)
  const [evidenceTitle, setEvidenceTitle] = useState('')
  const [evidenceCategory, setEvidenceCategory] = useState('approval_letter')
  const [evidenceReference, setEvidenceReference] = useState('')
  const [evidenceIssued, setEvidenceIssued] = useState('')
  const [evidenceExpires, setEvidenceExpires] = useState('')
  const [evidencePolicy, setEvidencePolicy] = useState('')
  const [evidenceNotes, setEvidenceNotes] = useState('')
  const [renewalEvidenceId, setRenewalEvidenceId] = useState<string | null>(null)
  const [savingEvidence, setSavingEvidence] = useState(false)
  const [eventVerification, setEventVerification] = useState<EventVerification | null>(null)
  const [policyDossier, setPolicyDossier] = useState<PolicyToProofDossier | null>(null)
  const [loadingPolicyDossier, setLoadingPolicyDossier] = useState(false)
  const [policyDossierError, setPolicyDossierError] = useState('')
  const [loadingTimeline, setLoadingTimeline] = useState(false)
  const [transitionReason, setTransitionReason] = useState('')
  const [transitionBusy, setTransitionBusy] = useState(false)
  const [compliance, setCompliance] = useState<ComplianceOverview | null>(null)
  const [operationsMetrics, setOperationsMetrics] = useState<OperationsMetrics | null>(null)
  const [pendencyAnalytics, setPendencyAnalytics] = useState<PendencyAnalytics | null>(null)
  const [taskInbox, setTaskInbox] = useState<TaskInbox | null>(null)
  const [loadingTaskInbox, setLoadingTaskInbox] = useState(false)
  const [inboxPriorityFilter, setInboxPriorityFilter] = useState('all')
  const [loadingCompliance, setLoadingCompliance] = useState(false)
  const [escalations, setEscalations] = useState<ComplianceEscalation[]>([])
  const [loadingEscalations, setLoadingEscalations] = useState(false)
  const [notifications, setNotifications] = useState<NotificationRecord[]>([])
  const [notificationsOpen, setNotificationsOpen] = useState(false)
  const [loadingNotifications, setLoadingNotifications] = useState(false)
  const [notificationOperations, setNotificationOperations] = useState<NotificationOperationsSummary | null>(null)
  const [loadingNotificationOperations, setLoadingNotificationOperations] = useState(false)
  const [notificationStatusFilter, setNotificationStatusFilter] = useState('all')
  const [retryingOperationalNotificationId, setRetryingOperationalNotificationId] = useState<string | null>(null)
  const [queueingNotifications, setQueueingNotifications] = useState(false)
  const [reportFromDate, setReportFromDate] = useState('')
  const [reportToDate, setReportToDate] = useState('')
  const [reportDownloading, setReportDownloading] = useState<string | null>(null)
  const [policies, setPolicies] = useState<PolicyVersion[]>([])
  const [loadingPolicies, setLoadingPolicies] = useState(false)
  const [evcVisits, setEvcVisits] = useState<EVCVisit[]>([])
  const [loadingEvcVisits, setLoadingEvcVisits] = useState(false)
  const [evcStatusFilter, setEvcStatusFilter] = useState('scheduled')
  const [showEvcForm, setShowEvcForm] = useState(false)
  const [savingEvcVisit, setSavingEvcVisit] = useState(false)
  const [evcApplicationId, setEvcApplicationId] = useState('')
  const [evcEligibility, setEvcEligibility] = useState<EVCEligibility | null>(null)
  const [loadingEvcEligibility, setLoadingEvcEligibility] = useState(false)
  const [evcScheduledFor, setEvcScheduledFor] = useState('')
  const [evcMode, setEvcMode] = useState<'onsite' | 'virtual'>('onsite')
  const [evcLocation, setEvcLocation] = useState('')
  const [evcNotes, setEvcNotes] = useState('')
  const [updatingEvcVisitId, setUpdatingEvcVisitId] = useState<string | null>(null)
  const [reportVisitId, setReportVisitId] = useState<string | null>(null)
  const [reportChecklist, setReportChecklist] = useState<EVCChecklistItem[]>(EVC_CHECKLIST.map(item => ({ ...item, result: 'pass', notes: '' })))
  const [reportOutcome, setReportOutcome] = useState('')
  const [reportObservations, setReportObservations] = useState('')
  const [reportEvidence, setReportEvidence] = useState<ApplicationEvidence[]>([])
  const [reportEvidenceIds, setReportEvidenceIds] = useState<string[]>([])
  const [loadingReportEvidence, setLoadingReportEvidence] = useState(false)
  const [savingEvcReport, setSavingEvcReport] = useState(false)
  const [total, setTotal] = useState(0)
  const [loadingCases, setLoadingCases] = useState(false)
  const [dashboardLoading, setDashboardLoading] = useState(false)
  const [dashboardRecentEvents, setDashboardRecentEvents] = useState<{ application: Application; event: ApplicationEvent }[]>([])
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
    if (!user || view !== 'overview') return
    let cancelled = false
    setDashboardLoading(true)
    Promise.all([
      api.complianceOverview().catch(() => null),
      api.operationsMetrics().catch(() => null),
      api.pendencyAnalytics().catch(() => null),
      api.evcVisits().catch(() => [] as EVCVisit[]),
      Promise.all(applications.slice(0, 8).map(async application => {
        try {
          const events = await api.applicationEvents(application.id)
          return events.map(event => ({ application, event }))
        } catch {
          return []
        }
      })),
    ]).then(([overview, operationalMetrics, pendency, visits, eventGroups]) => {
      if (cancelled) return
      if (overview) setCompliance(overview)
      if (operationalMetrics) setOperationsMetrics(operationalMetrics)
      if (pendency) setPendencyAnalytics(pendency)
      setEvcVisits(visits)
      setDashboardRecentEvents(eventGroups.flat().sort((a, b) => new Date(b.event.occurred_at).getTime() - new Date(a.event.occurred_at).getTime()).slice(0, 6))
    }).finally(() => {
      if (!cancelled) setDashboardLoading(false)
    })
    return () => { cancelled = true }
  }, [user, view, applications])

  useEffect(() => {
    if (!user || view !== 'detail' || !selectedApplication) return
    let cancelled = false
    setLoadingTimeline(true)
    setLoadingEvidence(true)
    setLoadingSubmissions(true)
    Promise.all([api.applicationEvents(selectedApplication.id), api.verifyEvents(selectedApplication.id), api.evidence(selectedApplication.id), api.evcVisits({ applicationId: selectedApplication.id }), api.submissions(selectedApplication.id)])
      .then(async ([events, verification, evidence, visits, submissionRecords]) => {
        const attachmentLists = await Promise.all(evidence.map(async item => ({
          id: item.id,
          files: await api.evidenceAttachments(selectedApplication.id, item.id),
        })))
        if (!cancelled) {
          setCaseEvents(events); setEventVerification(verification); setEvidenceItems(evidence); setEvidenceVisitReferences(visits); setSubmissions(submissionRecords)
          setAttachmentsByEvidence(Object.fromEntries(attachmentLists.map(item => [item.id, item.files])))
        }
      })
      .catch(error => { if (!cancelled) setNotice(error instanceof Error ? error.message : 'Could not load the application timeline and evidence.') })
      .finally(() => { if (!cancelled) { setLoadingTimeline(false); setLoadingEvidence(false); setLoadingSubmissions(false) } })
    return () => { cancelled = true }
  }, [user, view, selectedApplication])

  useEffect(() => {
    if (!user || view !== 'detail' || !selectedApplication) return
    let cancelled = false
    setLoadingPolicyDossier(true)
    setPolicyDossierError('')
    api.policyToProof(selectedApplication.id).then(dossier => {
      if (!cancelled) setPolicyDossier(dossier)
    }).catch(error => {
      if (!cancelled) {
        setPolicyDossier(null)
        setPolicyDossierError(error instanceof Error ? error.message : 'Could not load the traceability dossier.')
      }
    }).finally(() => { if (!cancelled) setLoadingPolicyDossier(false) })
    return () => { cancelled = true }
  }, [user, view, selectedApplication])

  const loadNotificationOperations = useCallback(async () => {
    if (!user) return
    setLoadingNotificationOperations(true)
    try { setNotificationOperations(await api.notificationOperations()) }
    catch (error) { setNotice(error instanceof Error ? error.message : 'Could not load notification operations.') }
    finally { setLoadingNotificationOperations(false) }
  }, [user])

  useEffect(() => { if (user && view === 'notifications') void loadNotificationOperations() }, [user, view, loadNotificationOperations])

  async function handleRetryOperationalNotification(item: NotificationOperationsItem) {
    setRetryingOperationalNotificationId(item.id)
    setNotice('')
    try {
      await api.retryOperationalNotification(item.id)
      await loadNotificationOperations()
      await loadNotifications()
      setNotice('Delivery retry queued. Attempt history was preserved and the request was added to the audit trail.')
    } catch (error) { setNotice(error instanceof Error ? error.message : 'Could not retry notification delivery.') }
    finally { setRetryingOperationalNotificationId(null) }
  }

  async function handleQueueOperationalNotifications() {
    setQueueingNotifications(true)
    setNotice('')
    try {
      const result = await api.queueExpiryNotifications()
      await loadNotificationOperations()
      await loadNotifications()
      setNotice(`Queued ${result.created} notification(s); ${result.skipped_existing} duplicate(s) skipped.`)
    } catch (error) { setNotice(error instanceof Error ? error.message : 'Could not queue expiry notifications.') }
    finally { setQueueingNotifications(false) }
  }

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

  async function handleRetryNotification(notification: NotificationRecord) {
    try {
      const updated = await api.retryNotification(notification.id)
      setNotifications(items => items.map(item => item.id === updated.id ? updated : item))
      setNotice('Delivery retry queued. The notification worker will attempt delivery when SMTP is configured.')
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'Could not retry notification delivery.')
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

  const loadTaskInbox = useCallback(async () => {
    if (!user) return
    setLoadingTaskInbox(true)
    try { setTaskInbox(await api.taskInbox()) }
    catch (error) { setNotice(error instanceof Error ? error.message : 'Could not load your task inbox.') }
    finally { setLoadingTaskInbox(false) }
  }, [user])

  useEffect(() => { if (user && view === 'inbox') void loadTaskInbox() }, [user, view, loadTaskInbox])

  const loadCompliance = useCallback(async () => {
    if (!user) return
    setLoadingCompliance(true)
    setNotice('')
    try { setCompliance(await api.complianceOverview()) }
    catch (error) { setNotice(error instanceof Error ? error.message : 'Could not load compliance overview.') }
    finally { setLoadingCompliance(false) }
  }, [user])

  useEffect(() => { if (user && view === 'compliance') void loadCompliance() }, [user, view, loadCompliance])

  async function openInboxTask(item: TaskInboxItem) {
    setNotice('')
    if (item.action_view === 'detail') {
      try { setSelectedApplication(await api.application(item.application_id)); setView('detail') }
      catch (error) { setNotice(error instanceof Error ? error.message : 'Could not open the task application.') }
      return
    }
    if (item.action_view === 'compliance') { setView('compliance'); return }
    if (item.action_view === 'evc') { setView('evc'); return }
    if (item.action_view === 'notifications') { setView('overview'); setNotificationsOpen(true); void loadNotifications(); return }
    setView('applications')
  }

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

  const loadEvcVisits = useCallback(async () => {
    if (!user) return
    setLoadingEvcVisits(true)
    setNotice('')
    try {
      setEvcVisits(await api.evcVisits({ status: evcStatusFilter || undefined }))
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'Could not load EVC visits.')
    } finally {
      setLoadingEvcVisits(false)
    }
  }, [user, evcStatusFilter])

  useEffect(() => {
    if (user && view === 'evc') void loadEvcVisits()
  }, [user, view, loadEvcVisits])

  const canScheduleEvc = ['evc_coordinator', 'bureau_officer', 'policy_admin', 'system_admin'].includes(user?.role || '')

  async function handleSelectEvcApplication(applicationId: string) {
    setEvcApplicationId(applicationId)
    setEvcEligibility(null)
    if (!applicationId) return
    setLoadingEvcEligibility(true)
    try {
      setEvcEligibility(await api.evcEligibility(applicationId))
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'Could not check EVC eligibility.')
    } finally {
      setLoadingEvcEligibility(false)
    }
  }

  async function handleScheduleEvcVisit(event: FormEvent) {
    event.preventDefault()
    if (!evcApplicationId || !evcScheduledFor) return
    setSavingEvcVisit(true)
    setNotice('')
    try {
      await api.scheduleEVCVisit({
        application_id: evcApplicationId,
        scheduled_for: new Date(evcScheduledFor).toISOString(),
        mode: evcMode,
        ...(evcMode === 'onsite' && evcLocation.trim() ? { location: evcLocation.trim() } : {}),
        ...(evcNotes.trim() ? { notes: evcNotes.trim() } : {}),
      })
      setShowEvcForm(false)
      setEvcApplicationId('')
      setEvcEligibility(null)
      setEvcScheduledFor('')
      setEvcMode('onsite')
      setEvcLocation('')
      setEvcNotes('')
      await loadEvcVisits()
      setNotice('EVC visit scheduled and recorded in the application audit timeline.')
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'Could not schedule EVC visit.')
    } finally {
      setSavingEvcVisit(false)
    }
  }

  async function handleUpdateEvcVisit(visit: EVCVisit, status: 'completed' | 'cancelled') {
    setUpdatingEvcVisitId(visit.id)
    setNotice('')
    try {
      await api.updateEVCVisitStatus(visit.id, status)
      await loadEvcVisits()
      setNotice(`EVC visit marked ${status}; the action was recorded in the audit timeline.`)
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'Could not update EVC visit.')
    } finally {
      setUpdatingEvcVisitId(null)
    }
  }

  async function openEvcReport(visit: EVCVisit) {
    setReportVisitId(visit.id)
    setReportChecklist(EVC_CHECKLIST.map(item => {
      const existing = visit.checklist?.find(entry => entry.key === item.key)
      return { ...item, result: existing?.result || 'pass', notes: existing?.notes || '' }
    }))
    setReportOutcome(visit.outcome_summary || '')
    setReportObservations(visit.observations || '')
    setReportEvidenceIds(visit.linked_evidence_ids || [])
    setLoadingReportEvidence(true)
    try {
      setReportEvidence(await api.evidence(visit.application_id))
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'Could not load application evidence.')
      setReportEvidence([])
    } finally {
      setLoadingReportEvidence(false)
    }
  }

  async function handleSaveEvcReport(event: FormEvent, submit: boolean) {
    event.preventDefault()
    if (!reportVisitId) return
    setSavingEvcReport(true)
    setNotice('')
    try {
      await api.saveEVCReport(reportVisitId, {
        checklist: reportChecklist.map(item => ({ ...item, notes: item.notes.trim() || null })),
        outcome_summary: reportOutcome.trim(),
        ...(reportObservations.trim() ? { observations: reportObservations.trim() } : {}),
        evidence_ids: reportEvidenceIds,
        submit,
      })
      setReportVisitId(null)
      await loadEvcVisits()
      setNotice(submit ? 'EVC outcome report submitted and locked in the audit timeline.' : 'EVC outcome report draft saved.')
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'Could not save the EVC report.')
    } finally {
      setSavingEvcReport(false)
    }
  }

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

  async function handleSubmitUndertaking(event: FormEvent) {
    event.preventDefault()
    if (!selectedApplication || !undertakingEvidenceIds.length || undertakingDeclaration.trim().length < 20) return
    setSubmissionBusy(true)
    try {
      const payload = { submission_type: undertakingType, title: undertakingTitle.trim(), declaration: undertakingDeclaration.trim(), evidence_ids: undertakingEvidenceIds }
      if (correctionForId) await api.resubmitSubmission(correctionForId, payload)
      else await api.createSubmission(selectedApplication.id, payload)
      setSubmissions(await api.submissions(selectedApplication.id))
      setCorrectionForId(null)
      setUndertakingDeclaration('')
      setReviewNotes('')
      setNotice(correctionForId ? 'Corrected undertaking submitted as a new version.' : 'Compliance undertaking submitted.')
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'Could not submit the compliance undertaking.')
    } finally {
      setSubmissionBusy(false)
    }
  }

  async function handleReviewUndertaking(item: ComplianceSubmission, decision: 'accepted' | 'changes_requested' | 'rejected') {
    if (!selectedApplication) return
    setSubmissionBusy(true)
    try {
      await api.reviewSubmission(item.id, decision, reviewNotes.trim() || undefined)
      setSubmissions(await api.submissions(selectedApplication.id))
      setCaseEvents(await api.applicationEvents(selectedApplication.id))
      setEventVerification(await api.verifyEvents(selectedApplication.id))
      setReviewNotes('')
      setNotice('Compliance submission review recorded.')
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'Could not record the submission review.')
    } finally {
      setSubmissionBusy(false)
    }
  }

  function handleStartCorrection(item: ComplianceSubmission) {
    setCorrectionForId(item.id)
    setUndertakingType(item.submission_type)
    setUndertakingTitle(item.title)
    setUndertakingDeclaration(item.declaration)
    setUndertakingEvidenceIds(item.evidence_ids)
    setNotice('Correction form loaded. Update the declaration and evidence before resubmitting.')
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
      if (renewalEvidenceId) await api.renewEvidence(selectedApplication.id, renewalEvidenceId, payload)
      else await api.registerEvidence(selectedApplication.id, payload)
      const [evidence, events, verification] = await Promise.all([api.evidence(selectedApplication.id), api.applicationEvents(selectedApplication.id), api.verifyEvents(selectedApplication.id)])
      setEvidenceItems(evidence)
      setCaseEvents(events)
      setEventVerification(verification)
      setEvidenceTitle(''); setEvidenceReference(''); setEvidenceIssued(''); setEvidenceExpires(''); setEvidencePolicy(''); setEvidenceNotes('')
      setNotice(renewalEvidenceId ? 'Renewal saved as a new version. The prior evidence metadata and history remain available.' : 'Evidence metadata registered and added to the audit timeline.')
      setRenewalEvidenceId(null)
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'Could not register evidence metadata.')
    } finally {
      setSavingEvidence(false)
    }
  }

  async function handleUploadEvidenceFile(evidenceId: string, file?: File) {
    if (!selectedApplication || !file) return
    setUploadingEvidenceId(evidenceId)
    setNotice('')
    try {
      await api.uploadEvidenceAttachment(selectedApplication.id, evidenceId, file)
      const [attachments, events, verification] = await Promise.all([
        api.evidenceAttachments(selectedApplication.id, evidenceId),
        api.applicationEvents(selectedApplication.id),
        api.verifyEvents(selectedApplication.id),
      ])
      setAttachmentsByEvidence(items => ({ ...items, [evidenceId]: attachments }))
      setCaseEvents(events)
      setEventVerification(verification)
      setNotice('File uploaded, validated and recorded in the application audit timeline.')
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'Could not upload this file.')
    } finally {
      setUploadingEvidenceId(null)
    }
  }

  async function handlePreviewEvidenceImage(evidenceId: string, attachment: EvidenceAttachment) {
    if (!selectedApplication) return
    setDownloadingAttachmentId(attachment.id)
    setNotice('')
    try {
      const blob = await api.downloadEvidenceAttachment(selectedApplication.id, evidenceId, attachment.id)
      if (!blob.type.startsWith('image/')) throw new Error('This file cannot be previewed as an image.')
      setPreviewImage({ url: URL.createObjectURL(blob), name: attachment.original_filename })
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'Could not preview this image.')
    } finally {
      setDownloadingAttachmentId(null)
    }
  }

  function closeImagePreview() {
    if (previewImage) URL.revokeObjectURL(previewImage.url)
    setPreviewImage(null)
  }

  async function handleDownloadEvidenceFile(evidenceId: string, attachment: EvidenceAttachment) {
    if (!selectedApplication) return
    setDownloadingAttachmentId(attachment.id)
    setNotice('')
    try {
      const blob = await api.downloadEvidenceAttachment(selectedApplication.id, evidenceId, attachment.id)
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = attachment.original_filename
      document.body.appendChild(anchor)
      anchor.click()
      anchor.remove()
      URL.revokeObjectURL(url)
      setNotice('Private evidence download started.')
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'Could not download this file.')
    } finally {
      setDownloadingAttachmentId(null)
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
          <p className="muted login-description">Choose a demo role to fill its account, or enter credentials manually.</p>
          <div className="demo-role-picker" aria-label="Choose a demo role">
            {[
              { label: 'Institution', email: 'demo.institution@example.test' },
              { label: 'Scrutiny Officer', email: 'demo.reviewer@example.test' },
              { label: 'Regional Officer', email: 'demo.regional@example.test' },
              { label: 'Bureau Officer', email: 'demo.bureau@example.test' },
              { label: 'EVC Coordinator', email: 'demo.evc@example.test' },
              { label: 'Competent Authority', email: 'demo.authority@example.test' },
              { label: 'Policy Admin', email: 'demo.policyadmin@example.test' },
              { label: 'System Admin', email: 'demo.admin@example.test' },
            ].map(account => (
              <button key={account.email} type="button" className={loginEmail === account.email ? 'demo-role-button selected' : 'demo-role-button'} onClick={() => { setLoginEmail(account.email); setLoginPassword('PravaahDemo2026!'); setLoginError('') }}>
                {account.label}
              </button>
            ))}
          </div>
          <label className="field-label" htmlFor="email">Email address</label>
          <div className="input-wrap"><Users size={17} /><input id="email" type="email" autoComplete="username" value={loginEmail} onChange={e => setLoginEmail(e.target.value)} required /></div>
          <label className="field-label" htmlFor="password">Password</label>
          <div className="input-wrap"><LockKeyhole size={17} /><input id="password" type="password" autoComplete="current-password" value={loginPassword} onChange={e => setLoginPassword(e.target.value)} placeholder="Choose a demo role above" required /></div>
          {loginError && <div className="inline-error" role="alert">{loginError}</div>}
          <button className="primary-button login-submit" disabled={loggingIn}>{loggingIn ? 'Signing in…' : 'Sign in'} <ArrowRight size={17} /></button>
          <div className="login-security"><LockKeyhole size={14} /><span>Demo session · Role-based access</span></div>
          <div className="demo-hint">Public synthetic demo accounts only. Never use these accounts for real or confidential data. Password: <strong>PravaahDemo2026!</strong></div>
        </form>
        <div className="login-bottom">© 2026 PRAVAAH <span>·</span> Transparent by design</div>
      </section>
    </main>
  )

  const downloadReport = async (type: 'applications' | 'compliance' | 'evidence' | 'evc' | 'notifications') => {
    if (reportFromDate && reportToDate && reportFromDate > reportToDate) {
      setNotice('The report start date must be on or before its end date.')
      return
    }
    setReportDownloading(type)
    try {
      await api.downloadOperationsReport(type, reportFromDate || undefined, reportToDate || undefined)
      setNotice(`${type[0].toUpperCase() + type.slice(1)} CSV export downloaded successfully.`)
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'Could not export this report.')
    } finally {
      setReportDownloading(null)
    }
  }

  const navItems = [
    { id: 'overview' as const, label: 'Overview', icon: LayoutDashboard },
    { id: 'applications' as const, label: 'Applications', icon: ClipboardList, count: total },
    { id: 'inbox' as const, label: 'Task inbox', icon: Inbox, count: taskInbox?.total },
    { id: 'reports' as const, label: 'Reports & exports', icon: FileText },
    ...(['scrutiny_officer', 'regional_officer', 'bureau_officer', 'policy_admin', 'system_admin', 'evc_coordinator'].includes(user.role) ? [{ id: 'notifications' as const, label: 'Notification ops', icon: MailWarning }] : []),
    { id: 'evc' as const, label: 'EVC scheduling', icon: CalendarClock },
    { id: 'compliance' as const, label: 'Deadlines & compliance', icon: ShieldCheck },

  ]
  const roleLabel = user.role.replaceAll('_', ' ').replace(/\b\w/g, char => char.toUpperCase())
  const workflowWorkMap: Record<string, { statuses: string[]; action: string; detail: string; priority: number; label: string }[]> = {
    institution_user: [
      { statuses: ['clarification_requested'], action: 'Respond to clarification', detail: 'Update the application and resubmit', priority: 1, label: 'Action required' },
      { statuses: ['returned'], action: 'Revise and resubmit', detail: 'Address the return notes before resubmission', priority: 1, label: 'Action required' },
      { statuses: ['draft'], action: 'Submit application', detail: 'Complete the draft and submit it for scrutiny', priority: 2, label: 'Ready to submit' },
    ],
    scrutiny_officer: [
      { statuses: ['submitted'], action: 'Start scrutiny', detail: 'Begin the initial application review', priority: 1, label: 'Review queue' },
      { statuses: ['under_scrutiny'], action: 'Continue scrutiny', detail: 'Request clarification, recommend approval or return', priority: 2, label: 'In progress' },
    ],
    bureau_officer: [
      { statuses: ['recommended_for_approval'], action: 'Forward for decision', detail: 'Move the recommendation to competent authority', priority: 1, label: 'Needs forwarding' },
    ],
    competent_authority: [
      { statuses: ['pending_authority_decision'], action: 'Record decision', detail: 'Review the case and approve or reject', priority: 1, label: 'Decision pending' },
    ],
  }
  const myWorkflowItems = applications.flatMap(application => {
    const rule = (workflowWorkMap[user.role] || []).find(item => item.statuses.includes(application.status))
    return rule ? [{ application, ...rule }] : []
  }).sort((a, b) => a.priority - b.priority || new Date(a.application.updated_at).getTime() - new Date(b.application.updated_at).getTime()).slice(0, 6)
  const myEvcReportItems = user.role === 'evc_coordinator'
    ? evcVisits.filter(visit => visit.status === 'completed' && visit.report_status !== 'submitted').sort((a, b) => new Date(a.scheduled_for).getTime() - new Date(b.scheduled_for).getTime()).slice(0, 4)
    : []

  return (
    <div className="app-shell">
      {mobileNav && <button className="mobile-backdrop" aria-label="Close navigation" onClick={() => setMobileNav(false)} />}
      <aside className={`sidebar ${mobileNav ? 'sidebar-open' : ''}`}>
        <div className="sidebar-brand"><div className="brand-mark"><Activity size={22} /></div><div><strong>PRAVAAH</strong><span>APPROVAL INTELLIGENCE</span></div><button className="mobile-close icon-button" onClick={() => setMobileNav(false)} aria-label="Close menu"><X size={18} /></button></div>
        <button type="button" className="workspace-select" onClick={() => { setView('overview'); setMobileNav(false); setNotice('Workspace overview opened. Use the profile control at the top right to sign out.') }} title="Open workspace overview" aria-label="Open workspace overview"><div className="workspace-avatar">{initials(user.full_name)}</div><div className="workspace-meta"><strong>{user.role === 'institution_user' ? 'Institution workspace' : 'Review workspace'}</strong><span>{roleLabel}</span></div><ChevronDown size={15} /></button>
        <div className="nav-label">WORKSPACE</div>
        <nav className="side-nav" aria-label="Main navigation">
          {navItems.map(item => <button key={item.id} className={`nav-item ${view === item.id ? 'active' : ''}`} onClick={() => { setView(item.id); setMobileNav(false) }}><item.icon size={18} /><span>{item.label}</span>{item.id === 'applications' && <span className="nav-count">{total}</span>}{item.id === 'inbox' && taskInbox && <span className="nav-count">{taskInbox.total}</span>}</button>)}
        </nav>
        <div className="nav-label nav-label-spaced">OPERATIONS</div>
        
        <button className={'nav-item ' + (view === 'policies' ? 'active' : '')} onClick={() => { setView('policies'); setMobileNav(false) }}><BookOpenCheck size={18} /><span>Policy registry</span></button>
        <button type="button" className={`nav-item ${view === 'detail' ? 'active' : ''}`} onClick={() => { setView('applications'); setMobileNav(false); setNotice('Open an application to view and manage its evidence and document attachments.') }} title="Find evidence in application records"><FileCheck2 size={18} /><span>Evidence & documents</span><ArrowRight size={14} className="nav-action-icon" /></button>
        <div className="sidebar-bottom"><div className="help-card"><div className="help-icon"><CircleHelp size={18} /></div><strong>Need a hand?</strong><p>Explore the workflow guide as modules become available.</p><span>Prototype workspace</span></div><div className="sidebar-foot"><span className="online-dot" /> API-connected workspace <span className="version">v0.1</span></div></div>
      </aside>

      <main className="main-panel">
        <header className="topbar"><div className="topbar-left"><button className="icon-button mobile-menu" aria-label="Open navigation" onClick={() => setMobileNav(true)}><Menu size={20} /></button><div className="breadcrumb">Workspace <span>/</span> <strong>{view === 'overview' ? 'Overview' : view === 'applications' ? 'Applications' : view === 'detail' ? 'Application details' : view === 'compliance' ? 'Deadlines & compliance' : view === 'evc' ? 'EVC scheduling' : view === 'inbox' ? 'Task inbox' : view === 'notifications' ? 'Notification operations' : view === 'reports' ? 'Reports & exports' : 'Policy registry'}</strong></div></div><div className="topbar-right"><div className="environment-pill"><span /> Demo environment</div><div className="notification-wrap"><button className="icon-button notification-button" aria-label="Notifications" title="Open notifications" onClick={() => { const next = !notificationsOpen; setNotificationsOpen(next); if (next) void loadNotifications() }}><Bell size={18} />{notifications.some(item => !item.read_at) && <i />}</button>{notificationsOpen && <div className="notification-popover"><div className="notification-popover-head"><div><strong>Notifications</strong><span>{notifications.filter(item => !item.read_at).length} unread</span></div><button className="text-button" onClick={() => void loadNotifications()} disabled={loadingNotifications}>Refresh</button></div>{loadingNotifications && notifications.length === 0 ? <div className="notification-empty">Loading notifications…</div> : notifications.length === 0 ? <div className="notification-empty">No notifications yet. Expiry alerts can be queued from Deadlines & compliance.</div> : <div className="notification-list">{notifications.slice(0, 12).map(item => <div className="notification-entry" key={item.id}><button className={'notification-row ' + (!item.read_at ? 'unread' : '')} onClick={() => void handleMarkNotificationRead(item)}><span className={'notification-severity ' + item.severity}><Bell size={14}/></span><span className="notification-row-copy"><strong>{item.title}</strong><span>{item.message}</span><small>{formatDate(item.created_at)} · {item.delivery_status} · {item.attempt_count}/{item.max_attempts} attempts</small>{item.last_error && <small className="notification-delivery-error">{item.last_error}</small>}{item.next_attempt_at && item.delivery_status === 'pending' && <small>Next attempt: {formatDate(item.next_attempt_at)}</small>}</span>{!item.read_at && <i />}</button>{item.delivery_status === 'failed' && <div className="notification-recovery"><span>Delivery failed after {item.attempt_count} attempt(s).</span><button className="text-button" onClick={() => void handleRetryNotification(item)}>Retry delivery</button></div>}</div>)}</div>}</div>}</div><div className="topbar-divider" /><button className="profile-button" onClick={signOut} title="Sign out"><div className="profile-avatar">{initials(user.full_name)}</div><div className="profile-copy"><strong>{user.full_name}</strong><span>{roleLabel}</span></div><LogOut size={16} className="logout-icon" /></button></div></header>

        <div className="content-area">
          <div className="page-heading"><div><div className="eyebrow">YOUR WORKSPACE <span className="heading-dot">·</span> {new Intl.DateTimeFormat('en-IN', { weekday: 'long', day: 'numeric', month: 'long' }).format(new Date())}</div><h1>{view === 'overview' ? 'Good to see you, ' + user.full_name.split(' ')[0] + '.' : view === 'applications' ? 'Applications' : view === 'detail' ? 'Application details' : view === 'compliance' ? 'Deadlines & compliance' : view === 'evc' ? 'EVC scheduling' : view === 'inbox' ? 'Task inbox' : view === 'notifications' ? 'Notification operations' : view === 'reports' ? 'Reports & exports' : 'Policy registry'}</h1><p>{view === 'overview' ? 'Here’s the latest view of your approval workflow.' : view === 'applications' ? 'Search, review and manage your application records.' : view === 'detail' ? 'Review the current record and its latest status.' : view === 'compliance' ? 'Monitor recorded evidence expiry dates across your visible applications.' : view === 'evc' ? 'Plan verification visits and keep outcomes traceable.' : view === 'inbox' ? 'Prioritized actions from the workflow records visible to your role.' : view === 'notifications' ? 'Monitor delivery health, investigate failures, and safely retry eligible notifications.' : view === 'reports' ? 'Export access-scoped operational records to CSV for analysis and review.' : 'Review versioned policy records and their configured rules.'}</p></div><div className="heading-actions"><button className="secondary-button" onClick={() => void (view === 'policies' ? loadPolicies() : view === 'compliance' ? loadCompliance() : view === 'evc' ? loadEvcVisits() : view === 'inbox' ? loadTaskInbox() : view === 'notifications' ? loadNotificationOperations() : loadApplications())} disabled={view === 'policies' ? loadingPolicies : view === 'compliance' ? loadingCompliance : view === 'evc' ? loadingEvcVisits : view === 'inbox' ? loadingTaskInbox : view === 'notifications' ? loadingNotificationOperations : loadingCases}><Activity size={16} className={(view === 'policies' ? loadingPolicies : view === 'compliance' ? loadingCompliance : view === 'evc' ? loadingEvcVisits : loadingCases) ? 'spin' : ''} /> Refresh</button>{view !== 'policies' && user.role === 'institution_user' && <button className="primary-button" onClick={() => setCreateOpen(true)}><Plus size={17} /> New application</button>}</div></div>

          {notice && <div className={`notice ${notice.toLowerCase().includes('success') ? 'notice-success' : ''}`} role="status" aria-live="polite" aria-atomic="true"><span>{notice}</span><button onClick={() => setNotice('')} aria-label="Dismiss message"><X size={16} /></button></div>}

          {view === 'overview' && <>
            <section className="welcome-banner"><div className="banner-orb orb-one" /><div className="banner-orb orb-two" /><div className="banner-copy"><div className="banner-kicker"><Sparkles size={14} /> WORKFLOW SNAPSHOT</div><h2>Clarity at every stage.</h2><p>Keep applications moving with a clearer view of status, ownership and next steps.</p><button className="banner-link" onClick={() => setView('applications')}>View application register <ArrowRight size={15} /></button></div><div className="banner-art" aria-hidden="true"><div className="art-ring ring-a"/><div className="art-ring ring-b"/><div className="art-center"><Activity size={36}/></div><div className="art-chip chip-a"><Check size={13}/></div><div className="art-chip chip-b"><Clock3 size={13}/></div><div className="art-chip chip-c"><FileCheck2 size={13}/></div></div></section>

            <div className="section-heading"><div><h2>Application overview</h2><p>Live figures from the records available to your account.</p></div><button className="text-button" onClick={() => setView('applications')}>View all <ArrowRight size={15}/></button></div>
            <section className="metrics-grid">
              <MetricCard icon={<BriefcaseBusiness size={19}/>} label="Visible applications" value={String(total)} note="Records in your current scope" tone="blue" trendIcon={<Activity size={14}/>} />
              <MetricCard icon={<Clock3 size={19}/>} label="Active cases" value={String(metrics.active)} note="Not completed or withdrawn" tone="amber" trendIcon={<ArrowUpRight size={14}/>} />
              <MetricCard icon={<ClipboardList size={19}/>} label="In review stages" value={String(metrics.awaiting)} note="Submitted or under scrutiny" tone="violet" trendIcon={<Activity size={14}/>} />
              <MetricCard icon={<FileCheck2 size={19}/>} label="Completed" value={String(metrics.completed)} note="Marked complete in the registry" tone="green" trendIcon={<Check size={14}/>} />
            </section>

            <div className="section-heading operations-metrics-heading"><div><h2>Operations at a glance</h2><p>Server-calculated totals across records visible to your role · As of {operationsMetrics ? formatDate(operationsMetrics.as_of) : 'loading'}</p></div></div>
            <section className="metrics-grid operations-metrics-grid">
              <MetricCard icon={<ClipboardList size={19}/>} label="Submissions awaiting review" value={operationsMetrics ? String(operationsMetrics.submissions_pending_review) : '—'} note="Submitted undertakings" tone="violet" trendIcon={<Activity size={14}/>} />
              <MetricCard icon={<AlertTriangle size={19}/>} label="Expired evidence" value={operationsMetrics ? String(operationsMetrics.expired_evidence) : '—'} note="Validity date has passed" tone="amber" trendIcon={<ArrowUpRight size={14}/>} />
              <MetricCard icon={<Clock3 size={19}/>} label="Evidence due in 7 days" value={operationsMetrics ? String(operationsMetrics.evidence_due_within_7_days) : '—'} note="Upcoming validity deadlines" tone="blue" trendIcon={<CalendarClock size={14}/>} />
              <MetricCard icon={<ShieldCheck size={19}/>} label="Open escalations" value={operationsMetrics ? String(operationsMetrics.open_escalations) : '—'} note="Require operational follow-up" tone="amber" trendIcon={<AlertTriangle size={14}/>} />
              <MetricCard icon={<Bell size={19}/>} label="Failed notifications" value={operationsMetrics ? String(operationsMetrics.failed_notifications) : '—'} note="Delivery recovery needed" tone="violet" trendIcon={<Activity size={14}/>} />
              <MetricCard icon={<FileCheck2 size={19}/>} label="EVC reports pending" value={operationsMetrics ? String(operationsMetrics.evc_reports_pending) : '—'} note="Completed visits without submitted reports" tone="green" trendIcon={<ClipboardList size={14}/>} />
            </section>

            <section className="pendency-analytics-grid">
              <div className="panel pendency-panel">
                <div className="panel-heading"><div><h2>Pendency aging</h2><p>{pendencyAnalytics ? `${pendencyAnalytics.total_pending} cases waiting · As of ${formatDate(pendencyAnalytics.as_of)}` : 'Loading scoped workload data…'}</p></div><Clock3 size={18} className="panel-heading-icon"/></div>
                <div className="pendency-buckets">
                  {[
                    { key: '0-2_days', label: '0–2 days', tone: 'bar-green' },
                    { key: '3-7_days', label: '3–7 days', tone: 'bar-blue' },
                    { key: '8-14_days', label: '8–14 days', tone: 'bar-violet' },
                    { key: '15+_days', label: '15+ days', tone: 'bar-amber' },
                  ].map(bucket => <div className="pendency-bucket" key={bucket.key}><span>{bucket.label}</span><strong>{pendencyAnalytics?.aging_buckets[bucket.key] ?? '—'}</strong><div className="bar-track"><div className={`bar-fill ${bucket.tone}`} style={{ width: `${pendencyAnalytics?.total_pending ? ((pendencyAnalytics.aging_buckets[bucket.key] || 0) / pendencyAnalytics.total_pending) * 100 : 0}%` }}/></div></div>)}
                </div>
                <div className="panel-heading pendency-subheading"><div><h3>Workload by status</h3><p>Average and oldest waiting time</p></div></div>
                {pendencyAnalytics?.by_status.length
                  ? <div className="pendency-status-list">{pendencyAnalytics.by_status.map(item => <div className="pendency-status-row" key={item.status}><span>{formatStatus(item.status)}</span><strong>{item.count}</strong><small>Avg {item.average_days}d · Oldest {item.oldest_days}d</small></div>)}</div>
                  : <div className="dashboard-empty"><Check size={18}/><span>{pendencyAnalytics ? 'No applications are currently waiting in review stages.' : 'Pendency analytics unavailable.'}</span></div>}
              </div>
              <div className="panel pendency-panel oldest-panel">
                <div className="panel-heading"><div><h2>Oldest pending cases</h2><p>Up to 10 cases, longest waiting first</p></div><button className="text-button" onClick={() => setView('applications')}>Open register <ArrowRight size={14}/></button></div>
                {pendencyAnalytics?.oldest_items.length
                  ? <div className="oldest-pendency-list">{pendencyAnalytics.oldest_items.map(item => <div className="oldest-pendency-row" key={item.application_id}><div className="case-icon"><FileText size={15}/></div><div className="oldest-pendency-copy"><strong>{item.title}</strong><span>{item.application_number} · {item.institution_name}</span><small>{formatStatus(item.status)} · Waiting since {formatDate(item.waiting_since)}</small></div><span className={`pendency-age ${item.days_waiting >= 15 ? 'pendency-age-high' : item.days_waiting >= 8 ? 'pendency-age-warn' : ''}`}>{item.days_waiting}d</span></div>)}</div>
                  : <div className="dashboard-empty"><Check size={18}/><span>{pendencyAnalytics ? 'No pending cases to display.' : 'Pendency analytics unavailable.'}</span></div>}
              </div>
            </section>

            <section className="content-grid"><div className="panel recent-panel"><div className="panel-heading"><div><h2>Recent applications</h2><p>Latest activity in your visible register</p></div><button className="subtle-icon-button" onClick={() => setView('applications')} aria-label="View all applications"><ArrowRight size={17}/></button></div><ApplicationTable applications={applications.slice(0, 5)} loading={loadingCases} onOpen={application => { setSelectedApplication(application); setView('detail') }} compact /></div><div className="panel status-panel"><div className="panel-heading"><div><h2>Workflow health</h2><p>Based on visible application statuses</p></div><Activity size={18} className="panel-heading-icon"/></div><div className="status-total"><strong>{total}</strong><span>total visible records</span></div><div className="status-bars">{[
              {label:'Draft', count:applications.filter(a=>a.status==='draft').length, color:'bar-slate'},
              {label:'Submitted', count:applications.filter(a=>a.status==='submitted').length, color:'bar-blue'},
              {label:'In scrutiny', count:applications.filter(a=>['scrutiny','re_scrutiny'].includes(a.status)).length, color:'bar-violet'},
              {label:'Completed', count:metrics.completed, color:'bar-green'},
            ].map(item=><div className="status-row" key={item.label}><div className="status-row-top"><span>{item.label}</span><strong>{item.count}</strong></div><div className="bar-track"><div className={`bar-fill ${item.color}`} style={{width: `${total ? Math.max(item.count / total * 100, item.count ? 4 : 0) : 0}%`}}/></div></div>)}</div><div className="status-foot"><span className="status-foot-dot"/> Counts update when the register refreshes.</div></div></section>
          </>}

          {view === 'overview' && <section className="dashboard-operations-grid">
               <div className="panel dashboard-ops-panel dashboard-work-panel">
                 <div className="panel-heading"><div><h2>My work</h2><p>{myWorkflowItems.length + myEvcReportItems.length} next step{myWorkflowItems.length + myEvcReportItems.length === 1 ? '' : 's'} for your {roleLabel.toLowerCase()} role</p></div><button className="text-button" onClick={() => setView('applications')}>Open register <ArrowRight size={14}/></button></div>
                 {myWorkflowItems.length === 0 && myEvcReportItems.length === 0
                   ? <div className="dashboard-empty"><Check size={18}/><span>No workflow actions are waiting in the currently loaded records.</span></div>
                   : <div className="dashboard-compact-list">
                     {myWorkflowItems.map(({application, action, detail, priority, label}) => <button className="dashboard-compact-row" key={application.id} onClick={() => { setSelectedApplication(application); setView('detail') }}><span className={'dashboard-work-mark ' + (priority === 1 ? 'priority-high' : '')}><ClipboardList size={15}/></span><span className="dashboard-compact-copy"><strong>{action}</strong><small>{application.application_number} · {application.title}</small><small>{detail}</small><span className={'dashboard-work-tag ' + (priority === 1 ? 'priority-high' : '')}>{label}</span></span><ArrowRight size={14}/></button>)}
                     {myEvcReportItems.map(visit => { const application = applications.find(item => item.id === visit.application_id); return <button className="dashboard-compact-row" key={visit.id} onClick={() => setView('evc')}><span className="dashboard-work-mark"><FileCheck2 size={15}/></span><span className="dashboard-compact-copy"><strong>Complete EVC report</strong><small>{application?.application_number || 'Application'} · {application?.title || 'Visit report'}</small><small>Visit completed; report is not submitted</small></span><ArrowRight size={14}/></button> })}
                   </div>}
                 <p className="dashboard-work-footnote">Actions shown are role and status based. The API validates permissions again when you submit a change.</p>
               </div>
               <div className="panel dashboard-ops-panel">
                 <div className="panel-heading"><div><h2>Evidence needing attention</h2><p>Expiry dates from records in your access scope</p></div><button className="text-button" onClick={() => setView('compliance')}>Open compliance <ArrowRight size={14}/></button></div>
                 {dashboardLoading && !compliance ? <div className="table-state"><span>Loading evidence alerts…</span></div> : !compliance ? <div className="dashboard-empty">Compliance data is currently unavailable.</div> : compliance.alerts.length === 0 ? <div className="dashboard-empty"><ShieldCheck size={18}/><span>No expired or near-expiry evidence in the current records.</span></div> : <div className="dashboard-compact-list">{compliance.alerts.slice(0, 4).map(alert => <button className="dashboard-compact-row" key={alert.evidence_id} onClick={() => void openAlertApplication(alert.application_id)}><span className={'dashboard-alert-mark ' + alert.severity}><AlertTriangle size={15}/></span><span className="dashboard-compact-copy"><strong>{alert.title}</strong><small>{alert.application_number} · {alert.days_remaining < 0 ? Math.abs(alert.days_remaining) + ' days overdue' : alert.days_remaining === 0 ? 'Expires today' : alert.days_remaining + ' days left'}</small></span><ArrowRight size={14}/></button>)}</div>}
               </div>
               <div className="panel dashboard-ops-panel">
                 <div className="panel-heading"><div><h2>Upcoming EVC visits</h2><p>Scheduled verification visits</p></div><button className="text-button" onClick={() => setView('evc')}>View schedule <ArrowRight size={14}/></button></div>
                 {dashboardLoading && evcVisits.length === 0 ? <div className="table-state"><span>Loading visit schedule…</span></div> : evcVisits.filter(visit => visit.status === 'scheduled' && new Date(visit.scheduled_for).getTime() >= Date.now()).sort((a, b) => new Date(a.scheduled_for).getTime() - new Date(b.scheduled_for).getTime()).length === 0 ? <div className="dashboard-empty"><CalendarClock size={18}/><span>No upcoming visits are scheduled.</span></div> : <div className="dashboard-compact-list">{evcVisits.filter(visit => visit.status === 'scheduled' && new Date(visit.scheduled_for).getTime() >= Date.now()).sort((a, b) => new Date(a.scheduled_for).getTime() - new Date(b.scheduled_for).getTime()).slice(0, 4).map(visit => { const application = applications.find(item => item.id === visit.application_id); return <button className="dashboard-compact-row" key={visit.id} onClick={() => setView('evc')}><span className="dashboard-visit-mark"><CalendarClock size={15}/></span><span className="dashboard-compact-copy"><strong>{application?.title || 'Application visit'}</strong><small>{new Intl.DateTimeFormat('en-IN', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }).format(new Date(visit.scheduled_for))} · {visit.mode}</small></span><ArrowRight size={14}/></button> })}</div>}
               </div>
               <div className="panel dashboard-ops-panel dashboard-activity-panel">
                 <div className="panel-heading"><div><h2>Recent workflow activity</h2><p>Latest events from your most recent visible applications</p></div><button className="text-button" onClick={() => setView('applications')}>Open register <ArrowRight size={14}/></button></div>
                 {dashboardLoading && dashboardRecentEvents.length === 0 ? <div className="table-state"><span>Loading recent activity…</span></div> : dashboardRecentEvents.length === 0 ? <div className="dashboard-empty"><Activity size={18}/><span>No workflow events are available yet.</span></div> : <div className="dashboard-timeline-list">{dashboardRecentEvents.map(({application,event}) => <button className="dashboard-timeline-row" key={event.id} onClick={() => { setSelectedApplication(application); setView('detail') }}><span className="dashboard-timeline-dot"/><span className="dashboard-compact-copy"><strong>{event.event_type.replaceAll('_',' ')}</strong><small>{application.application_number} · {application.title}</small></span><time>{new Intl.DateTimeFormat('en-IN', { day: '2-digit', month: 'short' }).format(new Date(event.occurred_at))}</time></button>)}</div>}
               </div>
          </section>}

          {view === 'inbox' && <section className="task-inbox-page">
            <div className="task-inbox-summary-grid">
              <article className="task-inbox-summary"><span>Open tasks</span><strong>{taskInbox?.total ?? '—'}</strong><small>Visible to your role</small></article>
              <article className="task-inbox-summary task-inbox-high"><span>High priority</span><strong>{taskInbox?.by_priority.high ?? '—'}</strong><small>Review first</small></article>
              <article className="task-inbox-summary task-inbox-medium"><span>Medium priority</span><strong>{taskInbox?.by_priority.medium ?? '—'}</strong><small>Follow up soon</small></article>
              <article className="task-inbox-summary task-inbox-low"><span>Low priority</span><strong>{taskInbox?.by_priority.low ?? '—'}</strong><small>Routine follow-up</small></article>
            </div>
            <section className="panel task-inbox-panel">
              <div className="panel-heading"><div><h2>Prioritized task list</h2><p>{taskInbox ? 'As of ' + formatDate(taskInbox.as_of) + ' · ' + taskInbox.items.length + ' items shown' : 'Tasks are loaded from server-side workflow records.'}</p></div><label className="task-filter-label" htmlFor="inbox-priority">Priority <select id="inbox-priority" value={inboxPriorityFilter} onChange={event => setInboxPriorityFilter(event.target.value)}><option value="all">All priorities</option><option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option></select></label></div>
              {loadingTaskInbox && !taskInbox ? <div className="table-state"><div className="loading-line"/><div className="loading-line"/><span>Loading task inbox…</span></div>
                : !taskInbox ? <div className="empty-state"><strong>Task inbox unavailable</strong><p>Refresh after checking the API connection.</p><button className="secondary-button" onClick={() => void loadTaskInbox()}>Try again</button></div>
                : taskInbox.items.filter(item => inboxPriorityFilter === 'all' || item.priority === inboxPriorityFilter).length === 0 ? <div className="empty-state"><div className="empty-icon"><Check size={22}/></div><strong>{inboxPriorityFilter === 'all' ? 'No open tasks' : 'No ' + inboxPriorityFilter + '-priority tasks'}</strong><p>New actions will appear here when workflow records need attention.</p></div>
                : <div className="task-inbox-list">{taskInbox.items.filter(item => inboxPriorityFilter === 'all' || item.priority === inboxPriorityFilter).map(item => <button className="task-inbox-row" key={item.task_id} onClick={() => void openInboxTask(item)}><span className={'task-priority-dot ' + item.priority} aria-label={item.priority + ' priority'}/><span className="task-inbox-copy"><strong>{item.title}</strong><span>{item.application_number} · {item.application_title}</span><small>{item.institution_name} · {item.description}</small><small>{formatStatus(item.status)} · Updated {formatDate(item.created_at)}{item.due_date ? ' · Due ' + formatDate(item.due_date) : ''}</small></span><span className={'task-priority-label ' + item.priority}>{item.priority}</span><ArrowRight size={16}/></button>)}</div>}
            </section>
            <p className="task-inbox-footnote">Tasks are derived from persisted records in your server-authorized scope. Opening a task takes you to its relevant workspace; every mutation is re-authorized by the API.</p>
          </section>}

          {view === 'reports' && <section className="reports-page">
            <div className="panel reports-intro"><div className="panel-heading"><div><h2>Operational reports</h2><p>CSV files are generated from persisted records each time you export and are restricted to applications visible to your account.</p></div></div>
              <div className="report-date-filters"><label>Created / scheduled from<input type="date" value={reportFromDate} onChange={event => setReportFromDate(event.target.value)} /></label><label>Through date<input type="date" value={reportToDate} onChange={event => setReportToDate(event.target.value)} /></label><button className="text-button" onClick={() => { setReportFromDate(''); setReportToDate('') }}>Clear dates</button></div>
              <p className="report-filter-note">Date filters apply to each report's relevant date field. Leave both blank to export all records in your access scope.</p>
            </div>
            <div className="reports-grid">
              {[
                { type: 'applications' as const, title: 'Application register', description: 'Application number, title, institution, workflow status and key timestamps.', icon: BriefcaseBusiness },
                { type: 'compliance' as const, title: 'Compliance submissions', description: 'Submission type, review status, version, review timestamps and notes.', icon: ShieldCheck },
                { type: 'evidence' as const, title: 'Evidence register', description: 'Evidence categories, versions, lifecycle status and expiry dates.', icon: FileCheck2 },
                { type: 'evc' as const, title: 'EVC visits and reports', description: 'Visit schedule, mode, status, report status and recorded outcomes.', icon: CalendarClock },
                { type: 'notifications' as const, title: 'Notification delivery', description: 'Delivery status, retry counts, timestamps and recorded error details.', icon: MailWarning },
              ].map(report => <article className="panel report-card" key={report.type}><div className="report-card-icon"><report.icon size={20}/></div><h3>{report.title}</h3><p>{report.description}</p><button className="secondary-button" onClick={() => void downloadReport(report.type)} disabled={reportDownloading !== null}>{reportDownloading === report.type ? 'Preparing CSV…' : 'Export CSV'}</button></article>)}
            </div>
            <p className="report-disclaimer">Exports reflect the current prototype data and are intended for operational analysis. They do not establish statutory compliance. Notification exports show persisted delivery state, not independent provider confirmation.</p>
          </section>}
          {view === 'notifications' && <section className="notification-operations-page">
            <div className="notification-ops-summary-grid">
              <article className="notification-ops-summary"><span>All visible records</span><strong>{notificationOperations?.total ?? '—'}</strong><small>Persisted notification records</small></article>
              <article className="notification-ops-summary"><span>Pending</span><strong>{notificationOperations?.by_status.pending ?? 0}</strong><small>Awaiting delivery attempt</small></article>
              <article className="notification-ops-summary notification-ops-danger"><span>Failed</span><strong>{notificationOperations?.failed ?? '—'}</strong><small>Delivery recovery needed</small></article>
              <article className="notification-ops-summary notification-ops-ready"><span>Retry eligible</span><strong>{notificationOperations?.retry_ready ?? '—'}</strong><small>Under the manual retry safety limit</small></article>
              <article className="notification-ops-summary"><span>Sent</span><strong>{notificationOperations?.by_status.sent ?? 0}</strong><small>Provider confirmed by delivery adapter</small></article>
              <article className="notification-ops-summary"><span>Retry limit reached</span><strong>{notificationOperations?.exhausted ?? '—'}</strong><small>Requires investigation</small></article>
            </div>
            <section className="panel notification-ops-panel">
              <div className="panel-heading"><div><h2>Delivery queue</h2><p>{notificationOperations ? 'Updated ' + formatDate(notificationOperations.as_of) + ' · up to 100 most recent records in your application scope' : 'Delivery states are loaded from persisted notification records.'}</p></div><div className="notification-ops-actions"><label className="task-filter-label" htmlFor="notification-status">Status <select id="notification-status" value={notificationStatusFilter} onChange={event => setNotificationStatusFilter(event.target.value)}><option value="all">All statuses</option><option value="pending">Pending</option><option value="failed">Failed</option><option value="sent">Sent</option></select></label><button className="secondary-button" onClick={() => void handleQueueOperationalNotifications()} disabled={queueingNotifications}>{queueingNotifications ? 'Queueing…' : 'Queue expiry alerts'}</button></div></div>
              {loadingNotificationOperations && !notificationOperations ? <div className="table-state"><div className="loading-line"/><span>Loading delivery records…</span></div>
                : !notificationOperations ? <div className="empty-state"><strong>Delivery console unavailable</strong><p>Refresh to retry loading operational notification data.</p></div>
                : notificationOperations.items.filter(item => notificationStatusFilter === 'all' || item.delivery_status === notificationStatusFilter).length === 0 ? <div className="empty-state"><div className="empty-icon"><Check size={22}/></div><strong>No matching notifications</strong><p>There are no records in the selected delivery state.</p></div>
                : <div className="notification-ops-list">{notificationOperations.items.filter(item => notificationStatusFilter === 'all' || item.delivery_status === notificationStatusFilter).map(item => <article className="notification-ops-row" key={item.id}><span className={'notification-ops-state ' + item.delivery_status}/><div className="notification-ops-copy"><div className="notification-ops-title"><strong>{item.title}</strong><span className={'notification-ops-status ' + item.delivery_status}>{formatStatus(item.delivery_status)}</span></div><p>{item.application_number} · {item.application_title}</p><small>Recipient: {item.recipient_name} ({formatStatus(item.recipient_role)}) · {formatStatus(item.notification_type)} · {formatDate(item.created_at)}</small><small>Attempts: {item.attempt_count}/{item.max_attempts}{item.next_attempt_at ? ' · Next attempt ' + formatDate(item.next_attempt_at) : ''}{item.sent_at ? ' · Sent ' + formatDate(item.sent_at) : ''}</small>{item.last_error && <p className="notification-ops-error">{item.last_error}</p>}</div>{item.delivery_status === 'failed' && <button className="secondary-button small-button" disabled={retryingOperationalNotificationId === item.id || item.attempt_count >= 10} onClick={() => void handleRetryOperationalNotification(item)}>{retryingOperationalNotificationId === item.id ? 'Queueing…' : item.attempt_count >= 10 ? 'Retry limit reached' : 'Retry delivery'}</button>}</article>)}</div>}
            </section>
            <p className="notification-ops-footnote">This console displays the latest 100 visible records; summary totals cover the full visible scope. Retry changes a failed record back to pending, preserves attempt history, and writes an audit event. SMTP delivery is not claimed until a configured worker/provider reports success.</p>
          </section>}

          {view === 'applications' && <section className="panel applications-panel"><div className="panel-heading list-panel-heading"><div><h2>Application register</h2><p>{total} record{total===1?'':'s'} visible within your access scope</p></div><div className="register-actions"><button className="secondary-button small-button" onClick={() => void loadApplications()} disabled={loadingCases}><Activity size={15} className={loadingCases?'spin':''}/> Refresh</button>{user.role==='institution_user'&&<button className="primary-button small-button" onClick={() => setCreateOpen(true)}><Plus size={16}/> New application</button>}</div></div><div className="filter-row"><div className="search-field"><Search size={17}/><input value={query} onChange={e=>setQuery(e.target.value)} onKeyDown={e=>{if(e.key==='Enter')void loadApplications()}} placeholder="Search by title or application ID" aria-label="Search applications"/><kbd>Enter</kbd></div><div className="filter-select-wrap"><Filter size={16}/><select value={statusFilter} onChange={e=>setStatusFilter(e.target.value)} aria-label="Filter by status"><option value="">All statuses</option>{Object.entries(statusLabels).map(([key,label])=><option key={key} value={key}>{label}</option>)}</select><ChevronDown size={14}/></div><button className="secondary-button filter-apply" onClick={()=>void loadApplications()}><SlidersHorizontal size={15}/> Apply filters</button></div><ApplicationTable applications={applications} loading={loadingCases} onOpen={application => { setSelectedApplication(application); setView('detail') }} /><div className="table-footer"><span>Showing <strong>{applications.length}</strong> of <strong>{total}</strong> matching records</span><span className="footer-scope"><ShieldCheck size={14}/> Access-scoped results</span></div></section>}


          {view === 'detail' && selectedApplication && <section className="panel case-detail-panel">
            <div className="panel-heading"><div><div className="eyebrow">APPLICATION {selectedApplication.application_number}</div><h2>{selectedApplication.title}</h2><p>{selectedApplication.summary || 'No summary provided.'}</p></div><button className="secondary-button small-button" onClick={() => setView('applications')}><ArrowRight size={15}/> Back to register</button></div>
            <div className="case-detail-facts"><div><span>Current status</span><strong>{statusLabels[selectedApplication.status] || selectedApplication.status.replaceAll('_', ' ')}</strong></div><div><span>Created</span><strong>{formatDate(selectedApplication.created_at)}</strong></div><div><span>Last updated</span><strong>{formatDate(selectedApplication.updated_at)}</strong></div><div><span>Submitted</span><strong>{selectedApplication.submitted_at ? formatDate(selectedApplication.submitted_at) : 'Not submitted'}</strong></div><div><span>Institution reference</span><strong>{selectedApplication.institution_id.slice(0, 8).toUpperCase()}</strong></div></div>
            <section className="policy-dossier" aria-labelledby="policy-dossier-heading">
              <div className="policy-dossier-heading">
                <div><div className="eyebrow">TRACEABILITY & EVIDENCE</div><h2 id="policy-dossier-heading">Policy-to-Proof dossier</h2><p>Connect policy versions, evidence, review activity and the audit chain.</p></div>
                <div className="policy-dossier-actions">
                  <button type="button" className="secondary-button small-button" disabled={!policyDossier || loadingPolicyDossier} onClick={() => {
                    if (!policyDossier) return
                    const blob = new Blob([JSON.stringify(policyDossier, null, 2)], { type: 'application/json;charset=utf-8' })
                    const url = URL.createObjectURL(blob)
                    const link = document.createElement('a')
                    link.href = url
                    link.download = `pravaah-policy-to-proof-${policyDossier.application.application_number.replace(/[^a-zA-Z0-9_-]/g, '-')}.json`
                    document.body.appendChild(link)
                    link.click()
                    link.remove()
                    URL.revokeObjectURL(url)
                  }}>Export JSON</button>
                  <button type="button" className="secondary-button small-button" disabled={!policyDossier || loadingPolicyDossier} onClick={() => {
                    if (!policyDossier) return
                    const columns = ['application_number', 'dossier_as_of', 'audit_chain_valid', 'first_invalid_sequence', 'sequence', 'occurred_at', 'event_type', 'from_status', 'to_status', 'actor_user_id', 'reason', 'previous_hash', 'event_hash']
                    const escapeCsv = (value: unknown) => {
                      const text = value == null ? '' : String(value)
                      return `"${text.replace(/"/g, '""')}"`
                    }
                    const rows = policyDossier.audit.events.map(event => [
                      policyDossier.application.application_number,
                      policyDossier.as_of,
                      policyDossier.audit.valid,
                      policyDossier.audit.first_invalid_sequence,
                      event.sequence,
                      event.occurred_at,
                      event.event_type,
                      event.from_status,
                      event.to_status,
                      event.actor_user_id,
                      event.reason,
                      event.previous_hash,
                      event.event_hash,
                    ])
                    const csv = [columns, ...rows].map(row => row.map(escapeCsv).join(',')).join('\r\n')
                    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' })
                    const url = URL.createObjectURL(blob)
                    const link = document.createElement('a')
                    link.href = url
                    link.download = `pravaah-audit-${policyDossier.application.application_number.replace(/[^a-zA-Z0-9_-]/g, '-')}.csv`
                    document.body.appendChild(link)
                    link.click()
                    link.remove()
                    URL.revokeObjectURL(url)
                  }}>Export audit CSV</button>
                  <button type="button" className="secondary-button small-button" disabled={loadingPolicyDossier} onClick={() => {
                    setLoadingPolicyDossier(true)
                    setPolicyDossierError('')
                    void api.policyToProof(selectedApplication.id).then(setPolicyDossier).catch(error => setPolicyDossierError(error instanceof Error ? error.message : 'Could not refresh the dossier.')).finally(() => setLoadingPolicyDossier(false))
                  }}>{loadingPolicyDossier ? 'Loading…' : 'Refresh dossier'}</button>
                </div>            </div>
              {loadingPolicyDossier && !policyDossier ? <div className="table-state"><div className="loading-line"/><span>Assembling traceability records…</span></div>
                : policyDossierError ? <div className="policy-dossier-error" role="alert"><strong>Dossier unavailable</strong><p>{policyDossierError}</p><button type="button" className="secondary-button small-button" onClick={() => {
                  setLoadingPolicyDossier(true)
                  setPolicyDossierError('')
                  void api.policyToProof(selectedApplication.id).then(setPolicyDossier).catch(error => setPolicyDossierError(error instanceof Error ? error.message : 'Could not load the dossier.')).finally(() => setLoadingPolicyDossier(false))
                }}>Try again</button></div>
                : policyDossier ? <>
                  <div className="policy-dossier-summary">
                    <div className={'policy-dossier-audit ' + (policyDossier.audit.valid ? 'valid' : 'invalid')}><ShieldCheck size={18}/><div><strong>{policyDossier.audit.valid ? 'Audit chain verified' : 'Audit chain check failed'}</strong><span>{policyDossier.audit.event_count} event(s) checked</span></div></div>
                    <div className="policy-dossier-count"><span>Policies</span><strong>{policyDossier.counts.policy_versions}</strong></div>
                    <div className="policy-dossier-count"><span>Evidence</span><strong>{policyDossier.counts.evidence}</strong></div>
                    <div className="policy-dossier-count"><span>Attachments</span><strong>{policyDossier.counts.attachments}</strong></div>
                    <div className="policy-dossier-count"><span>Undertakings</span><strong>{policyDossier.counts.compliance_submissions}</strong></div>
                    <div className="policy-dossier-count"><span>EVC visits</span><strong>{policyDossier.counts.evc_visits}</strong></div>
                    <div className="policy-dossier-count"><span>Notifications</span><strong>{policyDossier.counts.notifications}</strong></div>
                    <div className="policy-dossier-count"><span>Escalations</span><strong>{policyDossier.counts.escalations}</strong></div>
                  </div>
                  <div className="policy-dossier-sections">
                    <details><summary>Policy-to-evidence links <span>{policyDossier.policy_evidence_links.filter(item => item.matched).length}/{policyDossier.policy_evidence_links.length} matched</span></summary>
                      {policyDossier.policy_evidence_links.length ? policyDossier.policy_evidence_links.map(item => <article className="policy-dossier-record" key={item.evidence_id}><strong>{item.evidence_title}</strong><span>{item.policy_key || 'No policy key recorded'} · {item.matched ? 'Policy version linked' : 'Unresolved policy reference'}</span>{item.policy_versions.length ? item.policy_versions.map(policy => <small key={policy.id}>{policy.title} · v{policy.version} · {policy.source_label}{policy.is_active ? ' · Active' : ' · Inactive'}</small>) : <p>No policy version matches this evidence record's policy key. Review and resolve the reference before relying on it.</p>}</article>) : <p className="policy-dossier-empty">No evidence records are available to map to policy versions.</p>}
                    </details>
                    <details open><summary>Policy provenance <span>{policyDossier.policy_versions.length}</span></summary>
                      {policyDossier.policy_versions.length ? policyDossier.policy_versions.map(item => <article className="policy-dossier-record" key={item.id}><strong>{item.title} · v{item.version}</strong><span>{item.policy_key} · {item.source_label}</span><p>{item.description}</p><small>Effective {formatDate(item.effective_from)} · {item.is_active ? 'Active' : 'Inactive'}</small></article>) : <p className="policy-dossier-empty">No policy version is linked through evidence or event metadata.</p>}
                    </details>
                    <details><summary>Evidence & file integrity <span>{policyDossier.evidence.length}</span></summary>
                      {policyDossier.evidence.length ? policyDossier.evidence.map(item => <article className="policy-dossier-record" key={item.id}><strong>{item.title} · v{item.version}</strong><span>{item.category.replaceAll('_', ' ')} · {item.lifecycle_status}{item.policy_key ? ' · ' + item.policy_key : ''}</span><small>{item.expires_on ? 'Expires ' + formatDate(item.expires_on) : 'No expiry date'}{item.reference_number ? ' · Ref ' + item.reference_number : ''}</small><p>{policyDossier.attachments.filter(file => file.evidence_id === item.id).map(file => file.filename + ' · SHA-256 ' + file.sha256.slice(0, 16) + '…').join(' | ') || 'No attached files recorded'}</p></article>) : <p className="policy-dossier-empty">No evidence records are linked to this application.</p>}
                    </details>
                    <details><summary>Compliance submissions <span>{policyDossier.compliance_submissions.length}</span></summary>
                      {policyDossier.compliance_submissions.length ? policyDossier.compliance_submissions.map(item => <article className="policy-dossier-record" key={item.id}><strong>{item.title} · v{item.version}</strong><span>{item.submission_type.replaceAll('_', ' ')} · {formatStatus(item.status)} · {item.evidence_ids.length} evidence item(s)</span><small>{item.submitted_at ? 'Submitted ' + formatDate(item.submitted_at) : 'Not submitted'}{item.reviewed_at ? ' · Reviewed ' + formatDate(item.reviewed_at) : ''}</small>{item.review_notes && <p>Reviewer note: {item.review_notes}</p>}</article>) : <p className="policy-dossier-empty">No compliance submissions are recorded.</p>}
                    </details>
                    <details><summary>EVC visits & reports <span>{policyDossier.evc_visits.length}</span></summary>
                      {policyDossier.evc_visits.length ? policyDossier.evc_visits.map(item => <article className="policy-dossier-record" key={item.id}><strong>{formatDate(item.scheduled_for)} · {formatStatus(item.status)}</strong><span>{formatStatus(item.mode)} · report {formatStatus(item.report_status)} · {item.linked_evidence_ids.length} evidence item(s)</span>{item.outcome_summary && <p>{item.outcome_summary}</p>}{item.observations && <p>{item.observations}</p>}</article>) : <p className="policy-dossier-empty">No EVC visits are recorded.</p>}
                    </details>
                    <details><summary>Notifications & escalations <span>{policyDossier.notifications.length + policyDossier.escalations.length}</span></summary>
                      {policyDossier.notifications.map(item => <article className="policy-dossier-record" key={item.id}><strong>{item.title}</strong><span>Notification · {formatStatus(item.delivery_status)} · {item.attempt_count}/{item.max_attempts} attempts</span><small>{formatDate(item.created_at)}{item.sent_at ? ' · Sent ' + formatDate(item.sent_at) : ''}</small>{item.last_error && <p>{item.last_error}</p>}</article>)}
                      {policyDossier.escalations.map(item => <article className="policy-dossier-record" key={item.id}><strong>{item.summary}</strong><span>Escalation · {formatStatus(item.severity)} · {formatStatus(item.status)}</span><small>Raised {formatDate(item.triggered_at)}{item.resolved_at ? ' · Resolved ' + formatDate(item.resolved_at) : ''}</small></article>)}
                      {!policyDossier.notifications.length && !policyDossier.escalations.length && <p className="policy-dossier-empty">No notification or escalation records are linked.</p>}
                    </details>
                    <details><summary>Audit event history <span>{policyDossier.audit.events.length}</span></summary>
                      {policyDossier.audit.events.length ? policyDossier.audit.events.map(item => <article className="policy-dossier-record" key={item.id}><strong>#{item.sequence} · {item.event_type.replaceAll('_', ' ')}</strong><span>{item.from_status ? formatStatus(item.from_status) + ' → ' + formatStatus(item.to_status || '') : 'Initial or non-status event'}{item.reason ? ' · ' + item.reason : ''}</span><small>{new Intl.DateTimeFormat('en-IN', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(item.occurred_at))}</small><code>{item.event_hash}</code></article>) : <p className="policy-dossier-empty">No audit events are recorded.</p>}
                    </details>
                  </div>
                  <p className="policy-dossier-disclaimer">{policyDossier.disclaimer}</p>
                </> : <p className="policy-dossier-empty">The traceability dossier has not been loaded.</p>}
            </section>
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
            <div className="panel compliance-alerts" style={{ marginBottom: 24 }}>
              <div className="panel-heading"><div><h2>Compliance undertakings</h2><p>Versioned submissions, reviewer decisions, and correction history</p></div><span className="evidence-count">{submissions.length} versions</span></div>
              {loadingSubmissions ? <div className="table-state"><span>Loading submissions…</span></div> : submissions.length === 0 ? <div className="empty-state"><strong>No compliance undertakings submitted</strong><p>Choose supporting evidence below to create the first submission.</p></div> : <div className="compliance-alert-list">{submissions.map(item => <article className="compliance-alert-row" key={item.id}><div className="compliance-alert-main"><div className="compliance-alert-title"><strong>{item.title} · v{item.version}</strong><span className={'evidence-expiry ' + (item.status === 'accepted' ? 'valid' : item.status === 'rejected' ? 'expired' : item.status === 'changes_requested' ? 'expiring' : 'valid')}>{item.status.replaceAll('_', ' ')}</span></div><p>{item.submission_type.replaceAll('_', ' ')} · {item.evidence_ids.length} linked evidence item(s) · {item.submitted_at ? formatDate(item.submitted_at) : 'Not submitted'}</p><p>{item.declaration}</p>{item.review_notes && <span className="evidence-date">Reviewer note: {item.review_notes}</span>}{item.supersedes_submission_id && <span className="evidence-date">Corrects version {submissions.find(previous => previous.id === item.supersedes_submission_id)?.version ?? 'prior'}</span>}</div>{item.status === 'submitted' && ['scrutiny_officer', 'regional_officer', 'bureau_officer', 'competent_authority', 'policy_admin', 'system_admin'].includes(user.role) && <div className="detail-action-buttons"><button className="primary-button small-button" disabled={submissionBusy} onClick={() => void handleReviewUndertaking(item, 'accepted')}>Accept</button><button className="secondary-button small-button" disabled={submissionBusy || reviewNotes.trim().length < 3} onClick={() => void handleReviewUndertaking(item, 'changes_requested')}>Request changes</button><button className="secondary-button small-button" disabled={submissionBusy || reviewNotes.trim().length < 3} onClick={() => void handleReviewUndertaking(item, 'rejected')}>Reject</button></div>}{item.status === 'changes_requested' && user.role === 'institution_user' && <button className="primary-button small-button" onClick={() => handleStartCorrection(item)}>Correct and resubmit</button>}</article>)}</div>}
              {['institution_user', 'scrutiny_officer', 'regional_officer', 'bureau_officer', 'evc_coordinator', 'competent_authority', 'policy_admin', 'system_admin'].includes(user.role) && <form className="evidence-form" onSubmit={handleSubmitUndertaking}>
                <div className="evc-form-heading"><div><h3>{correctionForId ? 'Correct undertaking' : 'New undertaking'}</h3><p>Attach relevant items to support the declaration. Reviewer decisions remain human-controlled.</p></div>{correctionForId && <button type="button" className="text-button" onClick={() => setCorrectionForId(null)}>Cancel correction</button>}</div>
                <div className="evidence-form-grid"><label>Submission type<input value={undertakingType} onChange={event => setUndertakingType(event.target.value)} minLength={2} maxLength={80} required disabled={Boolean(correctionForId)}/></label><label>Title<input value={undertakingTitle} onChange={event => setUndertakingTitle(event.target.value)} minLength={3} maxLength={240} required/></label></div>
                <label>Declaration<textarea value={undertakingDeclaration} onChange={event => setUndertakingDeclaration(event.target.value)} minLength={20} maxLength={10000} rows={3} required placeholder="Confirm the information provided is accurate and complete."/></label>
                <div className="evc-report-evidence"><div className="evc-report-evidence-heading"><div><strong>Supporting evidence</strong><span>Choose supporting records from this application.</span></div><span className="evc-evidence-count">{undertakingEvidenceIds.length} selected</span></div>{evidenceItems.length === 0 ? <p className="evc-evidence-empty">Register evidence below before submitting an undertaking.</p> : <div className="evc-evidence-options">{evidenceItems.map(item => <label className="evc-evidence-option" key={item.id}><input type="checkbox" checked={undertakingEvidenceIds.includes(item.id)} onChange={event => setUndertakingEvidenceIds(ids => event.target.checked ? [...ids, item.id] : ids.filter(id => id !== item.id))}/><span className="evc-evidence-option-main"><strong>{item.title}</strong><small>{item.category.replaceAll('_', ' ')}</small></span><span className="evc-evidence-date">{item.expires_on ? 'Expires ' + formatDate(item.expires_on) : 'No expiry date'}</span></label>)}</div>}</div>
                {['scrutiny_officer', 'regional_officer', 'bureau_officer', 'competent_authority', 'policy_admin', 'system_admin'].includes(user.role) && <label>Review notes<textarea value={reviewNotes} onChange={event => setReviewNotes(event.target.value)} rows={2} maxLength={3000} placeholder="Required when requesting changes or rejecting"/></label>}
                <button className="primary-button" disabled={submissionBusy || !undertakingEvidenceIds.length || undertakingTitle.trim().length < 3 || undertakingDeclaration.trim().length < 20 || (correctionForId !== null && user.role !== 'institution_user')}>{submissionBusy ? 'Saving…' : correctionForId ? 'Submit corrected version' : 'Submit undertaking'}</button>
              </form>}
            </div>
            <div className="evidence-section">
              <div className="panel-heading"><div><h2>Evidence workspace</h2><p>Manage evidence metadata and private attachments, review expiry dates, and see EVC reports that reference each record.</p></div><span className="evidence-count">{evidenceItems.length} items</span></div>
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
                <div className="evidence-form-actions"><span>{renewalEvidenceId ? 'A renewal requires a new expiry date and preserves the prior version.' : 'New evidence is recorded as version 1.'}</span><div>{renewalEvidenceId && <button type="button" className="secondary-button" onClick={() => { setRenewalEvidenceId(null); setEvidenceTitle(''); setEvidenceReference(''); setEvidenceIssued(''); setEvidenceExpires(''); setEvidencePolicy(''); setEvidenceNotes('') }}>Cancel renewal</button>}<button className="primary-button" disabled={savingEvidence || evidenceTitle.trim().length < 2 || (Boolean(renewalEvidenceId) && !evidenceExpires)}>{savingEvidence ? 'Saving…' : renewalEvidenceId ? 'Create renewal version' : 'Register evidence'}</button></div></div>
              </form>
              <div className="evidence-list">
                {loadingEvidence ? <div className="table-state"><div className="loading-line"/><span>Loading evidence register…</span></div> : evidenceItems.length === 0 ? <div className="empty-state"><div className="empty-icon"><FileCheck2 size={20}/></div><strong>No evidence registered yet</strong><p>Add evidence metadata above to start the compliance register.</p></div> : evidenceItems.map(item => {
                  const today = new Date().toISOString().slice(0, 10)
                  const days = item.expires_on ? Math.ceil((new Date(item.expires_on + 'T00:00:00Z').getTime() - new Date(today + 'T00:00:00Z').getTime()) / 86400000) : null
                  const expiryState = days === null ? 'No expiry date' : days < 0 ? 'Expired' : days <= 30 ? 'Expires soon' : 'Valid'
                  return <article className="evidence-item" key={item.id}>
                    <div className="evidence-file-icon"><FileCheck2 size={18}/></div><div className="evidence-item-main"><div className="evidence-item-heading"><strong>{item.title}</strong><span className={'evidence-expiry ' + (days !== null && days < 0 ? 'expired' : days !== null && days <= 30 ? 'expiring' : 'valid')}>{expiryState}</span></div><p>{item.category.replaceAll('_', ' ')}{item.reference_number ? ' · Ref ' + item.reference_number : ''}{item.policy_key ? ' · Policy ' + item.policy_key : ''}</p>{item.notes && <p className="evidence-notes">{item.notes}</p>}<span className="evidence-date">{item.expires_on ? 'Expires ' + formatDate(item.expires_on) : 'Expiry not recorded'}{item.issued_on ? ' · Issued ' + formatDate(item.issued_on) : ''}</span>
                    <div className="evidence-renewal-row">{item.lifecycle_status === 'current' ? <button type="button" className="text-button" onClick={() => { setRenewalEvidenceId(item.id); setEvidenceTitle(item.title); setEvidenceCategory(item.category); setEvidenceReference(''); setEvidenceIssued(''); setEvidenceExpires(''); setEvidencePolicy(item.policy_key || ''); setEvidenceNotes('Renewal of evidence version ' + item.version + ' (' + item.id.slice(0, 8) + ').'); setNotice('Renewal draft prepared. Submit the new expiry date to create a linked version.') }}>Start renewal record <ArrowRight size={13}/></button> : <span>This version has been superseded.</span>}<span>Version {item.version} · {item.lifecycle_status === 'replaced' ? 'Superseded' : 'Current version'}</span>{item.supersedes_evidence_id && <span>Supersedes record {item.supersedes_evidence_id.slice(0, 8).toUpperCase()}</span>}</div>
                    {evidenceVisitReferences.some(visit => (visit.linked_evidence_ids || []).includes(item.id)) && <div className="evidence-report-references"><strong>Referenced by EVC reports</strong>{evidenceVisitReferences.filter(visit => (visit.linked_evidence_ids || []).includes(item.id)).map(visit => <span key={visit.id}>Visit {visit.id.slice(0, 8).toUpperCase()} · {visit.report_status.replaceAll('_', ' ')} · {visit.report_submitted_at ? 'Submitted ' + formatDate(visit.report_submitted_at) : 'Not submitted'}</span>)}</div>}
                    <div className="evidence-attachments">
                      <div className="evidence-attachments-heading"><strong><FileText size={13}/> Attached files</strong><span>{(attachmentsByEvidence[item.id] || []).length} file(s)</span></div>
                      {(attachmentsByEvidence[item.id] || []).length === 0 ? <p className="evidence-attachments-empty">No files attached. PDF, PNG and JPEG files up to the configured limit are supported.</p> : <div className="evidence-attachment-list">{(attachmentsByEvidence[item.id] || []).map(attachment => <div className="evidence-attachment-row" key={attachment.id}><div><strong>{attachment.original_filename}</strong><span>{(attachment.size_bytes / 1024).toFixed(1)} KB · SHA-256 {attachment.sha256_hex.slice(0, 12)}…</span></div><div className="evidence-attachment-actions">{/\.(png|jpe?g|webp|gif)$/i.test(attachment.original_filename) && <button type="button" className="text-button" disabled={downloadingAttachmentId === attachment.id} onClick={() => void handlePreviewEvidenceImage(item.id, attachment)}>{downloadingAttachmentId === attachment.id ? 'Opening…' : 'Preview'}</button>}<button type="button" className="text-button" disabled={downloadingAttachmentId === attachment.id} onClick={() => void handleDownloadEvidenceFile(item.id, attachment)}>{downloadingAttachmentId === attachment.id ? 'Preparing…' : 'Download'}</button></div></div>)}</div>}
                      {['institution_user', 'scrutiny_officer', 'regional_officer', 'bureau_officer', 'evc_coordinator', 'competent_authority', 'policy_admin', 'system_admin'].includes(user.role) && <label className="evidence-upload-control"><span>{uploadingEvidenceId === item.id ? 'Uploading and validating…' : 'Upload supporting file'}</span><input type="file" accept=".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg" disabled={uploadingEvidenceId === item.id} onChange={event => { const file = event.currentTarget.files?.[0]; void handleUploadEvidenceFile(item.id, file); event.currentTarget.value = '' }}/></label>}
                    </div></div>
                  </article>
                })}
              </div>
            </div>
            <div className="audit-summary"><ShieldCheck size={19}/><div><strong>{loadingTimeline ? 'Verifying audit history…' : eventVerification?.valid ? 'Audit chain verified' : eventVerification ? 'Audit chain check failed' : 'Audit verification unavailable'}</strong><p>{eventVerification ? eventVerification.event_count + ' events checked. ' + (eventVerification.valid ? 'No tampering detected in the stored chain.' : 'First invalid sequence: ' + eventVerification.first_invalid_sequence + '.') : 'The event chain is tamper-evident and is not an external trust anchor.'}</p></div></div>
            <div className="detail-timeline"><div className="panel-heading"><div><h2>Application timeline</h2><p>Chronological record of application events</p></div><span>{caseEvents.length} events</span></div>
              {loadingTimeline ? <div className="table-state"><div className="loading-line"/><span>Loading events…</span></div> : caseEvents.length === 0 ? <div className="empty-state"><strong>No timeline events</strong><p>Events appear here as the application progresses.</p></div> : <div className="event-list">{caseEvents.map(event => <div className="event-row" key={event.id}><div className="event-dot"/><div><strong>{event.event_type.replaceAll('_', ' ')}</strong><p>{event.from_status ? (statusLabels[event.from_status] || event.from_status.replaceAll('_', ' ')) + ' → ' + (statusLabels[event.to_status || ''] || (event.to_status || '').replaceAll('_', ' ')) : 'Initial record created'}{event.reason ? ' · ' + event.reason : ''}</p><span>{new Intl.DateTimeFormat('en-IN', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(event.occurred_at))}</span><details><summary>Event hash</summary><code>{event.event_hash}</code></details></div></div>)}</div>}
            </div>
          </section>}


          {view === 'evc' && <section className="evc-page">
            <div className="evc-intro">
              <div className="evc-intro-icon"><CalendarClock size={22}/></div>
              <div><div className="eyebrow">FIELD VERIFICATION OPERATIONS</div><h2>EVC visit schedule</h2><p>Plan visits, track outcomes and retain a traceable record against each application.</p></div>
              {canScheduleEvc && <button className="primary-button small-button" onClick={() => setShowEvcForm(value => !value)}><Plus size={15}/>{showEvcForm ? 'Close form' : 'Schedule visit'}</button>}
            </div>
            <div className="evc-notice"><ShieldCheck size={17}/><span>Visit scheduling is a coordination record only. Final approval or rejection remains a separate human decision in the application workflow.</span></div>
            {showEvcForm && canScheduleEvc && <form className="evc-form" onSubmit={handleScheduleEvcVisit}>
              <div className="evc-form-heading"><div><h3>Schedule a verification visit</h3><p>Select an application in an active review stage and add the visit details.</p></div><span className="evidence-count">New visit</span></div>
              <div className="evc-form-grid">
                <label>Application
                  <select value={evcApplicationId} onChange={event => void handleSelectEvcApplication(event.target.value)} required>
                    <option value="">Choose an application…</option>
                    {applications.filter(item => ['submitted', 'under_scrutiny', 'recommended_for_approval', 'pending_authority_decision', 'evc_pending', 'evc_scheduled'].includes(item.status)).map(item => <option key={item.id} value={item.id}>{item.application_number} · {item.title}</option>)}
                  </select>
                </label>
                <label>Visit date and time<input type="datetime-local" value={evcScheduledFor} min={new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 16)} onChange={event => setEvcScheduledFor(event.target.value)} required /></label>
                <label>Visit mode<select value={evcMode} onChange={event => setEvcMode(event.target.value as 'onsite' | 'virtual')}><option value="onsite">Onsite</option><option value="virtual">Virtual</option></select></label>
                {evcMode === 'onsite' && <label>Visit location<input value={evcLocation} onChange={event => setEvcLocation(event.target.value)} placeholder="Campus address or meeting location" maxLength={240} required /></label>}
                <label className="evc-notes-field">Coordinator notes<textarea value={evcNotes} onChange={event => setEvcNotes(event.target.value)} rows={2} maxLength={2000} placeholder="Optional agenda, preparation notes or joining details"/></label>
              </div>
              {evcApplicationId && <div className="evc-eligibility-note" role="status">{loadingEvcEligibility ? 'Checking scheduling eligibility…' : evcEligibility ? evcEligibility.eligible ? 'Eligible for scheduling. One active visit per application is allowed.' : evcEligibility.reasons.join(' ') : 'Eligibility could not be confirmed yet.'}</div>}
              <div className="evc-form-actions"><span>Saved visits are appended to the application audit timeline.</span><button className="primary-button" disabled={savingEvcVisit || loadingEvcEligibility || !evcEligibility?.eligible || !evcApplicationId || !evcScheduledFor || (evcMode === 'onsite' && !evcLocation.trim())}>{savingEvcVisit ? 'Scheduling…' : 'Confirm visit'}</button></div>
            </form>}
            <div className="panel evc-schedule-panel">
              <div className="panel-heading"><div><h2>Visit register</h2><p>Visits in your current application access scope</p></div><div className="evc-register-actions"><span className="evidence-count">{evcVisits.length} visits</span><select value={evcStatusFilter} onChange={event => setEvcStatusFilter(event.target.value)} aria-label="Filter EVC visits by status"><option value="scheduled">Scheduled</option><option value="completed">Completed</option><option value="cancelled">Cancelled</option><option value="">All statuses</option></select></div></div>
              {loadingEvcVisits && evcVisits.length === 0 ? <div className="table-state"><div className="loading-line"/><span>Loading EVC schedule…</span></div> : evcVisits.length === 0 ? <div className="empty-state"><div className="empty-icon"><CalendarClock size={22}/></div><strong>No visits in this view</strong><p>{evcStatusFilter ? 'No ' + evcStatusFilter + ' visits were found. Try another status or schedule a visit.' : 'Scheduled visits will appear here when a coordinator creates them.'}</p>{canScheduleEvc && <button className="secondary-button" onClick={() => setShowEvcForm(true)}>Schedule first visit <ArrowRight size={15}/></button>}</div> : <div className="evc-visit-list">{evcVisits.map(visit => {
                const application = applications.find(item => item.id === visit.application_id)
                const dateLabel = new Intl.DateTimeFormat('en-IN', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(visit.scheduled_for))
                return <article className="evc-visit-card" key={visit.id}>
                  <div className={'evc-visit-date ' + visit.status}><CalendarClock size={17}/><strong>{new Intl.DateTimeFormat('en-IN', { day: '2-digit', month: 'short' }).format(new Date(visit.scheduled_for))}</strong><span>{new Intl.DateTimeFormat('en-IN', { hour: '2-digit', minute: '2-digit' }).format(new Date(visit.scheduled_for))}</span></div>
                  <div className="evc-visit-main"><div className="evc-visit-title"><strong>{application?.title || 'Application record'}</strong><span className={'evc-status ' + visit.status}>{visit.status}</span></div><p>{application?.application_number || visit.application_id.slice(0, 8).toUpperCase()} · {visit.mode === 'onsite' ? 'Onsite visit' : 'Virtual visit'} · {dateLabel}</p>{visit.location && <p><strong>Location:</strong> {visit.location}</p>}{visit.notes && <p className="evc-visit-notes">{visit.notes}</p>}</div>
                  <div className="evc-visit-actions">{canScheduleEvc && visit.status === 'scheduled' && <><button className="secondary-button small-button" disabled={updatingEvcVisitId === visit.id} onClick={() => void handleUpdateEvcVisit(visit, 'completed')}>{updatingEvcVisitId === visit.id ? 'Saving…' : <><Check size={14}/> Complete</>}</button><button className="text-button evc-cancel-button" disabled={updatingEvcVisitId === visit.id} onClick={() => void handleUpdateEvcVisit(visit, 'cancelled')}>Cancel visit</button></>}{canScheduleEvc && visit.status === 'completed' && <><span className={'evc-status ' + visit.report_status}>{visit.report_status.replaceAll('_', ' ')}</span><button className="secondary-button small-button" onClick={() => openEvcReport(visit)}>{visit.report_status === 'submitted' ? 'View report' : visit.report_status === 'draft' ? 'Continue report' : 'Write report'}</button></>}</div>
                </article>
              })}</div>}
            </div>
          </section>}

          {view === 'evc' && reportVisitId && <section className="evc-report-form">
            <div className="evc-form-heading"><div><div className="eyebrow">VISIT OUTCOME</div><h3>{evcVisits.find(item => item.id === reportVisitId)?.report_status === 'submitted' ? 'Submitted EVC report' : 'Verification report'}</h3><p>Illustrative demo checklist, not an official regulatory checklist.</p></div><button type="button" className="text-button" onClick={() => setReportVisitId(null)}>Close</button></div>
            {EVC_CHECKLIST.map((definition, index) => {
              const item = reportChecklist.find(entry => entry.key === definition.key)!
              const locked = evcVisits.find(entry => entry.id === reportVisitId)?.report_status === 'submitted'
              return <div className="evc-checklist-row" key={item.key}><div className="evc-checklist-label"><span>{String(index + 1).padStart(2, '0')}</span><strong>{item.label}</strong></div><select aria-label={item.label + ' result'} value={item.result} disabled={locked} onChange={event => setReportChecklist(items => items.map(entry => entry.key === item.key ? { ...entry, result: event.target.value as EVCChecklistItem['result'] } : entry))}><option value="pass">Pass</option><option value="needs_attention">Needs attention</option><option value="not_applicable">Not applicable</option></select><input aria-label={item.label + ' notes'} value={item.notes} disabled={locked} onChange={event => setReportChecklist(items => items.map(entry => entry.key === item.key ? { ...entry, notes: event.target.value } : entry))} placeholder={item.result === 'needs_attention' ? 'Explain this finding (required)' : 'Optional observation'} maxLength={1500}/></div>
            })}
            <div className="evc-report-evidence">
              <div className="evc-report-evidence-heading"><div><strong>Supporting evidence</strong><span>Link registered evidence from this application to substantiate the visit report.</span></div><span className="evc-evidence-count">{reportEvidenceIds.length} linked</span></div>
              {loadingReportEvidence ? <p className="evc-evidence-empty">Loading application evidence…</p> : reportEvidence.length === 0 ? <p className="evc-evidence-empty">No evidence metadata registered for this application yet. Add evidence from the application detail page first.</p> : <div className="evc-evidence-options">{reportEvidence.map(item => {
                const locked = evcVisits.find(entry => entry.id === reportVisitId)?.report_status === 'submitted'
                const selected = reportEvidenceIds.includes(item.id)
                return <label className="evc-evidence-option" key={item.id}><input type="checkbox" checked={selected} disabled={locked} onChange={event => setReportEvidenceIds(ids => event.target.checked ? [...ids, item.id] : ids.filter(id => id !== item.id))}/><span className="evc-evidence-option-main"><strong>{item.title}</strong><small>{item.category.replaceAll('_', ' ')}{item.reference_number ? ' · Ref ' + item.reference_number : ''}</small></span><span className="evc-evidence-date">{item.expires_on ? 'Expires ' + formatDate(item.expires_on) : 'No expiry date'}</span></label>
              })}</div>}
              <p className="evc-evidence-footnote">Reports link to evidence metadata records. Private PDF/PNG/JPEG attachments are available from the application evidence workspace; checklist items remain illustrative, not official regulatory criteria.</p>
            </div>
            <label className="evc-report-field">Outcome summary<textarea value={reportOutcome} disabled={evcVisits.find(item => item.id === reportVisitId)?.report_status === 'submitted'} onChange={event => setReportOutcome(event.target.value)} minLength={10} maxLength={4000} rows={3} placeholder="Summarize the visit observations and outcome…" required/></label>
            <label className="evc-report-field">Additional observations<textarea value={reportObservations} disabled={evcVisits.find(item => item.id === reportVisitId)?.report_status === 'submitted'} onChange={event => setReportObservations(event.target.value)} maxLength={10000} rows={3} placeholder="Optional follow-up actions or supporting context"/></label>
            {evcVisits.find(item => item.id === reportVisitId)?.report_status !== 'submitted' && <div className="evc-form-actions"><span>Submission locks the report. Saves and submissions are recorded in the application timeline.</span><div className="evc-report-buttons"><button type="button" className="secondary-button" disabled={savingEvcReport || reportOutcome.trim().length < 10} onClick={() => void handleSaveEvcReport({ preventDefault: () => {} } as FormEvent, false)}>{savingEvcReport ? 'Saving…' : 'Save draft'}</button><button type="button" className="primary-button" disabled={savingEvcReport || reportOutcome.trim().length < 10 || reportChecklist.some(item => item.result === 'needs_attention' && !item.notes.trim())} onClick={() => void handleSaveEvcReport({ preventDefault: () => {} } as FormEvent, true)}>{savingEvcReport ? 'Submitting…' : 'Submit report'}</button></div></div>}
            {evcVisits.find(item => item.id === reportVisitId)?.report_submitted_at && <p className="evc-report-locked">Submitted {formatDate(evcVisits.find(item => item.id === reportVisitId)!.report_submitted_at!)} · Immutable audit record</p>}
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

      {previewImage && <div className="modal-backdrop image-preview-backdrop" role="presentation" onMouseDown={event => { if (event.target === event.currentTarget) closeImagePreview() }}><section className="modal-card image-preview-card" role="dialog" aria-modal="true" aria-label={`Image preview: ${previewImage.name}`}><div className="modal-heading"><div><div className="eyebrow">EVIDENCE ATTACHMENT</div><h2>{previewImage.name}</h2><p>Private file preview</p></div><button type="button" className="icon-button" onClick={closeImagePreview} aria-label="Close image preview"><X size={18}/></button></div><img className="evidence-image-preview" src={previewImage.url} alt={previewImage.name}/><div className="modal-actions"><button type="button" className="secondary-button" onClick={closeImagePreview}>Close preview</button></div></section></div>}
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
  return <div className="table-scroll"><table className="application-table"><thead><tr><th>APPLICATION</th><th>STATUS</th><th>LAST UPDATED</th>{!compact&&<th>INSTITUTION REF.</th>}<th><span className="sr-only">Open</span></th></tr></thead><tbody>{applications.map(application=><tr key={application.id} onClick={() => onOpen(application)} className="clickable-row"><td><div className="case-cell"><div className="case-icon"><FileText size={16}/></div><div><strong>{application.title}</strong><span>{application.application_number}</span></div></div></td><td><span className={`status-badge status-${application.status.replaceAll('_','-')}`}><span/>{formatStatus(application.status)}</span></td><td className="date-cell">{formatDate(application.updated_at)}</td>{!compact&&<td className="ref-cell">{application.institution_id.slice(0,8).toUpperCase()}</td>}<td><button className="row-arrow" aria-label={`Open ${application.application_number}`} onClick={e=>{e.stopPropagation();onOpen(application)}}><ArrowRight size={15}/></button></td></tr>)}</tbody></table></div>
}

export default App
