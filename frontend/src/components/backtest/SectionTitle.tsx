/** Small shared header used by every result section. */
export function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground mb-3 mt-1">
      {children}
    </h2>
  )
}
