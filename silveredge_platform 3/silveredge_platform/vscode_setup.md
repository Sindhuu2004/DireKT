# How to Run SilverEdge Project in VS Code

Follow these steps to get both the backend and frontend running simultaneously in your VS Code environment.

## 1. Open the Project
Open the `silveredge_platform` folder in VS Code.

## 2. Set Up the Backend
1. Open a new Terminal (**Ctrl+`**).
2. Navigate to the backend directory:
   ```bash
   cd silveredge_platform/backend
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Start the FastAPI server:
   ```bash
   python -m uvicorn main:app --reload --port 8000
   ```
   *The backend is now running at `http://localhost:8000`.*

## 3. Set Up the Frontend (Split Terminal)
1. In the same terminal window, click the **Split Terminal** button (the icon with two panels) or press **Ctrl+Shift+5**.
2. In the new terminal pane, navigate to the frontend directory:
   ```bash
   cd silveredge_platform/frontend
   ```
3. Install dependencies:
   ```bash
   npm install
   ```
4. Start the Vite dev server:
   ```bash
   npm run dev
   ```
   *The frontend is now running at `http://localhost:3000`.*

## 4. Automated Startup (Recommended)
You can start both the backend and frontend simultaneously using VS Code's **Run and Debug** feature:
1. Press **F5** or click the **Play** button in the "Run and Debug" sidebar.
2. Select **Full Stack (Backend + Frontend)** from the dropdown.
3. This will automatically:
   - Create a Python virtual environment and install backend dependencies.
   - Start the FastAPI server on port 8000.
   - Install frontend dependencies.
   - Start the Vite dev server on port 3000.
   - Open your browser to the platform dashboard.

## 5. Access the Platform
- Open your browser and go to: [http://localhost:3000](http://localhost:3000)
- You can now Sign Up or Log In to start trading!

---

### Useful VS Code Extensions
- **Python**: For better code highlighting and linting in `main.py`.
- **ES7+ React/Redux/React-Native snippets**: For React development.
- **REST Client**: To test the API endpoints directly from VS Code.
