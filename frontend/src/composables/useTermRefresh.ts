import { onMounted, onBeforeUnmount } from 'vue'

export function useTermRefresh(callback: () => void | Promise<void>) {
  function handler() {
    void callback()
  }
  onMounted(() => {
    window.addEventListener('zc:term-changed', handler)
  })
  onBeforeUnmount(() => {
    window.removeEventListener('zc:term-changed', handler)
  })
}
