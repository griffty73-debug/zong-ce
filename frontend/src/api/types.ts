export type Role = 'student' | 'teacher' | 'counselor'

export type User = {
  id: number
  studentNo: string
  name: string
  role: Role
  className?: string | null
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
  status: string
  resultOpinion?: string | null
  createdAt: string
  resolvedAt?: string | null
  material: Material
}

export type RankItem = {
  rank: number
  student: User
  totalScore: number
}
