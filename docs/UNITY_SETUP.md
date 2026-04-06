# Unity Setup Guide - Liberty Twin 3D Environment

## Which Editor to Use?

You have **3 options** to edit and view the 3D environment:

### Option 1: Unity Editor (Recommended)
**Download:** https://unity.com/download

**Steps:**
1. Download Unity Hub
2. Install Unity version **2022.3 LTS** (Long Term Support)
3. During installation, select:
   - Android/iOS Build Support (optional)
   - WebGL Build Support (optional)
   - Visual Studio Code integration (recommended)

**Pros:**
- Full 3D editor with real-time preview
- Drag-and-drop interface
- Visual scripting and debugging
- Best for learning

### Option 2: Visual Studio Code
**Download:** https://code.visualstudio.com/

**Extensions to install:**
- C# Dev Kit
- Unity Code Snippets
- Unity Tools

**Usage:**
- Edit C# scripts
- Syntax highlighting
- IntelliSense
- **Note:** Cannot view 3D scene, only code

### Option 3: JetBrains Rider
**Download:** https://www.jetbrains.com/rider/

**Best for:** Professional development
- Excellent Unity integration
- Advanced debugging
- Refactoring tools
- **Note:** Paid (free for students)

---

## Quick Setup Steps

### Step 1: Install Unity Hub

Unity Hub is a management application that lets you install different Unity editor versions and manage projects. It is available for download from the Unity website for both Windows and Mac.

### Step 2: Install Unity Editor

1. Open Unity Hub
2. Click "Installs" tab
3. Click "Install Editor"
4. Select version: **2022.3.x LTS**
5. Select modules (optional):
   - WebGL Build Support
   - Visual Studio Editor
6. Click "Install"

### Step 3: Create Project

1. In Unity Hub, click "Projects" tab
2. Click "New Project"
3. Select **"3D (URP)"** template
4. Name: "LibertyTwin"
5. Location: Choose your folder
6. Click "Create Project"

### Step 4: Add Scripts

1. In Unity, look for "Project" window (bottom)
2. Right-click, Create, Folder, Name it "Scripts"
3. Right-click, Create, Folder, Name it "Environment"
4. Drag the file `SimpleLibraryRoom.cs` into `Scripts/Environment` folder

### Step 5: Create the Scene

1. In "Hierarchy" window (left), right-click
2. Select "Create Empty"
3. Name it "LibraryRoom"
4. Drag `SimpleLibraryRoom.cs` script onto "LibraryRoom" object
5. Press **Play** button at top

### Step 6: View the Room

**Navigation controls:**
- **Right-click + drag**: Rotate view
- **Middle-click + drag**: Pan view
- **Scroll**: Zoom in/out
- **Alt + left-click**: Orbit around selection

**Game view:**
- Click "Game" tab (next to "Scene")
- Shows what the game looks like when running

---

## Project Files Created

```
unity/
├── Assets/
│   ├── Scripts/
│   │   └── Environment/
│   │       └── SimpleLibraryRoom.cs    # Creates the room
│   ├── Scenes/                          # Your saved scenes
│   └── Materials/                       # Colors and textures
├── Packages/
│   └── manifest.json                    # Unity packages
└── ProjectSettings/                     # Unity configuration
```

---

## What You'll See

When you press Play, the script will create:

1. **Floor**: Gray floor (20m x 16m)
2. **Walls**: 4 walls around the room
3. **8 Study Areas**:
   - 4 on the left side
   - 4 on the right side
   - Each has: 1 table (brown) + 1 chair (blue)
4. **Central Aisle**: Space for walking

---

## Next Steps

1. **Save the scene**:
   - File, Save Scene
   - Name: "LibrarySimulation"
   - Location: Assets/Scenes/

2. **Customize**:
   - Select "LibraryRoom" in Hierarchy
   - In Inspector (right), change:
     - Room Width/Length
     - Number of study areas
     - Colors

3. **Add more features**:
   - Create student prefabs
   - Add virtual sensor head
   - Set up MQTT connection

---

## Troubleshooting

**Problem: Scripts not showing**
- Solution: Make sure file has `.cs` extension
- Try: Right-click, Refresh in Project window

**Problem: Nothing appears when pressing Play**
- Check: Is script attached to GameObject?
- Check: Are there any console errors? (Window, General, Console)

**Problem: Camera view is wrong**
- Click on "Main Camera" in Hierarchy
- Move it with transform tools
- Or: GameObject, Align View to Selected

---

## Recommended Workflow

1. **Unity Editor**: For 3D scene editing
2. **VS Code**: For C# script editing (it's free and lightweight)
3. **Unity Play Mode**: To test changes instantly

---

## Need Help?

- Unity Documentation: https://docs.unity3d.com/
- Unity Learn (free tutorials): https://learn.unity.com/
- YouTube: Search "Unity 3D beginner tutorial"

**Start with Unity Editor!** It's the best way to learn and visualize your 3D environment.
