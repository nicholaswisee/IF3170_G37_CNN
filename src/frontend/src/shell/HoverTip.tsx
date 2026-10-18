import { useImperativeHandle, useRef, type Ref } from 'react'

export interface HoverTipHandle {
  show: (text: string, clientX: number, clientY: number) => void
  hide: () => void
}

/** Pointer tooltip for the 3D scene, updated imperatively so hovering never re-renders the app. */
export function HoverTip({ ref }: { ref: Ref<HoverTipHandle> }) {
  const tip = useRef<HTMLDivElement>(null)
  useImperativeHandle(ref, () => ({
    show(text, clientX, clientY) {
      const node = tip.current
      if (!node) return
      node.textContent = text
      node.style.transform = `translate(${clientX + 14}px, ${clientY + 14}px)`
      node.hidden = false
    },
    hide() {
      if (tip.current) tip.current.hidden = true
    },
  }), [])
  return <div ref={tip} className="hover-tip" role="tooltip" hidden />
}
