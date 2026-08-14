import { useState } from 'react'
import { Modal } from './Modal'
import { Button } from './Button'
import { useToast } from '@/hooks/useToast'
import { getApiKey, setApiKey } from '@/lib/api'

export function SetApiKeyModal({ onClose }: { onClose: () => void }) {
  const toast = useToast()
  const [key, setKey] = useState(getApiKey())

  function handleSave() {
    setApiKey(key)
    toast('API key saved', 'success')
    onClose()
  }

  return (
    <Modal
      open
      title="API Key"
      onClose={onClose}
      footer={
        <>
          <Button variant="primary" onClick={handleSave}>Save</Button>
          <Button variant="outline" onClick={onClose}>Cancel</Button>
        </>
      }
    >
      <p className="mb-3 text-sm leading-relaxed text-ink-soft/60">
        所有 <code className="rounded bg-gray-100 px-1 py-0.5 font-mono text-xs">/api/*</code> 请求通过{' '}
        <code className="rounded bg-gray-100 px-1 py-0.5 font-mono text-xs">X-API-Key</code> 头鉴权。
        默认 <code className="rounded bg-gray-100 px-1 py-0.5 font-mono text-xs">dev-key</code> 仅限本地开发；生产环境请在部署时通过环境变量注入强密钥。
      </p>
      <input
        className="w-full rounded-lg border border-gray-200 px-3 py-2 font-mono text-sm placeholder:text-gray-300"
        placeholder="X-API-Key"
        value={key}
        onChange={e => setKey(e.target.value)}
        onKeyDown={e => e.key === 'Enter' && handleSave()}
      />
    </Modal>
  )
}
