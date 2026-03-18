# Page snapshot

```yaml
- main [ref=e4]:
  - generic [ref=e5]:
    - heading "Note Taking App" [level=1] [ref=e6]
    - generic [ref=e7]:
      - generic [ref=e9]:
        - heading "Create New Note" [level=2] [ref=e10]
        - generic [ref=e11]:
          - generic [ref=e12]:
            - generic [ref=e13]: Title
            - textbox "Title" [ref=e14]
          - generic [ref=e15]:
            - generic [ref=e16]: Body
            - textbox "Body" [ref=e17]
          - generic [ref=e18]:
            - generic [ref=e19]: Tags (comma-separated)
            - textbox "Tags (comma-separated)" [ref=e20]:
              - /placeholder: tag1, tag2, tag3
          - button "Create Note" [ref=e22]
      - generic [ref=e24]:
        - heading "Your Notes (0)" [level=3] [ref=e25]
        - textbox "Filter by tag" [active] [ref=e26]: test
        - paragraph [ref=e28]: No notes yet
```