"""Static reference of every real UI feature in this dashboard.

This is the LLM's general-purpose fallback for "how do I / where is / what
does X do" questions that aren't common enough to warrant a dedicated
navigation_guide.py template. It is concatenated into the LLM instructions
as fixed ground truth (see llm_caller.py) — the model is told never to
invent a button, menu, or step that isn't listed here.

Keep this in sync with layout.py, the same discipline navigation_guide.py
already follows. When a UI feature changes or a new one ships, update the
matching bullet here; only add a bespoke navigation_guide.py template on top
of this if the feature is expected to be a very high-frequency question.
"""

SITE_KNOWLEDGE = """
- Login/signup/forgot-password: a full-screen gate covers the whole site until the user signs in. "Forgot password?" leads to a self-service reset using a saved security question — no email needed.
- Header, top-left: a ☰ menu button opens the "Navigation" panel with four items — "Custom Reports" is fully functional (see below); "Publication", "Data Sources", and "Source Code" are placeholders that are visible but do not currently do anything when clicked.
- Top bar: a "Category" dropdown selects which indicator category colors the map (or "Overall MHVI-M Score").
- Custom Report Builder (☰ menu → "Custom Reports"): lets a user build their own multi-section report. Click "+ Add Element" to add a section; for each one choose a type (Line Graph, Data Table, or Index Breakdown Table), one or more municipalities, a category, an indicator, and optionally Normalize (rescale 0-100) and/or Forecast (adds a projected trend line). Add as many elements as wanted, then click "Export to PDF" — this opens the browser's native print dialog (choose "Save as PDF" there); it is not a server-generated file.
- Map + right side panel: clicking any municipality on the map opens a side panel with that municipality's score and a trend graph. The panel has its own Category/Indicator dropdowns (primary and an optional secondary overlay), the same Normalize/Forecast toggles, an "Index Breakdown" showing which indicators have data vs. are missing, and an indicators table where each row has a "Plot" button to add it to the graph.
- Settings menu (⚙, fixed top-right corner — separate from the ☰ menu): shows the signed-in email, and has Change password, Security question, "🛟 Report an issue" (opens the support ticket form), and Sign out.
- Report an issue / support ticket: choose a category (Technical, Account, Data, Other), write a subject and a description, then Submit. A team member follows up by email; there is no live chat support.
- Data Dictionary: this feature is not currently available to users — say so plainly if asked, do not describe a way to open it.
- The AI chat widget (this chat): a launcher button bottom-left opens a resizable popup. Its "⋮" menu has: a 🌐 button to switch the chat language instantly, "Chat History" (search/rename/delete past conversations), "＋ New Chat", "⛶ Fit Window" to resize, and "Download Chat PDF" (the full conversation transcript). Typed slash-commands also work: /new (new chat), /spanish or /english (switch language), /delete (erase all chat history, asks to confirm first), /cancel, and /name <name> to set a preferred name.
- There are three separate "download as PDF" features — do not confuse them: (1) chat menu "Download Chat PDF" downloads the whole conversation transcript; (2) asking this chat to "generate a report for [municipality]" produces a single AI-written narrative PDF for one municipality, with a "Download report" button in that reply; (3) the Custom Report Builder's "Export to PDF" (above) is a browser print-to-PDF of a report the user builds themselves with their own chosen graphs/tables.
""".strip()
