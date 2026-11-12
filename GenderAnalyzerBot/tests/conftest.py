import os
import sys
import tempfile

# Make `modules` importable and keep every test run away from the real database / session files.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.environ["DB_PATH"] = os.path.join(tempfile.mkdtemp(prefix="gender-tests-"), "members.db")
os.environ.setdefault("GEMINI_API_KEY", "test-key-not-real")
os.environ.setdefault("API_ID", "12345")
os.environ.setdefault("API_HASH", "0123456789abcdef0123456789abcdef")
