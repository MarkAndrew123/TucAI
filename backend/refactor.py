import os

file_path = "frontend/src/App.jsx"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Import HubModal
if "import HubModal" not in content:
    content = content.replace(
        "import axios from 'axios';",
        "import axios from 'axios';\nimport HubModal from './components/HubModal';"
    )

# 2. Add showHubModal state
if "const [showHubModal, setShowHubModal]" not in content:
    content = content.replace(
        "const [view, setView] = useState('landing');",
        "const [view, setView] = useState('landing');\n  const [showHubModal, setShowHubModal] = useState(false);"
    )

# 3. Update auth route
content = content.replace(
        "setView('library'); // Take user to library",
        "setView('app'); // Take user straight to chat"
    )

# 4. Update Landing page Go to Studio
content = content.replace(
    "onClick={() => setView('library')}",
    "onClick={() => setView('app')}"
)

# 5. Update Profile Icon onClick in sidebar-footer
content = content.replace(
    "className=\"sidebar-footer\" onClick={handleLogout}",
    "className=\"sidebar-footer\" onClick={() => setShowHubModal(true)}"
)

# 6. Inject <HubModal /> right before the last closing div of app-layout
hub_modal_injection = """
        {showHubModal && (
          <HubModal 
            user={user}
            localVideos={localVideos}
            sessions={sessions}
            onClose={() => setShowHubModal(false)}
            onSelectVideo={(vid) => {
              setFile({ name: vid });
              setShowHubModal(false);
            }}
            onSelectSession={(sid) => {
              handleSessionSelect(sid);
              setShowHubModal(false);
            }}
            onLogout={handleLogout}
            onInitiatePayment={handleInitiatePayment}
          />
        )}
      </div>
"""
# Replace the end of app-layout
content = content.replace(
    "        </footer>\n\n        {showVideoModal && (",
    hub_modal_injection + "\n        </footer>\n\n        {showVideoModal && ("
)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("Refactoring complete.")
