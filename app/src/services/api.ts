const STORAGE_KEY = "notes"
const NEXT_ID_KEY = "notes_next_id"

function getNotes(): Note[] {
  const raw = localStorage.getItem(STORAGE_KEY)
  if (!raw) return []
  try {
    return JSON.parse(raw) as Note[]
  } catch {
    return []
  }
}

function setNotes(notes: Note[]): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(notes))
}

function getNextId(): number {
  const raw = localStorage.getItem(NEXT_ID_KEY)
  const next = raw ? parseInt(raw, 10) : 1
  localStorage.setItem(NEXT_ID_KEY, String(next + 1))
  return next
}

export interface Note {
  id: number
  title: string
  body: string
  tags: string[]
  archived: boolean
  updated_at: string
  version: number
}

export interface CreateNoteInput {
  title: string
  body: string
  tags: string[]
}

export interface UpdateNoteInput {
  title: string
  body: string
  tags: string[]
  archived?: boolean
}

export const api = {
  createNote: async (input: CreateNoteInput): Promise<Note> => {
    const notes = getNotes()
    const id = getNextId()
    const now = new Date().toISOString()
    const note: Note = {
      id,
      title: input.title,
      body: input.body,
      tags: input.tags,
      archived: false,
      updated_at: now,
      version: 1,
    }
    notes.push(note)
    setNotes(notes)
    return note
  },

  getNote: async (id: number): Promise<Note> => {
    const notes = getNotes()
    const note = notes.find(n => n.id === id)
    if (!note) throw new Error(`Note not found: ${id}`)
    return note
  },

  updateNote: async (id: number, input: UpdateNoteInput): Promise<Note> => {
    const notes = getNotes()
    const index = notes.findIndex(n => n.id === id)
    if (index === -1) throw new Error(`Note not found: ${id}`)
    const existing = notes[index]
    const updated: Note = {
      ...existing,
      title: input.title,
      body: input.body,
      tags: input.tags,
      archived: input.archived ?? existing.archived,
      updated_at: new Date().toISOString(),
      version: existing.version + 1,
    }
    notes[index] = updated
    setNotes(notes)
    return updated
  },

  deleteNote: async (id: number): Promise<void> => {
    const notes = getNotes().filter(n => n.id !== id)
    setNotes(notes)
  },
}
