import { useEffect, useId, useRef, useState, type KeyboardEvent } from "react"


export function useSearchableSelectKeyboard<T>({
  items,
  open,
  resetKey,
  onSelect,
  onEnter,
}: {
  items: T[]
  open: boolean
  resetKey: string
  onSelect: (item: T) => void
  onEnter?: () => void
}) {
  const listboxId = useId()
  const optionRefs = useRef<Array<HTMLElement | null>>([])
  const [keyboardState, setKeyboardState] = useState({
    resetKey,
    activeIndex: -1,
    dismissed: false,
  })
  const stateMatchesQuery = keyboardState.resetKey === resetKey
  const activeIndex = stateMatchesQuery && keyboardState.activeIndex < items.length
    ? keyboardState.activeIndex
    : -1
  const dismissed = stateMatchesQuery && keyboardState.dismissed
  const isOpen = open && !dismissed

  useEffect(() => {
    if (!isOpen || activeIndex < 0) return
    optionRefs.current[activeIndex]?.scrollIntoView({ block: "nearest" })
  }, [activeIndex, isOpen])

  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if ((event.key === "ArrowDown" || event.key === "ArrowUp") && open && items.length > 0) {
      event.preventDefault()
      setKeyboardState(currentState => {
        const current = currentState.resetKey === resetKey
          ? currentState.activeIndex
          : -1
        const nextIndex = event.key === "ArrowDown"
          ? current < 0 ? 0 : (current + 1) % items.length
          : current < 0 ? items.length - 1 : (current - 1 + items.length) % items.length
        return { resetKey, activeIndex: nextIndex, dismissed: false }
      })
      return
    }
    if (event.key === "Enter") {
      if (isOpen && activeIndex >= 0 && activeIndex < items.length) {
        event.preventDefault()
        onSelect(items[activeIndex])
      } else {
        onEnter?.()
      }
      return
    }
    if (event.key === "Escape" && isOpen) {
      event.preventDefault()
      setKeyboardState({ resetKey, activeIndex: -1, dismissed: true })
    }
  }

  return {
    activeIndex,
    activeOptionId:
      isOpen && activeIndex >= 0
        ? `${listboxId}-option-${activeIndex}`
        : undefined,
    isOpen,
    listboxId,
    onFocus: () => setKeyboardState(current => ({
      resetKey,
      activeIndex: current.resetKey === resetKey ? current.activeIndex : -1,
      dismissed: false,
    })),
    onKeyDown,
    optionId: (index: number) => `${listboxId}-option-${index}`,
    optionRef: (index: number) => (node: HTMLElement | null) => {
      optionRefs.current[index] = node
    },
    setActiveIndex: (index: number) => setKeyboardState({
      resetKey,
      activeIndex: index,
      dismissed: false,
    }),
  }
}
