# Blood Donor and Blood Stock Management System

## Setup Instructions for VS Code
1. Open this folder in VS Code.
2. Open Terminal (`Ctrl + ~`).
3. Create a virtual environment: `python -m venv venv`
4. Activate it:
   - Windows: `venv\Scripts\activate`
   - Mac/Linux: `source venv/bin/activate`
5. Install packages: `pip install -r requirements.txt`
6. Open MySQL Workbench, execute the `database.sql` script to create tables and data.
7. Update `config.py` with your MySQL `DB_PASSWORD`.
8. Run the app: `python app.py`
9. Open browser at `http://127.0.0.1:5000`
10. Login with Username: `admin`, Password: `admin123`