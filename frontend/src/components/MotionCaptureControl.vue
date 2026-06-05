<script setup lang="ts">
import { Camera, CameraOff, Hand } from 'lucide-vue-next'
import { computed, onBeforeUnmount, ref } from 'vue'
import { FilesetResolver, HandLandmarker } from '@mediapipe/tasks-vision'

import { postJson } from '@/api/client'
import { useSessionStore } from '@/stores/session'

type MotionPage = 'publicity' | 'list' | 'appeal'
type Direction = 'up' | 'down' | 'left' | 'right'
type SystemGesture = 'SWIPE_LEFT' | 'SWIPE_RIGHT' | 'SWIPE_UP' | 'SWIPE_DOWN'

type GestureResponse = {
  status: string
  action: string
  actionLabel: string
  allowed: boolean
  uiFeedback: { level: string; message: string }
  data: Record<string, unknown>
}

const props = withDefaults(
  defineProps<{
    page: MotionPage
    pageIndex?: number
    pageSize?: number
    context?: Record<string, unknown>
  }>(),
  {
    pageIndex: 1,
    pageSize: 5,
    context: () => ({}),
  },
)

const emit = defineEmits<{
  captured: [
    payload: {
      direction: Direction
      gesture: SystemGesture
      response: GestureResponse
    },
  ]
}>()

const MEDIAPIPE_WASM_BASE = '/mediapipe/wasm'
const MEDIAPIPE_MODEL_URL = '/mediapipe/model/hand_landmarker.task'

const MIN_HAND_DETECTION_CONFIDENCE = 0.5
const MIN_HAND_PRESENCE_CONFIDENCE = 0.5
const MIN_TRACKING_CONFIDENCE = 0.5
const WRIST_SMOOTHING = 0.6

const PATH_MIN_FRAMES = 5
const PATH_MAX_FRAMES = 16
const STAGNANT_FRAMES = 3
const STAGNANT_FRAME_DIST = 0.0045
const MIN_PATH_LENGTH = 0.18
const MIN_NET_DISPLACEMENT_H = 0.10
const MIN_NET_DISPLACEMENT_V = 0.12
const MIN_AXIS_RATIO = 2.4
const MIN_STRAIGHTNESS = 0.55
const AXIS_RATIO_DIVISOR_FLOOR = 0.0001
const PATH_LENGTH_DIVISOR_FLOOR = 0.0001
const DISPATCH_COOLDOWN_MS = 1700

const gestureByDirection: Record<Direction, SystemGesture> = {
  left: 'SWIPE_LEFT',
  right: 'SWIPE_RIGHT',
  up: 'SWIPE_UP',
  down: 'SWIPE_DOWN',
}

const session = useSessionStore()
const videoRef = ref<HTMLVideoElement | null>(null)
const state = ref<'idle' | 'loading' | 'loading-model' | 'running' | 'blocked' | 'error'>('idle')
const statusText = ref('动作捕捉未启动')
const lastDirection = ref<Direction | ''>('')
const lastFeedback = ref('')
const handDetected = ref(false)

let stream: MediaStream | null = null
let frameId = 0
let lastVideoTimeMs = -1
let handLandmarker: HandLandmarker | null = null
let smoothedWrist: { x: number; y: number } | null = null
let wristPath: Array<{ x: number; y: number }> = []
let lastDispatchAt = 0

const statusLabel = computed(() => {
  if (state.value === 'loading') return '正在启动摄像头'
  if (state.value === 'loading-model') return '正在加载手部识别模型'
  if (state.value === 'running') {
    if (lastDirection.value) return `已捕捉${directionLabel(lastDirection.value)}`
    return handDetected.value ? '已检测到手部，可挥动手腕' : '请将手部对准摄像头'
  }
  if (state.value === 'blocked') return '摄像头权限受限'
  if (state.value === 'error') return statusText.value
  return statusText.value
})

const handIndicatorClass = computed(() => {
  if (state.value !== 'running') return ''
  return handDetected.value ? 'active' : 'waiting'
})

async function startMotionCapture() {
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    state.value = 'error'
    statusText.value = '您的浏览器不支持摄像头功能'
    return
  }
  if (state.value === 'running' || state.value === 'loading' || state.value === 'loading-model') return
  state.value = 'loading'
  statusText.value = '正在启动摄像头'
  lastFeedback.value = ''
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      video: {
        facingMode: 'user',
        width: 640,
        height: 480,
      },
      audio: false,
    })
    const video = videoRef.value
    if (!video) throw new Error('摄像头画面初始化失败')
    video.srcObject = stream
    await new Promise<void>((resolve) => {
      video.onloadedmetadata = () => resolve()
    })
    await video.play()
    state.value = 'loading-model'
    statusText.value = '正在加载手部识别模型'
    await ensureHandLandmarker()
    resetMotionState()
    state.value = 'running'
    statusText.value = '正在捕捉动作'
    processMotionFrame()
  } catch (err: any) {
    state.value = err?.name === 'NotAllowedError' ? 'blocked' : 'error'
    statusText.value = err?.message || '无法启动摄像头'
    stopMotionCapture()
  }
}

function stopMotionCapture() {
  if (frameId) {
    cancelAnimationFrame(frameId)
    frameId = 0
  }
  stream?.getTracks().forEach((track) => track.stop())
  stream = null
  if (videoRef.value) videoRef.value.srcObject = null
  resetMotionState()
  if (state.value === 'running' || state.value === 'loading' || state.value === 'loading-model') {
    state.value = 'idle'
    statusText.value = '动作捕捉未启动'
  }
}

async function ensureHandLandmarker() {
  if (handLandmarker) return
  const vision = await FilesetResolver.forVisionTasks(MEDIAPIPE_WASM_BASE)
  handLandmarker = await HandLandmarker.createFromOptions(vision, {
    baseOptions: {
      modelAssetPath: MEDIAPIPE_MODEL_URL,
      delegate: 'GPU',
    },
    numHands: 1,
    minHandDetectionConfidence: MIN_HAND_DETECTION_CONFIDENCE,
    minHandPresenceConfidence: MIN_HAND_PRESENCE_CONFIDENCE,
    minTrackingConfidence: MIN_TRACKING_CONFIDENCE,
    runningMode: 'VIDEO',
  })
}

function resetMotionState() {
  lastVideoTimeMs = -1
  smoothedWrist = null
  wristPath = []
  handDetected.value = false
  lastDirection.value = ''
}

function processMotionFrame() {
  const video = videoRef.value
  if (state.value !== 'running' || !video || !handLandmarker) return

  const nowMs = performance.now()
  if (video.currentTime === 0 && lastVideoTimeMs === -1) {
    frameId = requestAnimationFrame(processMotionFrame)
    return
  }
  let result
  try {
    result = handLandmarker.detectForVideo(video, nowMs)
  } catch (err) {
    frameId = requestAnimationFrame(processMotionFrame)
    return
  }
  lastVideoTimeMs = nowMs

  const landmarks = result.landmarks?.[0]
  if (!landmarks || landmarks.length < 1) {
    handDetected.value = false
    smoothedWrist = null
    wristPath = []
    frameId = requestAnimationFrame(processMotionFrame)
    return
  }
  handDetected.value = true

  const wrist = landmarks[0]
  const observation = { x: wrist.x, y: wrist.y }
  if (!smoothedWrist) {
    smoothedWrist = observation
  } else {
    smoothedWrist = {
      x: smoothedWrist.x * WRIST_SMOOTHING + observation.x * (1 - WRIST_SMOOTHING),
      y: smoothedWrist.y * WRIST_SMOOTHING + observation.y * (1 - WRIST_SMOOTHING),
    }
  }

  wristPath.push({ x: smoothedWrist.x, y: smoothedWrist.y })
  if (wristPath.length > PATH_MAX_FRAMES) wristPath.shift()
  if (wristPath.length < PATH_MIN_FRAMES) {
    frameId = requestAnimationFrame(processMotionFrame)
    return
  }

  let recentDist = 0
  for (let i = wristPath.length - STAGNANT_FRAMES; i < wristPath.length; i += 1) {
    if (i <= 0) continue
    recentDist += Math.hypot(
      wristPath[i].x - wristPath[i - 1].x,
      wristPath[i].y - wristPath[i - 1].y,
    )
  }
  const isStagnant = recentDist < STAGNANT_FRAME_DIST * STAGNANT_FRAMES
  if (!isStagnant && wristPath.length < PATH_MAX_FRAMES) {
    frameId = requestAnimationFrame(processMotionFrame)
    return
  }

  const first = wristPath[0]
  const last = wristPath[wristPath.length - 1]
  const dx = last.x - first.x
  const dy = last.y - first.y
  const absDx = Math.abs(dx)
  const absDy = Math.abs(dy)
  let pathLength = 0
  for (let i = 1; i < wristPath.length; i += 1) {
    pathLength += Math.hypot(
      wristPath[i].x - wristPath[i - 1].x,
      wristPath[i].y - wristPath[i - 1].y,
    )
  }
  const netDistance = Math.sqrt(dx * dx + dy * dy)
  const axisRatio =
    Math.max(absDx, absDy) / Math.max(Math.min(absDx, absDy), AXIS_RATIO_DIVISOR_FLOOR)
  const straightness = netDistance / Math.max(pathLength, PATH_LENGTH_DIVISOR_FLOOR)
  const isHorizontal = absDx >= absDy
  const minNet = isHorizontal ? MIN_NET_DISPLACEMENT_H : MIN_NET_DISPLACEMENT_V
  const majorAxisNet = isHorizontal ? absDx : absDy

  const passesAxis = axisRatio >= MIN_AXIS_RATIO
  const passesMagnitude = pathLength >= MIN_PATH_LENGTH && majorAxisNet >= minNet
  const passesStraightness = straightness >= MIN_STRAIGHTNESS

  if (!passesAxis || !passesMagnitude || !passesStraightness) {
    if (isStagnant || wristPath.length >= PATH_MAX_FRAMES) {
      wristPath = []
    }
    frameId = requestAnimationFrame(processMotionFrame)
    return
  }

  const direction: Direction = isHorizontal
    ? dx < 0 ? 'left' : 'right'
    : dy < 0 ? 'up' : 'down'

  void dispatchSwipe(direction, pathLength, axisRatio, straightness)
  wristPath = []

  frameId = requestAnimationFrame(processMotionFrame)
}

async function dispatchSwipe(
  direction: Direction,
  pathLength: number,
  axisRatio: number,
  straightness: number,
) {
  if (Date.now() - lastDispatchAt < DISPATCH_COOLDOWN_MS) return

  const gesture = gestureByDirection[direction]
  const magnitudeScore = Math.min(1, pathLength / 0.45)
  const dominanceScore = Math.min(1, (axisRatio - MIN_AXIS_RATIO) / 2.5)
  const straightnessScore = Math.min(1, (straightness - MIN_STRAIGHTNESS) / 0.4)
  const confidence = Math.max(
    0.75,
    Math.min(
      0.97,
      0.6 + 0.15 * magnitudeScore + 0.15 * dominanceScore + 0.1 * straightnessScore,
    ),
  )

  lastDispatchAt = Date.now()
  lastDirection.value = direction
  statusText.value = `检测到${directionLabel(direction)}`

  try {
    const response = await postJson<GestureResponse>('/api/gesture/dispatch', {
      userId: session.user?.studentNo,
      role: session.user?.role,
      page: props.page,
      gesture,
      confidence,
      timestamp: Math.floor(Date.now() / 1000),
      context: {
        pageIndex: props.pageIndex,
        pageSize: props.pageSize,
        pathLength: Number(pathLength.toFixed(3)),
        axisRatio: Number(axisRatio.toFixed(2)),
        straightness: Number(straightness.toFixed(2)),
        ...props.context,
      },
    })
    lastFeedback.value = response.uiFeedback.message
    emit('captured', { direction, gesture, response })
  } catch (err: any) {
    lastFeedback.value = err.message || '动作调度失败'
  }
}

function directionLabel(direction: Direction | '') {
  const labels: Record<Direction, string> = {
    up: '上划',
    down: '下划',
    left: '上一页',
    right: '下一页',
  }
  return direction ? labels[direction] : ''
}

onBeforeUnmount(() => {
  stopMotionCapture()
  handLandmarker?.close()
  handLandmarker = null
})
</script>

<template>
  <section class="motion-control">
    <div class="motion-video-wrap">
      <video ref="videoRef" class="motion-video" autoplay playsinline muted />
      <span class="motion-hand" :class="handIndicatorClass" aria-hidden="true">
        <Hand :size="14" />
      </span>
    </div>
    <span class="motion-dot" :class="{ active: state === 'running' && handDetected }" />
    <div class="motion-copy">
      <strong>{{ statusLabel }}</strong>
      <span>{{ lastFeedback || '从手腕开始挥动，左扇上一页，右扇下一页' }}</span>
    </div>
    <button
      v-if="state !== 'running'"
      class="button secondary motion-button"
      type="button"
      :disabled="state === 'loading' || state === 'loading-model'"
      @click="startMotionCapture"
    >
      <Camera :size="16" aria-hidden="true" />
      {{
        state === 'loading'
          ? '启动中'
          : state === 'loading-model'
            ? '加载模型中'
            : '启动动作捕捉'
      }}
    </button>
    <button v-else class="button secondary motion-button" type="button" @click="stopMotionCapture">
      <CameraOff :size="16" aria-hidden="true" />
      停止动作捕捉
    </button>
  </section>
</template>

<style scoped>
.motion-control {
  display: grid;
  grid-template-columns: auto auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 10px;
  min-height: 56px;
  padding: 10px 12px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: #ffffff;
}

.motion-video-wrap {
  position: relative;
  width: 56px;
  height: 40px;
  border-radius: 6px;
  overflow: hidden;
  background: #111827;
}

.motion-video {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.motion-hand {
  position: absolute;
  right: 2px;
  bottom: 2px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  border-radius: 999px;
  background: rgba(17, 24, 39, 0.65);
  color: #cbd5f5;
  opacity: 0.4;
  transition: opacity 0.15s ease, color 0.15s ease, background 0.15s ease;
}

.motion-hand.active {
  opacity: 1;
  background: #35c996;
  color: #ffffff;
}

.motion-hand.waiting {
  opacity: 0.85;
  color: #fbbf24;
}

.motion-dot {
  width: 9px;
  height: 9px;
  border-radius: 999px;
  background: #9aa8ba;
}

.motion-dot.active {
  background: #35c996;
  box-shadow: 0 0 0 6px rgba(53, 201, 150, 0.16);
}

.motion-copy {
  min-width: 0;
  display: grid;
  gap: 2px;
}

.motion-copy span {
  color: var(--muted);
  font-size: 13px;
}

.motion-button {
  white-space: nowrap;
}

@media (max-width: 760px) {
  .motion-control {
    grid-template-columns: auto minmax(0, 1fr);
  }

  .motion-video-wrap {
    display: none;
  }

  .motion-dot {
    align-self: start;
    margin-top: 8px;
  }

  .motion-button {
    grid-column: 1 / -1;
    width: 100%;
  }
}
</style>
