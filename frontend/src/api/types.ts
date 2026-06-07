export type Role = 'student' | 'teacher' | 'counselor'

export type User = {
  id: number
  studentNo: string
  name: string
  role: Role
  className?: string | null
  collegeId?: number | null
  majorId?: number | null
  classGroupId?: number | null
}

export type Term = {
  id: number
  name: string
  academicYear: string
  semesterType: 'spring' | 'fall' | 'summer' | string
  startsAt: string
  endsAt: string
  isCurrent: boolean
  status: string
  createdAt: string
}

export type College = {
  id: number
  name: string
  code: string
}

export type Major = {
  id: number
  collegeId: number
  collegeName?: string | null
  name: string
  code: string
}

export type ClassGroup = {
  id: number
  majorId: number
  majorName?: string | null
  collegeId?: number | null
  collegeName?: string | null
  name: string
  gradeYear?: number | null
  counselorId?: number | null
}

export type NotificationItem = {
  id: number
  type: string
  title: string
  content: string
  link?: string | null
  relatedId?: number | null
  isRead: boolean
  createdAt: string
}

export type MaterialStatus =
  | '草稿'
  | '已提交'
  | '审核中'
  | '已通过'
  | '已打回'
  | '公示中'
  | '公示结束'
  | '申诉处理中'

export type Material = {
  id: number
  title: string
  category: string
  description?: string
  certificateNo: string
  issuedAt: string
  expiresAt?: string | null
  fileName?: string | null
  fileUrl?: string | null
  ocrText?: string | null
  score: number
  status: MaterialStatus
  riskLevel: string
  riskReasons: string[]
  termId?: number | null
  termName?: string | null
  updatedAt: string
  student?: User
}

export type ReviewRecord = {
  id: number
  materialId: number
  reviewer: User
  action: string
  opinion: string
  scoreDelta: number
  createdAt: string
}

export type Appeal = {
  id: number
  materialId: number
  student: User
  reason: string
  evidenceFiles: { name: string; url: string }[]
  status: string
  resultOpinion?: string | null
  createdAt: string
  resolvedAt?: string | null
  termId?: number | null
  termName?: string | null
  material: Material
}

export type RankItem = {
  rank: number
  student: User
  totalScore: number
}

export type CategoryScore = {
  category: string
  score: number
  cap?: number
}

export type ClassScore = {
  className: string
  totalScore: number
  studentCount: number
}

export type StatsOverview = {
  term: { id: number; name: string }
  summary: {
    totalMaterials: number
    pending: number
    approved: number
    rejected: number
    appealing: number
    pendingAppeals: number
  }
  categoryBreakdown: CategoryScore[]
  topStudents: { studentNo: string; name: string; className?: string | null; totalScore: number }[]
  classBreakdown: ClassScore[]
  trend: { date: string; count: number }[]
}

export type StudentStats = {
  term: { id: number; name: string }
  totalScore: number
  category: CategoryScore[]
  radar: Record<string, number>
  statusDistribution: Record<string, number>
  materials: Material[]
}

