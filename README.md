# A-GTAAM

DEM analysis and modification desktop app.

```
backend/    FastAPI backend: all the maths, data and file handling
frontend/   PyQt6 desktop GUI (just calls the backend)
```

## Run it (Windows)

You need Python 3.13 and Git.

```powershell
git clone https://github.com/asifmarwatlab/GTAAM.git
cd GTAAM

# 1. backend: its own virtual environment (the GUI starts it for you)
cd backend
py -3.13 -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
cd ..

# 2. frontend: install the GUI packages with your normal Python
cd frontend
py -m pip install -r requirements.txt

# 3. start the app
cd frontend
py main.py
```

Do not activate the backend's virtual environment before step 3. The GUI finds the
`backend` folder next to `frontend` and starts the backend by itself. To use a backend
somewhere else, write its path in `frontend/frontend/backend_dir.txt`.

The bottom bar of the window shows "Backend connected" when everything is working.
If the backend does not start, see `frontend/frontend/backend.log`.

## Where things live

* Backend: `routes/` (URLs), `schemas/` (request/response shapes), `services/`
  (the function a route calls), `core/` (the maths). See `backend/docs/`.
* Frontend: one folder per ribbon tab under `frontend/frontend/`, and `ui/` for the window.
  A tool in the GUI only reads the panel values, calls the backend, and shows the answer.
