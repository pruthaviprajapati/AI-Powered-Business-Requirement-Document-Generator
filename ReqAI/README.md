# ReqAI – AI Powered Business Requirement Document Generator

**ReqAI** automates Software Requirement Engineering by recording meetings, transcribing conversations, extracting requirements using Machine Learning, and generating professional Business Requirement Documents (BRDs).

---

## 🚀 Project Overview

ReqAI transforms the traditional requirement gathering process:
- **Before**: Manual note-taking → Manual document writing → Time-consuming
- **After**: Record meeting → AI processes audio → Auto-generate BRD

---

## 📋 Development Phases

### ✅ Phase 1 – Foundation (Current)
- Complete FastAPI backend
- SQLite database with SQLAlchemy ORM
- JWT authentication
- User registration & login
- Project management (CRUD)
- Meeting management (CRUD)
- Modern responsive frontend (HTML/CSS/JS/Bootstrap)

### 🔄 Phase 2 – Speech & NLP (Next)
- Audio file upload
- Speech-to-text (faster-whisper)
- Speaker identification (pyannote.audio)
- NLP processing (spaCy)
- Requirement extraction

### 🤖 Phase 3 – Machine Learning
- Fine-tuned DistilBERT requirement classifier
- Semantic duplicate detection (Sentence Transformers)
- Requirement categorization

### 🧠 Phase 4 – AI Validation & Generation
- Requirement validation (Groq API)
- Follow-up question generation
- Professional BRD generation
- DOCX export (python-docx)

---

## 🛠 Technology Stack

### Backend
- **Framework**: FastAPI
- **Database**: SQLite + SQLAlchemy ORM
- **Auth**: JWT (python-jose) + bcrypt password hashing
- **Validation**: Pydantic

### Frontend
- **Core**: HTML5, CSS3, JavaScript (ES6)
- **UI Framework**: Bootstrap 5
- **Icons**: Font Awesome 6

### Future AI Stack (Phase 2+)
- faster-whisper (speech recognition)
- pyannote.audio (speaker diarization)
- spaCy (NLP)
- DistilBERT (requirement classification)
- Sentence Transformers (duplicate detection)
- Groq API (LLM for validation & generation)
- python-docx (document export)

---

## 📁 Project Structure

```
ReqAI/
├── backend/
│   ├── app/
│   │   ├── routers/         # API endpoints
│   │   ├── models/          # SQLAlchemy ORM models
│   │   ├── schemas/         # Pydantic request/response schemas
│   │   ├── services/        # Business logic layer
│   │   ├── database/        # Database session & engine
│   │   ├── middleware/      # Request logging, etc.
│   │   ├── auth/            # JWT dependencies
│   │   ├── core/            # Config, security, logging
│   │   ├── utils/           # Helper functions
│   │   └── main.py          # FastAPI application entry
│   ├── uploads/             # Audio file storage (Phase 2)
│   ├── generated/           # Generated BRD files (Phase 4)
│   ├── logs/                # Application logs
│   ├── future_ml/           # ML models (Phase 3)
│   ├── future_nlp/          # NLP models (Phase 2)
│   ├── future_speech/       # Speech models (Phase 2)
│   ├── requirements.txt
│   ├── .env.example
│   └── .env
├── frontend/
│   ├── assets/
│   │   ├── css/             # Theme & styles
│   │   ├── js/              # Config, auth, API, UI utilities
│   │   └── images/
│   ├── pages/               # HTML pages
│   │   ├── login.html
│   │   ├── register.html
│   │   ├── dashboard.html
│   │   ├── projects.html
│   │   ├── meetings.html
│   │   ├── profile.html
│   │   └── settings.html
│   └── index.html
├── docs/
├── .gitignore
└── README.md
```

---

## 🚀 Installation & Setup

### Prerequisites
- Python 3.8+
- pip
- Live Server extension (VS Code) or any HTTP server

### Backend Setup

1. **Clone the repository**
   ```bash
   git clone <your-repo-url>
   cd ReqAI/backend
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   venv\Scripts\activate      # Windows
   source venv/bin/activate  # macOS/Linux
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env and set your SECRET_KEY
   ```

5. **Run the application**
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

   Server will start at: `http://127.0.0.1:8000`
   API docs at: `http://127.0.0.1:8000/api/docs`

### Frontend Setup

1. **Open frontend folder**
   ```bash
   cd ../frontend
   ```

2. **Serve with Live Server**
   - Right-click `index.html` → "Open with Live Server"
   - Or use any static file server on port 5500

3. **Access the application**
   - Frontend: `http://127.0.0.1:5500`
   - Login page: `http://127.0.0.1:5500/pages/login.html`

---

## 📖 Usage Guide

### 1. Register Account
- Navigate to register page
- Enter full name, email, username, password
- Account created ✓

### 2. Login
- Use username or email + password
- JWT tokens stored in localStorage
- Redirects to dashboard

### 3. Create Project
- Go to Projects page
- Click "New Project"
- Fill in project details, client info
- Save

### 4. Create Meeting
- Go to Meetings page
- Click "New Meeting"
- Select project, add title, date, participants
- Save

### 5. Manage Data
- View all projects & meetings on dashboard
- Edit or delete any item
- Update profile & change password

---

## 🔐 Security Features

- ✅ Password hashing with bcrypt
- ✅ JWT access tokens (30 min expiry)
- ✅ JWT refresh tokens (7 day expiry)
- ✅ Protected API endpoints
- ✅ CORS configuration
- ✅ SQL injection protection (ORM)
- ✅ Request validation (Pydantic)
- ✅ Soft-delete architecture

---

## 🗄 Database Schema

### Users
```sql
id, full_name, email, username, hashed_password,
is_verified, role, bio, profile_picture,
created_at, updated_at, is_active
```

### Projects
```sql
id, name, description, client_name, client_email,
status, owner_id, created_at, updated_at, is_active
```

### Meetings
```sql
id, title, description, meeting_date, duration_minutes,
participants, project_id, audio_file, transcript,
processing_status, generated_brd, brd_file_path,
requirements_count, follow_up_questions,
created_at, updated_at, is_active
```

---

## 🎯 API Endpoints

### Authentication
- `POST /api/v1/auth/register` – Register new user
- `POST /api/v1/auth/login` – Login and get tokens
- `POST /api/v1/auth/logout` – Logout
- `POST /api/v1/auth/refresh` – Refresh access token
- `GET /api/v1/auth/me` – Get current user

### Projects
- `GET /api/v1/projects` – List all projects
- `POST /api/v1/projects/` – Create project
- `GET /api/v1/projects/{id}` – Get project details
- `PUT /api/v1/projects/{id}` – Update project
- `DELETE /api/v1/projects/{id}` – Delete project

### Meetings
- `GET /api/v1/meetings` – List all meetings
- `POST /api/v1/meetings/` – Create meeting
- `GET /api/v1/meetings/{id}` – Get meeting details
- `PUT /api/v1/meetings/{id}` – Update meeting
- `DELETE /api/v1/meetings/{id}` – Delete meeting

### Users
- `GET /api/v1/users/profile` – Get user profile
- `PUT /api/v1/users/profile` – Update profile
- `PUT /api/v1/users/password` – Change password
- `DELETE /api/v1/users/account` – Deactivate account

### Health
- `GET /health` – Health check

---

## 🎨 UI Features

- ✅ Modern dark sidebar layout
- ✅ Fully responsive (mobile, tablet, desktop)
- ✅ Dashboard with statistics cards
- ✅ Data tables with search & pagination
- ✅ Modal forms for create/edit
- ✅ Toast notifications
- ✅ Loading overlays
- ✅ Status badges
- ✅ Professional color theme

---

## 🔮 Future Enhancements (Phase 2+)

### Phase 2 Features
- Audio file upload & storage
- Real-time transcription display
- Speaker identification visualization
- NLP-based sentence extraction
- Requirement candidate highlighting

### Phase 3 Features
- ML model training interface
- Requirement category statistics
- Duplicate detection dashboard
- Requirement knowledge base
- Similarity score visualization

### Phase 4 Features
- One-click BRD generation
- DOCX template customization
- Follow-up question interface
- Requirement completeness scoring
- Export to multiple formats

---

## 🐛 Troubleshooting

### Backend won't start
- Check `.env` file exists
- Verify all dependencies installed: `pip list`
- Check port 8000 is not in use
- View logs in `backend/logs/reqai.log`

### Frontend can't connect to API
- Verify backend is running on port 8000
- Check CORS settings in `.env`
- Verify `CONFIG.API_BASE_URL` in `config.js`
- Check browser console for errors

### Database issues
- Delete `reqai.db` to reset database
- Restart backend to recreate tables
- Check SQLAlchemy logs when `DEBUG=true`

---

## 🤝 Contributing

Phase 1 is complete. Contributions for Phase 2+ are welcome:
1. Fork the repository
2. Create feature branch: `git checkout -b feature/phase2-audio`
3. Commit changes: `git commit -m 'Add audio upload'`
4. Push to branch: `git push origin feature/phase2-audio`
5. Submit pull request

---

## 📄 License

This project is for educational purposes. Modify as needed.

---

## 👤 Author

**Your Name**
- Project: ReqAI
- Architecture: Multi-phase AI-powered requirement engineering
- Contact: your-email@example.com

---

## 🙏 Acknowledgments

- FastAPI documentation
- Bootstrap team
- Font Awesome icons
- HuggingFace transformers
- Groq API

---

**Phase 1 Complete ✓**  
Next: Phase 2 – Audio Upload & Speech Recognition
