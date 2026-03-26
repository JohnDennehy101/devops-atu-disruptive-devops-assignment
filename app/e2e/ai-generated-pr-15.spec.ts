import { test, expect } from '@playwright/test';

test.describe('Note Taking App - Character Counter Feature', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('should display character counter with initial value of 0', async ({ page }) => {
    const characterCounter = page.locator('p.text-xs.text-gray-500').filter({ hasText: '/ 5000' });
    await expect(characterCounter).toHaveText('0 / 5000');
  });

  test('should update character counter when typing in body field', async ({ page }) => {
    const bodyTextarea = page.getByRole('textbox', { name: 'Body' });
    const characterCounter = page.locator('p.text-xs.text-gray-500').filter({ hasText: '/ 5000' });
    
    const testText = 'This is a test note body.';
    await bodyTextarea.fill(testText);
    
    await expect(characterCounter).toHaveText(`${testText.length} / 5000`);
  });

  test('should update character counter dynamically as user types', async ({ page }) => {
    const bodyTextarea = page.getByRole('textbox', { name: 'Body' });
    const characterCounter = page.locator('p.text-xs.text-gray-500').filter({ hasText: '/ 5000' });
    
    await bodyTextarea.fill('Hello');
    await expect(characterCounter).toHaveText('5 / 5000');
    
    await bodyTextarea.fill('Hello World!');
    await expect(characterCounter).toHaveText('12 / 5000');
  });

  test('should show character counter with longer text', async ({ page }) => {
    const bodyTextarea = page.getByRole('textbox', { name: 'Body' });
    const characterCounter = page.locator('p.text-xs.text-gray-500').filter({ hasText: '/ 5000' });
    
    const longText = 'Lorem ipsum dolor sit amet, consectetur adipiscing elit. '.repeat(10);
    await bodyTextarea.fill(longText);
    
    await expect(characterCounter).toHaveText(`${longText.length} / 5000`);
  });

  test('should maintain character counter when creating a new note', async ({ page }) => {
    const titleTextbox = page.getByRole('textbox', { name: 'Title' });
    const bodyTextarea = page.getByRole('textbox', { name: 'Body' });
    const tagsTextbox = page.getByRole('textbox', { name: 'Tags (comma-separated)' });
    const createButton = page.getByRole('button', { name: 'Create Note' });
    const characterCounter = page.locator('p.text-xs.text-gray-500').filter({ hasText: '/ 5000' });
    
    await titleTextbox.fill('Test Note');
    await bodyTextarea.fill('This is a test note body with some content.');
    await tagsTextbox.fill('test, automation');
    
    const expectedCount = 'This is a test note body with some content.'.length;
    await expect(characterCounter).toHaveText(`${expectedCount} / 5000`);
    
    await createButton.click();
    
    // After creating, form should reset and counter should show 0
    await expect(characterCounter).toHaveText('0 / 5000');
  });

  test('should show character counter in edit mode', async ({ page }) => {
    // First create a note
    await page.getByRole('textbox', { name: 'Title' }).fill('Edit Test Note');
    await page.getByRole('textbox', { name: 'Body' }).fill('Original content for editing test.');
    await page.getByRole('textbox', { name: 'Tags (comma-separated)' }).fill('edit, test');
    await page.getByRole('button', { name: 'Create Note' }).click();
    
    // Load the created note
    await page.getByRole('button', { name: 'Note #1' }).click();
    
    // Enter edit mode
    await page.getByRole('button', { name: 'Edit' }).click();
    
    const characterCounter = page.locator('p.text-xs.text-gray-500').filter({ hasText: '/ 5000' });
    const originalContent = 'Original content for editing test.';
    await expect(characterCounter).toHaveText(`${originalContent.length} / 5000`);
    
    // Modify the content
    const bodyTextarea = page.getByRole('textbox', { name: 'Body' });
    await bodyTextarea.fill('Modified content for testing character counter in edit mode.');
    
    const newContent = 'Modified content for testing character counter in edit mode.';
    await expect(characterCounter).toHaveText(`${newContent.length} / 5000`);
  });

  test('should handle empty body field correctly', async ({ page }) => {
    const bodyTextarea = page.getByRole('textbox', { name: 'Body' });
    const characterCounter = page.locator('p.text-xs.text-gray-500').filter({ hasText: '/ 5000' });
    
    // Fill with text first
    await bodyTextarea.fill('Some text');
    await expect(characterCounter).toHaveText('9 / 5000');
    
    // Clear the text
    await bodyTextarea.fill('');
    await expect(characterCounter).toHaveText('0 / 5000');
  });

  test('should persist character count during form validation errors', async ({ page }) => {
    const bodyTextarea = page.getByRole('textbox', { name: 'Body' });
    const createButton = page.getByRole('button', { name: 'Create Note' });
    const characterCounter = page.locator('p.text-xs.text-gray-500').filter({ hasText: '/ 5000' });
    
    // Fill only body (missing required title)
    await bodyTextarea.fill('Body content without title should maintain character count.');
    const expectedCount = 'Body content without title should maintain character count.'.length;
    await expect(characterCounter).toHaveText(`${expectedCount} / 5000`);
    
    // Try to submit (should fail validation)
    await createButton.click();
    
    // Character counter should still show the correct count
    await expect(characterCounter).toHaveText(`${expectedCount} / 5000`);
  });

  test('should display character counter styling correctly', async ({ page }) => {
    const characterCounter = page.locator('p.text-xs.text-gray-500').filter({ hasText: '/ 5000' });
    
    // Verify the counter element has the correct CSS classes
    await expect(characterCounter).toHaveClass(/text-xs/);
    await expect(characterCounter).toHaveClass(/text-gray-500/);
    await expect(characterCounter).toHaveClass(/dark:text-gray-400/);
    await expect(characterCounter).toHaveClass(/mt-1/);
  });
});