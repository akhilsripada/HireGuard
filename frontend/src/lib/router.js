// Tiny history-based router: four routes don't need a library.
import { useEffect, useState } from 'react'

const listeners = new Set()

export function navigate(path, { replace = false } = {}) {
  if (replace) window.history.replaceState({}, '', path)
  else window.history.pushState({}, '', path)
  listeners.forEach((fn) => fn(window.location.pathname))
  window.scrollTo(0, 0)
}

export function usePath() {
  const [path, setPath] = useState(window.location.pathname)
  useEffect(() => {
    const onPop = () => setPath(window.location.pathname)
    listeners.add(setPath)
    window.addEventListener('popstate', onPop)
    return () => {
      listeners.delete(setPath)
      window.removeEventListener('popstate', onPop)
    }
  }, [])
  return path
}

// <a> that navigates without a page reload (keeps real hrefs for accessibility)
export function linkProps(path) {
  return {
    href: path,
    onClick: (e) => {
      if (e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return
      e.preventDefault()
      navigate(path)
    },
  }
}
