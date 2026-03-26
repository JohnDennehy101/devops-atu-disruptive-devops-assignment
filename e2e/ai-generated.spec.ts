import { test, expect } from '@playwright/test'

test.describe('Note Taking App - Clear All Functionality', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
  })

  test('should not show "Clear all" button when no notes exist', async ({ page }) => {
    // Verify the clear all button is not visible when no notes exist
    await expect(page.getByRole('button', { name: 'Clear all' })).not.toBeVisible()
    
    // Verify the notes count shows 0
    await expect(page.getByRole('heading', { name: 'Your Notes (0)' })).toBeVisible()
    
    // Verify "No notes yet" message is shown
    await expect(page.getByText('No notes yet')).toBeVisible()
  })

  test('should show "Clear all" button when notes exist', async ({ page }) => {
    // Create a test note
    await page.getByRole('textbox', { name: 'Title' }).fill('Test Note')
    await page.getByRole('textbox', { name: 'Body' }).fill('Test body content')
    await page.getByRole('textbox', { name: 'Tags (comma-separated)' }).fill('test')
    await page.getByRole('button', { name: 'Create Note' }).click()

    // Verify the clear all button is visible
    await expect(page.getByRole('button', { name: 'Clear all' })).toBeVisible()
    
    // Verify the notes count shows 1
    await expect(page.getByRole('heading', { name: 'Your Notes (1)' })).toBeVisible()
    
    // Verify the note appears in the list
    await expect(page.getByRole('button', { name: 'Note #1' })).toBeVisible()
  })

  test('should clear all notes when "Clear all" button is clicked', async ({ page }) => {
    // Create multiple test notes
    const notes = [
      { title: 'First Note', body: 'First note body', tags: 'first, test' },
      { title: 'Second Note', body: 'Second note body', tags: 'second, test' },
      { title: 'Third Note', body: 'Third note body', tags: 'third, important' }
    ]

    for (const note of notes) {
      await page.getByRole('textbox', { name: 'Title' }).fill(note.title)
      await page.getByRole('textbox', { name: 'Body' }).fill(note.body)
      await page.getByRole('textbox', { name: 'Tags (comma-separated)' }).fill(note.tags)
      await page.getByRole('button', { name: 'Create Note' }).click()
    }

    // Verify all notes are created
    await expect(page.getByRole('heading', { name: 'Your Notes (3)' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Note #1' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Note #2' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Note #3' })).toBeVisible()

    // Click "Clear all" button
    await page.getByRole('button', { name: 'Clear all' }).click()

    // Verify all notes are cleared
    await expect(page.getByRole('heading', { name: 'Your Notes (0)' })).toBeVisible()
    await expect(page.getByText('No notes yet')).toBeVisible()
    await expect(page.getByRole('button', { name: 'Clear all' })).not.toBeVisible()
    
    // Verify no note buttons exist
    await expect(page.getByRole('button', { name: /Note #\d+/ })).not.toBeVisible()
  })

  test('should clear selected note and form fields when "Clear all" is clicked', async ({ page }) => {
    // Create a test note
    await page.getByRole('textbox', { name: 'Title' }).fill('Selected Note')
    await page.getByRole('textbox', { name: 'Body' }).fill('Selected note content')
    await page.getByRole('textbox', { name: 'Tags (comma-separated)' }).fill('selected, test')
    await page.getByRole('button', { name: 'Create Note' }).click()

    // Select the note to load it
    await page.getByRole('button', { name: 'Note #1' }).click()

    // Verify note details are displayed
    await expect(page.getByRole('heading', { name: 'Note Details' })).toBeVisible()
    await expect(page.getByText('Title: Selected Note')).toBeVisible()
    await expect(page.getByRole('textbox', { name: 'Title' })).toHaveValue('Selected Note')
    await expect(page.getByRole('textbox', { name: 'Body' })).toHaveValue('Selected note content')
    await expect(page.getByRole('textbox', { name: 'Tags (comma-separated)' })).toHaveValue('selected, test')

    // Click "Clear all" button
    await page.getByRole('button', { name: 'Clear all' }).click()

    // Verify selected note is cleared
    await expect(page.getByRole('heading', { name: 'Note Details' })).not.toBeVisible()
    
    // Verify form fields are cleared
    await expect(page.getByRole('textbox', { name: 'Title' })).toHaveValue('')
    await expect(page.getByRole('textbox', { name: 'Body' })).toHaveValue('')
    await expect(page.getByRole('textbox', { name: 'Tags (comma-separated)' })).toHaveValue('')
  })

  test('should exit editing mode when "Clear all" is clicked', async ({ page }) => {
    // Create a test note
    await page.getByRole('textbox', { name: 'Title' }).fill('Editable Note')
    await page.getByRole('textbox', { name: 'Body' }).fill('Content to edit')
    await page.getByRole('textbox', { name: 'Tags (comma-separated)' }).fill('edit, test')
    await page.getByRole('button', { name: 'Create Note' }).click()

    // Select and edit the note
    await page.getByRole('button', { name: 'Note #1' }).click()
    await page.getByRole('button', { name: 'Edit' }).click()

    // Verify we're in editing mode
    await expect(page.getByRole('heading', { name: 'Edit Note' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Save' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Cancel' })).toBeVisible()

    // Click "Clear all" button
    await page.getByRole('button', { name: 'Clear all' }).click()

    // Verify we're back in create mode
    await expect(page.getByRole('heading', { name: 'Create New Note' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Create Note' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Save' })).not.toBeVisible()
    await expect(page.getByRole('button', { name: 'Cancel' })).not.toBeVisible()
  })

  test('should persist cleared state after page reload', async ({ page }) => {
    // Create a test note
    await page.getByRole('textbox', { name: 'Title' }).fill('Persistent Note')
    await page.getByRole('textbox', { name: 'Body' }).fill('This should be cleared')
    await page.getByRole('button', { name: 'Create Note' }).click()

    // Verify note exists
    await expect(page.getByRole('heading', { name: 'Your Notes (1)' })).toBeVisible()

    // Clear all notes
    await page.getByRole('button', { name: 'Clear all' }).click()

    // Reload the page
    await page.reload()

    // Verify the cleared state persists
    await expect(page.getByRole('heading', { name: 'Your Notes (0)' })).toBeVisible()
    await expect(page.getByText('No notes yet')).toBeVisible()
    await expect(page.getByRole('button', { name: 'Clear all' })).not.toBeVisible()
  })

  test('should handle multiple create and clear cycles', async ({ page }) => {
    // First cycle: create notes and clear
    await page.getByRole('textbox', { name: 'Title' }).fill('Cycle 1 Note')
    await page.getByRole('textbox', { name: 'Body' }).fill('First cycle content')
    await page.getByRole('button', { name: 'Create Note' }).click()
    
    await expect(page.getByRole('heading', { name: 'Your Notes (1)' })).toBeVisible()
    await page.getByRole('button', { name: 'Clear all' }).click()
    await expect(page.getByRole('heading', { name: 'Your Notes (0)' })).toBeVisible()

    // Second cycle: create multiple notes and clear
    const secondCycleNotes = ['Note A', 'Note B']
    for (const title of secondCycleNotes) {
      await page.getByRole('textbox', { name: 'Title' }).fill(title)
      await page.getByRole('textbox', { name: 'Body' }).fill(`Body for ${title}`)
      await page.getByRole('button', { name: 'Create Note' }).click()
    }

    await expect(page.getByRole('heading', { name: 'Your Notes (2)' })).toBeVisible()
    await page.getByRole('button', { name: 'Clear all' }).click()
    await expect(page.getByRole('heading', { name: 'Your Notes (0)' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Clear all' })).not.toBeVisible()
  })
})