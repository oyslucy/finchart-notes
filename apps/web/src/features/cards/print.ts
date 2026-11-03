/** Prints the current board in the light theme; the browser's print dialog saves it as PDF. */
export function exportPdf(): void {
  const root = document.documentElement
  const previous = root.dataset.theme
  root.dataset.theme = 'light'
  window.addEventListener(
    'afterprint',
    () => {
      if (previous) root.dataset.theme = previous
    },
    { once: true },
  )
  window.print()
}
