using UnityEngine;
using System.Collections.Generic;

public class ProfessionalLibrary : MonoBehaviour
{
    [Header("Room Dimensions")]
    public float roomWidth = 20f;
    public float roomLength = 16f;
    public float roomHeight = 4.0f;

    [Header("Display")]
    public bool showCeiling = true;

    [HideInInspector]
    public List<SeatInfo> allSeats = new List<SeatInfo>();
    private int seatCounter = 0;

    [System.Serializable]
    public class SeatInfo
    {
        public string seatId;
        public int zoneId;
        public Transform seatTransform;
    }

    Color floorGray = new Color(0.62f, 0.60f, 0.58f);
    Color ceilingWhite = new Color(0.94f, 0.94f, 0.93f);

    Color wallWhite = new Color(0.93f, 0.92f, 0.90f);
    Color wallBand = new Color(0.18f, 0.20f, 0.25f);

    Color partitionMaroon = new Color(0.55f, 0.18f, 0.22f);
    Color partitionFrame = new Color(0.88f, 0.86f, 0.82f);
    Color deskTopCream = new Color(0.85f, 0.80f, 0.72f);
    Color deskLeg = new Color(0.82f, 0.80f, 0.78f);

    Color chairPadMaroon = new Color(0.58f, 0.15f, 0.20f);
    Color chairMetal = new Color(0.30f, 0.30f, 0.32f);

    Color pillarWood = new Color(0.55f, 0.38f, 0.22f);
    Color pillarBase = new Color(0.48f, 0.33f, 0.20f);

    Color fanWhite = new Color(0.92f, 0.91f, 0.89f);
    Color fanBracket = new Color(0.75f, 0.74f, 0.72f);
    Color lightPanel = new Color(0.96f, 0.96f, 0.94f);
    Color lightFrame = new Color(0.85f, 0.85f, 0.83f);
    Color socketWhite = new Color(0.92f, 0.91f, 0.88f);

    Color windowGlass = new Color(0.70f, 0.82f, 0.92f, 0.35f);
    Color windowFrame = new Color(0.35f, 0.35f, 0.38f);
    Color doorColor = new Color(0.48f, 0.33f, 0.20f);
    Color exitGreen = new Color(0.15f, 0.65f, 0.22f);

    Color skyBlue = new Color(0.55f, 0.75f, 0.92f);
    Color groundGreen = new Color(0.35f, 0.52f, 0.28f);
    Color treeTrunk = new Color(0.40f, 0.28f, 0.18f);
    Color treeLeaves = new Color(0.25f, 0.50f, 0.22f);
    Color pathColor = new Color(0.72f, 0.68f, 0.60f);
    Color buildingColor = new Color(0.78f, 0.75f, 0.70f);

    Color sensorColor = new Color(0.32f, 0.32f, 0.36f);

    void Start() => BuildLibrary();

    [ContextMenu("Rebuild Library")]
    public void BuildLibrary()
    {
        var toDestroy = new List<GameObject>();
        for (int i = 0; i < transform.childCount; i++)
        {
            var child = transform.GetChild(i).gameObject;
            if (child.CompareTag("Player")) continue;
            toDestroy.Add(child);
        }
        foreach (var obj in toDestroy)
            DestroyImmediate(obj);

        allSeats.Clear();
        seatCounter = 0;

        CreateFloorAndCeiling();
        CreateWalls();
        CreateWindows();
        CreateDoors();
        CreatePillars();
        CreateCeilingLights();
        CreateACUnits();
        CreateStudyCubicles();
        CreateReferenceShelves();
        CreateAisleDetails();
        CreateRelaxationZone();
        CreateFrontDesk();
        CreateOutdoorScenery();
        CreateSensorMount();
        CreateSensorMonitor();
        CreateMiscDetails();

        Debug.Log($"[Liberty Twin] IIT ISM Style Library built: {roomWidth}x{roomLength}m, " +
                  $"{seatCounter} seats across 8 zones");
    }

    void CreateFloorAndCeiling()
    {
        GameObject p = new GameObject("Structure");
        p.transform.SetParent(transform);
        p.transform.localPosition = Vector3.zero;

        var floor = MakeBoxChild(p, "Floor",
            new Vector3(0, -0.05f, 0),
            new Vector3(roomWidth, 0.1f, roomLength), floorGray);
        AddCollider(floor);

        float halfW = roomWidth / 2f, halfL = roomLength / 2f;
        float tileSize = 0.6f;
        Color gridLine = new Color(0.56f, 0.54f, 0.52f);
        for (float x = -halfW; x <= halfW; x += tileSize)
        {
            MakeBoxChild(p, $"GridX_{x:F0}",
                new Vector3(x, 0.002f, 0),
                new Vector3(0.008f, 0.004f, roomLength), gridLine);
        }
        for (float z = -halfL; z <= halfL; z += tileSize)
        {
            MakeBoxChild(p, $"GridZ_{z:F0}",
                new Vector3(0, 0.002f, z),
                new Vector3(roomWidth, 0.004f, 0.008f), gridLine);
        }

        if (showCeiling)
        {
            var ceil = MakeBoxChild(p, "Ceiling",
                new Vector3(0, roomHeight, 0),
                new Vector3(roomWidth + 0.1f, 0.1f, roomLength + 0.1f), ceilingWhite);
            AddCollider(ceil);
        }
    }

    void CreateWalls()
    {
        GameObject p = new GameObject("Walls");
        p.transform.SetParent(transform);
        p.transform.localPosition = Vector3.zero;

        float halfW = roomWidth / 2f, halfL = roomLength / 2f;
        float wallT = 0.2f;
        float doorW = 2.4f;
        float sideW = (roomWidth - doorW) / 2f;

        float winY = 1.0f;
        float winH = 1.5f;
        float winTopY = winY + winH;

        float[] backWinX = { -7.5f, -3.3f, 0.9f, 5.1f };
        float backWinW = 2.0f;
        AddCollider(MakeBoxChild(p, "BackWall_Below",
            new Vector3(0, winY / 2f, -halfL),
            new Vector3(roomWidth + wallT, winY, wallT), wallWhite));
        float aboveH = roomHeight - winTopY;
        AddCollider(MakeBoxChild(p, "BackWall_Above",
            new Vector3(0, winTopY + aboveH / 2f, -halfL),
            new Vector3(roomWidth + wallT, aboveH, wallT), wallWhite));
        CreateWallPiers(p, backWinX, backWinW, winY, winH, roomWidth, -halfL, wallT, false, "Back");

        AddCollider(MakeBoxChild(p, "Wall_Front_L",
            new Vector3(-halfW + sideW / 2f, roomHeight / 2f, halfL),
            new Vector3(sideW, roomHeight, wallT), wallWhite));
        AddCollider(MakeBoxChild(p, "Wall_Front_R",
            new Vector3(halfW - sideW / 2f, roomHeight / 2f, halfL),
            new Vector3(sideW, roomHeight, wallT), wallWhite));
        float doorH = 2.8f;
        AddCollider(MakeBoxChild(p, "Wall_Front_Top",
            new Vector3(0, doorH + (roomHeight - doorH) / 2f, halfL),
            new Vector3(doorW, roomHeight - doorH, wallT), wallWhite));

        float[] leftWinZ = { -5.2f, -1.7f, 1.8f, 5.3f };
        float sideWinW = 1.6f;
        AddCollider(MakeBoxChild(p, "LeftWall_Below",
            new Vector3(-halfW, winY / 2f, 0),
            new Vector3(wallT, winY, roomLength), wallWhite));
        AddCollider(MakeBoxChild(p, "LeftWall_Above",
            new Vector3(-halfW, winTopY + aboveH / 2f, 0),
            new Vector3(wallT, aboveH, roomLength), wallWhite));
        CreateWallPiers(p, leftWinZ, sideWinW, winY, winH, roomLength, -halfW, wallT, true, "Left");

        float[] rightWinZ = { -5.2f, -1.7f, 1.8f, 5.3f };
        AddCollider(MakeBoxChild(p, "RightWall_Below",
            new Vector3(halfW, winY / 2f, 0),
            new Vector3(wallT, winY, roomLength), wallWhite));
        AddCollider(MakeBoxChild(p, "RightWall_Above",
            new Vector3(halfW, winTopY + aboveH / 2f, 0),
            new Vector3(wallT, aboveH, roomLength), wallWhite));
        CreateWallPiers(p, rightWinZ, sideWinW, winY, winH, roomLength, halfW, wallT, true, "Right");
    }

    void CreateWallPiers(GameObject parent, float[] winPositions, float winW,
        float winY, float winH, float wallLength, float wallPos, float wallT,
        bool isSideWall, string label)
    {
        float halfLen = wallLength / 2f;

        System.Array.Sort(winPositions);

        float firstWinStart = winPositions[0] - winW / 2f;
        float pierW = firstWinStart + halfLen;
        if (pierW > 0.1f)
        {
            float pierCenter = -halfLen + pierW / 2f;
            if (isSideWall)
                AddCollider(MakeBoxChild(parent, $"{label}_Pier_Start",
                    new Vector3(wallPos, winY + winH / 2f, pierCenter),
                    new Vector3(wallT, winH, pierW), wallWhite));
            else
                AddCollider(MakeBoxChild(parent, $"{label}_Pier_Start",
                    new Vector3(pierCenter, winY + winH / 2f, wallPos),
                    new Vector3(pierW, winH, wallT), wallWhite));
        }

        for (int i = 0; i < winPositions.Length - 1; i++)
        {
            float gapStart = winPositions[i] + winW / 2f;
            float gapEnd = winPositions[i + 1] - winW / 2f;
            float gapW = gapEnd - gapStart;
            if (gapW > 0.05f)
            {
                float gapCenter = (gapStart + gapEnd) / 2f;
                if (isSideWall)
                    AddCollider(MakeBoxChild(parent, $"{label}_Pier_{i}",
                        new Vector3(wallPos, winY + winH / 2f, gapCenter),
                        new Vector3(wallT, winH, gapW), wallWhite));
                else
                    AddCollider(MakeBoxChild(parent, $"{label}_Pier_{i}",
                        new Vector3(gapCenter, winY + winH / 2f, wallPos),
                        new Vector3(gapW, winH, wallT), wallWhite));
            }
        }

        float lastWinEnd = winPositions[winPositions.Length - 1] + winW / 2f;
        float endPierW = halfLen - lastWinEnd;
        if (endPierW > 0.1f)
        {
            float endCenter = lastWinEnd + endPierW / 2f;
            if (isSideWall)
                AddCollider(MakeBoxChild(parent, $"{label}_Pier_End",
                    new Vector3(wallPos, winY + winH / 2f, endCenter),
                    new Vector3(wallT, winH, endPierW), wallWhite));
            else
                AddCollider(MakeBoxChild(parent, $"{label}_Pier_End",
                    new Vector3(endCenter, winY + winH / 2f, wallPos),
                    new Vector3(endPierW, winH, wallT), wallWhite));
        }
    }

    void CreateWindows()
    {
        GameObject p = new GameObject("Windows");
        p.transform.SetParent(transform);
        p.transform.localPosition = Vector3.zero;

        float halfW = roomWidth / 2f, halfL = roomLength / 2f;
        float winY = 1.0f;
        float winH = 1.5f;
        float winCenterY = winY + winH / 2f;

        float[] backWinX = { -7.5f, -3.3f, 0.9f, 5.1f };
        float backWinW = 2.0f;
        for (int i = 0; i < backWinX.Length; i++)
            CreateWindow(p, new Vector3(backWinX[i], winCenterY, -halfL),
                backWinW, winH, false, $"Win_Back_{i}");

        float[] leftWinZ = { -5.2f, -1.7f, 1.8f, 5.3f };
        float sideWinW = 1.6f;
        for (int i = 0; i < leftWinZ.Length; i++)
            CreateWindow(p, new Vector3(-halfW, winCenterY, leftWinZ[i]),
                sideWinW, winH, true, $"Win_Left_{i}");

        float[] rightWinZ = { -5.2f, -1.7f, 1.8f, 5.3f };
        for (int i = 0; i < rightWinZ.Length; i++)
            CreateWindow(p, new Vector3(halfW, winCenterY, rightWinZ[i]),
                sideWinW, winH, true, $"Win_Right_{i}");
    }

    void CreateWindow(GameObject parent, Vector3 pos, float w, float h, bool sideWall, string name)
    {
        GameObject win = new GameObject(name);
        win.transform.SetParent(parent.transform);
        win.transform.localPosition = pos;

        float frameT = 0.05f;

        if (sideWall)
        {
            MakeBoxChild(win, "Glass", Vector3.zero, new Vector3(0.02f, h - 0.04f, w - 0.04f), windowGlass);
            MakeBoxChild(win, "Frame_T", new Vector3(0, h / 2f, 0), new Vector3(0.06f, frameT, w), windowFrame);
            MakeBoxChild(win, "Frame_B", new Vector3(0, -h / 2f, 0), new Vector3(0.06f, frameT, w), windowFrame);
            MakeBoxChild(win, "Frame_L", new Vector3(0, 0, -w / 2f), new Vector3(0.06f, h, frameT), windowFrame);
            MakeBoxChild(win, "Frame_R", new Vector3(0, 0, w / 2f), new Vector3(0.06f, h, frameT), windowFrame);
            MakeBoxChild(win, "Muntin_H", Vector3.zero, new Vector3(0.04f, 0.025f, w - 0.06f), windowFrame);
            MakeBoxChild(win, "Muntin_V", Vector3.zero, new Vector3(0.04f, h - 0.06f, 0.025f), windowFrame);
            float sillDir = pos.x < 0 ? 0.08f : -0.08f;
            MakeBoxChild(win, "Sill", new Vector3(sillDir, -h / 2f - 0.02f, 0),
                new Vector3(0.14f, 0.035f, w + 0.10f), windowFrame);
        }
        else
        {
            MakeBoxChild(win, "Glass", Vector3.zero, new Vector3(w - 0.04f, h - 0.04f, 0.02f), windowGlass);
            MakeBoxChild(win, "Frame_T", new Vector3(0, h / 2f, 0), new Vector3(w, frameT, 0.06f), windowFrame);
            MakeBoxChild(win, "Frame_B", new Vector3(0, -h / 2f, 0), new Vector3(w, frameT, 0.06f), windowFrame);
            MakeBoxChild(win, "Frame_L", new Vector3(-w / 2f, 0, 0), new Vector3(frameT, h, 0.06f), windowFrame);
            MakeBoxChild(win, "Frame_R", new Vector3(w / 2f, 0, 0), new Vector3(frameT, h, 0.06f), windowFrame);
            MakeBoxChild(win, "Muntin_H", Vector3.zero, new Vector3(w - 0.06f, 0.025f, 0.04f), windowFrame);
            MakeBoxChild(win, "Muntin_V", Vector3.zero, new Vector3(0.025f, h - 0.06f, 0.04f), windowFrame);
            MakeBoxChild(win, "Sill", new Vector3(0, -h / 2f - 0.02f, 0.08f),
                new Vector3(w + 0.10f, 0.035f, 0.14f), windowFrame);
        }
    }

    void CreateDoors()
    {
        GameObject p = new GameObject("Entrance");
        p.transform.SetParent(transform);
        p.transform.localPosition = Vector3.zero;

        float halfL = roomLength / 2f;
        float doorW = 1.1f, doorH = 2.7f, doorT = 0.05f;

        MakeBoxChild(p, "Frame_L", new Vector3(-doorW - 0.05f, doorH / 2f, halfL),
            new Vector3(0.08f, doorH + 0.08f, 0.18f), windowFrame);
        MakeBoxChild(p, "Frame_R", new Vector3(doorW + 0.05f, doorH / 2f, halfL),
            new Vector3(0.08f, doorH + 0.08f, 0.18f), windowFrame);
        MakeBoxChild(p, "Frame_T", new Vector3(0, doorH + 0.04f, halfL),
            new Vector3(doorW * 2 + 0.18f, 0.08f, 0.18f), windowFrame);

        GameObject hingeL = new GameObject("Door_Hinge_L");
        hingeL.transform.SetParent(p.transform);
        hingeL.transform.localPosition = new Vector3(-doorW - 0.01f, 0, halfL);
        var dL = MakeBoxChild(hingeL, "Door_L", new Vector3(doorW / 2f, doorH / 2f, 0),
            new Vector3(doorW, doorH, doorT), doorColor);
        AddCollider(dL);
        MakeBoxChild(hingeL, "Handle_L", new Vector3(doorW - 0.10f, doorH * 0.45f, -0.04f),
            new Vector3(0.025f, 0.12f, 0.04f), windowFrame);
        MakeBoxChild(hingeL, "Glass_L", new Vector3(doorW / 2f, doorH * 0.65f, -0.005f),
            new Vector3(doorW - 0.2f, doorH * 0.25f, 0.02f), windowGlass);
        hingeL.AddComponent<DoorController>().openAngle = -90f;

        GameObject hingeR = new GameObject("Door_Hinge_R");
        hingeR.transform.SetParent(p.transform);
        hingeR.transform.localPosition = new Vector3(doorW + 0.01f, 0, halfL);
        var dR = MakeBoxChild(hingeR, "Door_R", new Vector3(-doorW / 2f, doorH / 2f, 0),
            new Vector3(doorW, doorH, doorT), doorColor);
        AddCollider(dR);
        MakeBoxChild(hingeR, "Handle_R", new Vector3(-doorW + 0.10f, doorH * 0.45f, -0.04f),
            new Vector3(0.025f, 0.12f, 0.04f), windowFrame);
        MakeBoxChild(hingeR, "Glass_R", new Vector3(-doorW / 2f, doorH * 0.65f, -0.005f),
            new Vector3(doorW - 0.2f, doorH * 0.25f, 0.02f), windowGlass);
        hingeR.AddComponent<DoorController>().openAngle = 90f;

        MakeBoxChild(p, "ExitSign", new Vector3(doorW + 1.5f, 2.6f, halfL - 0.05f),
            new Vector3(0.30f, 0.12f, 0.03f), exitGreen);
        MakeBoxChild(p, "ExitText", new Vector3(doorW + 1.5f, 2.6f, halfL - 0.07f),
            new Vector3(0.25f, 0.08f, 0.005f), new Color(0.95f, 0.95f, 0.95f));
    }

    void CreatePillars()
    {
        GameObject p = new GameObject("Pillars");
        p.transform.SetParent(transform);
        p.transform.localPosition = Vector3.zero;

        float halfL = roomLength / 2f;
        float[] pillarX = { -3.3f, 3.3f };

        for (int col = 0; col < 2; col++)
        {
            for (int row = 0; row < 3; row++)
            {
                float z = -halfL + 3.5f + row * 4.5f;
                CreatePillar(p, new Vector3(pillarX[col], 0, z), $"Pillar_{col}_{row}");
            }
        }
    }

    void CreatePillar(GameObject parent, Vector3 pos, string name)
    {
        GameObject pil = new GameObject(name);
        pil.transform.SetParent(parent.transform);
        pil.transform.localPosition = pos;

        float w = 0.45f, d = 0.45f;

        var shaft = MakeBoxChild(pil, "Shaft",
            new Vector3(0, roomHeight / 2f, 0),
            new Vector3(w, roomHeight, d), pillarWood);
        AddCollider(shaft);

        MakeBoxChild(pil, "Base",
            new Vector3(0, 0.15f, 0),
            new Vector3(w + 0.04f, 0.30f, d + 0.04f), pillarBase);

        MakeBoxChild(pil, "Cap",
            new Vector3(0, roomHeight - 0.05f, 0),
            new Vector3(w + 0.04f, 0.10f, d + 0.04f), pillarBase);

        for (int i = 0; i < 3; i++)
        {
            float xOff = -0.12f + i * 0.12f;
            MakeBoxChild(pil, $"Grain_{i}",
                new Vector3(xOff, roomHeight / 2f, d / 2f + 0.005f),
                new Vector3(0.008f, roomHeight - 0.5f, 0.005f),
                pillarWood * 0.88f);
        }
    }

    void CreateCeilingLights()
    {
        GameObject p = new GameObject("CeilingLights");
        p.transform.SetParent(transform);
        p.transform.localPosition = Vector3.zero;

        float halfW = roomWidth / 2f, halfL = roomLength / 2f;

        for (int col = 0; col < 5; col++)
        {
            for (int row = 0; row < 4; row++)
            {
                float x = -halfW + 2.5f + col * 3.8f;
                float z = -halfL + 2.5f + row * 3.6f;
                CreateCeilingPanel(p, new Vector3(x, roomHeight - 0.01f, z),
                    $"Light_{col}_{row}");
            }
        }

        GameObject ambient = new GameObject("AmbientLight");
        ambient.transform.SetParent(p.transform);
        ambient.transform.rotation = Quaternion.Euler(90f, 0, 0);
        Light al = ambient.AddComponent<Light>();
        al.type = LightType.Directional;
        al.intensity = 0.5f;
        al.color = new Color(0.98f, 0.97f, 0.95f);
        al.shadows = LightShadows.Soft;
    }

    void CreateCeilingPanel(GameObject parent, Vector3 pos, string name)
    {
        GameObject panel = new GameObject(name);
        panel.transform.SetParent(parent.transform);
        panel.transform.localPosition = pos;

        float pw = 0.60f, pl = 0.60f;

        MakeBoxChild(panel, "Panel",
            new Vector3(0, -0.01f, 0),
            new Vector3(pw, 0.02f, pl), lightPanel);

        MakeBoxChild(panel, "Fr_F", new Vector3(0, -0.01f, pl / 2f + 0.01f),
            new Vector3(pw + 0.04f, 0.03f, 0.02f), lightFrame);
        MakeBoxChild(panel, "Fr_B", new Vector3(0, -0.01f, -pl / 2f - 0.01f),
            new Vector3(pw + 0.04f, 0.03f, 0.02f), lightFrame);
        MakeBoxChild(panel, "Fr_L", new Vector3(-pw / 2f - 0.01f, -0.01f, 0),
            new Vector3(0.02f, 0.03f, pl + 0.04f), lightFrame);
        MakeBoxChild(panel, "Fr_R", new Vector3(pw / 2f + 0.01f, -0.01f, 0),
            new Vector3(0.02f, 0.03f, pl + 0.04f), lightFrame);

        GameObject lt = new GameObject("Light");
        lt.transform.SetParent(panel.transform);
        lt.transform.localPosition = new Vector3(0, -0.05f, 0);
        Light l = lt.AddComponent<Light>();
        l.type = LightType.Point;
        l.intensity = 0.6f;
        l.range = 4.5f;
        l.color = new Color(1f, 0.98f, 0.94f);
    }

    void CreateACUnits()
    {
        GameObject p = new GameObject("AirConditioning");
        p.transform.SetParent(transform);
        p.transform.localPosition = Vector3.zero;

        float halfW = roomWidth / 2f, halfL = roomLength / 2f;
        Color acWhite = new Color(0.95f, 0.94f, 0.92f);
        Color acGrill = new Color(0.88f, 0.87f, 0.85f);
        Color acDark = new Color(0.25f, 0.25f, 0.28f);

        float[] acZ = { -3.45f, 0.05f, 3.55f };
        for (int i = 0; i < acZ.Length; i++)
        {
            CreateACUnit(p, new Vector3(-halfW + 0.10f, 2.6f, acZ[i]), true,
                $"AC_Left_{i}", acWhite, acGrill, acDark);
            CreateACUnit(p, new Vector3(halfW - 0.10f, 2.6f, acZ[i]), false,
                $"AC_Right_{i}", acWhite, acGrill, acDark);
        }

        CreateACUnit(p, new Vector3(-5.4f, 2.6f, -halfL + 0.10f), true,
            "AC_Back_1", acWhite, acGrill, acDark);
        CreateACUnit(p, new Vector3(-1.2f, 2.6f, -halfL + 0.10f), true,
            "AC_Back_2", acWhite, acGrill, acDark);
        CreateACUnit(p, new Vector3(3.0f, 2.6f, -halfL + 0.10f), true,
            "AC_Back_3", acWhite, acGrill, acDark);
    }

    void CreateACUnit(GameObject parent, Vector3 pos, bool leftSide, string name,
        Color body, Color grill, Color dark)
    {
        GameObject ac = new GameObject(name);
        ac.transform.SetParent(parent.transform);
        ac.transform.localPosition = pos;

        bool onBackWall = Mathf.Abs(pos.z) > roomLength / 2f - 0.5f;

        if (onBackWall)
        {
            MakeBoxChild(ac, "Body", Vector3.zero, new Vector3(0.90f, 0.28f, 0.20f), body);
            MakeBoxChild(ac, "TopPanel", new Vector3(0, 0.12f, 0), new Vector3(0.88f, 0.02f, 0.18f), grill);
            MakeBoxChild(ac, "GrillBottom", new Vector3(0, -0.10f, 0.08f), new Vector3(0.80f, 0.04f, 0.02f), grill);
            for (int v = 0; v < 5; v++)
                MakeBoxChild(ac, $"Vent_{v}",
                    new Vector3(0, -0.04f + v * 0.04f, 0.10f),
                    new Vector3(0.75f, 0.008f, 0.005f), grill);
            MakeBoxChild(ac, "Display", new Vector3(0.30f, 0.05f, 0.105f),
                new Vector3(0.10f, 0.03f, 0.005f), dark);
            MakeBoxChild(ac, "LED", new Vector3(0.36f, 0.05f, 0.106f),
                new Vector3(0.01f, 0.01f, 0.003f), new Color(0.1f, 0.8f, 0.2f));
        }
        else
        {
            float d = leftSide ? 1f : -1f;
            MakeBoxChild(ac, "Body", Vector3.zero, new Vector3(0.20f, 0.28f, 0.90f), body);
            MakeBoxChild(ac, "TopPanel", new Vector3(0, 0.12f, 0), new Vector3(0.18f, 0.02f, 0.88f), grill);
            MakeBoxChild(ac, "GrillBottom", new Vector3(d * 0.08f, -0.10f, 0), new Vector3(0.02f, 0.04f, 0.80f), grill);
            for (int v = 0; v < 5; v++)
                MakeBoxChild(ac, $"Vent_{v}",
                    new Vector3(d * 0.10f, -0.04f + v * 0.04f, 0),
                    new Vector3(0.005f, 0.008f, 0.75f), grill);
            MakeBoxChild(ac, "Display", new Vector3(d * 0.105f, 0.05f, 0.30f),
                new Vector3(0.005f, 0.03f, 0.10f), dark);
            MakeBoxChild(ac, "LED", new Vector3(d * 0.106f, 0.05f, 0.36f),
                new Vector3(0.003f, 0.01f, 0.01f), new Color(0.1f, 0.8f, 0.2f));
        }
    }

    void CreateStudyCubicles()
    {
        GameObject p = new GameObject("Zones");
        p.transform.SetParent(transform);
        p.transform.localPosition = Vector3.zero;

        float halfW = roomWidth / 2f, halfL = roomLength / 2f;
        float cubicleW = 0.90f;
        float rowSpacing = 2.2f;

        float usableW = roomWidth - 4.0f;
        float colSpacing = usableW / 4f;
        float startX = -usableW / 2f + colSpacing / 2f;

        float backPairZ = -halfL + 4.5f;
        float frontPairZ = backPairZ + rowSpacing + 3.5f;

        for (int col = 0; col < 4; col++)
        {
            float x = startX + col * colSpacing;
            int zoneId = col + 1;

            GameObject zone = new GameObject($"Zone_{zoneId}");
            zone.transform.SetParent(p.transform);
            zone.transform.localPosition = new Vector3(x, 0, backPairZ);

            float dx = cubicleW / 2f + 0.05f;
            CreateCubicle(zone, new Vector3(-dx, 0, -rowSpacing / 2f), -1, zoneId);
            CreateCubicle(zone, new Vector3(dx, 0, -rowSpacing / 2f), -1, zoneId);
            CreateCubicle(zone, new Vector3(-dx, 0, rowSpacing / 2f), 1, zoneId);
            CreateCubicle(zone, new Vector3(dx, 0, rowSpacing / 2f), 1, zoneId);
        }

        for (int col = 0; col < 4; col++)
        {
            if (col == 3) continue;

            float x = startX + col * colSpacing;
            int zoneId = col + 5;

            GameObject zone = new GameObject($"Zone_{zoneId}");
            zone.transform.SetParent(p.transform);
            zone.transform.localPosition = new Vector3(x, 0, frontPairZ);

            float dx = cubicleW / 2f + 0.05f;
            CreateCubicle(zone, new Vector3(-dx, 0, -rowSpacing / 2f), -1, zoneId);
            CreateCubicle(zone, new Vector3(dx, 0, -rowSpacing / 2f), -1, zoneId);
            CreateCubicle(zone, new Vector3(-dx, 0, rowSpacing / 2f), 1, zoneId);
            CreateCubicle(zone, new Vector3(dx, 0, rowSpacing / 2f), 1, zoneId);
        }
    }

    void CreateCubicle(GameObject parent, Vector3 pos, int chairSide, int zoneId)
    {
        seatCounter++;
        string seatId = $"S{seatCounter}";
        float dir = chairSide;

        GameObject cubicle = new GameObject(seatId);
        cubicle.transform.SetParent(parent.transform);
        cubicle.transform.localPosition = pos;

        float dW = 0.90f;
        float dD = 0.55f;
        float dH = 0.74f;
        float partH = 0.40f;

        var top = MakeBoxChild(cubicle, "DeskTop",
            new Vector3(0, dH, 0),
            new Vector3(dW, 0.03f, dD), deskTopCream);
        AddCollider(top);

        MakeBoxChild(cubicle, "EdgeFront",
            new Vector3(0, dH - 0.005f, -dir * dD / 2f),
            new Vector3(dW, 0.025f, 0.015f), new Color(0.70f, 0.65f, 0.55f));
        MakeBoxChild(cubicle, "EdgeBack",
            new Vector3(0, dH - 0.005f, dir * dD / 2f),
            new Vector3(dW, 0.025f, 0.015f), new Color(0.70f, 0.65f, 0.55f));

        float li = 0.05f;
        float legH = dH - 0.03f;
        MakeBoxChild(cubicle, "Leg_1", new Vector3(-dW / 2f + li, legH / 2f, -dD / 2f + li),
            new Vector3(0.035f, legH, 0.035f), deskLeg);
        MakeBoxChild(cubicle, "Leg_2", new Vector3(dW / 2f - li, legH / 2f, -dD / 2f + li),
            new Vector3(0.035f, legH, 0.035f), deskLeg);
        MakeBoxChild(cubicle, "Leg_3", new Vector3(-dW / 2f + li, legH / 2f, dD / 2f - li),
            new Vector3(0.035f, legH, 0.035f), deskLeg);
        MakeBoxChild(cubicle, "Leg_4", new Vector3(dW / 2f - li, legH / 2f, dD / 2f - li),
            new Vector3(0.035f, legH, 0.035f), deskLeg);

        MakeBoxChild(cubicle, "Brace_L", new Vector3(-dW / 2f + li, 0.12f, 0),
            new Vector3(0.02f, 0.02f, dD - li * 2), deskLeg);
        MakeBoxChild(cubicle, "Brace_R", new Vector3(dW / 2f - li, 0.12f, 0),
            new Vector3(0.02f, 0.02f, dD - li * 2), deskLeg);

        MakeBoxChild(cubicle, "CableTray",
            new Vector3(0, 0.62f, -dir * (dD / 2f - 0.08f)),
            new Vector3(dW * 0.6f, 0.03f, 0.10f), deskLeg);

        float pf = 0.035f;

        float partZ = -dir * (dD / 2f + 0.01f);
        MakeBoxChild(cubicle, "Part_Front_Frame",
            new Vector3(0, (dH + partH) / 2f + 0.20f, partZ),
            new Vector3(dW + 0.04f, dH + partH - 0.10f, pf), partitionFrame);
        MakeBoxChild(cubicle, "Part_Front_Panel",
            new Vector3(0, dH + partH / 2f, partZ + dir * 0.022f),
            new Vector3(dW - 0.06f, partH - 0.06f, 0.018f), partitionMaroon);

        MakeBoxChild(cubicle, "Part_Left_Frame",
            new Vector3(-dW / 2f - 0.01f, dH + partH / 2f, 0),
            new Vector3(pf, partH + 0.02f, dD + 0.04f), partitionFrame);
        MakeBoxChild(cubicle, "Part_Left_Panel",
            new Vector3(-dW / 2f - 0.01f + 0.022f, dH + partH / 2f, 0),
            new Vector3(0.018f, partH - 0.06f, dD - 0.06f), partitionMaroon);

        MakeBoxChild(cubicle, "Part_Right_Frame",
            new Vector3(dW / 2f + 0.01f, dH + partH / 2f, 0),
            new Vector3(pf, partH + 0.02f, dD + 0.04f), partitionFrame);
        MakeBoxChild(cubicle, "Part_Right_Panel",
            new Vector3(dW / 2f + 0.01f - 0.022f, dH + partH / 2f, 0),
            new Vector3(0.018f, partH - 0.06f, dD - 0.06f), partitionMaroon);

        MakeBoxChild(cubicle, "Modesty",
            new Vector3(0, dH / 2f, partZ + dir * 0.025f),
            new Vector3(dW - 0.04f, dH - 0.14f, 0.018f), partitionFrame);

        MakeBoxChild(cubicle, "Socket_Panel",
            new Vector3(0.20f, dH + 0.10f, partZ + dir * 0.025f),
            new Vector3(0.16f, 0.07f, 0.02f), socketWhite);
        MakeBoxChild(cubicle, "Socket_1",
            new Vector3(0.17f, dH + 0.10f, partZ + dir * 0.035f),
            new Vector3(0.028f, 0.028f, 0.005f), new Color(0.28f, 0.28f, 0.30f));
        MakeBoxChild(cubicle, "Socket_2",
            new Vector3(0.23f, dH + 0.10f, partZ + dir * 0.035f),
            new Vector3(0.028f, 0.028f, 0.005f), new Color(0.28f, 0.28f, 0.30f));

        MakeBoxChild(cubicle, "Label",
            new Vector3(0.30f, dH + partH - 0.03f, partZ + dir * 0.022f),
            new Vector3(0.10f, 0.05f, 0.005f), new Color(0.95f, 0.95f, 0.93f));

        float chairZ = dir * (dD / 2f + 0.35f);
        CreateStudyChair(cubicle, new Vector3(0, 0, chairZ), chairSide);

        allSeats.Add(new SeatInfo { seatId = seatId, zoneId = zoneId, seatTransform = cubicle.transform });
    }

    void CreateStudyChair(GameObject parent, Vector3 pos, int chairSide)
    {
        GameObject chair = new GameObject("Chair");
        chair.transform.SetParent(parent.transform);
        chair.transform.localPosition = pos;

        float cW = 0.46f, cD = 0.44f, cH = 0.45f;
        float f = (float)chairSide;

        MakeBoxChild(chair, "Seat",
            new Vector3(0, cH, 0),
            new Vector3(cW, 0.055f, cD), chairPadMaroon);
        MakeBoxChild(chair, "SeatLip",
            new Vector3(0, cH + 0.01f, f * cD * 0.3f),
            new Vector3(cW - 0.06f, 0.02f, cD * 0.3f), chairPadMaroon * 1.05f);

        MakeBoxChild(chair, "SeatFrame",
            new Vector3(0, cH - 0.04f, 0),
            new Vector3(cW + 0.01f, 0.03f, cD + 0.01f), chairMetal);

        float backZ = f * (cD / 2f - 0.015f);
        MakeBoxChild(chair, "Back",
            new Vector3(0, cH + 0.24f, backZ),
            new Vector3(cW - 0.04f, 0.42f, 0.045f), chairPadMaroon);
        MakeBoxChild(chair, "BackFrame",
            new Vector3(0, cH + 0.24f, backZ + f * 0.025f),
            new Vector3(cW, 0.44f, 0.02f), chairMetal);
        MakeBoxChild(chair, "TopRail",
            new Vector3(0, cH + 0.47f, backZ + f * 0.01f),
            new Vector3(cW + 0.02f, 0.035f, 0.04f), chairMetal);

        float armY = cH + 0.14f;
        MakeBoxChild(chair, "Arm_L",
            new Vector3(-cW / 2f + 0.01f, armY, 0),
            new Vector3(0.035f, 0.025f, cD * 0.55f), chairMetal);
        MakeBoxChild(chair, "Arm_R",
            new Vector3(cW / 2f - 0.01f, armY, 0),
            new Vector3(0.035f, 0.025f, cD * 0.55f), chairMetal);
        MakeBoxChild(chair, "ArmSup_L",
            new Vector3(-cW / 2f + 0.01f, cH + 0.07f, f * 0.06f),
            new Vector3(0.025f, 0.14f, 0.025f), chairMetal);
        MakeBoxChild(chair, "ArmSup_R",
            new Vector3(cW / 2f - 0.01f, cH + 0.07f, f * 0.06f),
            new Vector3(0.025f, 0.14f, 0.025f), chairMetal);

        float lo = 0.04f;
        MakeBoxChild(chair, "Leg_FL", new Vector3(-cW / 2f + lo, cH / 2f, cD / 2f - lo),
            new Vector3(0.022f, cH, 0.022f), chairMetal);
        MakeBoxChild(chair, "Leg_FR", new Vector3(cW / 2f - lo, cH / 2f, cD / 2f - lo),
            new Vector3(0.022f, cH, 0.022f), chairMetal);
        MakeBoxChild(chair, "Leg_BL", new Vector3(-cW / 2f + lo, cH / 2f, -cD / 2f + lo),
            new Vector3(0.022f, cH, 0.022f), chairMetal);
        MakeBoxChild(chair, "Leg_BR", new Vector3(cW / 2f - lo, cH / 2f, -cD / 2f + lo),
            new Vector3(0.022f, cH, 0.022f), chairMetal);

        MakeBoxChild(chair, "Str_L", new Vector3(-cW / 2f + lo, cH * 0.28f, 0),
            new Vector3(0.018f, 0.018f, cD - lo * 2), chairMetal);
        MakeBoxChild(chair, "Str_R", new Vector3(cW / 2f - lo, cH * 0.28f, 0),
            new Vector3(0.018f, 0.018f, cD - lo * 2), chairMetal);
        MakeBoxChild(chair, "Str_Front", new Vector3(0, cH * 0.28f, -f * (cD / 2f - lo)),
            new Vector3(cW - lo * 2, 0.018f, 0.018f), chairMetal);

        MakeBoxChild(chair, "Glide_FL", new Vector3(-cW / 2f + lo, 0.01f, cD / 2f - lo),
            new Vector3(0.028f, 0.02f, 0.028f), new Color(0.2f, 0.2f, 0.2f));
        MakeBoxChild(chair, "Glide_FR", new Vector3(cW / 2f - lo, 0.01f, cD / 2f - lo),
            new Vector3(0.028f, 0.02f, 0.028f), new Color(0.2f, 0.2f, 0.2f));
        MakeBoxChild(chair, "Glide_BL", new Vector3(-cW / 2f + lo, 0.01f, -cD / 2f + lo),
            new Vector3(0.028f, 0.02f, 0.028f), new Color(0.2f, 0.2f, 0.2f));
        MakeBoxChild(chair, "Glide_BR", new Vector3(cW / 2f - lo, 0.01f, -cD / 2f + lo),
            new Vector3(0.028f, 0.02f, 0.028f), new Color(0.2f, 0.2f, 0.2f));
    }

    void CreateReferenceShelves()
    {
        GameObject p = new GameObject("Bookshelves");
        p.transform.SetParent(transform);
        p.transform.localPosition = Vector3.zero;

        float halfW = roomWidth / 2f, halfL = roomLength / 2f;

        float[] backX = { -8.5f, -5.2f, -1.1f, 2.1f, 6.3f };
        for (int i = 0; i < backX.Length; i++)
            CreateBookshelf(p, new Vector3(backX[i], 0, -halfL + 0.40f),
                $"Back_{i}", 1.4f, 2.4f, 0.35f, false);

        float[] leftZ = { -3.5f, 0.0f, 3.5f };
        for (int i = 0; i < leftZ.Length; i++)
            CreateBookshelf(p, new Vector3(-halfW + 0.40f, 0, leftZ[i]),
                $"Left_{i}", 1.2f, 1.6f, 0.30f, true);

        for (int i = 0; i < leftZ.Length; i++)
            CreateBookshelf(p, new Vector3(halfW - 0.40f, 0, leftZ[i]),
                $"Right_{i}", 1.2f, 1.6f, 0.30f, true);

    }

    void CreateBookshelf(GameObject parent, Vector3 pos, string label,
        float w, float h, float d, bool sideWall)
    {
        GameObject shelf = new GameObject($"Shelf_{label}");
        shelf.transform.SetParent(parent.transform);
        shelf.transform.localPosition = pos;

        Color shelfWood = new Color(0.50f, 0.35f, 0.20f);
        Color shelfDark = new Color(0.38f, 0.25f, 0.15f);
        Color[] bookPalette = {
            new Color(0.58f, 0.16f, 0.14f), new Color(0.14f, 0.24f, 0.45f),
            new Color(0.16f, 0.38f, 0.20f), new Color(0.50f, 0.35f, 0.18f),
            new Color(0.35f, 0.14f, 0.30f), new Color(0.62f, 0.52f, 0.20f),
            new Color(0.20f, 0.30f, 0.48f), new Color(0.45f, 0.20f, 0.22f),
            new Color(0.28f, 0.42f, 0.28f), new Color(0.55f, 0.40f, 0.28f),
        };

        if (sideWall)
        {
            MakeBoxChild(shelf, "Back", new Vector3(-d / 2f + 0.02f, h / 2f, 0),
                new Vector3(0.03f, h, w), shelfDark);
            MakeBoxChild(shelf, "Side_L", new Vector3(0, h / 2f, -w / 2f + 0.02f),
                new Vector3(d, h, 0.04f), shelfDark);
            MakeBoxChild(shelf, "Side_R", new Vector3(0, h / 2f, w / 2f - 0.02f),
                new Vector3(d, h, 0.04f), shelfDark);
            MakeBoxChild(shelf, "TopCap", new Vector3(0, h + 0.02f, 0),
                new Vector3(d + 0.02f, 0.04f, w + 0.02f), shelfWood);
            MakeBoxChild(shelf, "Crown", new Vector3(d / 4f, h + 0.05f, 0),
                new Vector3(d / 2f + 0.04f, 0.04f, w + 0.06f), shelfDark);
            MakeBoxChild(shelf, "Base", new Vector3(0, 0.04f, 0),
                new Vector3(d + 0.02f, 0.08f, w + 0.02f), shelfDark);
        }
        else
        {
            MakeBoxChild(shelf, "Back", new Vector3(0, h / 2f, -d / 2f + 0.02f),
                new Vector3(w, h, 0.03f), shelfDark);
            MakeBoxChild(shelf, "Side_L", new Vector3(-w / 2f + 0.02f, h / 2f, 0),
                new Vector3(0.04f, h, d), shelfDark);
            MakeBoxChild(shelf, "Side_R", new Vector3(w / 2f - 0.02f, h / 2f, 0),
                new Vector3(0.04f, h, d), shelfDark);
            MakeBoxChild(shelf, "TopCap", new Vector3(0, h + 0.02f, 0),
                new Vector3(w + 0.02f, 0.04f, d + 0.02f), shelfWood);
            MakeBoxChild(shelf, "Crown", new Vector3(0, h + 0.05f, d / 4f),
                new Vector3(w + 0.06f, 0.04f, d / 2f + 0.04f), shelfDark);
            MakeBoxChild(shelf, "Base", new Vector3(0, 0.04f, 0),
                new Vector3(w + 0.02f, 0.08f, d + 0.02f), shelfDark);
        }

        int levels = Mathf.Max(2, Mathf.RoundToInt(h / 0.42f));
        for (int s = 0; s < levels; s++)
        {
            float y = 0.15f + s * ((h - 0.15f) / (levels + 0.2f));

            if (sideWall)
                MakeBoxChild(shelf, $"Board_{s}", new Vector3(0, y, 0),
                    new Vector3(d - 0.06f, 0.02f, w - 0.06f), shelfWood);
            else
                MakeBoxChild(shelf, $"Board_{s}", new Vector3(0, y, 0),
                    new Vector3(w - 0.06f, 0.02f, d - 0.06f), shelfWood);

            float bookAreaW = sideWall ? w - 0.12f : w - 0.12f;
            float bookDepth = sideWall ? d - 0.10f : d - 0.10f;
            float bx = -bookAreaW / 2f + 0.03f;
            int bookCount = Random.Range(8, 18);
            bool hasBookend = Random.value > 0.6f;
            bool hasDecor = Random.value > 0.7f;

            for (int b = 0; b < bookCount && bx < bookAreaW / 2f - 0.04f; b++)
            {
                float bw = Random.Range(0.018f, 0.048f);
                float bh = Random.Range(0.14f, 0.28f);
                Color col = bookPalette[Random.Range(0, bookPalette.Length)] * Random.Range(0.80f, 1.20f);

                if (sideWall)
                    MakeBoxChild(shelf, $"Book_{s}_{b}",
                        new Vector3(0.02f, y + 0.02f + bh / 2f, bx + bw / 2f),
                        new Vector3(bookDepth * 0.80f, bh, bw), col);
                else
                    MakeBoxChild(shelf, $"Book_{s}_{b}",
                        new Vector3(bx + bw / 2f, y + 0.02f + bh / 2f, 0.02f),
                        new Vector3(bw, bh, bookDepth * 0.80f), col);

                bx += bw + Random.Range(0.002f, 0.008f);

                if (Random.value > 0.85f) bx += 0.04f;
            }

            if (hasBookend && bx < bookAreaW / 2f - 0.02f)
            {
                if (sideWall)
                {
                    MakeBoxChild(shelf, $"Bookend_{s}",
                        new Vector3(0.02f, y + 0.06f, bx + 0.01f),
                        new Vector3(bookDepth * 0.6f, 0.10f, 0.015f),
                        new Color(0.30f, 0.30f, 0.32f));
                }
                else
                {
                    MakeBoxChild(shelf, $"Bookend_{s}",
                        new Vector3(bx + 0.01f, y + 0.06f, 0.02f),
                        new Vector3(0.015f, 0.10f, bookDepth * 0.6f),
                        new Color(0.30f, 0.30f, 0.32f));
                }
            }

            if (hasDecor && s == levels - 1)
            {
                float dx = Random.Range(-bookAreaW * 0.3f, bookAreaW * 0.3f);
                if (sideWall)
                {
                    for (int fb = 0; fb < 3; fb++)
                    {
                        MakeBoxChild(shelf, $"FlatBook_{s}_{fb}",
                            new Vector3(0, y + 0.03f + fb * 0.025f, dx),
                            new Vector3(bookDepth * 0.7f, 0.02f, 0.16f),
                            bookPalette[Random.Range(0, bookPalette.Length)]);
                    }
                }
                else
                {
                    for (int fb = 0; fb < 3; fb++)
                    {
                        MakeBoxChild(shelf, $"FlatBook_{s}_{fb}",
                            new Vector3(dx, y + 0.03f + fb * 0.025f, 0),
                            new Vector3(0.16f, 0.02f, bookDepth * 0.7f),
                            bookPalette[Random.Range(0, bookPalette.Length)]);
                    }
                }
            }
        }

        if (sideWall)
        {
            var col2 = MakeBoxChild(shelf, "Col", new Vector3(0, h / 2f, 0),
                new Vector3(d, h, w), shelfWood);
            col2.GetComponent<Renderer>().enabled = false;
            AddCollider(col2);
        }
        else
        {
            var col2 = MakeBoxChild(shelf, "Col", new Vector3(0, h / 2f, 0),
                new Vector3(w, h, d), shelfWood);
            col2.GetComponent<Renderer>().enabled = false;
            AddCollider(col2);
        }
    }

    void CreateAisleDetails()
    {
        GameObject p = new GameObject("AisleDetails");
        p.transform.SetParent(transform);
        p.transform.localPosition = Vector3.zero;

        float halfL = roomLength / 2f;

        MakeBoxChild(p, "AisleStrip",
            new Vector3(0, 0.003f, 0),
            new Vector3(1.5f, 0.006f, roomLength - 3f),
            new Color(0.68f, 0.66f, 0.63f));

        MakeBoxChild(p, "AisleLine_L",
            new Vector3(-0.78f, 0.004f, 0),
            new Vector3(0.04f, 0.005f, roomLength - 3f),
            new Color(0.55f, 0.22f, 0.20f));

        MakeBoxChild(p, "AisleLine_R",
            new Vector3(0.78f, 0.004f, 0),
            new Vector3(0.04f, 0.005f, roomLength - 3f),
            new Color(0.55f, 0.22f, 0.20f));

        float backPairZ = -halfL + 4.5f;
        float frontPairZ = backPairZ + 2.2f + 3.5f;
        float usableW = roomWidth - 4.0f;
        float colSpacing = usableW / 4f;
        float startX = -usableW / 2f + colSpacing / 2f;

        for (int i = 0; i < 4; i++)
        {
            float x = startX + i * colSpacing;
            MakeBoxChild(p, $"ZoneMark_{i + 1}",
                new Vector3(x, 0.005f, backPairZ),
                new Vector3(0.25f, 0.004f, 0.12f),
                new Color(0.50f, 0.18f, 0.20f));
            MakeBoxChild(p, $"ZoneMark_{i + 5}",
                new Vector3(x, 0.005f, frontPairZ),
                new Vector3(0.25f, 0.004f, 0.12f),
                new Color(0.50f, 0.18f, 0.20f));
        }

        float halfW = roomWidth / 2f;
        MakeBoxChild(p, "SilenceSign",
            new Vector3(halfW - 0.05f, 2.2f, -2.0f),
            new Vector3(0.02f, 0.20f, 0.50f),
            new Color(0.92f, 0.90f, 0.85f));
        MakeBoxChild(p, "SilenceBorder",
            new Vector3(halfW - 0.05f, 2.2f, -2.0f),
            new Vector3(0.025f, 0.24f, 0.54f),
            new Color(0.55f, 0.18f, 0.22f));
    }

    void CreateRelaxationZone()
    {
        GameObject p = new GameObject("RelaxationZone");
        p.transform.SetParent(transform);
        float halfW = roomWidth / 2f, halfL = roomLength / 2f;
        p.transform.localPosition = new Vector3(halfW - 3.5f, 0, halfL - 4.5f);

        Color carpet = new Color(0.42f, 0.25f, 0.18f);
        Color carpetEdge = new Color(0.55f, 0.32f, 0.20f);
        MakeBoxChild(p, "Carpet", new Vector3(0, 0.006f, 0),
            new Vector3(5.5f, 0.012f, 5.5f), carpet);
        MakeBoxChild(p, "CarpetInner", new Vector3(0, 0.008f, 0),
            new Vector3(4.5f, 0.008f, 4.5f), carpet * 1.08f);
        MakeBoxChild(p, "CE_F", new Vector3(0, 0.009f, 2.78f), new Vector3(5.5f, 0.006f, 0.06f), carpetEdge);
        MakeBoxChild(p, "CE_B", new Vector3(0, 0.009f, -2.78f), new Vector3(5.5f, 0.006f, 0.06f), carpetEdge);
        MakeBoxChild(p, "CE_L", new Vector3(-2.78f, 0.009f, 0), new Vector3(0.06f, 0.006f, 5.5f), carpetEdge);
        MakeBoxChild(p, "CE_R", new Vector3(2.78f, 0.009f, 0), new Vector3(0.06f, 0.006f, 5.5f), carpetEdge);

        Color[] beanCol = {
            new Color(0.62f, 0.18f, 0.20f), new Color(0.20f, 0.35f, 0.55f),
            new Color(0.32f, 0.48f, 0.25f), new Color(0.52f, 0.30f, 0.16f),
            new Color(0.45f, 0.20f, 0.42f), new Color(0.20f, 0.45f, 0.50f),
        };
        CreateBeanBag(p, new Vector3(-1.6f, 0, -1.2f), 30f, beanCol[0], "Bean_1");
        CreateBeanBag(p, new Vector3(-0.5f, 0, -1.5f), -15f, beanCol[1], "Bean_2");
        CreateBeanBag(p, new Vector3(-1.8f, 0, 0.2f), 50f, beanCol[2], "Bean_3");
        CreateBeanBag(p, new Vector3(1.2f, 0, -0.8f), -25f, beanCol[3], "Bean_4");
        CreateBeanBag(p, new Vector3(0.5f, 0, 0.4f), 10f, beanCol[4], "Bean_5");
        CreateBeanBag(p, new Vector3(1.8f, 0, 0.6f), -40f, beanCol[5], "Bean_6");

        CreateLoungeTable(p, new Vector3(-1.0f, 0, -0.5f), "Table_1");
        CreateLoungeTable(p, new Vector3(1.2f, 0, 0.0f), "Table_2");

        CreateFloorLamp(p, new Vector3(-2.3f, 0, -0.5f), "Lamp_1");
        CreateFloorLamp(p, new Vector3(2.3f, 0, -0.2f), "Lamp_2");

        CreateMagRack(p, new Vector3(0, 0, -2.2f));

        CreateTallPlant(p, new Vector3(-2.2f, 0, 1.8f), "Plant_1");
        CreateTallPlant(p, new Vector3(2.2f, 0, 1.8f), "Plant_2");

        MakeBoxChild(p, "Divider_Frame", new Vector3(-2.8f, 0.55f, 0),
            new Vector3(0.06f, 1.1f, 4.0f), new Color(0.45f, 0.32f, 0.20f));
        MakeBoxChild(p, "Divider_Panel", new Vector3(-2.8f + 0.035f, 0.55f, 0),
            new Vector3(0.02f, 0.90f, 3.8f), partitionMaroon * 0.85f);
        MakeBoxChild(p, "Divider_Cap", new Vector3(-2.8f, 1.12f, 0),
            new Vector3(0.10f, 0.03f, 4.1f), new Color(0.45f, 0.32f, 0.20f));

        MakeBoxChild(p, "Sign_Bg", new Vector3(0, 2.2f, 2.65f),
            new Vector3(1.8f, 0.25f, 0.03f), partitionMaroon);
        MakeBoxChild(p, "Sign_Text", new Vector3(0, 2.2f, 2.63f),
            new Vector3(1.5f, 0.15f, 0.005f), new Color(0.95f, 0.88f, 0.68f));
    }

    void CreateBeanBag(GameObject parent, Vector3 pos, float rotY, Color col, string name)
    {
        GameObject bb = new GameObject(name);
        bb.transform.SetParent(parent.transform);
        bb.transform.localPosition = pos;
        bb.transform.localRotation = Quaternion.Euler(0, rotY, 0);

        GameObject body = GameObject.CreatePrimitive(PrimitiveType.Sphere);
        body.name = "Body";
        body.transform.SetParent(bb.transform);
        body.transform.localPosition = new Vector3(0, 0.24f, 0);
        body.transform.localScale = new Vector3(0.75f, 0.38f, 0.70f);
        SetColor(body, col);
        DestroyImmediate(body.GetComponent<Collider>());

        GameObject back = GameObject.CreatePrimitive(PrimitiveType.Sphere);
        back.name = "Back";
        back.transform.SetParent(bb.transform);
        back.transform.localPosition = new Vector3(0, 0.40f, -0.20f);
        back.transform.localScale = new Vector3(0.65f, 0.50f, 0.42f);
        SetColor(back, col * 0.93f);
        DestroyImmediate(back.GetComponent<Collider>());

        GameObject top = GameObject.CreatePrimitive(PrimitiveType.Sphere);
        top.name = "Top";
        top.transform.SetParent(bb.transform);
        top.transform.localPosition = new Vector3(0, 0.35f, 0.06f);
        top.transform.localScale = new Vector3(0.58f, 0.18f, 0.52f);
        SetColor(top, col * 1.06f);
        DestroyImmediate(top.GetComponent<Collider>());

        GameObject wrinkle = GameObject.CreatePrimitive(PrimitiveType.Sphere);
        wrinkle.name = "Wrinkle";
        wrinkle.transform.SetParent(bb.transform);
        wrinkle.transform.localPosition = new Vector3(0.22f, 0.18f, 0.10f);
        wrinkle.transform.localScale = new Vector3(0.18f, 0.14f, 0.20f);
        SetColor(wrinkle, col * 0.97f);
        DestroyImmediate(wrinkle.GetComponent<Collider>());
    }

    void CreateLoungeTable(GameObject parent, Vector3 pos, string name)
    {
        GameObject t = new GameObject(name);
        t.transform.SetParent(parent.transform);
        t.transform.localPosition = pos;

        Color top = new Color(0.52f, 0.38f, 0.24f);
        Color leg = new Color(0.22f, 0.22f, 0.24f);

        MakeBoxChild(t, "Top", new Vector3(0, 0.34f, 0), new Vector3(0.60f, 0.035f, 0.60f), top);
        MakeBoxChild(t, "TopEdge_F", new Vector3(0, 0.33f, 0.30f), new Vector3(0.60f, 0.02f, 0.012f), top * 0.85f);
        MakeBoxChild(t, "TopEdge_B", new Vector3(0, 0.33f, -0.30f), new Vector3(0.60f, 0.02f, 0.012f), top * 0.85f);
        MakeBoxChild(t, "TopEdge_L", new Vector3(-0.30f, 0.33f, 0), new Vector3(0.012f, 0.02f, 0.60f), top * 0.85f);
        MakeBoxChild(t, "TopEdge_R", new Vector3(0.30f, 0.33f, 0), new Vector3(0.012f, 0.02f, 0.60f), top * 0.85f);

        float lo = 0.22f;
        MakeBoxChild(t, "L1", new Vector3(-lo, 0.17f, -lo), new Vector3(0.02f, 0.34f, 0.02f), leg);
        MakeBoxChild(t, "L2", new Vector3(lo, 0.17f, -lo), new Vector3(0.02f, 0.34f, 0.02f), leg);
        MakeBoxChild(t, "L3", new Vector3(-lo, 0.17f, lo), new Vector3(0.02f, 0.34f, 0.02f), leg);
        MakeBoxChild(t, "L4", new Vector3(lo, 0.17f, lo), new Vector3(0.02f, 0.34f, 0.02f), leg);

        MakeBoxChild(t, "Magazine", new Vector3(-0.10f, 0.37f, 0.05f),
            new Vector3(0.18f, 0.008f, 0.24f), new Color(0.80f, 0.20f, 0.18f));
        MakeBoxChild(t, "Magazine2", new Vector3(-0.06f, 0.378f, 0.03f),
            new Vector3(0.18f, 0.008f, 0.24f), new Color(0.18f, 0.40f, 0.62f));

        GameObject mug = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
        mug.name = "Mug";
        mug.transform.SetParent(t.transform);
        mug.transform.localPosition = new Vector3(0.15f, 0.39f, -0.10f);
        mug.transform.localScale = new Vector3(0.045f, 0.04f, 0.045f);
        SetColor(mug, new Color(0.90f, 0.88f, 0.82f));
        DestroyImmediate(mug.GetComponent<Collider>());
    }

    void CreateFloorLamp(GameObject parent, Vector3 pos, string name)
    {
        GameObject lp = new GameObject(name);
        lp.transform.SetParent(parent.transform);
        lp.transform.localPosition = pos;

        Color metal = new Color(0.26f, 0.26f, 0.28f);

        MakeBoxChild(lp, "Base", new Vector3(0, 0.015f, 0), new Vector3(0.22f, 0.03f, 0.22f), metal);
        MakeBoxChild(lp, "Pole", new Vector3(0, 0.85f, 0), new Vector3(0.022f, 1.65f, 0.022f), metal);
        MakeBoxChild(lp, "Arm", new Vector3(0.10f, 1.65f, 0), new Vector3(0.22f, 0.02f, 0.02f), metal);
        MakeBoxChild(lp, "Shade", new Vector3(0.20f, 1.58f, 0),
            new Vector3(0.28f, 0.18f, 0.28f), new Color(0.88f, 0.82f, 0.68f));
        MakeBoxChild(lp, "ShadeRim", new Vector3(0.20f, 1.67f, 0),
            new Vector3(0.29f, 0.01f, 0.29f), metal);

        GameObject lt = new GameObject("Light");
        lt.transform.SetParent(lp.transform);
        lt.transform.localPosition = new Vector3(0.20f, 1.50f, 0);
        Light l = lt.AddComponent<Light>();
        l.type = LightType.Point;
        l.intensity = 0.6f;
        l.range = 4.0f;
        l.color = new Color(1f, 0.92f, 0.75f);
    }

    void CreateMagRack(GameObject parent, Vector3 pos)
    {
        GameObject rack = new GameObject("MagazineRack");
        rack.transform.SetParent(parent.transform);
        rack.transform.localPosition = pos;

        Color wood = new Color(0.48f, 0.34f, 0.22f);
        Color woodD = new Color(0.38f, 0.26f, 0.16f);

        MakeBoxChild(rack, "Side_L", new Vector3(-0.45f, 0.50f, 0), new Vector3(0.04f, 1.0f, 0.30f), wood);
        MakeBoxChild(rack, "Side_R", new Vector3(0.45f, 0.50f, 0), new Vector3(0.04f, 1.0f, 0.30f), wood);
        MakeBoxChild(rack, "Back", new Vector3(0, 0.50f, -0.13f), new Vector3(0.90f, 1.0f, 0.03f), woodD);
        MakeBoxChild(rack, "TopCap", new Vector3(0, 1.02f, 0), new Vector3(0.94f, 0.03f, 0.32f), wood);

        for (int s = 0; s < 3; s++)
        {
            float y = 0.18f + s * 0.28f;
            MakeBoxChild(rack, $"Shelf_{s}", new Vector3(0, y, 0.02f),
                new Vector3(0.84f, 0.02f, 0.24f), wood);
            MakeBoxChild(rack, $"Lip_{s}", new Vector3(0, y + 0.06f, 0.14f),
                new Vector3(0.84f, 0.10f, 0.02f), wood);

            Color[] mc = { new Color(0.82f, 0.18f, 0.15f), new Color(0.15f, 0.38f, 0.62f),
                new Color(0.60f, 0.50f, 0.15f), new Color(0.18f, 0.52f, 0.28f) };
            float mx = -0.35f;
            for (int m = 0; m < Random.Range(3, 6) && mx < 0.35f; m++)
            {
                MakeBoxChild(rack, $"Mag_{s}_{m}",
                    new Vector3(mx, y + 0.10f, 0.06f),
                    new Vector3(0.005f, 0.16f, 0.20f),
                    mc[Random.Range(0, mc.Length)] * Random.Range(0.85f, 1.15f));
                mx += Random.Range(0.08f, 0.14f);
            }
        }
    }

    void CreateTallPlant(GameObject parent, Vector3 pos, string name)
    {
        GameObject pl = new GameObject(name);
        pl.transform.SetParent(parent.transform);
        pl.transform.localPosition = pos;

        GameObject pot = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
        pot.name = "Pot";
        pot.transform.SetParent(pl.transform);
        pot.transform.localPosition = new Vector3(0, 0.22f, 0);
        pot.transform.localScale = new Vector3(0.28f, 0.22f, 0.28f);
        SetColor(pot, new Color(0.55f, 0.38f, 0.25f));
        DestroyImmediate(pot.GetComponent<Collider>());

        GameObject soil = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
        soil.name = "Soil";
        soil.transform.SetParent(pl.transform);
        soil.transform.localPosition = new Vector3(0, 0.40f, 0);
        soil.transform.localScale = new Vector3(0.25f, 0.02f, 0.25f);
        SetColor(soil, new Color(0.22f, 0.16f, 0.10f));
        DestroyImmediate(soil.GetComponent<Collider>());

        GameObject trunk = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
        trunk.name = "Trunk";
        trunk.transform.SetParent(pl.transform);
        trunk.transform.localPosition = new Vector3(0, 0.65f, 0);
        trunk.transform.localScale = new Vector3(0.05f, 0.28f, 0.05f);
        SetColor(trunk, new Color(0.40f, 0.28f, 0.18f));
        DestroyImmediate(trunk.GetComponent<Collider>());

        Vector3[] lPos = {
            new Vector3(0, 0.95f, 0), new Vector3(0.10f, 0.88f, 0.08f),
            new Vector3(-0.08f, 0.92f, -0.06f), new Vector3(0.05f, 1.02f, -0.04f),
            new Vector3(-0.06f, 0.85f, 0.10f), new Vector3(0.08f, 1.0f, 0.05f),
        };
        for (int i = 0; i < lPos.Length; i++)
        {
            GameObject leaf = GameObject.CreatePrimitive(PrimitiveType.Sphere);
            leaf.name = $"Leaf_{i}";
            leaf.transform.SetParent(pl.transform);
            leaf.transform.localPosition = lPos[i];
            float s = Random.Range(0.14f, 0.22f);
            leaf.transform.localScale = new Vector3(s, s * 0.70f, s);
            SetColor(leaf, new Color(0.22f, 0.48f, 0.28f) * Random.Range(0.85f, 1.15f));
            DestroyImmediate(leaf.GetComponent<Collider>());
        }
    }

    void CreateFrontDesk()
    {
        GameObject p = new GameObject("FrontDesk");
        p.transform.SetParent(transform);
        float halfW = roomWidth / 2f, halfL = roomLength / 2f;
        p.transform.localPosition = new Vector3(-halfW + 3.5f, 0, halfL - 2.2f);
        p.transform.localRotation = Quaternion.Euler(0, 180f, 0);

        Color deskWood = new Color(0.48f, 0.33f, 0.20f);
        Color deskDark = new Color(0.35f, 0.24f, 0.15f);
        Color deskTop = new Color(0.55f, 0.42f, 0.28f);
        Color metal = new Color(0.30f, 0.30f, 0.32f);

        var frontPanel = MakeBoxChild(p, "FrontPanel", new Vector3(0, 0.55f, 0.35f),
            new Vector3(2.2f, 1.1f, 0.06f), deskWood);
        AddCollider(frontPanel);
        MakeBoxChild(p, "FrontInset", new Vector3(0, 0.55f, 0.34f),
            new Vector3(1.9f, 0.85f, 0.015f), deskDark);

        var top = MakeBoxChild(p, "DeskTop", new Vector3(0, 0.92f, 0),
            new Vector3(2.2f, 0.04f, 0.75f), deskTop);
        AddCollider(top);

        MakeBoxChild(p, "SidePanel", new Vector3(1.08f, 0.45f, -0.05f),
            new Vector3(0.06f, 0.90f, 0.65f), deskWood);
        MakeBoxChild(p, "SideTop", new Vector3(1.40f, 0.82f, -0.20f),
            new Vector3(0.70f, 0.04f, 0.50f), deskTop);

        MakeBoxChild(p, "BackPanel", new Vector3(0, 0.45f, -0.35f),
            new Vector3(2.2f, 0.90f, 0.04f), deskWood);

        MakeBoxChild(p, "Leg_FL", new Vector3(-1.08f, 0.45f, 0.32f), new Vector3(0.04f, 0.90f, 0.04f), metal);
        MakeBoxChild(p, "Leg_BL", new Vector3(-1.08f, 0.45f, -0.33f), new Vector3(0.04f, 0.90f, 0.04f), metal);

        MakeBoxChild(p, "MonitorStand", new Vector3(-0.3f, 0.94f, 0.05f),
            new Vector3(0.08f, 0.02f, 0.10f), metal);
        MakeBoxChild(p, "MonitorNeck", new Vector3(-0.3f, 1.06f, 0.05f),
            new Vector3(0.03f, 0.22f, 0.03f), metal);
        MakeBoxChild(p, "MonitorScreen", new Vector3(-0.3f, 1.16f, 0.10f),
            new Vector3(0.48f, 0.28f, 0.025f), new Color(0.12f, 0.12f, 0.15f));
        MakeBoxChild(p, "ScreenBezel", new Vector3(-0.3f, 1.16f, 0.095f),
            new Vector3(0.44f, 0.24f, 0.005f), new Color(0.20f, 0.35f, 0.55f));

        MakeBoxChild(p, "Keyboard", new Vector3(-0.3f, 0.94f, 0.20f),
            new Vector3(0.30f, 0.012f, 0.10f), new Color(0.20f, 0.20f, 0.22f));
        MakeBoxChild(p, "Mouse", new Vector3(-0.05f, 0.94f, 0.22f),
            new Vector3(0.05f, 0.02f, 0.08f), new Color(0.20f, 0.20f, 0.22f));

        MakeBoxChild(p, "LampBase", new Vector3(0.5f, 0.94f, 0.15f),
            new Vector3(0.10f, 0.02f, 0.08f), metal);
        MakeBoxChild(p, "LampArm", new Vector3(0.5f, 1.08f, 0.15f),
            new Vector3(0.015f, 0.25f, 0.015f), metal);
        MakeBoxChild(p, "LampShade", new Vector3(0.5f, 1.20f, 0.18f),
            new Vector3(0.14f, 0.06f, 0.10f), new Color(0.22f, 0.40f, 0.25f));

        MakeBoxChild(p, "Phone", new Vector3(0.3f, 0.95f, 0.20f),
            new Vector3(0.10f, 0.04f, 0.15f), new Color(0.20f, 0.20f, 0.22f));
        MakeBoxChild(p, "PhoneHandset", new Vector3(0.3f, 0.98f, 0.20f),
            new Vector3(0.12f, 0.02f, 0.04f), new Color(0.18f, 0.18f, 0.20f));

        MakeBoxChild(p, "PaperTray1", new Vector3(0.75f, 0.95f, 0.0f),
            new Vector3(0.22f, 0.02f, 0.28f), metal);
        MakeBoxChild(p, "PaperTray2", new Vector3(0.75f, 0.99f, 0.0f),
            new Vector3(0.22f, 0.02f, 0.28f), metal);
        MakeBoxChild(p, "Papers", new Vector3(0.75f, 0.97f, 0.0f),
            new Vector3(0.20f, 0.02f, 0.26f), new Color(0.95f, 0.95f, 0.92f));

        MakeBoxChild(p, "LibChairSeat", new Vector3(0, 0.46f, -0.60f),
            new Vector3(0.46f, 0.06f, 0.44f), chairPadMaroon);
        MakeBoxChild(p, "LibChairBack", new Vector3(0, 0.72f, -0.82f),
            new Vector3(0.46f, 0.46f, 0.04f), chairPadMaroon);
        MakeBoxChild(p, "LibChairFrame", new Vector3(0, 0.72f, -0.84f),
            new Vector3(0.48f, 0.48f, 0.02f), metal);
        GameObject chairBase = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
        chairBase.name = "ChairBase";
        chairBase.transform.SetParent(p.transform);
        chairBase.transform.localPosition = new Vector3(0, 0.08f, -0.60f);
        chairBase.transform.localScale = new Vector3(0.30f, 0.08f, 0.30f);
        SetColor(chairBase, metal);
        DestroyImmediate(chairBase.GetComponent<Collider>());
        MakeBoxChild(p, "ChairPole", new Vector3(0, 0.28f, -0.60f),
            new Vector3(0.04f, 0.35f, 0.04f), metal);

        MakeBoxChild(p, "InfoSign", new Vector3(0, 2.0f, 0.38f),
            new Vector3(1.2f, 0.20f, 0.03f), deskDark);
        MakeBoxChild(p, "InfoText", new Vector3(0, 2.0f, 0.37f),
            new Vector3(1.0f, 0.12f, 0.005f), new Color(0.92f, 0.82f, 0.55f));

        GameObject penHolder = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
        penHolder.name = "PenHolder";
        penHolder.transform.SetParent(p.transform);
        penHolder.transform.localPosition = new Vector3(0.15f, 0.97f, 0.10f);
        penHolder.transform.localScale = new Vector3(0.04f, 0.05f, 0.04f);
        SetColor(penHolder, new Color(0.22f, 0.22f, 0.25f));
        DestroyImmediate(penHolder.GetComponent<Collider>());
    }

    void CreateOutdoorScenery()
    {
        GameObject p = new GameObject("Outdoors");
        p.transform.SetParent(transform);
        p.transform.localPosition = Vector3.zero;

        float halfW = roomWidth / 2f, halfL = roomLength / 2f;

        float groundExtent = 30f;
        MakeBoxChild(p, "Ground",
            new Vector3(0, -0.15f, 0),
            new Vector3(groundExtent * 2, 0.1f, groundExtent * 2), groundGreen);

        MakeBoxChild(p, "Path_Back",
            new Vector3(0, -0.08f, -halfL - 2.5f),
            new Vector3(groundExtent, 0.06f, 3.0f), pathColor);
        MakeBoxChild(p, "Path_Right",
            new Vector3(halfW + 2.5f, -0.08f, 0),
            new Vector3(3.0f, 0.06f, groundExtent), pathColor);
        MakeBoxChild(p, "Path_Left",
            new Vector3(-halfW - 2.5f, -0.08f, 0),
            new Vector3(3.0f, 0.06f, groundExtent), pathColor);

        for (int i = 0; i < 5; i++)
        {
            float x = -12f + i * 6f;
            float z = -halfL - 5f - Random.Range(0f, 3f);
            CreateTree(p, new Vector3(x, 0, z), $"Tree_B{i}", Random.Range(2.5f, 4.5f));
        }

        for (int i = 0; i < 4; i++)
        {
            float x = halfW + 4f + Random.Range(0f, 3f);
            float z = -8f + i * 5f;
            CreateTree(p, new Vector3(x, 0, z), $"Tree_R{i}", Random.Range(2.5f, 4.5f));
        }

        for (int i = 0; i < 4; i++)
        {
            float x = -halfW - 4f - Random.Range(0f, 3f);
            float z = -8f + i * 5f;
            CreateTree(p, new Vector3(x, 0, z), $"Tree_L{i}", Random.Range(2.5f, 4.5f));
        }

        MakeBoxChild(p, "Building_1",
            new Vector3(-6f, 3f, -halfL - 15f),
            new Vector3(8f, 6f, 4f), buildingColor);
        MakeBoxChild(p, "Building_1_Roof",
            new Vector3(-6f, 6.1f, -halfL - 15f),
            new Vector3(8.5f, 0.2f, 4.5f), buildingColor * 0.85f);
        for (int r = 0; r < 2; r++)
        {
            for (int c = 0; c < 4; c++)
            {
                MakeBoxChild(p, $"BldWin_{r}_{c}",
                    new Vector3(-8.5f + c * 2.2f, 1.5f + r * 2.5f, -halfL - 12.95f),
                    new Vector3(1.0f, 1.2f, 0.05f),
                    new Color(0.55f, 0.68f, 0.80f));
            }
        }

        MakeBoxChild(p, "Building_2",
            new Vector3(8f, 2.5f, -halfL - 18f),
            new Vector3(6f, 5f, 3f), buildingColor * 0.92f);
        MakeBoxChild(p, "Building_2_Roof",
            new Vector3(8f, 5.1f, -halfL - 18f),
            new Vector3(6.5f, 0.2f, 3.5f), buildingColor * 0.8f);

        MakeBoxChild(p, "Building_3",
            new Vector3(halfW + 18f, 4f, -2f),
            new Vector3(5f, 8f, 10f), buildingColor * 0.95f);

        MakeBoxChild(p, "FlowerBed_1",
            new Vector3(-3f, 0.05f, -halfL - 1.5f),
            new Vector3(4f, 0.10f, 1.0f), new Color(0.30f, 0.45f, 0.22f));
        MakeBoxChild(p, "FlowerBed_2",
            new Vector3(5f, 0.05f, -halfL - 1.5f),
            new Vector3(3f, 0.10f, 1.0f), new Color(0.30f, 0.45f, 0.22f));

        Color[] flowerColors = {
            new Color(0.85f, 0.25f, 0.30f), new Color(0.90f, 0.75f, 0.20f),
            new Color(0.80f, 0.30f, 0.65f), new Color(0.95f, 0.55f, 0.25f),
        };
        for (int i = 0; i < 12; i++)
        {
            float fx = -4.5f + i * 0.7f + Random.Range(-0.2f, 0.2f);
            float fz = -halfL - 1.5f + Random.Range(-0.3f, 0.3f);
            MakeBoxChild(p, $"Flower_{i}",
                new Vector3(fx, 0.15f + Random.Range(0f, 0.08f), fz),
                new Vector3(0.12f, 0.12f, 0.12f),
                flowerColors[Random.Range(0, flowerColors.Length)]);
        }

        CreateOutdoorBench(p, new Vector3(-4f, 0, -halfL - 4f), "Bench_1");
        CreateOutdoorBench(p, new Vector3(4f, 0, -halfL - 4f), "Bench_2");
        CreateOutdoorBench(p, new Vector3(halfW + 4f, 0, -1f), "Bench_3");
        CreateOutdoorBench(p, new Vector3(-halfW - 4f, 0, 2f), "Bench_4");

        float gateZ = -halfL - 10f;
        MakeBoxChild(p, "GatePost_L", new Vector3(-3f, 1.5f, gateZ), new Vector3(0.4f, 3f, 0.4f), buildingColor * 0.9f);
        MakeBoxChild(p, "GatePost_R", new Vector3(3f, 1.5f, gateZ), new Vector3(0.4f, 3f, 0.4f), buildingColor * 0.9f);
        MakeBoxChild(p, "GateArch", new Vector3(0, 3.1f, gateZ), new Vector3(6.4f, 0.3f, 0.5f), buildingColor * 0.85f);
        MakeBoxChild(p, "GateBar_1", new Vector3(-1.5f, 1.5f, gateZ), new Vector3(0.05f, 2.8f, 0.05f), new Color(0.20f, 0.20f, 0.22f));
        MakeBoxChild(p, "GateBar_2", new Vector3(0, 1.5f, gateZ), new Vector3(0.05f, 2.8f, 0.05f), new Color(0.20f, 0.20f, 0.22f));
        MakeBoxChild(p, "GateBar_3", new Vector3(1.5f, 1.5f, gateZ), new Vector3(0.05f, 2.8f, 0.05f), new Color(0.20f, 0.20f, 0.22f));
        MakeBoxChild(p, "BoundaryWall_L", new Vector3(-8f, 0.5f, gateZ), new Vector3(10f, 1.0f, 0.25f), buildingColor * 0.88f);
        MakeBoxChild(p, "BoundaryWall_R", new Vector3(8f, 0.5f, gateZ), new Vector3(10f, 1.0f, 0.25f), buildingColor * 0.88f);

        float fountainZ = -halfL - 6f;
        CreateFountain(p, new Vector3(0, 0, fountainZ));

        CreateLampPost(p, new Vector3(-5f, 0, -halfL - 5f), "Lamp_1");
        CreateLampPost(p, new Vector3(5f, 0, -halfL - 5f), "Lamp_2");
        CreateLampPost(p, new Vector3(halfW + 3f, 0, 3f), "Lamp_3");

        MakeBoxChild(p, "Sky_Back",
            new Vector3(0, 8f, -halfL - 35f),
            new Vector3(80f, 25f, 0.1f), skyBlue);
        MakeBoxChild(p, "Sky_Right",
            new Vector3(halfW + 35f, 8f, 0),
            new Vector3(0.1f, 25f, 80f), skyBlue);
        MakeBoxChild(p, "Sky_Left",
            new Vector3(-halfW - 35f, 8f, 0),
            new Vector3(0.1f, 25f, 80f), skyBlue * 0.97f);

        for (int i = 0; i < 6; i++)
        {
            float cx = Random.Range(-20f, 20f);
            float cy = Random.Range(10f, 16f);
            float cz = -halfL - Random.Range(15f, 30f);
            float cw = Random.Range(3f, 8f);
            MakeBoxChild(p, $"Cloud_{i}",
                new Vector3(cx, cy, cz),
                new Vector3(cw, Random.Range(0.8f, 1.5f), Random.Range(1.5f, 3f)),
                new Color(0.97f, 0.97f, 0.98f));
        }

        GameObject sun = GameObject.CreatePrimitive(PrimitiveType.Sphere);
        sun.name = "Sun";
        sun.transform.SetParent(p.transform);
        sun.transform.localPosition = new Vector3(15f, 18f, -halfL - 25f);
        sun.transform.localScale = new Vector3(3f, 3f, 3f);
        SetColor(sun, new Color(1f, 0.95f, 0.75f));
        DestroyImmediate(sun.GetComponent<Collider>());
    }

    void CreateTree(GameObject parent, Vector3 pos, string name, float height)
    {
        GameObject tree = new GameObject(name);
        tree.transform.SetParent(parent.transform);
        tree.transform.localPosition = pos;

        GameObject trunk = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
        trunk.name = "Trunk";
        trunk.transform.SetParent(tree.transform);
        trunk.transform.localPosition = new Vector3(0, height * 0.3f, 0);
        trunk.transform.localScale = new Vector3(0.2f, height * 0.3f, 0.2f);
        SetColor(trunk, treeTrunk * Random.Range(0.9f, 1.1f));
        DestroyImmediate(trunk.GetComponent<Collider>());

        float canopyBase = height * 0.5f;
        float canopyR = height * 0.3f;

        GameObject canopy1 = GameObject.CreatePrimitive(PrimitiveType.Sphere);
        canopy1.name = "Canopy_1";
        canopy1.transform.SetParent(tree.transform);
        canopy1.transform.localPosition = new Vector3(0, canopyBase + canopyR * 0.5f, 0);
        canopy1.transform.localScale = new Vector3(canopyR * 2, canopyR * 1.6f, canopyR * 2);
        SetColor(canopy1, treeLeaves * Random.Range(0.85f, 1.15f));
        DestroyImmediate(canopy1.GetComponent<Collider>());

        GameObject canopy2 = GameObject.CreatePrimitive(PrimitiveType.Sphere);
        canopy2.name = "Canopy_2";
        canopy2.transform.SetParent(tree.transform);
        canopy2.transform.localPosition = new Vector3(canopyR * 0.3f, canopyBase + canopyR * 0.8f, canopyR * 0.2f);
        canopy2.transform.localScale = new Vector3(canopyR * 1.5f, canopyR * 1.3f, canopyR * 1.5f);
        SetColor(canopy2, treeLeaves * Random.Range(0.88f, 1.12f));
        DestroyImmediate(canopy2.GetComponent<Collider>());

        GameObject canopy3 = GameObject.CreatePrimitive(PrimitiveType.Sphere);
        canopy3.name = "Canopy_3";
        canopy3.transform.SetParent(tree.transform);
        canopy3.transform.localPosition = new Vector3(-canopyR * 0.2f, canopyBase + canopyR, -canopyR * 0.15f);
        canopy3.transform.localScale = new Vector3(canopyR * 1.3f, canopyR * 1.1f, canopyR * 1.3f);
        SetColor(canopy3, treeLeaves * Random.Range(0.90f, 1.10f));
        DestroyImmediate(canopy3.GetComponent<Collider>());
    }

    void CreateOutdoorBench(GameObject parent, Vector3 pos, string name)
    {
        GameObject bench = new GameObject(name);
        bench.transform.SetParent(parent.transform);
        bench.transform.localPosition = pos;

        Color benchWood = new Color(0.45f, 0.30f, 0.18f);
        Color benchMetal = new Color(0.25f, 0.25f, 0.28f);

        MakeBoxChild(bench, "Seat", new Vector3(0, 0.42f, 0),
            new Vector3(1.2f, 0.04f, 0.35f), benchWood);
        MakeBoxChild(bench, "Back", new Vector3(0, 0.70f, -0.15f),
            new Vector3(1.2f, 0.04f, 0.25f), benchWood);
        MakeBoxChild(bench, "Leg_L", new Vector3(-0.50f, 0.21f, 0),
            new Vector3(0.05f, 0.42f, 0.35f), benchMetal);
        MakeBoxChild(bench, "Leg_R", new Vector3(0.50f, 0.21f, 0),
            new Vector3(0.05f, 0.42f, 0.35f), benchMetal);
    }

    void CreateSensorMount()
    {
        GameObject sensors = new GameObject("SensorSystem");
        sensors.transform.SetParent(transform);
        sensors.transform.localPosition = Vector3.zero;

        float halfW = roomWidth / 2f, halfL = roomLength / 2f;
        float railY = roomHeight - 0.06f;

        float usableW = roomWidth - 4f;
        float colSpacing = usableW / 4f;
        float startX = -usableW / 2f + colSpacing / 2f;

        float backZ = -halfL + 4.5f;
        float frontZ = backZ + 2.2f + 3.5f;

        float railStartX = startX - 1.5f;
        float railEndX = startX + 3 * colSpacing + 1.5f;

        var rail1 = CreateSensorRail(sensors, "Rail_Back", backZ, railY, railStartX, railEndX, 4);
        rail1.AddComponent<RailSensorController>();

        var rail2 = CreateSensorRail(sensors, "Rail_Front", frontZ, railY, railStartX, railEndX, 3);
        rail2.AddComponent<RailSensorController>();
    }

    GameObject CreateSensorRail(GameObject parent, string name, float railZ, float railY,
        float startX, float endX, int checkpoints)
    {
        GameObject rail = new GameObject(name);
        rail.transform.SetParent(parent.transform);
        rail.transform.localPosition = Vector3.zero;

        float railLen = endX - startX;
        float railCenterX = (startX + endX) / 2f;
        Color railColor = new Color(0.70f, 0.70f, 0.72f);

        MakeBoxChild(rail, "Track_Main",
            new Vector3(railCenterX, railY, railZ),
            new Vector3(railLen + 0.2f, 0.04f, 0.06f), railColor);
        MakeBoxChild(rail, "Track_TopFlange",
            new Vector3(railCenterX, railY + 0.025f, railZ),
            new Vector3(railLen + 0.2f, 0.01f, 0.10f), railColor);
        MakeBoxChild(rail, "Track_BotFlange",
            new Vector3(railCenterX, railY - 0.025f, railZ),
            new Vector3(railLen + 0.2f, 0.01f, 0.10f), railColor);

        for (float x = startX; x <= endX; x += 2f)
        {
            MakeBoxChild(rail, $"Bracket_{x:F0}",
                new Vector3(x, railY + 0.04f, railZ),
                new Vector3(0.04f, 0.06f, 0.04f), railColor * 0.85f);
        }

        MakeBoxChild(rail, "EndStop_L",
            new Vector3(startX - 0.12f, railY, railZ),
            new Vector3(0.04f, 0.06f, 0.10f), new Color(0.75f, 0.20f, 0.15f));
        MakeBoxChild(rail, "EndStop_R",
            new Vector3(endX + 0.12f, railY, railZ),
            new Vector3(0.04f, 0.06f, 0.10f), new Color(0.75f, 0.20f, 0.15f));

        float usableW = roomWidth - 4f;
        float colSpacing = usableW / 4f;
        float cpStartX = -usableW / 2f + colSpacing / 2f;
        for (int i = 0; i < checkpoints; i++)
        {
            float cpX = cpStartX + i * colSpacing;
            MakeBoxChild(rail, $"Checkpoint_{i}",
                new Vector3(cpX, railY - 0.035f, railZ),
                new Vector3(0.05f, 0.005f, 0.05f), new Color(0.15f, 0.65f, 0.25f));
        }

        MakeBoxChild(rail, "Cable",
            new Vector3(railCenterX, railY + 0.06f, railZ + 0.04f),
            new Vector3(railLen, 0.02f, 0.02f), new Color(0.20f, 0.20f, 0.22f));

        GameObject carriage = new GameObject("Carriage");
        carriage.transform.SetParent(rail.transform);
        carriage.transform.localPosition = new Vector3(cpStartX, railY, railZ);

        MakeBoxChild(carriage, "Body",
            new Vector3(0, -0.04f, 0),
            new Vector3(0.16f, 0.05f, 0.12f), sensorColor);

        MakeBoxChild(carriage, "Wheel_L",
            new Vector3(-0.06f, 0, 0),
            new Vector3(0.02f, 0.03f, 0.03f), new Color(0.25f, 0.25f, 0.28f));
        MakeBoxChild(carriage, "Wheel_R",
            new Vector3(0.06f, 0, 0),
            new Vector3(0.02f, 0.03f, 0.03f), new Color(0.25f, 0.25f, 0.28f));

        MakeBoxChild(carriage, "Arm",
            new Vector3(0, -0.10f, 0),
            new Vector3(0.035f, 0.08f, 0.035f), sensorColor);

        MakeBoxChild(carriage, "SensorHead",
            new Vector3(0, -0.17f, 0),
            new Vector3(0.10f, 0.06f, 0.10f), sensorColor);

        GameObject lens = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
        lens.name = "Lens";
        lens.transform.SetParent(carriage.transform);
        lens.transform.localPosition = new Vector3(0, -0.21f, 0);
        lens.transform.localScale = new Vector3(0.05f, 0.01f, 0.05f);
        SetColor(lens, Color.black);
        DestroyImmediate(lens.GetComponent<Collider>());

        MakeBoxChild(carriage, "Radar",
            new Vector3(0.055f, -0.15f, 0),
            new Vector3(0.01f, 0.04f, 0.06f), new Color(0.22f, 0.22f, 0.25f));

        MakeBoxChild(carriage, "LED",
            new Vector3(-0.04f, -0.14f, 0.05f),
            new Vector3(0.008f, 0.008f, 0.008f), new Color(0.10f, 0.85f, 0.20f));

        for (int i = 0; i < 4; i++)
        {
            float a = i * 90f * Mathf.Deg2Rad;
            MakeBoxChild(carriage, $"IR_{i}",
                new Vector3(Mathf.Cos(a) * 0.035f, -0.20f, Mathf.Sin(a) * 0.035f),
                new Vector3(0.008f, 0.008f, 0.008f), new Color(0.30f, 0.05f, 0.05f));
        }

        MakeBoxChild(carriage, "Label",
            new Vector3(0, -0.04f, 0.065f),
            new Vector3(0.10f, 0.02f, 0.005f), new Color(0.90f, 0.88f, 0.82f));

        return rail;
    }

    void CreateSensorMonitor()
    {
        GameObject monitor = new GameObject("SensorMonitorMount");
        monitor.transform.SetParent(transform);
        monitor.transform.localPosition = Vector3.zero;
        monitor.AddComponent<SensorFeedUI>();
    }

    void CreateMiscDetails()
    {
        GameObject p = new GameObject("Details");
        p.transform.SetParent(transform);
        p.transform.localPosition = Vector3.zero;

        float halfW = roomWidth / 2f, halfL = roomLength / 2f;

        CreateDustbin(p, new Vector3(-halfW + 0.5f, 0, halfL - 1.0f), "Bin_1");
        CreateDustbin(p, new Vector3(halfW - 0.5f, 0, halfL - 1.0f), "Bin_2");
        CreateDustbin(p, new Vector3(0, 0, -halfL + 0.5f), "Bin_3");
        CreateDustbin(p, new Vector3(-3.5f, 0, 0), "Bin_4");
        CreateDustbin(p, new Vector3(3.5f, 0, 0), "Bin_5");

        MakeBoxChild(p, "FireExt",
            new Vector3(-halfW + 0.06f, 0.85f, halfL - 2.0f),
            new Vector3(0.08f, 0.35f, 0.08f), new Color(0.75f, 0.12f, 0.10f));
        MakeBoxChild(p, "FireBracket",
            new Vector3(-halfW + 0.04f, 0.90f, halfL - 2.0f),
            new Vector3(0.02f, 0.12f, 0.10f), windowFrame);

        CreateWallClock(p, new Vector3(0, 2.6f, -halfL + 0.05f));

        CreateWaterCooler(p, new Vector3(halfW - 1.5f, 0, halfL - 1.5f));

        CreateNoticeBoard(p, new Vector3(-halfW + 4.5f, 1.55f, halfL - 0.05f),
            "RulesBoard", "Library Rules");
        CreateNoticeBoard(p, new Vector3(halfW - 5.0f, 1.55f, halfL - 0.05f),
            "ScheduleBoard", "Schedule");

        MakeBoxChild(p, "Conduit_1",
            new Vector3(0, 0.02f, -halfL + 4.5f),
            new Vector3(roomWidth - 3.0f, 0.04f, 0.06f), floorGray * 0.85f);
        MakeBoxChild(p, "Conduit_2",
            new Vector3(0, 0.02f, -halfL + 10.2f),
            new Vector3(roomWidth - 3.0f, 0.04f, 0.06f), floorGray * 0.85f);

        MakeBoxChild(p, "EntranceMat",
            new Vector3(0, 0.005f, halfL - 0.8f),
            new Vector3(2.2f, 0.01f, 0.8f), new Color(0.28f, 0.15f, 0.12f));
    }

    void CreateWaterCooler(GameObject parent, Vector3 pos)
    {
        GameObject wc = new GameObject("WaterCooler");
        wc.transform.SetParent(parent.transform);
        wc.transform.localPosition = pos;

        Color wcBody = new Color(0.93f, 0.92f, 0.90f);
        Color wcDark = new Color(0.28f, 0.28f, 0.30f);
        Color wcAccent = new Color(0.15f, 0.42f, 0.72f);

        MakeBoxChild(wc, "BaseCab", new Vector3(0, 0.20f, 0),
            new Vector3(0.35f, 0.40f, 0.35f), wcBody);
        MakeBoxChild(wc, "BaseDoor", new Vector3(0, 0.20f, 0.175f),
            new Vector3(0.30f, 0.34f, 0.01f), wcBody * 0.95f);
        MakeBoxChild(wc, "BaseHandle", new Vector3(0.08f, 0.20f, 0.185f),
            new Vector3(0.015f, 0.10f, 0.015f), wcDark);

        MakeBoxChild(wc, "UpperBody", new Vector3(0, 0.65f, 0),
            new Vector3(0.34f, 0.50f, 0.34f), wcBody);

        MakeBoxChild(wc, "AccentBand", new Vector3(0, 0.55f, 0.172f),
            new Vector3(0.30f, 0.04f, 0.005f), wcAccent);

        MakeBoxChild(wc, "DispenseArea", new Vector3(0, 0.72f, 0.12f),
            new Vector3(0.22f, 0.16f, 0.10f), wcDark);

        MakeBoxChild(wc, "Tap_Hot", new Vector3(-0.06f, 0.74f, 0.175f),
            new Vector3(0.025f, 0.05f, 0.025f), new Color(0.80f, 0.15f, 0.12f));
        MakeBoxChild(wc, "Tap_Normal", new Vector3(0, 0.74f, 0.175f),
            new Vector3(0.025f, 0.05f, 0.025f), new Color(0.60f, 0.60f, 0.62f));
        MakeBoxChild(wc, "Tap_Cold", new Vector3(0.06f, 0.74f, 0.175f),
            new Vector3(0.025f, 0.05f, 0.025f), new Color(0.15f, 0.45f, 0.80f));
        MakeBoxChild(wc, "Label_H", new Vector3(-0.06f, 0.80f, 0.175f),
            new Vector3(0.03f, 0.012f, 0.003f), new Color(0.80f, 0.15f, 0.12f));
        MakeBoxChild(wc, "Label_C", new Vector3(0.06f, 0.80f, 0.175f),
            new Vector3(0.03f, 0.012f, 0.003f), new Color(0.15f, 0.45f, 0.80f));

        MakeBoxChild(wc, "DripTray", new Vector3(0, 0.64f, 0.14f),
            new Vector3(0.22f, 0.015f, 0.10f), wcDark);
        MakeBoxChild(wc, "DripGrate", new Vector3(0, 0.648f, 0.14f),
            new Vector3(0.20f, 0.005f, 0.08f), new Color(0.50f, 0.50f, 0.52f));

        MakeBoxChild(wc, "TopCap", new Vector3(0, 0.91f, 0),
            new Vector3(0.36f, 0.03f, 0.36f), wcDark);

        GameObject bottle = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
        bottle.name = "Bottle";
        bottle.transform.SetParent(wc.transform);
        bottle.transform.localPosition = new Vector3(0, 1.18f, 0);
        bottle.transform.localScale = new Vector3(0.24f, 0.24f, 0.24f);
        SetColor(bottle, new Color(0.50f, 0.70f, 0.88f, 0.55f));
        DestroyImmediate(bottle.GetComponent<Collider>());

        GameObject cap = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
        cap.name = "BottleCap";
        cap.transform.SetParent(wc.transform);
        cap.transform.localPosition = new Vector3(0, 0.94f, 0);
        cap.transform.localScale = new Vector3(0.10f, 0.02f, 0.10f);
        SetColor(cap, wcAccent);
        DestroyImmediate(cap.GetComponent<Collider>());

        GameObject neck = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
        neck.name = "BottleNeck";
        neck.transform.SetParent(wc.transform);
        neck.transform.localPosition = new Vector3(0, 0.96f, 0);
        neck.transform.localScale = new Vector3(0.08f, 0.03f, 0.08f);
        SetColor(neck, new Color(0.50f, 0.70f, 0.88f, 0.55f));
        DestroyImmediate(neck.GetComponent<Collider>());

        MakeBoxChild(wc, "CupDispenser", new Vector3(0.20f, 0.78f, 0),
            new Vector3(0.08f, 0.18f, 0.08f), wcBody);
        MakeBoxChild(wc, "CupSlot", new Vector3(0.20f, 0.70f, 0.01f),
            new Vector3(0.06f, 0.03f, 0.06f), wcDark);

        MakeBoxChild(wc, "SideTable", new Vector3(0.30f, 0.50f, 0),
            new Vector3(0.25f, 0.03f, 0.30f), wcBody * 0.95f);
        MakeBoxChild(wc, "TableLeg1", new Vector3(0.20f, 0.25f, 0.12f),
            new Vector3(0.02f, 0.50f, 0.02f), wcDark);
        MakeBoxChild(wc, "TableLeg2", new Vector3(0.40f, 0.25f, -0.12f),
            new Vector3(0.02f, 0.50f, 0.02f), wcDark);

        for (int i = 0; i < 3; i++)
        {
            GameObject cup = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
            cup.name = $"Cup_{i}";
            cup.transform.SetParent(wc.transform);
            cup.transform.localPosition = new Vector3(0.26f + i * 0.06f, 0.55f, 0.02f);
            cup.transform.localScale = new Vector3(0.035f, 0.04f, 0.035f);
            SetColor(cup, new Color(0.95f, 0.95f, 0.92f));
            DestroyImmediate(cup.GetComponent<Collider>());
        }
    }

    void CreateNoticeBoard(GameObject parent, Vector3 pos, string name, string boardType)
    {
        GameObject nb = new GameObject(name);
        nb.transform.SetParent(parent.transform);
        nb.transform.localPosition = pos;

        Color corkBg = new Color(0.72f, 0.58f, 0.38f);
        Color frame = new Color(0.35f, 0.25f, 0.18f);

        MakeBoxChild(nb, "Board", Vector3.zero,
            new Vector3(1.4f, 1.0f, 0.03f), corkBg);

        MakeBoxChild(nb, "Fr_T", new Vector3(0, 0.52f, 0),
            new Vector3(1.46f, 0.04f, 0.05f), frame);
        MakeBoxChild(nb, "Fr_B", new Vector3(0, -0.52f, 0),
            new Vector3(1.46f, 0.04f, 0.05f), frame);
        MakeBoxChild(nb, "Fr_L", new Vector3(-0.72f, 0, 0),
            new Vector3(0.04f, 1.04f, 0.05f), frame);
        MakeBoxChild(nb, "Fr_R", new Vector3(0.72f, 0, 0),
            new Vector3(0.04f, 1.04f, 0.05f), frame);

        MakeBoxChild(nb, "TitleBar", new Vector3(0, 0.40f, -0.018f),
            new Vector3(1.2f, 0.12f, 0.005f), partitionMaroon);

        Color[] paperColors = {
            new Color(0.98f, 0.98f, 0.95f),
            new Color(1f, 1f, 0.72f),
            new Color(0.75f, 0.90f, 1f),
            new Color(1f, 0.82f, 0.82f),
            new Color(0.80f, 1f, 0.82f),
        };

        if (boardType == "Library Rules")
        {
            MakeBoxChild(nb, "RulesSheet", new Vector3(0, -0.02f, -0.018f),
                new Vector3(0.85f, 0.60f, 0.003f), paperColors[0]);
            for (int line = 0; line < 8; line++)
                MakeBoxChild(nb, $"Line_{line}",
                    new Vector3(-0.05f, 0.18f - line * 0.07f, -0.020f),
                    new Vector3(0.55f, 0.012f, 0.002f), new Color(0.2f, 0.2f, 0.2f));
            MakeBoxChild(nb, "Notice_1", new Vector3(-0.52f, 0.10f, -0.019f),
                new Vector3(0.22f, 0.28f, 0.003f), paperColors[1]);
            MakeBoxChild(nb, "Notice_2", new Vector3(0.52f, -0.10f, -0.019f),
                new Vector3(0.22f, 0.22f, 0.003f), paperColors[2]);
        }
        else
        {
            MakeBoxChild(nb, "ScheduleSheet", new Vector3(-0.15f, -0.05f, -0.018f),
                new Vector3(0.70f, 0.65f, 0.003f), paperColors[0]);
            for (int r = 0; r < 6; r++)
                MakeBoxChild(nb, $"HLine_{r}",
                    new Vector3(-0.15f, 0.20f - r * 0.10f, -0.020f),
                    new Vector3(0.65f, 0.005f, 0.002f), new Color(0.3f, 0.3f, 0.3f));
            for (int c = 0; c < 5; c++)
                MakeBoxChild(nb, $"VLine_{c}",
                    new Vector3(-0.40f + c * 0.15f, -0.05f, -0.020f),
                    new Vector3(0.005f, 0.60f, 0.002f), new Color(0.3f, 0.3f, 0.3f));
            MakeBoxChild(nb, "SideNote_1", new Vector3(0.52f, 0.15f, -0.019f),
                new Vector3(0.22f, 0.25f, 0.003f), paperColors[3]);
            MakeBoxChild(nb, "SideNote_2", new Vector3(0.52f, -0.18f, -0.019f),
                new Vector3(0.22f, 0.20f, 0.003f), paperColors[4]);
        }

        Color[] pinColors = { new Color(0.85f, 0.15f, 0.12f), new Color(0.12f, 0.45f, 0.85f),
            new Color(0.15f, 0.70f, 0.22f), new Color(0.85f, 0.75f, 0.12f) };
        for (int i = 0; i < 6; i++)
        {
            float px = Random.Range(-0.55f, 0.55f);
            float py = Random.Range(-0.35f, 0.35f);
            MakeBoxChild(nb, $"Pin_{i}", new Vector3(px, py, -0.022f),
                new Vector3(0.02f, 0.02f, 0.01f), pinColors[Random.Range(0, pinColors.Length)]);
        }
    }

    void CreateDustbin(GameObject parent, Vector3 pos, string name)
    {
        GameObject bin = new GameObject(name);
        bin.transform.SetParent(parent.transform);
        bin.transform.localPosition = pos;
        GameObject body = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
        body.name = "Body";
        body.transform.SetParent(bin.transform);
        body.transform.localPosition = new Vector3(0, 0.20f, 0);
        body.transform.localScale = new Vector3(0.20f, 0.20f, 0.20f);
        SetColor(body, new Color(0.35f, 0.35f, 0.38f));
        DestroyImmediate(body.GetComponent<Collider>());
    }

    void CreateWallClock(GameObject parent, Vector3 pos)
    {
        GameObject cl = new GameObject("Clock");
        cl.transform.SetParent(parent.transform);
        cl.transform.localPosition = pos;

        GameObject face = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
        face.name = "Face";
        face.transform.SetParent(cl.transform);
        face.transform.localPosition = Vector3.zero;
        face.transform.localRotation = Quaternion.Euler(90f, 0, 0);
        face.transform.localScale = new Vector3(0.30f, 0.02f, 0.30f);
        SetColor(face, new Color(0.95f, 0.95f, 0.93f));
        DestroyImmediate(face.GetComponent<Collider>());

        GameObject frame = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
        frame.name = "Frame";
        frame.transform.SetParent(cl.transform);
        frame.transform.localPosition = new Vector3(0, 0, -0.01f);
        frame.transform.localRotation = Quaternion.Euler(90f, 0, 0);
        frame.transform.localScale = new Vector3(0.34f, 0.025f, 0.34f);
        SetColor(frame, new Color(0.25f, 0.25f, 0.28f));
        DestroyImmediate(frame.GetComponent<Collider>());
    }

    void CreateFountain(GameObject parent, Vector3 pos)
    {
        GameObject ft = new GameObject("Fountain");
        ft.transform.SetParent(parent.transform);
        ft.transform.localPosition = pos;

        Color stone = new Color(0.72f, 0.68f, 0.62f);
        Color water = new Color(0.35f, 0.55f, 0.72f, 0.5f);

        GameObject pool = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
        pool.name = "Pool";
        pool.transform.SetParent(ft.transform);
        pool.transform.localPosition = new Vector3(0, 0.20f, 0);
        pool.transform.localScale = new Vector3(2.0f, 0.20f, 2.0f);
        SetColor(pool, stone);
        DestroyImmediate(pool.GetComponent<Collider>());

        GameObject waterSurf = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
        waterSurf.name = "Water";
        waterSurf.transform.SetParent(ft.transform);
        waterSurf.transform.localPosition = new Vector3(0, 0.32f, 0);
        waterSurf.transform.localScale = new Vector3(1.8f, 0.02f, 1.8f);
        SetColor(waterSurf, water);
        DestroyImmediate(waterSurf.GetComponent<Collider>());

        GameObject pillar = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
        pillar.name = "Pillar";
        pillar.transform.SetParent(ft.transform);
        pillar.transform.localPosition = new Vector3(0, 0.60f, 0);
        pillar.transform.localScale = new Vector3(0.25f, 0.40f, 0.25f);
        SetColor(pillar, stone * 0.92f);
        DestroyImmediate(pillar.GetComponent<Collider>());

        GameObject bowl = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
        bowl.name = "Bowl";
        bowl.transform.SetParent(ft.transform);
        bowl.transform.localPosition = new Vector3(0, 0.95f, 0);
        bowl.transform.localScale = new Vector3(0.8f, 0.10f, 0.8f);
        SetColor(bowl, stone);
        DestroyImmediate(bowl.GetComponent<Collider>());
    }

    void CreateLampPost(GameObject parent, Vector3 pos, string name)
    {
        GameObject lp = new GameObject(name);
        lp.transform.SetParent(parent.transform);
        lp.transform.localPosition = pos;

        Color metal = new Color(0.22f, 0.22f, 0.25f);

        GameObject pole = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
        pole.name = "Pole";
        pole.transform.SetParent(lp.transform);
        pole.transform.localPosition = new Vector3(0, 1.5f, 0);
        pole.transform.localScale = new Vector3(0.06f, 1.5f, 0.06f);
        SetColor(pole, metal);
        DestroyImmediate(pole.GetComponent<Collider>());

        MakeBoxChild(lp, "LampHead", new Vector3(0, 3.1f, 0),
            new Vector3(0.25f, 0.12f, 0.15f), metal);
        MakeBoxChild(lp, "LampGlass", new Vector3(0, 3.0f, 0),
            new Vector3(0.20f, 0.06f, 0.10f), new Color(0.95f, 0.92f, 0.78f));

        GameObject lt = new GameObject("Light");
        lt.transform.SetParent(lp.transform);
        lt.transform.localPosition = new Vector3(0, 3.0f, 0);
        Light l = lt.AddComponent<Light>();
        l.type = LightType.Point;
        l.intensity = 0.3f;
        l.range = 5f;
        l.color = new Color(1f, 0.92f, 0.72f);
    }

    GameObject MakeBoxChild(GameObject parent, string name, Vector3 localPos, Vector3 scale, Color color)
    {
        GameObject box = GameObject.CreatePrimitive(PrimitiveType.Cube);
        box.name = name;
        box.transform.SetParent(parent.transform);
        box.transform.localPosition = localPos;
        box.transform.localScale = scale;
        SetColor(box, color);
        DestroyImmediate(box.GetComponent<Collider>());
        return box;
    }

    void SetColor(GameObject obj, Color color)
    {
        var renderer = obj.GetComponent<Renderer>();
        if (renderer == null) return;
        var mat = new Material(renderer.sharedMaterial);
        mat.color = color;
        if (color.a < 1f)
        {
            mat.SetFloat("_Surface", 1);
            mat.SetFloat("_Blend", 0);
            mat.SetFloat("_AlphaClip", 0);
            mat.SetOverrideTag("RenderType", "Transparent");
            mat.SetInt("_SrcBlend", (int)UnityEngine.Rendering.BlendMode.SrcAlpha);
            mat.SetInt("_DstBlend", (int)UnityEngine.Rendering.BlendMode.OneMinusSrcAlpha);
            mat.SetInt("_ZWrite", 0);
            mat.DisableKeyword("_ALPHATEST_ON");
            mat.EnableKeyword("_ALPHABLEND_ON");
            mat.DisableKeyword("_ALPHAPREMULTIPLY_ON");
            mat.EnableKeyword("_SURFACE_TYPE_TRANSPARENT");
            mat.renderQueue = 3000;
        }
        renderer.sharedMaterial = mat;
    }

    void AddCollider(GameObject obj)
    {
        if (obj.GetComponent<Collider>() == null) obj.AddComponent<BoxCollider>();
    }

    public List<SeatInfo> GetSeatsInZone(int z) => allSeats.FindAll(s => s.zoneId == z);
    public SeatInfo GetSeatById(string id) => allSeats.Find(s => s.seatId == id);
    public Transform GetSensorSystem() => transform.Find("SensorSystem");
    public int GetTotalSeats() => seatCounter;

    [ContextMenu("Print Layout")]
    public void PrintLayout()
    {
        Debug.Log($"=== Liberty Twin - IIT ISM Dhanbad Style ===");
        Debug.Log($"Room: {roomWidth}x{roomLength}m, Height: {roomHeight}m, Seats: {seatCounter}");
        for (int z = 1; z <= 8; z++)
        {
            var seats = GetSeatsInZone(z);
            Debug.Log($"  Zone {z}: {string.Join(", ", seats.ConvertAll(s => s.seatId))}");
        }
    }
}
