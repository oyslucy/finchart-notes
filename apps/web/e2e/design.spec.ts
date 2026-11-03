import { expect, test } from '@playwright/test'

for (const theme of ['light', 'dark'] as const) {
  test(`design page renders in ${theme}`, async ({ page }) => {
    const errors: string[] = []
    page.on('pageerror', (e) => errors.push(e.message))
    page.on('console', (m) => {
      if (m.type() === 'error') errors.push(m.text())
    })

    await page.emulateMedia({ colorScheme: theme, reducedMotion: 'reduce' })
    await page.goto('/design')
    await expect(page.locator('html')).toHaveAttribute('data-theme', theme)
    await page.evaluate('document.fonts.ready')

    await page.screenshot({ path: `screenshots/design-${theme}.png`, fullPage: true })

    await page.getByRole('button', { name: '보드 삭제' }).click()
    await expect(page.getByRole('dialog')).toBeVisible()
    await expect(page.getByRole('dialog')).toHaveCSS('opacity', '1')
    await page.screenshot({ path: `screenshots/design-${theme}-dialog.png` })
    await page.keyboard.press('Escape')
    await expect(page.getByRole('dialog')).toBeHidden()

    expect(errors).toEqual([])
  })
}
