const { test, expect } = require('@playwright/test');

if (process.env.PLAYWRIGHT_CHANNEL) test.use({ channel: process.env.PLAYWRIGHT_CHANNEL });

const SITE_URL = process.env.SITE_URL || 'http://127.0.0.1:8000/';

test('language, contact heading, contents navigation, and failure dialog work', async ({ page }) => {
  await page.goto(SITE_URL);
  await expect(page.locator('#notesGrid .note-card')).toHaveCount(3);
  await expect(page.locator('.contact-info h3')).toHaveText('联系方式');
  await expect(page.locator('.copy-help')).toHaveCount(0);

  await page.locator('#langSwitch').click();
  await expect(page.locator('html')).toHaveAttribute('lang', 'en');
  await expect(page.locator('.contact-info h3')).toHaveText('Contact');
  await expect(page.locator('[data-language-indicator="en"]')).toHaveClass(/current/);

  await page.locator('.toc-links a[href="#about"]').click();
  await expect(page.locator('.toc-links a[href="#about"]')).toHaveAttribute('aria-current', 'location');

  await page.locator('#downloadSupport').click();
  await expect(page.locator('#failureDialog')).toBeVisible();
  await expect(page.locator('#failureDialogTitle')).toHaveText('Download failed');
  await page.locator('#failureConfirm').click();
  await expect(page.locator('#failureDialog')).toBeHidden();
});

test('mobile contents panel remains centered and inside the viewport', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 780 });
  await page.goto(SITE_URL);
  await expect(page.locator('#pageToc')).toHaveClass(/collapsed/);
  await page.locator('#tocExpand').click();
  await expect(page.locator('#pageToc')).not.toHaveClass(/collapsed/);

  for (const selector of ['#pageToc', '#jumpTop', '#jumpBottom']) {
    const box = await page.locator(selector).boundingBox();
    expect(box).not.toBeNull();
    expect(box.y).toBeGreaterThanOrEqual(0);
    expect(box.y + box.height).toBeLessThanOrEqual(780);
  }
});

test('large note catalogs are paginated', async ({ page }) => {
  let pdfChecks = 0;
  let activePdfChecks = 0;
  let maximumConcurrentChecks = 0;
  const baseNote = {
    updated: '2026-09-24T12:00+08:00',
    categories: ['geometric-representation'],
    category: { zh: '几何表示论', en: 'GEOMETRIC REPRESENTATION THEORY' },
    title: { zh: '测试笔记', en: 'Test Note' },
    description: { zh: '用于分页测试。', en: 'Used to test pagination.' }
  };
  const notes = Array.from({ length: 14 }, (_, index) => ({
    ...baseNote,
    file: `test-note-${index + 1}.pdf`,
    title: { zh: `测试笔记 ${index + 1}`, en: `Test Note ${index + 1}` }
  }));
  await page.route('**/notes/metadata.json', (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ schemaVersion: 1, notes })
  }));
  await page.route('**/notes/test-note-*.pdf', async (route) => {
    pdfChecks += 1;
    activePdfChecks += 1;
    maximumConcurrentChecks = Math.max(maximumConcurrentChecks, activePdfChecks);
    await new Promise((resolve) => setTimeout(resolve, 30));
    activePdfChecks -= 1;
    await route.fulfill({ status: 200, headers: { 'content-length': '128' }, body: '' });
  });
  await page.goto(SITE_URL);
  await expect(page.locator('#notesGrid .note-card')).toHaveCount(6);
  await expect(page.locator('#notesCount')).toHaveText('显示 6 / 14 篇笔记');
  await expect.poll(() => pdfChecks).toBe(6);
  expect(maximumConcurrentChecks).toBeLessThanOrEqual(4);
  await page.locator('#notesLoadMore').click();
  await expect(page.locator('#notesGrid .note-card')).toHaveCount(12);
  await expect(page.locator('#notesCount')).toHaveText('显示 12 / 14 篇笔记');
  await expect.poll(() => pdfChecks).toBe(12);
  expect(maximumConcurrentChecks).toBeLessThanOrEqual(4);
});

test('note columns are generated from metadata', async ({ page }) => {
  await page.route('**/notes/metadata.json', (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({
      schemaVersion: 1,
      columns: [
        { id: 'geometric-langlands', label: { zh: '几何 Langlands', en: 'Geometric Langlands' }, visible: true },
        { id: 'hidden-column', label: { zh: '隐藏专栏', en: 'Hidden Column' }, visible: false }
      ],
      notes: [{
        file: 'langlands.pdf', updated: '', categories: ['geometric-langlands'],
        category: { zh: '旧名称', en: 'Old label' },
        title: { zh: '几何 Langlands 笔记', en: 'Geometric Langlands Notes' },
        description: { zh: '测试动态专栏。', en: 'Tests dynamic columns.' }
      }]
    })
  }));
  await page.route('**/notes/langlands.pdf', (route) => route.fulfill({ status: 200, headers: { 'content-length': '128' }, body: '' }));
  await page.goto(SITE_URL);
  await expect(page.locator('.filter-button[data-filter="geometric-langlands"]')).toHaveText('几何 Langlands');
  await expect(page.locator('.filter-button[data-filter="hidden-column"]')).toHaveCount(0);
  await expect(page.locator('#notesGrid .note-category')).toHaveText('几何 Langlands');
});

test('Unicode PDF filenames are preserved and URL-encoded', async ({ page }) => {
  const filename = '几何 Satake 学习笔记（第 1 讲）.pdf';
  await page.route('**/notes/metadata.json', (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({
      schemaVersion: 1,
      notes: [{
        file: filename,
        updated: '2026-09-24T12:00+08:00',
        pageCount: 12,
        author: 'Yijia Zhao',
        categories: ['geometric-representation'],
        category: { zh: '几何表示论', en: 'GEOMETRIC REPRESENTATION THEORY' },
        title: { zh: '含中文文件名的笔记', en: 'Notes with a Unicode Filename' },
        description: { zh: '验证中文与空格。', en: 'Verifies Chinese characters and spaces.' }
      }]
    })
  }));
  await page.route('**/notes/*.pdf', (route) => route.fulfill({ status: 200, headers: { 'content-length': '128' }, body: '' }));
  await page.goto(SITE_URL);
  const download = page.locator('#notesGrid .note-download');
  await expect(download).toHaveAttribute('download', filename);
  await expect(download).toHaveAttribute('href', `notes/${encodeURIComponent(filename)}`);
  await expect(page.locator('#notesGrid .note-document-info')).toHaveText('12 页 · 作者：Yijia Zhao');
});

test('external large PDFs use a direct HTTPS download without a cross-origin check', async ({ page }) => {
  const downloadUrl = 'https://files.example.org/notes/large-notes.pdf';
  let externalChecks = 0;
  await page.route('**/notes/metadata.json', (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({
      schemaVersion: 1,
      notes: [{
        file: 'large-notes.pdf', downloadUrl, updated: '2026-09-24T12:00+08:00',
        categories: ['geometric-representation'],
        category: { zh: '几何表示论', en: 'GEOMETRIC REPRESENTATION THEORY' },
        title: { zh: '大型讲义', en: 'Large Lecture Notes' },
        description: { zh: '存储在独立对象存储中。', en: 'Stored in external object storage.' }
      }]
    })
  }));
  await page.route('https://files.example.org/**', (route) => {
    externalChecks += 1;
    return route.abort();
  });
  await page.goto(SITE_URL);
  const download = page.locator('#notesGrid .note-download');
  await expect(download).toHaveAttribute('href', downloadUrl);
  await expect(download).toHaveAttribute('target', '_blank');
  await expect(download).not.toHaveClass(/unavailable/);
  expect(externalChecks).toBe(0);
});
