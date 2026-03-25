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
            - textbox "Title" [ref=e14]: Copy Test
          - generic [ref=e15]:
            - generic [ref=e16]: Body
            - textbox "Body" [ref=e17]: This is the body to copy
          - generic [ref=e18]:
            - generic [ref=e19]: Tags (comma-separated)
            - textbox "Tags (comma-separated)" [ref=e20]:
              - /placeholder: tag1, tag2, tag3
              - text: copy
          - button "Create Note" [ref=e22]
      - generic [ref=e23]:
        - generic [ref=e24]:
          - heading "Your Notes (1)" [level=3] [ref=e25]
          - 'button "Note #1" [ref=e27]'
        - generic [ref=e28]:
          - generic [ref=e29]:
            - heading "Note Details" [level=3] [ref=e30]
            - button "Edit" [ref=e31]
            - button "Copy" [active] [ref=e32]
          - generic [ref=e33]:
            - paragraph [ref=e34]: "ID: 1"
            - paragraph [ref=e35]: "Title: Copy Test"
            - paragraph [ref=e36]: "Body: This is the body to copy"
            - paragraph [ref=e37]: "Tags: copy"
            - paragraph [ref=e38]: "Archived: No"
            - paragraph [ref=e39]: "Updated: 3/25/2026, 10:23:25 AM"
```