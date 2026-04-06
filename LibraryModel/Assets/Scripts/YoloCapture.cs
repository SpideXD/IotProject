using UnityEngine;
using System.IO;
using System.Collections.Generic;

/// <summary>
/// Captures camera frames and generates YOLO-format ground truth labels.
/// Per-sensor capture - finds the real Rail_Back/Front sensors by name.
/// </summary>
public class YoloCapture : MonoBehaviour
{
    [Header("Output Settings")]
    [Tooltip("Base path for output")]
    public string outputBasePath = "Assets/YoloCapture";

    [Header("Capture Settings")]
    [Tooltip("Seconds between captures")]
    public float captureInterval = 1f;
    public int captureWidth = 640;
    public int captureHeight = 640;
    public bool captureEnabled = true;
    public List<string> latestDetections = new List<string>();

    [Header("Classes - Must match YOLO dataset")]
    public string[] classNames = {
        "person", "bag", "chair", "book",
        "laptop", "cup", "phone", "backpack", "headphones"
    };

    // Components
    RailSensorController railSensor;
    Camera sensorCamera;

    // State
    int frameCounter;
    string sensorName;
    bool wasAtCheckpoint;
    bool initialized;

    // Scene references
    SimStudent[] students;
    ProfessionalLibrary library;

    // YOLO class mapping
    Dictionary<string, int> classToId;

    void Start()
    {
        TryInitialize();
    }

    void TryInitialize()
    {
        // First check if we have a valid RailSensorController with sensorRT
        railSensor = GetComponent<RailSensorController>();

        // If not found OR doesn't have sensorRT yet, find the actual sensors
        if (railSensor == null || railSensor.sensorRT == null)
        {
            // We're on a separate/misconfigured YoloCapture object - find real sensors
            GameObject sensorObj = GameObject.Find("Rail_Back");
            if (sensorObj == null)
                sensorObj = GameObject.Find("Rail_Front");

            if (sensorObj != null)
            {
                railSensor = sensorObj.GetComponent<RailSensorController>();
            }

            if (railSensor == null)
            {
                if (Time.frameCount < 10 || Time.frameCount % 300 == 0)
                    Debug.LogError("[YoloCapture] RailSensorController not found on sensor objects!");
                return;
            }

            if (railSensor.sensorRT == null)
            {
                // Sensor not ready yet - will retry next frame
                return;
            }
        }

        // Now we have a valid railSensor with sensorRT
        sensorCamera = railSensor.GetComponentInChildren<Camera>();
        if (sensorCamera == null)
        {
            if (Time.frameCount < 10 || Time.frameCount % 300 == 0)
                Debug.LogError("[YoloCapture] Camera not found in RailSensor children!");
            return;
        }

        library = FindFirstObjectByType<ProfessionalLibrary>();
        if (library == null)
        {
            if (Time.frameCount < 10 || Time.frameCount % 300 == 0)
                Debug.LogError("[YoloCapture] ProfessionalLibrary not found!");
            return;
        }

        // Build class ID map
        classToId = new Dictionary<string, int>();
        for (int i = 0; i < classNames.Length; i++)
            classToId[classNames[i]] = i;

        sensorName = railSensor.transform.name.Replace(" ", "_");

        // Create directories
        CreateDirectories();

        initialized = true;
        Debug.Log($"[YoloCapture] Initialized for {sensorName}");
    }

    void CreateDirectories()
    {
        string imagesPath = Path.Combine(outputBasePath, "images");
        string labelsPath = Path.Combine(outputBasePath, "labels");

        Directory.CreateDirectory(imagesPath);
        Directory.CreateDirectory(labelsPath);

        // Export classes.txt
        string classesPath = Path.Combine(outputBasePath, "classes.txt");
        System.IO.File.WriteAllLines(classesPath, classNames);

        Debug.Log($"[YoloCapture] Output directories created at {outputBasePath}");
    }

    void Update()
    {
        // Reinitialize if needed (handles domain reload)
        if (!initialized || railSensor == null)
        {
            TryInitialize();
            return;
        }

        // Reset flag when leaving checkpoint
        if (!railSensor.isAtCheckpoint)
        {
            wasAtCheckpoint = false;
            return;
        }

        // Rising edge: capture once when arriving at checkpoint
        if (wasAtCheckpoint)
            return;

        wasAtCheckpoint = true;
        CaptureFrame();
    }

    void CaptureFrame()
    {
        if (railSensor.sensorRT == null)
        {
            Debug.LogWarning("[YoloCapture] No render texture");
            return;
        }

        // Refresh students
        students = FindObjectsByType<SimStudent>(FindObjectsSortMode.None);

        string imagePath = null;
        string labelPath = null;

        try
        {
            // Capture image
            imagePath = CaptureImage();
            if (imagePath == null)
            {
                Debug.LogError("[YoloCapture] Image capture failed");
                return;
            }

            // Get zone
            int zoneId = railSensor.zoneIds[railSensor.currentZoneIndex];

            // Save label
            labelPath = SaveLabel(imagePath, zoneId);

            // Verify files exist
            if (!File.Exists(imagePath))
            {
                Debug.LogError($"[YoloCapture] Image missing: {imagePath}");
                return;
            }

            if (labelPath != null && !File.Exists(labelPath))
            {
                Debug.LogError($"[YoloCapture] Label missing: {labelPath}");
                File.Delete(imagePath);
                return;
            }

            frameCounter++;
            Debug.Log($"[YoloCapture] Frame {frameCounter} captured at zone Z{zoneId}");
        }
        catch (System.Exception ex)
        {
            Debug.LogError($"[YoloCapture] Capture failed: {ex.Message}");

            // Cleanup on failure
            if (imagePath != null && File.Exists(imagePath))
            {
                File.Delete(imagePath);
                Debug.Log("[YoloCapture] Deleted corrupted image");
            }
            if (labelPath != null && File.Exists(labelPath))
            {
                File.Delete(labelPath);
                Debug.Log("[YoloCapture] Deleted corrupted label");
            }
        }
    }

    string CaptureImage()
    {
        RenderTexture prev = RenderTexture.active;
        RenderTexture.active = railSensor.sensorRT;

        Texture2D tex = new Texture2D(railSensor.sensorRT.width, railSensor.sensorRT.height, TextureFormat.RGB24, false);
        tex.ReadPixels(new Rect(0, 0, railSensor.sensorRT.width, railSensor.sensorRT.height), 0, 0);
        tex.Apply();

        RenderTexture.active = prev;

        byte[] pngData = tex.EncodeToPNG();
        Destroy(tex);

        if (pngData == null || pngData.Length == 0)
        {
            Debug.LogError("[YoloCapture] PNG encoding failed");
            return null;
        }

        string fileName = $"{sensorName}_f{frameCounter:D4}.png";
        string fullPath = Path.Combine(outputBasePath, "images", fileName);

        File.WriteAllBytes(fullPath, pngData);

        return fullPath;
    }

    string SaveLabel(string imagePath, int zoneId)
    {
        var seats = library.GetSeatsInZone(zoneId);
        var labelLines = new List<string>();

        foreach (var seat in seats)
        {
            if (seat.seatTransform == null) continue;

            // Find student at this seat
            SimStudent student = null;
            foreach (var st in students)
            {
                if (st != null && st.assignedSeatId == seat.seatId)
                {
                    student = st;
                    break;
                }
            }

            string cls = null;
            Vector3 worldPos = seat.seatTransform.position;

            if (student != null)
            {
                // Check if student is in an active state
                switch (student.state)
                {
                    case SimStudent.S.STUDY:
                    case SimStudent.S.STUDY2:
                    case SimStudent.S.SIT:
                    case SimStudent.S.SIT2:
                    case SimStudent.S.PLACE:
                    case SimStudent.S.STAND:
                    case SimStudent.S.STAND2:
                    case SimStudent.S.PACK:
                    case SimStudent.S.WALK_TO_COOLER:
                    case SimStudent.S.DRINK:
                    case SimStudent.S.WALK_BACK:
                    case SimStudent.S.USE_PHONE:
                    case SimStudent.S.PUT_AWAY_PHONE:
                    case SimStudent.S.STRETCH:
                    case SimStudent.S.YAW:
                    case SimStudent.S.TALK:
                        cls = "person";
                        break;
                }

                // Use student's actual position when walking
                if (student.state == SimStudent.S.WALK_TO_COOLER ||
                    student.state == SimStudent.S.DRINK ||
                    student.state == SimStudent.S.WALK_BACK ||
                    student.state == SimStudent.S.WALK_TO_SEAT ||
                    student.state == SimStudent.S.WALK_OUT)
                {
                    worldPos = student.transform.position;
                }
            }

            if (cls == null) continue;

            // Project to screen using proper corner projection (from old code)
            float personHeight = 1.6f;
            float personWidth = 0.4f;

            Vector3 headPos = worldPos + Vector3.up * personHeight * 0.85f;
            Vector3 feetPos = worldPos;

            Vector3 headVp = sensorCamera.WorldToViewportPoint(headPos);
            Vector3 feetVp = sensorCamera.WorldToViewportPoint(feetPos);

            if (headVp.z < 0 || feetVp.z < 0) continue;

            // Calculate horizontal bounds
            Vector3 leftPos = worldPos + sensorCamera.transform.right * (-personWidth * 0.5f);
            Vector3 rightPos = worldPos + sensorCamera.transform.right * (personWidth * 0.5f);
            Vector3 leftVp = sensorCamera.WorldToViewportPoint(leftPos);
            Vector3 rightVp = sensorCamera.WorldToViewportPoint(rightPos);

            float x_min = Mathf.Min(leftVp.x, rightVp.x, headVp.x, feetVp.x);
            float x_max = Mathf.Max(leftVp.x, rightVp.x, headVp.x, feetVp.x);
            float y_min = Mathf.Min(leftVp.y, rightVp.y, headVp.y, feetVp.y);
            float y_max = Mathf.Max(leftVp.y, rightVp.y, headVp.y, feetVp.y);

            // Flip Y (viewport Y is inverted)
            float temp = y_min;
            y_min = 1f - y_max;
            y_max = 1f - temp;

            x_min = Mathf.Clamp01(x_min);
            x_max = Mathf.Clamp01(x_max);
            y_min = Mathf.Clamp01(y_min);
            y_max = Mathf.Clamp01(y_max);

            if (x_max - x_min < 0.01f || y_max - y_min < 0.01f) continue;

            // Convert to YOLO format: class x_center y_center width height
            float x_center = (x_min + x_max) / 2f;
            float y_center = (y_min + y_max) / 2f;
            float width = x_max - x_min;
            float height = y_max - y_min;

            int classId = classToId.GetValueOrDefault(cls, 0);
            labelLines.Add($"{classId} {x_center:F6} {y_center:F6} {width:F6} {height:F6}");

            // Ghost objects (bag, laptop, book, etc.)
            if (student != null)
            {
                var ghostObjects = student.GetGhostObjects();
                foreach (var ghost in ghostObjects)
                {
                    AddGhostLabel(labelLines, ghost, zoneId);
                }
            }
        }

        // Write label file
        string labelFileName = Path.GetFileName(imagePath).Replace(".png", ".txt");
        string labelPath = Path.Combine(outputBasePath, "labels", labelFileName);

        if (labelLines.Count == 0)
        {
            File.WriteAllText(labelPath, "");
        }
        else
        {
            File.WriteAllLines(labelPath, labelLines);
        }

        return labelPath;
    }

    void AddGhostLabel(List<string> labelLines, SimStudent.GhostObjectInfo ghost, int zoneId)
    {
        Vector3 center = ghost.worldPos;
        float halfW = ghost.widthM * 0.5f;
        float halfH = ghost.heightM * 0.5f;

        // Use camera's right and up vectors
        Vector3 camRight = sensorCamera.transform.right;
        Vector3 camUp = sensorCamera.transform.up;

        // Calculate 8 corners of bounding box
        Vector3[] corners = new Vector3[8];
        corners[0] = center + camRight * halfW + camUp * halfH;
        corners[1] = center - camRight * halfW + camUp * halfH;
        corners[2] = center + camRight * halfW - camUp * halfH;
        corners[3] = center - camRight * halfW - camUp * halfH;
        corners[4] = center + camRight * halfW + camUp * halfH;
        corners[5] = center - camRight * halfW + camUp * halfH;
        corners[6] = center + camRight * halfW - camUp * halfH;
        corners[7] = center - camRight * halfW - camUp * halfH;

        float x_min = float.MaxValue, x_max = float.MinValue;
        float y_min = float.MaxValue, y_max = float.MinValue;

        foreach (var corner in corners)
        {
            Vector3 vp = sensorCamera.WorldToViewportPoint(corner);
            if (vp.z < 0) continue;
            x_min = Mathf.Min(x_min, vp.x);
            x_max = Mathf.Max(x_max, vp.x);
            y_min = Mathf.Min(y_min, vp.y);
            y_max = Mathf.Max(y_max, vp.y);
        }

        if (x_min == float.MaxValue) return;

        // Flip Y
        float temp = y_min;
        y_min = 1f - y_max;
        y_max = 1f - temp;

        x_min = Mathf.Clamp01(x_min);
        x_max = Mathf.Clamp01(x_max);
        y_min = Mathf.Clamp01(y_min);
        y_max = Mathf.Clamp01(y_max);

        if (x_max - x_min < 0.005f || y_max - y_min < 0.005f) return;

        // YOLO format
        float x_center = (x_min + x_max) / 2f;
        float y_center = (y_min + y_max) / 2f;
        float width = x_max - x_min;
        float height = y_max - y_min;

        int classId = classToId.GetValueOrDefault(ghost.objName, -1);
        if (classId >= 0)
        {
            labelLines.Add($"{classId} {x_center:F6} {y_center:F6} {width:F6} {height:F6}");
        }
    }

    void OnDestroy()
    {
        Debug.Log($"[YoloCapture] Total frames captured: {frameCounter}");
    }
}
