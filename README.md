## Diagnostic Report Browser

Internal Streamlit tool for browsing pre-diagnostic users, their sessions, session transcripts, and matched WhatsApp feedback.

### Run

```bash
streamlit run main.py
```

### Environment

Set `DATABASE_URL` before starting the app.

Optional S3 variables enable audio links in the UI.

### Layout

- `main.py`: Streamlit app
- `scripts/`: data preparation helpers
- `data/exports/`: raw CSV exports and split session folders
- `data/whatsapp/`: WhatsApp exports, unzipped chat media, and normalized feedback CSV
- `data/agents/raw_sessions/`: downloaded agent session artifacts
