import { test, expect } from '@playwright/test';

test('should display the new description and clear all button', async ({ page }) => {
  await page.goto('http://localhost:5175');

  // Check if the new description is present
  await expect(page.locator('p:text-is("Create and manage notes. Your notes are stored locally.")')).toBeVisible();

  // Create a note to ensure there are notes to clear
  await page.fill('input#note-title', 'Test Note');
  await page.fill('textarea#note-body', 'This is a test note.');
  await page.fill('input#note-tags', 'test, note');
  await page.click('button:text-is("Create Note")');

  // Wait for the note to be created and displayed
  await page.waitForSelector('button:text-is("Note #1")');

  // Check if the clear all button is present
  await expect(page.locator('button:text-is("Clear all")')).toBeVisible();

  // Click the clear all button
  await page.click('button:text-is("Clear all")');

  // Confirm that the notes list is empty
  await expect(page.locator('p:text-is("No notes yet")')).toBeVisible();
});