import { test, expect } from '@playwright/test';

test('should update note successfully', async ({ page }) => {
  await page.goto('http://localhost:5175');

  // Assuming there's a note to edit, we first need to create one
  await page.getByLabel('Title').fill('Test Note');
  await page.getByLabel('Body').fill('This is a test note.');
  await page.getByLabel('Tags (comma-separated)').fill('test, playwright');
  await page.getByRole('button', { name: /create note/i }).click();

  // Wait for the note to be created and displayed in the list
  await page.getByRole('button', { name: /note #\d+/i }).first().waitFor();

  // Click on the created note to select it
  const noteButton = await page.getByRole('button', { name: /note #\d+/i }).first();
  await noteButton.click();

  // Wait for the note details to be loaded
  await page.getByText('Note Details').waitFor();

  // Click on the edit button
  await page.getByRole('button', { name: /edit/i }).click();

  // Update the note
  await page.getByLabel('Title').fill('Updated Test Note');
  await page.getByLabel('Body').fill('This is an updated test note.');
  await page.getByLabel('Tags (comma-separated)').fill('updated, test, playwright');
  await page.getByRole('button', { name: /save/i }).click();

  // Wait for the update to complete and check if the note details are updated
  await page.getByText('Title: Updated Test Note').waitFor();
  await expect(page.getByText('Title: Updated Test Note')).toBeVisible();
  await expect(page.getByText('Body: This is an updated test note.')).toBeVisible();
  await expect(page.getByText('Tags: updated, test, playwright')).toBeVisible();
});