# Page snapshot

```yaml
- main [ref=e4]:
  - generic [ref=e5]:
    - heading "Note Taking App" [level=1] [ref=e6]
    - paragraph [ref=e7]: Create and manage notes. Your notes are stored locally.
    - generic [ref=e8]:
      - generic [ref=e10]:
        - heading "Edit Note" [level=2] [ref=e11]
        - generic [ref=e12]:
          - generic [ref=e13]:
            - generic [ref=e14]: Title
            - textbox "Title" [ref=e15]: Test Note
          - generic [ref=e16]:
            - generic [ref=e17]: Body
            - textbox "Body" [ref=e18]: Test Body
          - generic [ref=e19]:
            - generic [ref=e20]: Tags (comma-separated)
            - textbox "Tags (comma-separated)" [ref=e21]:
              - /placeholder: tag1, tag2, tag3
              - text: test
          - generic [ref=e22]:
            - button "Save" [ref=e23]
            - button "Cancel" [ref=e24]
            - button "Delete" [active] [ref=e25]
      - generic [ref=e27]:
        - generic [ref=e28]:
          - heading "Your Notes (1)" [level=3] [ref=e29]
          - button "Clear all" [ref=e30]
        - 'button "Note #1" [ref=e32]'
```