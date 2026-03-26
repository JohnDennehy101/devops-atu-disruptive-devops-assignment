import { test, expect } from '@playwright/test';

test.describe('Clear All Notes Functionality', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('should display Clear all button only when notes exist', async ({ page }) => {
    // Initially no notes, Clear all button should not be visible
    await expect(page.getByRole('button', { name: 'Clear all' })).not.toBeVisible();
    await expect(page.getByRole('heading', { name: 'Your Notes (0)' })).toBeVisible();

    // Create a note
    await page.getByRole('textbox', { name: 'Title' }).fill('Test Note');
    await page.getByRole('textbox', { name: 'Body' }).fill('Test Body');
    await page.getByRole('button', { name: 'Create Note' }).click();

    // Now Clear all button should be visible
    await expect(page.getByRole('button', { name: 'Clear all' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Your Notes (1)' })).toBeVisible();
  });

  test('should clear all notes and reset form state', async ({ page }) => {
    // Create multiple notes
    const notes = [
      { title: 'Note 1', body: 'Body 1', tags: 'tag1, test' },
      { title: 'Note 2', body: 'Body 2', tags: 'tag2, example' },
      { title: 'Note 3', body: 'Body 3', tags: 'tag3' }
    ];

    for (const note of notes) {
      await page.getByRole('textbox', { name: 'Title' }).fill(note.title);
      await page.getByRole('textbox', { name: 'Body' }).fill(note.body);
      await page.getByRole('textbox', { name: 'Tags (comma-separated)' }).fill(note.tags);
      await page.getByRole('button', { name: 'Create Note' }).click();
    }

    // Verify notes were created
    await expect(page.getByRole('heading', { name: 'Your Notes (3)' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Note #1' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Note #2' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Note #3' })).toBeVisible();

    // Click Clear all button
    await page.getByRole('button', { name: 'Clear all' }).click();

    // Verify all notes are cleared
    await expect(page.getByRole('heading', { name: 'Your Notes (0)' })).toBeVisible();
    await expect(page.getByText('No notes yet')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Clear all' })).not.toBeVisible();
    await expect(page.getByRole('button', { name: 'Note #1' })).not.toBeVisible();
    await expect(page.getByRole('button', { name: 'Note #2' })).not.toBeVisible();
    await expect(page.getByRole('button', { name: 'Note #3' })).not.toBeVisible();

    // Verify form is cleared
    await expect(page.getByRole('textbox', { name: 'Title' })).toHaveValue('');
    await expect(page.getByRole('textbox', { name: 'Body' })).toHaveValue('');
    await expect(page.getByRole('textbox', { name: 'Tags (comma-separated)' })).toHaveValue('');
    
    // Verify form is back to create mode
    await expect(page.getByRole('heading', { name: 'Create New Note' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Create Note' })).toBeVisible();
  });

  test('should clear notes when in editing mode', async ({ page }) => {
    // Create a note
    await page.getByRole('textbox', { name: 'Title' }).fill('Test Note');
    await page.getByRole('textbox', { name: 'Body' }).fill('Test Body');
    await page.getByRole('button', { name: 'Create Note' }).click();

    // Load the note for viewing
    await page.getByRole('button', { name: 'Note #1' }).click();
    
    // Wait for note details to load
    await expect(page.getByText('Note Details')).toBeVisible();
    
    // Start editing
    await page.getByRole('button', { name: 'Edit' }).click();
    
    // Verify we're in edit mode
    await expect(page.getByRole('heading', { name: 'Edit Note' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Save' })).toBeVisible();
    
    // Click Clear all while in edit mode
    await page.getByRole('button', { name: 'Clear all' }).click();

    // Verify everything is cleared and back to create mode
    await expect(page.getByRole('heading', { name: 'Create New Note' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Your Notes (0)' })).toBeVisible();
    await expect(page.getByText('No notes yet')).toBeVisible();
    await expect(page.getByText('Note Details')).not.toBeVisible();
    
    // Verify form is empty
    await expect(page.getByRole('textbox', { name: 'Title' })).toHaveValue('');
    await expect(page.getByRole('textbox', { name: 'Body' })).toHaveValue('');
    await expect(page.getByRole('textbox', { name: 'Tags (comma-separated)' })).toHaveValue('');
  });

  test('should persist cleared state after page reload', async ({ page }) => {
    // Create a note
    await page.getByRole('textbox', { name: 'Title' }).fill('Persistent Test');
    await page.getByRole('textbox', { name: 'Body' }).fill('This should be cleared');
    await page.getByRole('button', { name: 'Create Note' }).click();

    // Verify note exists
    await expect(page.getByRole('heading', { name: 'Your Notes (1)' })).toBeVisible();

    // Clear all notes
    await page.getByRole('button', { name: 'Clear all' }).click();

    // Reload page
    await page.reload();

    // Verify notes are still cleared after reload
    await expect(page.getByRole('heading', { name: 'Your Notes (0)' })).toBeVisible();
    await expect(page.getByText('No notes yet')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Clear all' })).not.toBeVisible();
  });

  test('should have correct styling for Clear all button', async ({ page }) => {
    // Create a note to show the Clear all button
    await page.getByRole('textbox', { name: 'Title' }).fill('Style Test');
    await page.getByRole('textbox', { name: 'Body' }).fill('Test styling');
    await page.getByRole('button', { name: 'Create Note' }).click();

    const clearAllButton = page.getByRole('button', { name: 'Clear all' });
    
    // Check button classes and styling
    await expect(clearAllButton).toHaveClass(/text-sm/);
    await expect(clearAllButton).toHaveClass(/text-red-600/);
    await expect(clearAllButton).toHaveClass(/hover:underline/);
    
    // Verify button is positioned correctly in the header
    const notesHeader = page.locator('.flex.justify-between.items-center').filter({ hasText: 'Your Notes' });
    await expect(notesHeader).toContainText('Your Notes (1)');
    await expect(notesHeader).toContainText('Clear all');
  });

  test('should work with notes that have no tags', async ({ page }) => {
    // Create note without tags
    await page.getByRole('textbox', { name: 'Title' }).fill('No Tags Note');
    await page.getByRole('textbox', { name: 'Body' }).fill('This note has no tags');
    await page.getByRole('button', { name: 'Create Note' }).click();

    // Create note with tags
    await page.getByRole('textbox', { name: 'Title' }).fill('Tagged Note');
    await page.getByRole('textbox', { name: 'Body' }).fill('This note has tags');
    await page.getByRole('textbox', { name: 'Tags (comma-separated)' }).fill('tag1, tag2');
    await page.getByRole('button', { name: 'Create Note' }).click();

    // Verify both notes exist
    await expect(page.getByRole('heading', { name: 'Your Notes (2)' })).toBeVisible();

    // Clear all notes
    await page.getByRole('button', { name: 'Clear all' }).click();

    // Verify all notes cleared regardless of tag presence
    await expect(page.getByRole('heading', { name: 'Your Notes (0)' })).toBeVisible();
    await expect(page.getByText('No notes yet')).toBeVisible();
  });
});